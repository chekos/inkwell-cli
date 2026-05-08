"""Tests for the demo URL resolver.

The resolver layer is what enforces the duration cap *before* the
inkwell pipeline spends transcription/LLM budget, so each rejection
path is covered with an explicit reason.
"""

from __future__ import annotations

import socket
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import respx
from httpx import Response

from inkwell.demo.classifier import ClassifiedUrl, DemoUrlError, UrlKind
from inkwell.demo.config import DemoConfig
from inkwell.demo.resolver import _fetch_feed_safely, resolve_demo_source
from inkwell.feeds.models import Episode
from inkwell.utils.errors import ValidationError


def _fake_getaddrinfo(*ips: str):
    """Return a getaddrinfo stub that resolves any host to ``ips``."""

    def _resolve(host: str, *args: Any, **kwargs: Any) -> list[Any]:
        return [(socket.AF_INET, socket.SOCK_STREAM, 0, "", (ip, 0)) for ip in ips]

    return _resolve


def _fake_getaddrinfo_by_host(mapping: dict[str, str], default: str = "93.184.216.34"):
    """Return a getaddrinfo stub that maps specific hosts to specific IPs.

    Hosts not in ``mapping`` resolve to ``default`` (a public IP). Useful
    when a redirect chain needs the *initial* host to be public and a
    later hop to be private.
    """

    def _resolve(host: str, *args: Any, **kwargs: Any) -> list[Any]:
        ip = mapping.get(host, default)
        return [(socket.AF_INET, socket.SOCK_STREAM, 0, "", (ip, 0))]

    return _resolve


def _config(**overrides: Any) -> DemoConfig:
    base: dict[str, Any] = {"max_duration_seconds": 30 * 60}
    base.update(overrides)
    return DemoConfig(**base)


def _classified(url: str, kind: UrlKind = UrlKind.YOUTUBE_VIDEO) -> ClassifiedUrl:
    return ClassifiedUrl(kind=kind, normalized_url=url)


def _episode(
    *,
    title: str = "Latest episode",
    audio_url: str = "https://example.com/audio.mp3",
    duration_seconds: int | None = 600,
    podcast_name: str = "Demo Pod",
) -> Episode:
    return Episode(
        title=title,
        url=audio_url,  # type: ignore[arg-type]
        published=datetime(2026, 5, 7, tzinfo=timezone.utc),
        description="",
        duration_seconds=duration_seconds,
        podcast_name=podcast_name,
    )


class TestYouTubeResolution:
    @pytest.mark.asyncio
    async def test_returns_resolved_source_under_cap(self) -> None:
        info = {
            "duration": 1200,
            "title": "Some video",
            "channel": "Some Channel",
        }
        with patch(
            "inkwell.demo.resolver._fetch_youtube_video_info", return_value=info
        ) as mock_fetch:
            result = await resolve_demo_source(
                _classified("https://www.youtube.com/watch?v=abc"),
                demo_config=_config(),
            )

        mock_fetch.assert_called_once_with("https://www.youtube.com/watch?v=abc")
        assert result.kind is UrlKind.YOUTUBE_VIDEO
        assert result.pipeline_url == "https://www.youtube.com/watch?v=abc"
        assert result.duration_seconds == 1200
        assert result.episode_title == "Some video"
        assert result.podcast_name == "Some Channel"

    @pytest.mark.asyncio
    async def test_falls_back_to_uploader_when_channel_missing(self) -> None:
        info = {"duration": 60.0, "title": "Vid", "uploader": "Some Uploader"}
        with patch("inkwell.demo.resolver._fetch_youtube_video_info", return_value=info):
            result = await resolve_demo_source(
                _classified("https://youtu.be/xyz"),
                demo_config=_config(),
            )
        assert result.podcast_name == "Some Uploader"

    @pytest.mark.asyncio
    async def test_uses_default_titles_when_metadata_blank(self) -> None:
        info = {"duration": 30, "title": "  ", "channel": ""}
        with patch("inkwell.demo.resolver._fetch_youtube_video_info", return_value=info):
            result = await resolve_demo_source(
                _classified("https://youtu.be/xyz"),
                demo_config=_config(),
            )
        assert result.episode_title == "YouTube video"
        assert result.podcast_name == "YouTube"

    @pytest.mark.asyncio
    async def test_rejects_video_over_cap(self) -> None:
        info = {"duration": 30 * 60 + 1, "title": "Long video"}
        with patch("inkwell.demo.resolver._fetch_youtube_video_info", return_value=info):
            with pytest.raises(DemoUrlError) as excinfo:
                await resolve_demo_source(
                    _classified("https://youtu.be/long"),
                    demo_config=_config(),
                )
        assert "30 minutes" in excinfo.value.user_message
        assert "duration_over_cap" in excinfo.value.reason

    @pytest.mark.asyncio
    async def test_rejects_fractional_duration_over_cap(self) -> None:
        # Codex P2: ``int(1800.9)`` truncates to 1800 and slips past a
        # 1800s cap, deferring rejection to post-transcription backstops
        # after pipeline spend has started. ``math.ceil`` rounds up so
        # any fractional value strictly over the cap rejects here.
        info = {"duration": 30 * 60 + 0.9, "title": "Just over"}
        with patch("inkwell.demo.resolver._fetch_youtube_video_info", return_value=info):
            with pytest.raises(DemoUrlError) as excinfo:
                await resolve_demo_source(
                    _classified("https://youtu.be/fractional"),
                    demo_config=_config(),
                )
        assert "duration_over_cap" in excinfo.value.reason

    @pytest.mark.asyncio
    async def test_accepts_fractional_duration_at_cap(self) -> None:
        # ``1800.0`` is exactly at the cap; ``math.ceil`` keeps it at
        # 1800 so the resolver still accepts boundary-correct durations.
        info = {"duration": float(30 * 60), "title": "At cap"}
        with patch("inkwell.demo.resolver._fetch_youtube_video_info", return_value=info):
            result = await resolve_demo_source(
                _classified("https://youtu.be/at-cap"),
                demo_config=_config(),
            )
        assert result.duration_seconds == 30 * 60

    @pytest.mark.asyncio
    async def test_rejects_video_with_unknown_duration(self) -> None:
        info = {"title": "No duration", "channel": "Acme"}
        with patch("inkwell.demo.resolver._fetch_youtube_video_info", return_value=info):
            with pytest.raises(DemoUrlError) as excinfo:
                await resolve_demo_source(
                    _classified("https://youtu.be/no-dur"),
                    demo_config=_config(),
                )
        assert excinfo.value.reason == "youtube_missing_duration"

    @pytest.mark.asyncio
    async def test_parses_duration_string_when_numeric_missing(self) -> None:
        info = {"duration_string": "12:34", "title": "Tee"}
        with patch("inkwell.demo.resolver._fetch_youtube_video_info", return_value=info):
            result = await resolve_demo_source(
                _classified("https://youtu.be/xyz"),
                demo_config=_config(),
            )
        assert result.duration_seconds == 12 * 60 + 34

    @pytest.mark.asyncio
    async def test_rejects_zero_duration(self) -> None:
        info = {"duration": 0, "title": "Empty"}
        with patch("inkwell.demo.resolver._fetch_youtube_video_info", return_value=info):
            with pytest.raises(DemoUrlError) as excinfo:
                await resolve_demo_source(
                    _classified("https://youtu.be/empty"),
                    demo_config=_config(),
                )
        assert excinfo.value.reason == "youtube_missing_duration"


def _stub_feed(title: str | None = "Cool Pod") -> MagicMock:
    """Build a feedparser-shaped object the resolver can read a title from."""
    feed = MagicMock()
    feed.feed = MagicMock(spec=[]) if title is None else MagicMock(title=title)
    return feed


def _patch_safe_fetch(feed: Any) -> Any:
    """Replace ``_fetch_feed_safely`` with one that returns ``feed`` directly."""
    return patch("inkwell.demo.resolver._fetch_feed_safely", AsyncMock(return_value=feed))


class TestRSSResolution:
    @pytest.mark.asyncio
    async def test_returns_latest_episode_under_cap(self) -> None:
        feed = _stub_feed("Cool Pod")
        episode = _episode(podcast_name="Cool Pod", duration_seconds=900)

        with (
            _patch_safe_fetch(feed) as safe_fetch,
            patch("inkwell.demo.resolver.RSSParser") as parser_cls,
        ):
            parser_cls.return_value.get_latest_episode = MagicMock(return_value=episode)

            result = await resolve_demo_source(
                _classified("https://example.com/feed.rss", UrlKind.PUBLIC_RSS),
                demo_config=_config(),
            )

        safe_fetch.assert_awaited_once_with("https://example.com/feed.rss")
        parser_cls.return_value.get_latest_episode.assert_called_once_with(feed, "Cool Pod")
        assert result.kind is UrlKind.PUBLIC_RSS
        assert result.pipeline_url == str(episode.url)
        assert result.podcast_name == "Cool Pod"
        assert result.episode_title == "Latest episode"
        assert result.duration_seconds == 900

    @pytest.mark.asyncio
    async def test_uses_fallback_podcast_name_when_feed_missing_title(self) -> None:
        feed = _stub_feed(title=None)
        episode = _episode(podcast_name="Demo episode")

        with _patch_safe_fetch(feed), patch("inkwell.demo.resolver.RSSParser") as parser_cls:
            parser_cls.return_value.get_latest_episode = MagicMock(return_value=episode)

            result = await resolve_demo_source(
                _classified("https://example.com/feed.rss", UrlKind.PUBLIC_RSS),
                demo_config=_config(),
            )

        parser_cls.return_value.get_latest_episode.assert_called_once_with(feed, "Demo episode")
        assert result.podcast_name == "Demo episode"

    @pytest.mark.asyncio
    async def test_rejects_episode_over_cap(self) -> None:
        feed = _stub_feed()
        long_episode = _episode(duration_seconds=30 * 60 + 1)

        with _patch_safe_fetch(feed), patch("inkwell.demo.resolver.RSSParser") as parser_cls:
            parser_cls.return_value.get_latest_episode = MagicMock(return_value=long_episode)

            with pytest.raises(DemoUrlError) as excinfo:
                await resolve_demo_source(
                    _classified("https://example.com/feed.rss", UrlKind.PUBLIC_RSS),
                    demo_config=_config(),
                )
        assert "duration_over_cap" in excinfo.value.reason

    @pytest.mark.asyncio
    async def test_rejects_episode_with_unknown_duration(self) -> None:
        feed = _stub_feed()
        episode = _episode(duration_seconds=None)

        with _patch_safe_fetch(feed), patch("inkwell.demo.resolver.RSSParser") as parser_cls:
            parser_cls.return_value.get_latest_episode = MagicMock(return_value=episode)

            with pytest.raises(DemoUrlError) as excinfo:
                await resolve_demo_source(
                    _classified("https://example.com/feed.rss", UrlKind.PUBLIC_RSS),
                    demo_config=_config(),
                )
        assert excinfo.value.reason == "rss_missing_duration"

    @pytest.mark.asyncio
    async def test_propagates_safe_fetch_demo_url_errors_unchanged(self) -> None:
        # ``_fetch_feed_safely`` already produces user-safe DemoUrlError
        # instances; the resolver must not re-wrap them.
        original = DemoUrlError(
            "That feed is private. The demo only supports public RSS feeds.",
            reason="rss_authentication_required",
        )
        with patch(
            "inkwell.demo.resolver._fetch_feed_safely",
            AsyncMock(side_effect=original),
        ):
            with pytest.raises(DemoUrlError) as excinfo:
                await resolve_demo_source(
                    _classified("https://example.com/feed.rss", UrlKind.PUBLIC_RSS),
                    demo_config=_config(),
                )
        assert excinfo.value is original

    @pytest.mark.asyncio
    async def test_maps_no_latest_episode_to_demo_url_error(self) -> None:
        feed = _stub_feed()

        with _patch_safe_fetch(feed), patch("inkwell.demo.resolver.RSSParser") as parser_cls:
            parser_cls.return_value.get_latest_episode = MagicMock(
                side_effect=ValidationError("No episodes found in feed")
            )

            with pytest.raises(DemoUrlError) as excinfo:
                await resolve_demo_source(
                    _classified("https://example.com/feed.rss", UrlKind.PUBLIC_RSS),
                    demo_config=_config(),
                )
        assert excinfo.value.reason.startswith("rss_no_latest_episode:")

    @pytest.mark.asyncio
    async def test_maps_pydantic_validation_error_to_demo_url_error(self) -> None:
        # Codex P2: when a feed entry has a malformed enclosure URL, the
        # ``Episode`` Pydantic model raises ``pydantic.ValidationError``
        # (not the inkwell error). Without this catch the demo returns a
        # 500 instead of a clean DemoUrlError.
        import pydantic
        from pydantic import BaseModel, HttpUrl

        class _Probe(BaseModel):
            url: HttpUrl

        try:
            _Probe(url="not a real url")  # type: ignore[arg-type]
        except pydantic.ValidationError as real_error:
            pyd_error = real_error
        else:  # pragma: no cover — Pydantic must raise here
            raise AssertionError("expected pydantic.ValidationError to be raised")

        feed = _stub_feed()

        with _patch_safe_fetch(feed), patch("inkwell.demo.resolver.RSSParser") as parser_cls:
            parser_cls.return_value.get_latest_episode = MagicMock(side_effect=pyd_error)

            with pytest.raises(DemoUrlError) as excinfo:
                await resolve_demo_source(
                    _classified("https://example.com/feed.rss", UrlKind.PUBLIC_RSS),
                    demo_config=_config(),
                )
        assert excinfo.value.reason.startswith("rss_no_latest_episode:")
        assert "ValidationError" in excinfo.value.reason

    @pytest.mark.asyncio
    async def test_rejects_unsafe_audio_enclosure_url(self) -> None:
        # Even if the feed itself is on a public host, the latest episode's
        # enclosure URL might point at private infrastructure. The resolver
        # must revalidate it via assert_demo_safe_url before handing the
        # URL to the orchestrator.
        feed = _stub_feed()
        episode = _episode(audio_url="http://127.0.0.1/audio.mp3", duration_seconds=600)

        with _patch_safe_fetch(feed), patch("inkwell.demo.resolver.RSSParser") as parser_cls:
            parser_cls.return_value.get_latest_episode = MagicMock(return_value=episode)

            with pytest.raises(DemoUrlError) as excinfo:
                await resolve_demo_source(
                    _classified("https://example.com/feed.rss", UrlKind.PUBLIC_RSS),
                    demo_config=_config(),
                )
        assert excinfo.value.reason.startswith("rss_unsafe_enclosure:")

    @pytest.mark.asyncio
    async def test_rejects_enclosure_when_hostname_resolves_to_private_ip(self) -> None:
        # Codex P1 follow-up: the enclosure URL host literal can be
        # public-looking (passes assert_demo_safe_url) while resolving to
        # RFC1918 / loopback / RFC6598 space at fetch time. The resolver
        # must apply assert_resolved_host_is_public before handoff.
        feed = _stub_feed()
        episode = _episode(
            audio_url="https://audio.attacker.tld/file.mp3",
            duration_seconds=600,
        )

        with (
            _patch_safe_fetch(feed),
            patch("inkwell.demo.resolver.RSSParser") as parser_cls,
            patch(
                "inkwell.demo.classifier.socket.getaddrinfo",
                side_effect=_fake_getaddrinfo("10.0.0.5"),
            ),
        ):
            parser_cls.return_value.get_latest_episode = MagicMock(return_value=episode)

            with pytest.raises(DemoUrlError) as excinfo:
                await resolve_demo_source(
                    _classified("https://example.com/feed.rss", UrlKind.PUBLIC_RSS),
                    demo_config=_config(),
                )
        assert excinfo.value.reason.startswith("rss_unsafe_enclosure:resolved_private_ip:")

    @pytest.mark.asyncio
    async def test_rejects_enclosure_when_hostname_resolves_to_rfc6598(self) -> None:
        feed = _stub_feed()
        episode = _episode(
            audio_url="https://cgn.attacker.tld/file.mp3",
            duration_seconds=600,
        )

        with (
            _patch_safe_fetch(feed),
            patch("inkwell.demo.resolver.RSSParser") as parser_cls,
            patch(
                "inkwell.demo.classifier.socket.getaddrinfo",
                side_effect=_fake_getaddrinfo("100.64.0.5"),
            ),
        ):
            parser_cls.return_value.get_latest_episode = MagicMock(return_value=episode)

            with pytest.raises(DemoUrlError) as excinfo:
                await resolve_demo_source(
                    _classified("https://example.com/feed.rss", UrlKind.PUBLIC_RSS),
                    demo_config=_config(),
                )
        assert excinfo.value.reason.startswith("rss_unsafe_enclosure:resolved_private_ip:")


class TestSafeFetchFeed:
    """Direct tests for ``_fetch_feed_safely`` redirect-revalidation."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_blocks_redirect_to_private_host(self) -> None:
        # Public URL responds with 302 -> http://127.0.0.1/feed.rss.
        # The redirect target must trip assert_demo_safe_url and fail.
        respx.get("https://example.com/feed.rss").mock(
            return_value=Response(302, headers={"location": "http://127.0.0.1/feed.rss"}),
        )

        with pytest.raises(DemoUrlError) as excinfo:
            await _fetch_feed_safely("https://example.com/feed.rss")
        assert excinfo.value.reason.startswith("rss_redirect_to_unsafe_host:")

    @pytest.mark.asyncio
    @respx.mock
    async def test_follows_safe_redirect_chain(self) -> None:
        # 302 to a different public host should be followed and parsed.
        rss_xml = (
            b"<?xml version='1.0'?>\n"
            b"<rss xmlns:itunes='http://www.itunes.com/dtds/podcast-1.0.dtd' "
            b"version='2.0'><channel>"
            b"<title>Acme</title>"
            b"<item><title>Ep 1</title>"
            b"<enclosure url='https://example.com/audio.mp3' type='audio/mpeg'/>"
            b"<itunes:duration>600</itunes:duration>"
            b"</item></channel></rss>"
        )
        respx.get("https://old.example.com/feed.rss").mock(
            return_value=Response(
                302,
                headers={"location": "https://feeds.example.net/acme.rss"},
            ),
        )
        respx.get("https://feeds.example.net/acme.rss").mock(
            return_value=Response(200, content=rss_xml),
        )

        with patch(
            "inkwell.demo.classifier.socket.getaddrinfo",
            side_effect=_fake_getaddrinfo("93.184.216.34"),
        ):
            feed = await _fetch_feed_safely("https://old.example.com/feed.rss")
        assert feed.entries
        assert feed.entries[0]["title"] == "Ep 1"

    @pytest.mark.asyncio
    @respx.mock
    async def test_blocks_redirect_when_hostname_resolves_to_private_ip(self) -> None:
        # Public-looking hostname; assert_demo_safe_url passes the host
        # literal, but DNS resolution returns RFC1918. The redirect guard
        # must reject before issuing the next request.
        respx.get("https://example.com/feed.rss").mock(
            return_value=Response(
                302,
                headers={"location": "https://internal.example.net/feed.rss"},
            ),
        )

        with patch(
            "inkwell.demo.classifier.socket.getaddrinfo",
            side_effect=_fake_getaddrinfo_by_host({"internal.example.net": "10.0.0.5"}),
        ):
            with pytest.raises(DemoUrlError) as excinfo:
                await _fetch_feed_safely("https://example.com/feed.rss")
        assert excinfo.value.reason.startswith("rss_redirect_to_unsafe_host:resolved_private_ip:")

    @pytest.mark.asyncio
    @respx.mock
    async def test_blocks_redirect_when_hostname_resolves_to_loopback(self) -> None:
        respx.get("https://example.com/feed.rss").mock(
            return_value=Response(
                302,
                headers={"location": "https://rebind.example.net/feed.rss"},
            ),
        )

        with patch(
            "inkwell.demo.classifier.socket.getaddrinfo",
            side_effect=_fake_getaddrinfo_by_host({"rebind.example.net": "127.0.0.1"}),
        ):
            with pytest.raises(DemoUrlError) as excinfo:
                await _fetch_feed_safely("https://example.com/feed.rss")
        assert excinfo.value.reason.startswith("rss_redirect_to_unsafe_host:resolved_private_ip:")

    @pytest.mark.asyncio
    @respx.mock
    async def test_blocks_redirect_when_hostname_resolves_to_rfc6598(self) -> None:
        # 100.64.0.0/10 is RFC6598 carrier-grade NAT space. Python flags
        # neither ``is_private`` nor ``is_reserved`` on it, so the
        # boolean-disjunction check codex flagged on PR #73 missed it.
        # ``not ip.is_global`` catches it.
        respx.get("https://example.com/feed.rss").mock(
            return_value=Response(
                302,
                headers={"location": "https://cgn.example.net/feed.rss"},
            ),
        )

        with patch(
            "inkwell.demo.classifier.socket.getaddrinfo",
            side_effect=_fake_getaddrinfo_by_host({"cgn.example.net": "100.64.0.5"}),
        ):
            with pytest.raises(DemoUrlError) as excinfo:
                await _fetch_feed_safely("https://example.com/feed.rss")
        assert excinfo.value.reason.startswith("rss_redirect_to_unsafe_host:resolved_private_ip:")

    @pytest.mark.asyncio
    @respx.mock
    async def test_blocks_initial_url_when_dns_rebinds_to_private_ip(self) -> None:
        # Codex P1 follow-up: classify time and worker fetch time are
        # decoupled (m1 + m5), so a DNS-rebinding attacker can submit a
        # name that resolves public at classify and flips to private
        # before the worker calls _fetch_feed_safely. The first hop
        # must rerun the host-literal + DNS checks.
        with patch(
            "inkwell.demo.classifier.socket.getaddrinfo",
            side_effect=_fake_getaddrinfo("10.0.0.5"),
        ):
            with pytest.raises(DemoUrlError) as excinfo:
                await _fetch_feed_safely("https://example.com/feed.rss")
        assert excinfo.value.reason.startswith("rss_unsafe_host:resolved_private_ip:")

    @pytest.mark.asyncio
    @respx.mock
    async def test_blocks_redirect_when_hostname_dns_fails(self) -> None:
        # Initial host resolves public; redirect target raises gaierror.
        respx.get("https://example.com/feed.rss").mock(
            return_value=Response(
                302,
                headers={"location": "https://nxdomain.example.net/feed.rss"},
            ),
        )

        def _resolve(host: str, *args: Any, **kwargs: Any) -> list[Any]:
            if host == "nxdomain.example.net":
                raise socket.gaierror(8, "nodename nor servname provided, or not known")
            return [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("93.184.216.34", 0))]

        with patch(
            "inkwell.demo.classifier.socket.getaddrinfo",
            side_effect=_resolve,
        ):
            with pytest.raises(DemoUrlError) as excinfo:
                await _fetch_feed_safely("https://example.com/feed.rss")
        assert excinfo.value.reason.startswith("rss_redirect_to_unsafe_host:dns_resolution_failed:")

    @pytest.mark.asyncio
    async def test_maps_malformed_redirect_location_to_demo_url_error(self) -> None:
        # Codex P2 from PR #73 post-merge review: an RSS endpoint that
        # 30x's with a malformed ``Location`` value would crash
        # ``httpx.URL(current).join(location)`` with ``httpx.InvalidURL``
        # and surface as a 500. Map it to a user-safe DemoUrlError with a
        # structured reason so the worker doesn't leak internals.
        #
        # httpx.AsyncClient itself pre-validates the ``Location`` header
        # in ``_send_handling_redirects`` and would raise
        # ``RemoteProtocolError`` before our loop sees the response, so we
        # patch ``_safe_get`` to hand the resolver a redirect Response
        # with a malformed Location verbatim — that's the state our join()
        # guard is defending against (e.g. if httpx loosens validation
        # upstream, or a future change moves us off ``AsyncClient``).
        from httpx import Response as _HttpxResponse

        bad_response = _HttpxResponse(302, headers={"location": "invalid://[::1"})

        async def _fake_safe_get(client: Any, url: str) -> _HttpxResponse:
            return bad_response

        with (
            patch(
                "inkwell.demo.classifier.socket.getaddrinfo",
                side_effect=_fake_getaddrinfo("93.184.216.34"),
            ),
            patch("inkwell.demo.resolver._safe_get", side_effect=_fake_safe_get),
        ):
            with pytest.raises(DemoUrlError) as excinfo:
                await _fetch_feed_safely("https://example.com/feed.rss")
        assert excinfo.value.reason.startswith("rss_redirect_malformed_location:")
        assert "InvalidURL" in excinfo.value.reason

    @pytest.mark.asyncio
    @respx.mock
    async def test_rejects_redirect_chain_over_hop_budget(self) -> None:
        # Public → public → public … should hit the hop budget and refuse
        # rather than spinning forever.
        respx.get(url__regex=r"https://[^/]*example\.com/feed\.rss").mock(
            return_value=Response(
                302,
                headers={"location": "https://other.example.com/feed.rss"},
            ),
        )

        with patch(
            "inkwell.demo.classifier.socket.getaddrinfo",
            side_effect=_fake_getaddrinfo("93.184.216.34"),
        ):
            with pytest.raises(DemoUrlError) as excinfo:
                await _fetch_feed_safely("https://example.com/feed.rss")
        assert excinfo.value.reason == "rss_too_many_redirects"

    @pytest.mark.asyncio
    @respx.mock
    async def test_maps_401_to_authentication_required(self) -> None:
        respx.get("https://example.com/private.rss").mock(return_value=Response(401))
        with pytest.raises(DemoUrlError) as excinfo:
            await _fetch_feed_safely("https://example.com/private.rss")
        assert excinfo.value.reason == "rss_authentication_required"

    @pytest.mark.asyncio
    @respx.mock
    async def test_maps_other_4xx_to_http_status_reason(self) -> None:
        respx.get("https://example.com/missing.rss").mock(return_value=Response(404))
        with pytest.raises(DemoUrlError) as excinfo:
            await _fetch_feed_safely("https://example.com/missing.rss")
        assert excinfo.value.reason == "rss_http_status:404"

    @pytest.mark.asyncio
    @respx.mock
    async def test_rejects_empty_feed(self) -> None:
        respx.get("https://example.com/empty.rss").mock(
            return_value=Response(
                200, content=b"<?xml version='1.0'?><rss><channel></channel></rss>"
            ),
        )
        with pytest.raises(DemoUrlError) as excinfo:
            await _fetch_feed_safely("https://example.com/empty.rss")
        assert excinfo.value.reason == "rss_no_entries"
