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
            side_effect=_fake_getaddrinfo("10.0.0.5"),
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
            side_effect=_fake_getaddrinfo("127.0.0.1"),
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
            side_effect=_fake_getaddrinfo("100.64.0.5"),
        ):
            with pytest.raises(DemoUrlError) as excinfo:
                await _fetch_feed_safely("https://example.com/feed.rss")
        assert excinfo.value.reason.startswith("rss_redirect_to_unsafe_host:resolved_private_ip:")

    @pytest.mark.asyncio
    @respx.mock
    async def test_blocks_redirect_when_hostname_dns_fails(self) -> None:
        respx.get("https://example.com/feed.rss").mock(
            return_value=Response(
                302,
                headers={"location": "https://nxdomain.example.net/feed.rss"},
            ),
        )

        def _gaierror(*args: Any, **kwargs: Any) -> list[Any]:
            raise socket.gaierror(8, "nodename nor servname provided, or not known")

        with patch(
            "inkwell.demo.classifier.socket.getaddrinfo",
            side_effect=_gaierror,
        ):
            with pytest.raises(DemoUrlError) as excinfo:
                await _fetch_feed_safely("https://example.com/feed.rss")
        assert excinfo.value.reason.startswith("rss_redirect_to_unsafe_host:dns_resolution_failed:")

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
