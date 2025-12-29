"""Tests for URL metadata extraction utilities."""

import pytest

from inkwell.utils.url_metadata import (
    INBOX_PODCAST_NAME,
    URLMetadata,
    create_fallback_title,
    extract_filename_from_url,
    extract_url_slug,
    extract_youtube_id,
    get_episode_title_from_metadata,
)


class TestExtractYoutubeId:
    """Tests for extract_youtube_id function."""

    def test_standard_watch_url(self):
        """Should extract ID from standard youtube.com/watch URL."""
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        assert extract_youtube_id(url) == "dQw4w9WgXcQ"

    def test_watch_url_with_extra_params(self):
        """Should extract ID even with extra query parameters."""
        url = "https://youtube.com/watch?v=abc123&t=120&list=PLxyz"
        assert extract_youtube_id(url) == "abc123"

    def test_short_url(self):
        """Should extract ID from youtu.be short URL."""
        url = "https://youtu.be/dQw4w9WgXcQ"
        assert extract_youtube_id(url) == "dQw4w9WgXcQ"

    def test_short_url_with_timestamp(self):
        """Should extract ID from short URL with timestamp."""
        url = "https://youtu.be/dQw4w9WgXcQ?t=42"
        assert extract_youtube_id(url) == "dQw4w9WgXcQ"

    def test_embed_url(self):
        """Should extract ID from embed URL."""
        url = "https://www.youtube.com/embed/dQw4w9WgXcQ"
        assert extract_youtube_id(url) == "dQw4w9WgXcQ"

    def test_v_url(self):
        """Should extract ID from /v/ URL format."""
        url = "https://www.youtube.com/v/dQw4w9WgXcQ"
        assert extract_youtube_id(url) == "dQw4w9WgXcQ"

    def test_mobile_url(self):
        """Should extract ID from mobile YouTube URL."""
        url = "https://m.youtube.com/watch?v=dQw4w9WgXcQ"
        assert extract_youtube_id(url) == "dQw4w9WgXcQ"

    def test_non_youtube_url(self):
        """Should return None for non-YouTube URLs."""
        url = "https://vimeo.com/123456"
        assert extract_youtube_id(url) is None

    def test_invalid_youtube_url(self):
        """Should return None for YouTube URL without video ID."""
        url = "https://youtube.com/channel/UCxyz"
        assert extract_youtube_id(url) is None


class TestExtractUrlSlug:
    """Tests for extract_url_slug function."""

    def test_youtube_url_returns_video_id(self):
        """Should return video ID for YouTube URLs."""
        url = "https://youtube.com/watch?v=abc123xyz"
        assert extract_url_slug(url) == "abc123xyz"

    def test_non_youtube_returns_hash(self):
        """Should return hash for non-YouTube URLs."""
        url = "https://example.com/podcast/episode-42.mp3"
        slug = extract_url_slug(url)
        assert len(slug) == 12  # Hash is 12 chars
        assert slug.isalnum()

    def test_same_url_same_hash(self):
        """Should return same hash for same URL."""
        url = "https://example.com/audio.mp3"
        assert extract_url_slug(url) == extract_url_slug(url)

    def test_different_urls_different_hashes(self):
        """Should return different hashes for different URLs."""
        url1 = "https://example.com/episode1.mp3"
        url2 = "https://example.com/episode2.mp3"
        assert extract_url_slug(url1) != extract_url_slug(url2)


class TestExtractFilenameFromUrl:
    """Tests for extract_filename_from_url function."""

    def test_simple_filename(self):
        """Should extract filename from URL path."""
        url = "https://example.com/podcasts/my-episode.mp3"
        assert extract_filename_from_url(url) == "my-episode"

    def test_filename_with_underscores(self):
        """Should handle filenames with underscores (preserved as-is after cleaning)."""
        url = "https://example.com/episode_42_final.mp3"
        # Underscores are kept, only special chars are removed
        assert extract_filename_from_url(url) == "episode_42_final"

    def test_short_filename_returns_none(self):
        """Should return None for very short filenames."""
        url = "https://example.com/ep.mp3"
        assert extract_filename_from_url(url) is None

    def test_no_filename_returns_none(self):
        """Should return None when no filename in path."""
        url = "https://example.com/"
        assert extract_filename_from_url(url) is None


class TestCreateFallbackTitle:
    """Tests for create_fallback_title function."""

    def test_uses_filename_when_available(self):
        """Should use cleaned filename when available."""
        url = "https://example.com/my-great-episode.mp3"
        title = create_fallback_title(url)
        assert "Great" in title or "great" in title.lower()

    def test_uses_domain_when_no_filename(self):
        """Should use domain + hash when no filename."""
        url = "https://spotify.com/"
        title = create_fallback_title(url)
        assert "Spotify" in title

    def test_strips_www_from_domain(self):
        """Should strip www. from domain."""
        url = "https://www.podcasts.com/"
        title = create_fallback_title(url)
        assert "Podcasts" in title
        assert "www" not in title.lower()


class TestGetEpisodeTitleFromMetadata:
    """Tests for get_episode_title_from_metadata function."""

    def test_uses_metadata_title_when_available(self):
        """Should prefer metadata title over fallback."""
        metadata = URLMetadata(title="The Real Title")
        url = "https://example.com/episode.mp3"
        assert get_episode_title_from_metadata(metadata, url) == "The Real Title"

    def test_uses_fallback_when_no_title(self):
        """Should use fallback when metadata has no title."""
        metadata = URLMetadata(title=None)
        url = "https://example.com/great-episode.mp3"
        title = get_episode_title_from_metadata(metadata, url)
        assert "Great" in title or "great" in title.lower()


class TestURLMetadata:
    """Tests for URLMetadata model."""

    def test_all_fields_optional(self):
        """Should allow creating with no fields."""
        metadata = URLMetadata()
        assert metadata.title is None
        assert metadata.video_id is None
        assert metadata.domain is None
        assert metadata.duration_seconds is None

    def test_with_all_fields(self):
        """Should store all fields correctly."""
        metadata = URLMetadata(
            title="Test Episode",
            video_id="abc123",
            domain="youtube.com",
            duration_seconds=3600.5,
        )
        assert metadata.title == "Test Episode"
        assert metadata.video_id == "abc123"
        assert metadata.domain == "youtube.com"
        assert metadata.duration_seconds == 3600.5


class TestInboxConstant:
    """Tests for INBOX_PODCAST_NAME constant."""

    def test_inbox_name(self):
        """Should be _inbox."""
        assert INBOX_PODCAST_NAME == "_inbox"

    def test_starts_with_underscore(self):
        """Should start with underscore for sorting."""
        assert INBOX_PODCAST_NAME.startswith("_")
