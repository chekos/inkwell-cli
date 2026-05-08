"""Tests for the demo URL classifier."""

import socket
from typing import Any
from unittest.mock import patch

import pytest

from inkwell.demo.classifier import (
    DemoUrlError,
    UrlKind,
    assert_demo_safe_url,
    assert_resolved_host_is_public,
    classify_demo_url,
)


def _fake_getaddrinfo(*ips: str):
    """Return a getaddrinfo stub that resolves any host to ``ips``."""

    def _resolve(_host: str, *_args: Any, **_kwargs: Any) -> list[Any]:
        return [(socket.AF_INET, socket.SOCK_STREAM, 0, "", (ip, 0)) for ip in ips]

    return _resolve


class TestYouTubeAcceptance:
    @pytest.mark.parametrize(
        "url",
        [
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "https://youtube.com/watch?v=dQw4w9WgXcQ",
            "https://m.youtube.com/watch?v=dQw4w9WgXcQ",
            "https://youtu.be/dQw4w9WgXcQ",
            "https://www.youtube.com/shorts/abc12345xyz",
            "https://www.youtube.com/live/abc12345xyz",
            "https://www.youtube.com/embed/abc12345xyz",
        ],
    )
    def test_accepts_single_video_url_shapes(self, url: str) -> None:
        result = classify_demo_url(url)
        assert result.kind is UrlKind.YOUTUBE_VIDEO
        assert result.normalized_url == url


class TestYouTubeRejection:
    @pytest.mark.parametrize(
        "url",
        [
            "https://www.youtube.com/playlist?list=PLabc123",
            "https://www.youtube.com/watch?v=abc&list=PLabc123",
        ],
    )
    def test_rejects_playlist_urls(self, url: str) -> None:
        with pytest.raises(DemoUrlError) as excinfo:
            classify_demo_url(url)
        assert "playlist" in excinfo.value.user_message.lower()

    @pytest.mark.parametrize(
        "url",
        [
            "https://www.youtube.com/",
            "https://www.youtube.com",
            "https://www.youtube.com/@somehandle",
            "https://www.youtube.com/c/SomeChannel",
            "https://www.youtube.com/channel/UCabc123",
            "https://www.youtube.com/user/SomeUser",
        ],
    )
    def test_rejects_non_video_youtube_urls(self, url: str) -> None:
        with pytest.raises(DemoUrlError):
            classify_demo_url(url)

    def test_rejects_watch_without_video_id(self) -> None:
        with pytest.raises(DemoUrlError) as excinfo:
            classify_demo_url("https://www.youtube.com/watch")
        assert "video id" in excinfo.value.user_message.lower()

    def test_rejects_youtu_be_without_video_id(self) -> None:
        with pytest.raises(DemoUrlError):
            classify_demo_url("https://youtu.be/")


class TestPublicRSSAcceptance:
    @pytest.mark.parametrize(
        "url",
        [
            "https://example.com/feed.rss",
            "https://feeds.simplecast.com/abc123",
            "http://example.com/podcast/feed.xml",
        ],
    )
    def test_accepts_public_rss_urls(self, url: str) -> None:
        result = classify_demo_url(url)
        assert result.kind is UrlKind.PUBLIC_RSS
        assert result.normalized_url == url


class TestSchemeAndHostRejections:
    @pytest.mark.parametrize(
        "url",
        [
            "ftp://example.com/feed.rss",
            "file:///etc/passwd",
            "javascript:alert(1)",
            "not-a-url",
            "",
        ],
    )
    def test_rejects_non_http_schemes(self, url: str) -> None:
        with pytest.raises(DemoUrlError):
            classify_demo_url(url)

    @pytest.mark.parametrize(
        "url",
        [
            "http://localhost/feed.rss",
            "http://127.0.0.1/feed.rss",
            "http://192.168.1.10/feed.rss",
            "http://10.0.0.5/feed.rss",
            "http://172.16.0.1/feed.rss",
            "http://[::1]/feed.rss",
            "http://service.local/feed.rss",
            "http://kubernetes.internal/feed.rss",
        ],
    )
    def test_rejects_private_or_local_addresses(self, url: str) -> None:
        with pytest.raises(DemoUrlError):
            classify_demo_url(url)

    def test_strips_whitespace_before_classifying(self) -> None:
        result = classify_demo_url("   https://example.com/feed.rss  ")
        assert result.kind is UrlKind.PUBLIC_RSS
        assert result.normalized_url == "https://example.com/feed.rss"


class TestLegacyIPv4EncodingRejection:
    """Codex P1: libc resolvers normalize these to loopback/RFC1918.

    ``ipaddress.ip_address`` doesn't parse them, so the canonical-IP
    check alone lets them through. ``socket.inet_aton`` matches the
    libc behavior, which is what HTTP clients ultimately use.
    """

    @pytest.mark.parametrize(
        ("url", "reason_prefix"),
        [
            # decimal integer form of 127.0.0.1
            ("http://2130706433/feed.rss", "legacy_ipv4_private"),
            # hex form of 127.0.0.1
            ("http://0x7f000001/feed.rss", "legacy_ipv4_private"),
            # octal/short-form of 127.0.0.1
            ("http://0177.0.0.1/feed.rss", "legacy_ipv4_private"),
            ("http://127.1/feed.rss", "legacy_ipv4_private"),
            # 192.168.1.1 in hex/octal octets — RFC1918
            ("http://0xc0.0xa8.0x01.0x01/feed.rss", "legacy_ipv4_private"),
            ("http://0300.0250.01.01/feed.rss", "legacy_ipv4_private"),
        ],
    )
    def test_rejects_legacy_ipv4_encodings_for_private_ranges(
        self, url: str, reason_prefix: str
    ) -> None:
        with pytest.raises(DemoUrlError) as excinfo:
            classify_demo_url(url)
        assert excinfo.value.reason.startswith(reason_prefix)

    def test_rejects_legacy_ipv4_encoding_even_when_resolves_public(self) -> None:
        # 1.1.1.1 in decimal-int form. Public IP, but the encoding itself
        # is the smell: real podcast hosts don't use it.
        with pytest.raises(DemoUrlError) as excinfo:
            classify_demo_url("http://16843009/feed.rss")
        assert excinfo.value.reason.startswith("legacy_ipv4_encoding")


class TestAssertDemoSafeUrl:
    """The redirect-revalidation helper m2's fetcher will call on each hop."""

    def test_accepts_canonical_public_url(self) -> None:
        # Should not raise.
        assert_demo_safe_url("https://example.com/feed.rss")

    @pytest.mark.parametrize(
        "url",
        [
            "http://localhost/feed.rss",
            "http://127.0.0.1/feed.rss",
            "http://192.168.1.1/feed.rss",
            "http://2130706433/feed.rss",
            "http://0x7f000001/feed.rss",
            "http://127.1/feed.rss",
            "http://service.local/feed.rss",
        ],
    )
    def test_rejects_redirect_targets_that_classifier_would_reject(self, url: str) -> None:
        with pytest.raises(DemoUrlError):
            assert_demo_safe_url(url)

    def test_rejects_non_http_redirect_targets(self) -> None:
        with pytest.raises(DemoUrlError):
            assert_demo_safe_url("file:///etc/passwd")

    def test_rejects_empty_input(self) -> None:
        with pytest.raises(DemoUrlError):
            assert_demo_safe_url("")


class TestClassifierDnsResolution:
    """OBRA-81 P1: classifier must reject hostnames that *resolve* to private IPs.

    ``_reject_private_or_local_host`` only checks the host literal in
    the URL string. A public-looking hostname whose A/AAAA records
    point at RFC1918 / loopback / link-local space (DNS rebinding,
    attacker-controlled DNS, internal split-horizon resolvers) used to
    pass and only get caught later on redirect hops in the resolver.
    The classifier now closes that gap at submission time.
    """

    @pytest.mark.parametrize(
        ("resolved_ip", "expected_reason_prefix"),
        [
            ("10.0.0.5", "resolved_private_ip:"),
            ("192.168.1.10", "resolved_private_ip:"),
            ("172.16.0.1", "resolved_private_ip:"),
            ("127.0.0.1", "resolved_private_ip:"),
            ("169.254.169.254", "resolved_private_ip:"),  # link-local / IMDS
            ("::1", "resolved_private_ip:"),
        ],
    )
    def test_rejects_public_hostname_resolving_to_private_ip(
        self, resolved_ip: str, expected_reason_prefix: str
    ) -> None:
        with patch(
            "inkwell.demo.classifier.socket.getaddrinfo",
            side_effect=_fake_getaddrinfo(resolved_ip),
        ):
            with pytest.raises(DemoUrlError) as excinfo:
                classify_demo_url("https://internal.example.com/feed.rss")
        assert excinfo.value.reason.startswith(expected_reason_prefix)
        assert resolved_ip in excinfo.value.reason

    def test_rejects_when_dns_resolution_fails(self) -> None:
        def _gaierror(*_args: Any, **_kwargs: Any) -> list[Any]:
            raise socket.gaierror(8, "nodename nor servname provided, or not known")

        with patch(
            "inkwell.demo.classifier.socket.getaddrinfo",
            side_effect=_gaierror,
        ):
            with pytest.raises(DemoUrlError) as excinfo:
                classify_demo_url("https://nxdomain.example.com/feed.rss")
        assert excinfo.value.reason.startswith("dns_resolution_failed:")

    def test_accepts_public_hostname_resolving_to_public_ip(self) -> None:
        with patch(
            "inkwell.demo.classifier.socket.getaddrinfo",
            side_effect=_fake_getaddrinfo("93.184.216.34"),
        ):
            result = classify_demo_url("https://example.com/feed.rss")
        assert result.kind is UrlKind.PUBLIC_RSS

    def test_rejects_when_any_resolved_address_is_private(self) -> None:
        # Mixed result (one public, one private) must still be refused —
        # the worker would happily connect to the private one otherwise.
        with patch(
            "inkwell.demo.classifier.socket.getaddrinfo",
            side_effect=_fake_getaddrinfo("93.184.216.34", "10.0.0.5"),
        ):
            with pytest.raises(DemoUrlError) as excinfo:
                classify_demo_url("https://mixed.example.com/feed.rss")
        assert excinfo.value.reason.startswith("resolved_private_ip:")


class TestAssertResolvedHostIsPublic:
    """Direct coverage of the standalone DNS-resolution helper."""

    def test_skips_dns_for_ip_literal(self) -> None:
        # IP literals are already covered by _reject_private_or_local_host;
        # the DNS helper must short-circuit to avoid a redundant lookup.
        with patch(
            "inkwell.demo.classifier.socket.getaddrinfo",
            side_effect=AssertionError("getaddrinfo should not be called for IP literals"),
        ):
            assert_resolved_host_is_public("93.184.216.34")
            assert_resolved_host_is_public("::1")

    def test_raises_on_private_resolution(self) -> None:
        with patch(
            "inkwell.demo.classifier.socket.getaddrinfo",
            side_effect=_fake_getaddrinfo("10.0.0.5"),
        ):
            with pytest.raises(DemoUrlError) as excinfo:
                assert_resolved_host_is_public("internal.example.com")
        assert excinfo.value.reason == "resolved_private_ip:internal.example.com->10.0.0.5"

    def test_raises_on_dns_failure(self) -> None:
        def _gaierror(*_args: Any, **_kwargs: Any) -> list[Any]:
            raise socket.gaierror(8, "nodename nor servname provided, or not known")

        with patch(
            "inkwell.demo.classifier.socket.getaddrinfo",
            side_effect=_gaierror,
        ):
            with pytest.raises(DemoUrlError) as excinfo:
                assert_resolved_host_is_public("nxdomain.example.com")
        assert excinfo.value.reason == "dns_resolution_failed:gaierror"
