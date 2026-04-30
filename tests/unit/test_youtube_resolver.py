"""Tests for YouTube URL resolver."""

from unittest.mock import MagicMock, patch

import pytest
from yt_dlp.utils import DownloadError, ExtractorError

from inkwell.feeds.youtube_resolver import resolve_youtube_url
from inkwell.utils.errors import ValidationError


def _mock_ytdlp(
    channel_id: str | None = "UCtestChannelIdExample",
    channel: str | None = "Test Channel",
    title: str | None = "Test Episode Title",
):
    """Build a patch context for yt_dlp.YoutubeDL returning the given info dict."""
    info: dict[str, str | None] = {"channel_id": channel_id, "channel": channel, "title": title}
    mock_instance = MagicMock()
    mock_instance.extract_info.return_value = info
    mock_class = MagicMock()
    mock_class.return_value.__enter__.return_value = mock_instance
    return patch("inkwell.feeds.youtube_resolver.YoutubeDL", mock_class), mock_class


class TestResolveYouTubeUrlPureLayer:
    """URL-shape cases that never touch yt-dlp."""

    @pytest.mark.asyncio
    async def test_channel_path_returns_feed_url_without_ytdlp(self) -> None:
        """/channel/UCxxx URLs extract channel_id via regex — yt-dlp is never called."""
        patcher, mock_class = _mock_ytdlp()
        with patcher:
            result = await resolve_youtube_url(
                "https://www.youtube.com/channel/UCtestChannelIdExample"
            )
        assert result is not None
        assert "channel_id=UCtestChannelIdExample" in result.feed_url
        mock_class.assert_not_called()

    @pytest.mark.asyncio
    async def test_already_resolved_feed_url_passes_through(self) -> None:
        """feeds/videos.xml?channel_id=... URLs are returned unchanged."""
        patcher, mock_class = _mock_ytdlp()
        url = "https://www.youtube.com/feeds/videos.xml?channel_id=UCabc"
        with patcher:
            result = await resolve_youtube_url(url)
        assert result is not None
        assert result.feed_url == url
        assert result.channel_name is None
        mock_class.assert_not_called()

    @pytest.mark.asyncio
    async def test_non_youtube_url_returns_none(self) -> None:
        """Non-YouTube URLs return None so caller falls through to existing RSS flow."""
        patcher, mock_class = _mock_ytdlp()
        with patcher:
            result = await resolve_youtube_url("https://example.com/feed.rss")
        assert result is None
        mock_class.assert_not_called()

    @pytest.mark.asyncio
    async def test_malformed_url_returns_none(self) -> None:
        """Malformed/empty URLs return None without raising."""
        patcher, _ = _mock_ytdlp()
        with patcher:
            assert await resolve_youtube_url("") is None
            assert await resolve_youtube_url("not-a-url") is None

    @pytest.mark.asyncio
    async def test_uppercase_host_accepted(self) -> None:
        """Host matching is case-insensitive (browsers normalize anyway)."""
        patcher, _ = _mock_ytdlp()
        with patcher:
            result = await resolve_youtube_url("https://WWW.YOUTUBE.COM/channel/UCabc")
        assert result is not None
        assert "channel_id=UCabc" in result.feed_url


class TestResolveYouTubeUrlWithYtDlp:
    """URL shapes that require yt-dlp to resolve the channel_id."""

    @pytest.mark.asyncio
    async def test_watch_url_resolves_via_ytdlp(self) -> None:
        patcher, mock_class = _mock_ytdlp(
            channel_id="UCabc",
            channel="Some Channel",
            title="How to Build Durable Systems",
        )
        with patcher:
            result = await resolve_youtube_url("https://www.youtube.com/watch?v=someVideoId")
        assert result is not None
        assert "channel_id=UCabc" in result.feed_url
        assert result.episode_title == "How to Build Durable Systems"
        mock_class.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_url_resolves_via_ytdlp(self) -> None:
        patcher, mock_class = _mock_ytdlp(channel_id="UChandle")
        with patcher:
            result = await resolve_youtube_url("https://www.youtube.com/@somehandle")
        assert result is not None
        assert "channel_id=UChandle" in result.feed_url
        mock_class.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_tab_suffixed_url_resolves(self) -> None:
        """/@handle/videos, /@handle/shorts, /@handle/streams all resolve."""
        patcher, _ = _mock_ytdlp(channel_id="UChandle")
        with patcher:
            for suffix in ("videos", "shorts", "streams", "featured"):
                result = await resolve_youtube_url(f"https://www.youtube.com/@somehandle/{suffix}")
                assert result is not None
                assert "channel_id=UChandle" in result.feed_url

    @pytest.mark.asyncio
    async def test_youtu_be_resolves_via_ytdlp(self) -> None:
        patcher, _ = _mock_ytdlp(channel_id="UCshort")
        with patcher:
            result = await resolve_youtube_url("https://youtu.be/someVideoId")
        assert result is not None
        assert "channel_id=UCshort" in result.feed_url

    @pytest.mark.asyncio
    async def test_shorts_url_resolves_via_ytdlp(self) -> None:
        patcher, _ = _mock_ytdlp(channel_id="UCshorts")
        with patcher:
            result = await resolve_youtube_url("https://www.youtube.com/shorts/someShortId")
        assert result is not None
        assert "channel_id=UCshorts" in result.feed_url

    @pytest.mark.asyncio
    async def test_live_url_resolves_via_ytdlp(self) -> None:
        patcher, _ = _mock_ytdlp(channel_id="UClive")
        with patcher:
            result = await resolve_youtube_url("https://www.youtube.com/live/someLiveId")
        assert result is not None
        assert "channel_id=UClive" in result.feed_url

    @pytest.mark.asyncio
    async def test_mobile_host_resolves_via_ytdlp(self) -> None:
        patcher, _ = _mock_ytdlp(channel_id="UCmobile")
        with patcher:
            result = await resolve_youtube_url("https://m.youtube.com/watch?v=someVideoId")
        assert result is not None
        assert "channel_id=UCmobile" in result.feed_url

    @pytest.mark.asyncio
    async def test_legacy_user_form_normalizes_to_channel_id(self) -> None:
        """/user/LegacyName goes through yt-dlp; result normalizes to ?channel_id= form."""
        patcher, mock_class = _mock_ytdlp(channel_id="UClegacy")
        with patcher:
            result = await resolve_youtube_url("https://www.youtube.com/user/LegacyUsername")
        assert result is not None
        assert "channel_id=UClegacy" in result.feed_url
        mock_class.assert_called_once()

    @pytest.mark.asyncio
    async def test_embed_url_resolves_via_ytdlp(self) -> None:
        patcher, _ = _mock_ytdlp(channel_id="UCembed")
        with patcher:
            result = await resolve_youtube_url("https://www.youtube.com/embed/someVideoId")
        assert result is not None
        assert "channel_id=UCembed" in result.feed_url

    @pytest.mark.asyncio
    async def test_c_path_resolves_via_ytdlp(self) -> None:
        """Legacy /c/SomeName vanity URLs go through yt-dlp (no path-shortcut)."""
        patcher, mock_class = _mock_ytdlp(channel_id="UCvanity")
        with patcher:
            result = await resolve_youtube_url("https://www.youtube.com/c/SomeVanityName")
        assert result is not None
        assert "channel_id=UCvanity" in result.feed_url
        mock_class.assert_called_once()

    @pytest.mark.asyncio
    async def test_tracking_params_do_not_trigger_playlist_rejection(self) -> None:
        """URLs with share tracking params (?si=, &t=) must not look like playlists."""
        patcher, _ = _mock_ytdlp(channel_id="UCtrack")
        with patcher:
            # youtu.be/<id>?si=<tracking>&t=10 — common "Copy link" output.
            result = await resolve_youtube_url("https://youtu.be/abcVid?si=xyz123&t=10")
        assert result is not None
        assert "channel_id=UCtrack" in result.feed_url


class TestResolveYouTubeUrlPlaylistRejection:
    """Playlist URLs are out of scope — reject with a clear error."""

    @pytest.mark.asyncio
    async def test_watch_with_list_param_rejected(self) -> None:
        patcher, _ = _mock_ytdlp()
        with patcher:
            with pytest.raises(ValidationError, match="[Pp]laylist"):
                await resolve_youtube_url("https://www.youtube.com/watch?v=VID&list=PL12345")

    @pytest.mark.asyncio
    async def test_playlist_path_rejected(self) -> None:
        patcher, _ = _mock_ytdlp()
        with patcher:
            with pytest.raises(ValidationError, match="[Pp]laylist"):
                await resolve_youtube_url("https://www.youtube.com/playlist?list=PL12345")

    @pytest.mark.asyncio
    async def test_playlists_listing_page_is_not_a_playlist(self) -> None:
        """/playlists (plural — YouTube's playlists-listing page) must not
        be confused with a single-playlist URL. It should hand off to yt-dlp."""
        patcher, mock_class = _mock_ytdlp(channel_id="UCowner")
        with patcher:
            # Should NOT raise a playlist ValidationError. yt-dlp may or may
            # not resolve it, but the rejection-by-startswith bug would raise
            # "Playlist URLs aren't supported" before yt-dlp ever runs.
            result = await resolve_youtube_url("https://www.youtube.com/playlists")
        # Either yt-dlp resolved it or returned nothing — the key is that we
        # didn't short-circuit with a playlist rejection.
        assert result is not None
        assert "channel_id=UCowner" in result.feed_url
        mock_class.assert_called_once()


class TestResolveYouTubeUrlFailFastGuards:
    """URL shapes that should surface an actionable error before yt-dlp runs."""

    @pytest.mark.asyncio
    async def test_empty_channel_id_value_does_not_pass_through_as_resolved(self) -> None:
        """feeds/videos.xml?channel_id= (empty value) must not pretend to be resolved."""
        patcher, mock_class = _mock_ytdlp(channel_id=None)
        with patcher:
            # Must NOT return (url, None) as the resolved branch would —
            # falls through to yt-dlp, which raises ValidationError.
            with pytest.raises(ValidationError):
                await resolve_youtube_url("https://www.youtube.com/feeds/videos.xml?channel_id=")

    @pytest.mark.asyncio
    async def test_root_url_rejected_with_specific_message(self) -> None:
        """https://youtube.com (homepage) must not reach yt-dlp with an opaque error."""
        patcher, mock_class = _mock_ytdlp()
        with patcher:
            with pytest.raises(ValidationError, match="homepage"):
                await resolve_youtube_url("https://youtube.com")
            with pytest.raises(ValidationError, match="homepage"):
                await resolve_youtube_url("https://www.youtube.com/")
        mock_class.assert_not_called()


class TestResolveYouTubeUrlErrors:
    """yt-dlp failure modes propagate as ValidationError with actionable suggestions."""

    @pytest.mark.asyncio
    async def test_ytdlp_returns_no_channel_id_raises(self) -> None:
        patcher, _ = _mock_ytdlp(channel_id=None)
        with patcher:
            with pytest.raises(ValidationError, match="[Cc]ouldn't resolve"):
                await resolve_youtube_url("https://www.youtube.com/watch?v=private")

    @pytest.mark.asyncio
    async def test_ytdlp_extractor_error_wrapped_as_validation(self) -> None:
        mock_instance = MagicMock()
        mock_instance.extract_info.side_effect = ExtractorError(
            "Sign in to confirm you're not a bot"
        )
        mock_class = MagicMock()
        mock_class.return_value.__enter__.return_value = mock_instance
        with patch("inkwell.feeds.youtube_resolver.YoutubeDL", mock_class):
            with pytest.raises(ValidationError) as exc_info:
                await resolve_youtube_url("https://www.youtube.com/watch?v=blocked")
            # Manual escape hatch is preserved in the suggestion so users aren't stuck.
            assert exc_info.value.suggestion is not None
            assert "feeds/videos.xml" in exc_info.value.suggestion

    @pytest.mark.asyncio
    async def test_ytdlp_download_error_wrapped_as_validation(self) -> None:
        mock_instance = MagicMock()
        mock_instance.extract_info.side_effect = DownloadError("Video unavailable")
        mock_class = MagicMock()
        mock_class.return_value.__enter__.return_value = mock_instance
        with patch("inkwell.feeds.youtube_resolver.YoutubeDL", mock_class):
            with pytest.raises(ValidationError):
                await resolve_youtube_url("https://www.youtube.com/watch?v=gone")
