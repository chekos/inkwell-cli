"""Tests for YouTube URL resolver."""

from unittest.mock import MagicMock, patch

import pytest
from yt_dlp.utils import DownloadError, ExtractorError

from inkwell.feeds.youtube_resolver import resolve_youtube_url
from inkwell.utils.errors import ValidationError


def _mock_ytdlp(
    channel_id: str | None = "UCtestChannelIdExample", channel: str | None = "Test Channel"
):
    """Build a patch context for yt_dlp.YoutubeDL returning the given info dict."""
    info: dict[str, str | None] = {"channel_id": channel_id, "channel": channel}
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
        feed_url, _ = result
        assert "channel_id=UCtestChannelIdExample" in feed_url
        mock_class.assert_not_called()

    @pytest.mark.asyncio
    async def test_already_resolved_feed_url_passes_through(self) -> None:
        """feeds/videos.xml?channel_id=... URLs are returned unchanged."""
        patcher, mock_class = _mock_ytdlp()
        url = "https://www.youtube.com/feeds/videos.xml?channel_id=UCabc"
        with patcher:
            result = await resolve_youtube_url(url)
        assert result == (url, None)
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
        assert "channel_id=UCabc" in result[0]


class TestResolveYouTubeUrlWithYtDlp:
    """URL shapes that require yt-dlp to resolve the channel_id."""

    @pytest.mark.asyncio
    async def test_watch_url_resolves_via_ytdlp(self) -> None:
        patcher, mock_class = _mock_ytdlp(channel_id="UCabc", channel="Some Channel")
        with patcher:
            result = await resolve_youtube_url("https://www.youtube.com/watch?v=someVideoId")
        assert result is not None
        feed_url, channel_name = result
        assert "channel_id=UCabc" in feed_url
        assert channel_name == "Some Channel"
        mock_class.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_url_resolves_via_ytdlp(self) -> None:
        patcher, mock_class = _mock_ytdlp(channel_id="UChandle")
        with patcher:
            result = await resolve_youtube_url("https://www.youtube.com/@somehandle")
        assert result is not None
        assert "channel_id=UChandle" in result[0]
        mock_class.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_tab_suffixed_url_resolves(self) -> None:
        """/@handle/videos, /@handle/shorts, /@handle/streams all resolve."""
        patcher, _ = _mock_ytdlp(channel_id="UChandle")
        with patcher:
            for suffix in ("videos", "shorts", "streams", "featured"):
                result = await resolve_youtube_url(f"https://www.youtube.com/@somehandle/{suffix}")
                assert result is not None
                assert "channel_id=UChandle" in result[0]

    @pytest.mark.asyncio
    async def test_youtu_be_resolves_via_ytdlp(self) -> None:
        patcher, _ = _mock_ytdlp(channel_id="UCshort")
        with patcher:
            result = await resolve_youtube_url("https://youtu.be/someVideoId")
        assert result is not None
        assert "channel_id=UCshort" in result[0]

    @pytest.mark.asyncio
    async def test_shorts_url_resolves_via_ytdlp(self) -> None:
        patcher, _ = _mock_ytdlp(channel_id="UCshorts")
        with patcher:
            result = await resolve_youtube_url("https://www.youtube.com/shorts/someShortId")
        assert result is not None
        assert "channel_id=UCshorts" in result[0]

    @pytest.mark.asyncio
    async def test_live_url_resolves_via_ytdlp(self) -> None:
        patcher, _ = _mock_ytdlp(channel_id="UClive")
        with patcher:
            result = await resolve_youtube_url("https://www.youtube.com/live/someLiveId")
        assert result is not None
        assert "channel_id=UClive" in result[0]

    @pytest.mark.asyncio
    async def test_mobile_host_resolves_via_ytdlp(self) -> None:
        patcher, _ = _mock_ytdlp(channel_id="UCmobile")
        with patcher:
            result = await resolve_youtube_url("https://m.youtube.com/watch?v=someVideoId")
        assert result is not None
        assert "channel_id=UCmobile" in result[0]

    @pytest.mark.asyncio
    async def test_legacy_user_form_normalizes_to_channel_id(self) -> None:
        """/user/LegacyName goes through yt-dlp; result normalizes to ?channel_id= form."""
        patcher, mock_class = _mock_ytdlp(channel_id="UClegacy")
        with patcher:
            result = await resolve_youtube_url("https://www.youtube.com/user/LegacyUsername")
        assert result is not None
        assert "channel_id=UClegacy" in result[0]
        mock_class.assert_called_once()

    @pytest.mark.asyncio
    async def test_embed_url_resolves_via_ytdlp(self) -> None:
        patcher, _ = _mock_ytdlp(channel_id="UCembed")
        with patcher:
            result = await resolve_youtube_url("https://www.youtube.com/embed/someVideoId")
        assert result is not None
        assert "channel_id=UCembed" in result[0]


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
