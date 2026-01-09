"""Tests for YouTube transcript extraction."""

from unittest.mock import Mock, patch

import pytest
from youtube_transcript_api._errors import (
    CouldNotRetrieveTranscript,
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
)

from inkwell.transcription import YouTubeTranscriber
from inkwell.utils.errors import APIError


class TestYouTubeURLDetection:
    """Tests for YouTube URL detection."""

    @pytest.fixture
    def transcriber(self):
        """Create a YouTubeTranscriber instance."""
        return YouTubeTranscriber()

    @pytest.mark.asyncio
    async def test_youtube_watch_url(self, transcriber):
        """Test detection of youtube.com/watch URLs."""
        url = "https://www.youtube.com/watch?v=abc123"
        assert await transcriber.can_transcribe(url) is True

    @pytest.mark.asyncio
    async def test_youtube_short_url(self, transcriber):
        """Test detection of youtu.be short URLs."""
        url = "https://youtu.be/xyz789"
        assert await transcriber.can_transcribe(url) is True

    @pytest.mark.asyncio
    async def test_youtube_embed_url(self, transcriber):
        """Test detection of youtube.com/embed URLs."""
        url = "https://youtube.com/embed/def456"
        assert await transcriber.can_transcribe(url) is True

    @pytest.mark.asyncio
    async def test_mobile_youtube_url(self, transcriber):
        """Test detection of m.youtube.com URLs."""
        url = "https://m.youtube.com/watch?v=mobile123"
        assert await transcriber.can_transcribe(url) is True

    @pytest.mark.asyncio
    async def test_non_youtube_url(self, transcriber):
        """Test rejection of non-YouTube URLs."""
        urls = [
            "https://example.com/video",
            "https://vimeo.com/123456",
            "https://podcasts.apple.com/episode",
        ]
        for url in urls:
            assert await transcriber.can_transcribe(url) is False

    @pytest.mark.asyncio
    async def test_case_insensitive_detection(self, transcriber):
        """Test that URL detection is case-insensitive."""
        urls = [
            "https://WWW.YOUTUBE.COM/watch?v=ABC",
            "https://YOUTU.BE/XYZ",
            "https://YouTube.com/embed/DEF",
        ]
        for url in urls:
            assert await transcriber.can_transcribe(url) is True


class TestVideoIDExtraction:
    """Tests for extracting video IDs from URLs."""

    @pytest.fixture
    def transcriber(self):
        """Create a YouTubeTranscriber instance."""
        return YouTubeTranscriber()

    def test_extract_from_watch_url(self, transcriber):
        """Test extracting ID from youtube.com/watch URL."""
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        video_id = transcriber._extract_video_id(url)
        assert video_id == "dQw4w9WgXcQ"

    def test_extract_from_watch_url_with_params(self, transcriber):
        """Test extracting ID from URL with additional parameters."""
        url = "https://www.youtube.com/watch?v=abc123&t=30s&list=PLxyz"
        video_id = transcriber._extract_video_id(url)
        assert video_id == "abc123"

    def test_extract_from_short_url(self, transcriber):
        """Test extracting ID from youtu.be short URL."""
        url = "https://youtu.be/xyz789"
        video_id = transcriber._extract_video_id(url)
        assert video_id == "xyz789"

    def test_extract_from_short_url_with_params(self, transcriber):
        """Test extracting ID from short URL with timestamp."""
        url = "https://youtu.be/def456?t=120"
        video_id = transcriber._extract_video_id(url)
        assert video_id == "def456"

    def test_extract_from_embed_url(self, transcriber):
        """Test extracting ID from embed URL."""
        url = "https://www.youtube.com/embed/embed123"
        video_id = transcriber._extract_video_id(url)
        assert video_id == "embed123"

    def test_extract_returns_none_for_invalid_url(self, transcriber):
        """Test that invalid URLs return None."""
        urls = [
            "https://youtube.com/notawatch",
            "https://example.com/video",
            "https://youtube.com/",
        ]
        for url in urls:
            assert transcriber._extract_video_id(url) is None


class TestTranscriptFetching:
    """Tests for fetching transcripts from YouTube."""

    @pytest.fixture
    def transcriber(self):
        """Create a YouTubeTranscriber instance."""
        return YouTubeTranscriber()

    @pytest.fixture
    def mock_transcript_data(self):
        """Create mock transcript data."""
        return [
            {"text": "Hello world", "start": 0.0, "duration": 2.0},
            {"text": "This is a test", "start": 2.0, "duration": 3.0},
            {"text": "Goodbye", "start": 5.0, "duration": 1.5},
        ]

    @pytest.mark.asyncio
    async def test_successful_transcript_fetch(self, transcriber, mock_transcript_data):
        """Test successful transcript fetching."""
        url = "https://youtube.com/watch?v=test123"

        # Mock the API
        mock_transcript = Mock()
        mock_transcript.language_code = "en"
        mock_transcript.fetch.return_value = mock_transcript_data

        mock_transcript_list = Mock()
        mock_transcript_list.find_transcript.return_value = mock_transcript

        with patch.object(transcriber.api, "list", return_value=mock_transcript_list):
            transcript = await transcriber.transcribe(url)

        assert transcript.source == "youtube"
        assert transcript.language == "en"
        assert transcript.episode_url == url
        assert len(transcript.segments) == 3
        assert transcript.segments[0].text == "Hello world"
        assert transcript.segments[0].start == 0.0
        assert transcript.segments[0].duration == 2.0

    @pytest.mark.asyncio
    async def test_fallback_to_generated_transcript(self, transcriber, mock_transcript_data):
        """Test fallback to auto-generated transcript."""
        url = "https://youtube.com/watch?v=test123"

        # Mock: first call to find_transcript fails, generated succeeds
        mock_transcript = Mock()
        mock_transcript.language_code = "en"
        mock_transcript.fetch.return_value = mock_transcript_data

        mock_transcript_list = Mock()
        mock_transcript_list.find_transcript.side_effect = NoTranscriptFound(
            "test123", ["en"], None
        )
        mock_transcript_list.find_generated_transcript.return_value = mock_transcript

        with patch.object(transcriber.api, "list", return_value=mock_transcript_list):
            transcript = await transcriber.transcribe(url)

        assert transcript.source == "youtube"
        assert len(transcript.segments) == 3
        # Verify find_generated_transcript was called
        mock_transcript_list.find_generated_transcript.assert_called_once()

    @pytest.mark.asyncio
    async def test_language_preference_order(self, transcriber, mock_transcript_data):
        """Test that language preferences are tried in order."""
        transcriber.preferred_languages = ["es", "en", "fr"]
        url = "https://youtube.com/watch?v=test123"

        # Mock: es fails, en succeeds
        mock_en_transcript = Mock()
        mock_en_transcript.language_code = "en"
        mock_en_transcript.fetch.return_value = mock_transcript_data

        call_count = [0]

        def find_transcript_side_effect(langs):
            call_count[0] += 1
            if call_count[0] == 1:  # First call with ['es']
                raise NoTranscriptFound("test123", langs, None)
            return mock_en_transcript  # Second call with ['en']

        mock_transcript_list = Mock()
        mock_transcript_list.find_transcript.side_effect = find_transcript_side_effect

        with patch.object(transcriber.api, "list", return_value=mock_transcript_list):
            transcript = await transcriber.transcribe(url)

        assert transcript.language == "en"
        assert mock_transcript_list.find_transcript.call_count == 2

    @pytest.mark.asyncio
    async def test_invalid_url_raises_error(self, transcriber):
        """Test that invalid URL raises APIError."""
        url = "https://youtube.com/invalid"

        with pytest.raises(APIError) as exc_info:
            await transcriber.transcribe(url)

        assert "Could not extract video ID" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_transcripts_disabled_error(self, transcriber):
        """Test handling of disabled transcripts."""
        url = "https://youtube.com/watch?v=test123"

        mock_transcript_list = Mock()
        mock_transcript_list.find_transcript.side_effect = TranscriptsDisabled("test123")

        with patch.object(transcriber.api, "list", return_value=mock_transcript_list):
            with pytest.raises(APIError) as exc_info:
                await transcriber.transcribe(url)

        assert "disabled" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_video_unavailable_error(self, transcriber):
        """Test handling of unavailable video."""
        url = "https://youtube.com/watch?v=test123"

        mock_transcript_list = Mock()
        mock_transcript_list.find_transcript.side_effect = VideoUnavailable("test123")

        with patch.object(transcriber.api, "list", return_value=mock_transcript_list):
            with pytest.raises(APIError) as exc_info:
                await transcriber.transcribe(url)

        assert "unavailable" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_could_not_retrieve_transcript_error(self, transcriber):
        """Test handling of retrieval failures (403, network errors)."""
        url = "https://youtube.com/watch?v=test123"

        with patch.object(
            transcriber.api,
            "list",
            side_effect=CouldNotRetrieveTranscript("test123"),
        ):
            with pytest.raises(APIError) as exc_info:
                await transcriber.transcribe(url)

        error_msg = str(exc_info.value).lower()
        assert "failed to retrieve" in error_msg or "could not retrieve" in error_msg

    @pytest.mark.asyncio
    async def test_no_transcript_in_any_language(self, transcriber):
        """Test when no transcript available in any preferred language."""
        url = "https://youtube.com/watch?v=test123"

        # Mock available transcripts
        mock_fr_transcript = Mock()
        mock_fr_transcript.language_code = "fr"
        mock_de_transcript = Mock()
        mock_de_transcript.language_code = "de"

        mock_transcript_list = Mock()
        mock_transcript_list.find_transcript.side_effect = NoTranscriptFound(
            "test123", ["en"], None
        )
        mock_transcript_list.find_generated_transcript.side_effect = NoTranscriptFound(
            "test123", ["en"], None
        )
        # For the error message
        mock_transcript_list.__iter__ = Mock(
            return_value=iter([mock_fr_transcript, mock_de_transcript])
        )

        with patch.object(transcriber.api, "list", return_value=mock_transcript_list):
            with pytest.raises(APIError) as exc_info:
                await transcriber.transcribe(url)

        error_msg = str(exc_info.value)
        assert "No transcript found" in error_msg
        assert "fr, de" in error_msg  # Available languages mentioned

    @pytest.mark.asyncio
    async def test_unexpected_error_handling(self, transcriber):
        """Test handling of unexpected errors."""
        url = "https://youtube.com/watch?v=test123"

        with patch.object(
            transcriber.api,
            "list",
            side_effect=Exception("Unexpected API error"),
        ):
            with pytest.raises(APIError) as exc_info:
                await transcriber.transcribe(url)

        assert "Unexpected error" in str(exc_info.value)


class TestCostEstimation:
    """Tests for cost estimation."""

    def test_estimate_cost_always_zero(self):
        """Test that YouTube transcripts are always free."""
        transcriber = YouTubeTranscriber()

        # Various durations
        assert transcriber.estimate_cost(0) == 0.0
        assert transcriber.estimate_cost(60) == 0.0
        assert transcriber.estimate_cost(3600) == 0.0
        assert transcriber.estimate_cost(10000) == 0.0


class TestLanguagePreferences:
    """Tests for language preference handling."""

    def test_default_language_is_english(self):
        """Test that default preferred language is English."""
        transcriber = YouTubeTranscriber()
        assert transcriber.preferred_languages == ["en"]

    def test_custom_language_preferences(self):
        """Test setting custom language preferences."""
        transcriber = YouTubeTranscriber(preferred_languages=["es", "fr", "de"])
        assert transcriber.preferred_languages == ["es", "fr", "de"]

    def test_empty_language_list_defaults_to_english(self):
        """Test that empty language list defaults to English."""
        transcriber = YouTubeTranscriber(preferred_languages=[])
        assert transcriber.preferred_languages == ["en"]


class TestEdgeCases:
    """Tests for edge cases and unusual scenarios."""

    @pytest.fixture
    def transcriber(self):
        """Create a YouTubeTranscriber instance."""
        return YouTubeTranscriber()

    def test_extract_video_id_with_trailing_slash(self, transcriber):
        """Test URL with trailing slash."""
        url = "https://youtu.be/abc123/"
        video_id = transcriber._extract_video_id(url)
        assert video_id == "abc123"

    def test_extract_video_id_with_fragment(self, transcriber):
        """Test URL with fragment (#)."""
        url = "https://youtube.com/watch?v=xyz789#comments"
        video_id = transcriber._extract_video_id(url)
        assert video_id == "xyz789"

    @pytest.mark.asyncio
    async def test_empty_transcript_data(self, transcriber):
        """Test handling of empty transcript (no segments)."""
        url = "https://youtube.com/watch?v=test123"

        mock_transcript = Mock()
        mock_transcript.language_code = "en"
        mock_transcript.fetch.return_value = []  # Empty!

        mock_transcript_list = Mock()
        mock_transcript_list.find_transcript.return_value = mock_transcript

        with patch.object(transcriber.api, "list", return_value=mock_transcript_list):
            transcript = await transcriber.transcribe(url)

        assert len(transcript.segments) == 0
        assert transcript.source == "youtube"
