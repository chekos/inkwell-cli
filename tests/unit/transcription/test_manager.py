"""Tests for transcription manager."""

from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest

from inkwell.transcription import (
    Transcript,
    TranscriptionManager,
    TranscriptSegment,
)
from inkwell.utils.errors import APIError


class TestTranscriptionManager:
    """Test TranscriptionManager class."""

    @pytest.fixture
    def sample_transcript(self) -> Transcript:
        """Create sample transcript."""
        return Transcript(
            segments=[
                TranscriptSegment(text="Hello world", start=0.0, duration=2.0),
            ],
            source="youtube",
            language="en",
            episode_url="https://example.com/episode",
        )

    @pytest.fixture
    def mock_cache(self) -> Mock:
        """Create mock cache."""
        cache = Mock()
        cache.get = AsyncMock(return_value=None)
        cache.set = AsyncMock()
        cache.clear = AsyncMock(return_value=5)
        cache.clear_expired = AsyncMock(return_value=2)
        cache.stats = AsyncMock(return_value={"total": 10})
        return cache

    @pytest.fixture
    def mock_youtube(self) -> Mock:
        """Create mock YouTube transcriber."""
        youtube = Mock()
        youtube.can_transcribe = AsyncMock(return_value=True)
        youtube.transcribe = AsyncMock()
        return youtube

    @pytest.fixture
    def mock_downloader(self) -> Mock:
        """Create mock audio downloader."""
        downloader = Mock()
        downloader.download = AsyncMock(return_value=Path("/tmp/audio.m4a"))
        return downloader

    @pytest.fixture
    def mock_gemini(self) -> Mock:
        """Create mock Gemini transcriber."""
        gemini = Mock()
        gemini.transcribe = AsyncMock()
        return gemini

    @pytest.fixture
    def manager(
        self,
        mock_cache: Mock,
        mock_youtube: Mock,
        mock_downloader: Mock,
        mock_gemini: Mock,
    ) -> TranscriptionManager:
        """Create TranscriptionManager instance."""
        return TranscriptionManager(
            cache=mock_cache,
            youtube_transcriber=mock_youtube,
            audio_downloader=mock_downloader,
            gemini_transcriber=mock_gemini,
        )

    def test_initialization_with_components(
        self,
        mock_cache: Mock,
        mock_youtube: Mock,
        mock_downloader: Mock,
        mock_gemini: Mock,
    ) -> None:
        """Test initialization with provided components."""
        manager = TranscriptionManager(
            cache=mock_cache,
            youtube_transcriber=mock_youtube,
            audio_downloader=mock_downloader,
            gemini_transcriber=mock_gemini,
        )

        assert manager.cache == mock_cache
        assert manager.youtube_transcriber == mock_youtube
        assert manager.audio_downloader == mock_downloader
        assert manager.gemini_transcriber == mock_gemini

    def test_initialization_with_defaults(self) -> None:
        """Test initialization creates default components."""
        manager = TranscriptionManager()

        assert manager.cache is not None
        assert manager.youtube_transcriber is not None
        assert manager.audio_downloader is not None
        # Gemini may be None if no API key

    @pytest.mark.asyncio
    async def test_transcribe_cache_hit(
        self,
        manager: TranscriptionManager,
        mock_cache: Mock,
        sample_transcript: Transcript,
    ) -> None:
        """Test transcription with cache hit."""
        # Setup cache to return transcript
        cached = sample_transcript.model_copy(update={"source": "cached"})
        mock_cache.get.return_value = cached

        result = await manager.transcribe("https://example.com/episode")

        assert result.success is True
        assert result.transcript is not None
        assert result.transcript.source == "cached"
        assert result.from_cache is True
        assert result.cost_usd == 0.0
        assert "cache" in result.attempts
        assert len(result.attempts) == 1

        mock_cache.get.assert_called_once_with("https://example.com/episode")

    @pytest.mark.asyncio
    async def test_transcribe_youtube_success(
        self,
        manager: TranscriptionManager,
        mock_cache: Mock,
        mock_youtube: Mock,
        sample_transcript: Transcript,
    ) -> None:
        """Test successful YouTube transcription."""
        mock_cache.get.return_value = None  # Cache miss
        mock_youtube.transcribe.return_value = sample_transcript

        result = await manager.transcribe("https://youtube.com/watch?v=test")

        assert result.success is True
        assert result.transcript is not None
        assert result.from_cache is False
        assert result.cost_usd == 0.0  # YouTube is free
        assert "youtube" in result.attempts

        # Verify transcript was cached
        mock_cache.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_transcribe_youtube_failure_gemini_fallback(
        self,
        manager: TranscriptionManager,
        mock_cache: Mock,
        mock_youtube: Mock,
        mock_downloader: Mock,
        mock_gemini: Mock,
        sample_transcript: Transcript,
    ) -> None:
        """Test fallback to Gemini when YouTube fails."""
        mock_cache.get.return_value = None
        mock_youtube.transcribe.side_effect = APIError("YouTube failed")

        gemini_transcript = sample_transcript.model_copy(
            update={"source": "gemini", "cost_usd": 0.001}
        )
        mock_gemini.transcribe.return_value = gemini_transcript

        result = await manager.transcribe("https://youtube.com/watch?v=test")

        assert result.success is True
        assert result.transcript is not None
        assert result.transcript.source == "gemini"
        assert result.from_cache is False
        assert result.cost_usd == 0.001
        assert "youtube" in result.attempts
        assert "gemini" in result.attempts

        # Verify audio was downloaded
        mock_downloader.download.assert_called_once()

        # Verify Gemini was used
        mock_gemini.transcribe.assert_called_once()

        # Verify result was cached
        mock_cache.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_transcribe_all_tiers_fail(
        self,
        manager: TranscriptionManager,
        mock_cache: Mock,
        mock_youtube: Mock,
        mock_gemini: Mock,
    ) -> None:
        """Test handling when all tiers fail."""
        mock_cache.get.return_value = None
        mock_youtube.transcribe.side_effect = APIError("YouTube failed")
        mock_gemini.transcribe.side_effect = Exception("Gemini failed")

        result = await manager.transcribe("https://youtube.com/watch?v=test")

        assert result.success is False
        assert result.transcript is None
        assert result.error is not None
        assert "failed" in result.error.lower()
        assert "youtube" in result.attempts
        assert "gemini" in result.attempts

    @pytest.mark.asyncio
    async def test_transcribe_skip_youtube(
        self,
        manager: TranscriptionManager,
        mock_cache: Mock,
        mock_youtube: Mock,
        mock_gemini: Mock,
        sample_transcript: Transcript,
    ) -> None:
        """Test skipping YouTube tier."""
        mock_cache.get.return_value = None

        gemini_transcript = sample_transcript.model_copy(update={"source": "gemini"})
        mock_gemini.transcribe.return_value = gemini_transcript

        result = await manager.transcribe("https://youtube.com/watch?v=test", skip_youtube=True)

        assert result.success is True
        assert result.transcript.source == "gemini"
        assert "youtube" not in result.attempts
        assert "gemini" in result.attempts

        # Verify YouTube was not called
        mock_youtube.transcribe.assert_not_called()

    @pytest.mark.asyncio
    async def test_transcribe_disable_cache(
        self,
        manager: TranscriptionManager,
        mock_cache: Mock,
        mock_youtube: Mock,
        sample_transcript: Transcript,
    ) -> None:
        """Test disabling cache."""
        mock_youtube.transcribe.return_value = sample_transcript

        result = await manager.transcribe("https://youtube.com/watch?v=test", use_cache=False)

        assert result.success is True

        # Verify cache was not checked or updated
        mock_cache.get.assert_not_called()
        mock_cache.set.assert_not_called()

    @pytest.mark.asyncio
    async def test_transcribe_no_gemini_api_key(
        self,
        mock_cache: Mock,
        mock_youtube: Mock,
        mock_downloader: Mock,
    ) -> None:
        """Test transcription when Gemini is not configured."""
        manager = TranscriptionManager(
            cache=mock_cache,
            youtube_transcriber=mock_youtube,
            audio_downloader=mock_downloader,
            gemini_transcriber=None,  # No Gemini
        )

        mock_cache.get.return_value = None
        mock_youtube.transcribe.side_effect = APIError("YouTube failed")

        result = await manager.transcribe("https://youtube.com/watch?v=test")

        assert result.success is False
        assert result.error is not None
        # Check for helpful error message with API key configuration instructions
        assert "api key not configured" in result.error.lower()
        assert "inkwell config set" in result.error.lower()

    @pytest.mark.asyncio
    async def test_get_transcript_success(
        self,
        manager: TranscriptionManager,
        mock_cache: Mock,
        sample_transcript: Transcript,
    ) -> None:
        """Test get_transcript convenience method."""
        mock_cache.get.return_value = sample_transcript

        transcript = await manager.get_transcript("https://example.com/episode")

        assert transcript is not None
        assert transcript.episode_url == "https://example.com/episode"

    @pytest.mark.asyncio
    async def test_get_transcript_failure(
        self,
        manager: TranscriptionManager,
        mock_cache: Mock,
        mock_youtube: Mock,
        mock_gemini: Mock,
    ) -> None:
        """Test get_transcript returns None on failure."""
        mock_cache.get.return_value = None
        mock_youtube.transcribe.side_effect = APIError("Failed")
        mock_gemini.transcribe.side_effect = Exception("Failed")

        transcript = await manager.get_transcript("https://example.com/episode")

        assert transcript is None

    @pytest.mark.asyncio
    async def test_get_transcript_force_refresh(
        self,
        manager: TranscriptionManager,
        mock_cache: Mock,
        mock_youtube: Mock,
        sample_transcript: Transcript,
    ) -> None:
        """Test force_refresh bypasses cache."""
        mock_youtube.transcribe.return_value = sample_transcript

        transcript = await manager.get_transcript(
            "https://youtube.com/watch?v=test", force_refresh=True
        )

        assert transcript is not None

        # Cache should not have been checked
        mock_cache.get.assert_not_called()

    def test_clear_cache(self, manager: TranscriptionManager, mock_cache: Mock) -> None:
        """Test clear_cache delegates to cache."""
        count = manager.clear_cache()

        assert count == 5
        mock_cache.clear.assert_called_once()

    def test_clear_expired_cache(self, manager: TranscriptionManager, mock_cache: Mock) -> None:
        """Test clear_expired_cache delegates to cache."""
        count = manager.clear_expired_cache()

        assert count == 2
        mock_cache.clear_expired.assert_called_once()

    def test_cache_stats(self, manager: TranscriptionManager, mock_cache: Mock) -> None:
        """Test cache_stats delegates to cache."""
        stats = manager.cache_stats()

        assert stats["total"] == 10
        mock_cache.stats.assert_called_once()

    @pytest.mark.asyncio
    async def test_transcribe_non_youtube_url(
        self,
        manager: TranscriptionManager,
        mock_cache: Mock,
        mock_youtube: Mock,
        mock_gemini: Mock,
        sample_transcript: Transcript,
    ) -> None:
        """Test transcription of non-YouTube URL."""
        mock_cache.get.return_value = None
        mock_youtube.can_transcribe.return_value = False  # Not YouTube

        gemini_transcript = sample_transcript.model_copy(update={"source": "gemini"})
        mock_gemini.transcribe.return_value = gemini_transcript

        result = await manager.transcribe("https://example.com/podcast.mp3")

        assert result.success is True
        assert result.transcript.source == "gemini"

        # YouTube should not have been attempted
        mock_youtube.transcribe.assert_not_called()

        # Gemini should have been used
        mock_gemini.transcribe.assert_called_once()
