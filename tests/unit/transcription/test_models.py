"""Tests for transcription data models."""

from datetime import timedelta

import pytest
from pydantic import ValidationError

from inkwell.transcription.models import Transcript, TranscriptionResult, TranscriptSegment
from inkwell.utils.datetime import now_utc


class TestTranscriptSegment:
    """Tests for TranscriptSegment model."""

    def test_create_segment(self):
        """Test creating a basic segment."""
        segment = TranscriptSegment(
            text="Hello world",
            start=0.0,
            duration=2.0,
        )

        assert segment.text == "Hello world"
        assert segment.start == 0.0
        assert segment.duration == 2.0
        assert segment.end == 2.0

    def test_segment_end_calculation(self):
        """Test that end time is calculated correctly."""
        segment = TranscriptSegment(text="Test", start=5.5, duration=3.2)
        assert segment.end == 8.7

    def test_segment_string_format(self):
        """Test string formatting with timestamp."""
        segment = TranscriptSegment(text="Hello", start=65.0, duration=2.0)
        assert str(segment) == "[01:05] Hello"

        segment2 = TranscriptSegment(text="World", start=3661.0, duration=1.0)
        assert str(segment2) == "[61:01] World"

    def test_contains_time(self):
        """Test checking if a time falls within segment."""
        segment = TranscriptSegment(text="Test", start=10.0, duration=5.0)

        assert segment.contains_time(10.0) is True
        assert segment.contains_time(12.5) is True
        assert segment.contains_time(14.9) is True
        assert segment.contains_time(15.0) is False  # End is exclusive
        assert segment.contains_time(9.9) is False
        assert segment.contains_time(15.1) is False

    def test_empty_text_validation(self):
        """Test that empty text is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            TranscriptSegment(text="", start=0.0, duration=1.0)

        errors = exc_info.value.errors()
        assert any("empty" in str(e["msg"]).lower() for e in errors)

    def test_whitespace_only_text_validation(self):
        """Test that whitespace-only text is rejected."""
        with pytest.raises(ValidationError):
            TranscriptSegment(text="   ", start=0.0, duration=1.0)

    def test_negative_start_rejected(self):
        """Test that negative start time is rejected."""
        with pytest.raises(ValidationError):
            TranscriptSegment(text="Test", start=-1.0, duration=1.0)

    def test_negative_duration_rejected(self):
        """Test that negative duration is rejected."""
        with pytest.raises(ValidationError):
            TranscriptSegment(text="Test", start=0.0, duration=-1.0)

    def test_zero_duration_allowed(self):
        """Test that zero duration is allowed (for instantaneous events)."""
        segment = TranscriptSegment(text="[Music]", start=5.0, duration=0.0)
        assert segment.duration == 0.0
        assert segment.end == 5.0


class TestTranscript:
    """Tests for Transcript model."""

    def test_create_empty_transcript(self):
        """Test creating a transcript with no segments."""
        transcript = Transcript(
            segments=[],
            source="youtube",
            episode_url="https://example.com/episode",
        )

        assert len(transcript.segments) == 0
        assert transcript.source == "youtube"
        assert transcript.full_text == ""
        assert transcript.total_duration == timedelta(0)

    def test_create_transcript_with_segments(self):
        """Test creating a transcript with multiple segments."""
        segments = [
            TranscriptSegment(text="First", start=0.0, duration=2.0),
            TranscriptSegment(text="Second", start=2.0, duration=3.0),
            TranscriptSegment(text="Third", start=5.0, duration=1.5),
        ]

        transcript = Transcript(
            segments=segments,
            source="gemini",
            episode_url="https://example.com/episode",
            language="en",
        )

        assert len(transcript.segments) == 3
        assert transcript.segment_count == 3
        assert transcript.language == "en"

    def test_full_text_concatenation(self):
        """Test that full_text concatenates all segments."""
        segments = [
            TranscriptSegment(text="Hello", start=0.0, duration=1.0),
            TranscriptSegment(text="world", start=1.0, duration=1.0),
            TranscriptSegment(text="test", start=2.0, duration=1.0),
        ]

        transcript = Transcript(
            segments=segments,
            source="youtube",
            episode_url="https://example.com/episode",
        )

        assert transcript.full_text == "Hello world test"

    def test_total_duration_from_duration_seconds(self):
        """Test total_duration uses duration_seconds if available."""
        transcript = Transcript(
            segments=[TranscriptSegment(text="Test", start=0.0, duration=10.0)],
            source="youtube",
            episode_url="https://example.com/episode",
            duration_seconds=3600.0,
        )

        assert transcript.total_duration == timedelta(seconds=3600)

    def test_total_duration_from_segments(self):
        """Test total_duration calculates from last segment if duration_seconds not set."""
        segments = [
            TranscriptSegment(text="First", start=0.0, duration=10.0),
            TranscriptSegment(text="Last", start=10.0, duration=5.0),
        ]

        transcript = Transcript(
            segments=segments,
            source="youtube",
            episode_url="https://example.com/episode",
        )

        # Should be end of last segment: 10.0 + 5.0 = 15.0
        assert transcript.total_duration == timedelta(seconds=15.0)

    def test_get_segment_at_time(self):
        """Test retrieving segment at specific time."""
        segments = [
            TranscriptSegment(text="First", start=0.0, duration=10.0),
            TranscriptSegment(text="Second", start=10.0, duration=15.0),
            TranscriptSegment(text="Third", start=25.0, duration=5.0),
        ]

        transcript = Transcript(
            segments=segments,
            source="youtube",
            episode_url="https://example.com/episode",
        )

        # Test finding each segment
        seg1 = transcript.get_segment_at_time(5.0)
        assert seg1 is not None
        assert seg1.text == "First"

        seg2 = transcript.get_segment_at_time(15.0)
        assert seg2 is not None
        assert seg2.text == "Second"

        seg3 = transcript.get_segment_at_time(27.0)
        assert seg3 is not None
        assert seg3.text == "Third"

        # Test gap
        seg_none = transcript.get_segment_at_time(100.0)
        assert seg_none is None

    def test_get_segments_in_range(self):
        """Test retrieving segments in a time range."""
        segments = [
            TranscriptSegment(text="A", start=0.0, duration=5.0),
            TranscriptSegment(text="B", start=5.0, duration=5.0),
            TranscriptSegment(text="C", start=10.0, duration=5.0),
            TranscriptSegment(text="D", start=15.0, duration=5.0),
        ]

        transcript = Transcript(
            segments=segments,
            source="youtube",
            episode_url="https://example.com/episode",
        )

        # Get segments overlapping 7-12 range
        # Should include B (5-10) and C (10-15)
        result = transcript.get_segments_in_range(7.0, 12.0)
        assert len(result) == 2
        assert result[0].text == "B"
        assert result[1].text == "C"

    def test_calculate_word_count(self):
        """Test word count calculation."""
        segments = [
            TranscriptSegment(text="Hello world", start=0.0, duration=1.0),
            TranscriptSegment(text="This is a test", start=1.0, duration=1.0),
            TranscriptSegment(text="Final segment", start=2.0, duration=1.0),
        ]

        transcript = Transcript(
            segments=segments,
            source="youtube",
            episode_url="https://example.com/episode",
        )

        # 2 + 4 + 2 = 8 words
        assert transcript.calculate_word_count() == 8

    def test_word_count_auto_calculated(self):
        """Test that word_count is calculated if not provided."""
        segments = [
            TranscriptSegment(text="One two three", start=0.0, duration=1.0),
        ]

        transcript = Transcript(
            segments=segments,
            source="youtube",
            episode_url="https://example.com/episode",
        )

        # Should be auto-calculated
        assert transcript.word_count == 3

    def test_segments_auto_sorted(self):
        """Test that segments are sorted by start time."""
        # Create segments out of order
        segments = [
            TranscriptSegment(text="Third", start=20.0, duration=5.0),
            TranscriptSegment(text="First", start=0.0, duration=5.0),
            TranscriptSegment(text="Second", start=10.0, duration=5.0),
        ]

        transcript = Transcript(
            segments=segments,
            source="youtube",
            episode_url="https://example.com/episode",
        )

        # Should be sorted
        assert transcript.segments[0].text == "First"
        assert transcript.segments[1].text == "Second"
        assert transcript.segments[2].text == "Third"

    def test_is_cached_property(self):
        """Test is_cached property."""
        cached = Transcript(
            segments=[],
            source="cached",
            episode_url="https://example.com/episode",
        )
        assert cached.is_cached is True

        not_cached = Transcript(
            segments=[],
            source="youtube",
            episode_url="https://example.com/episode",
        )
        assert not_cached.is_cached is False

    def test_is_free_property(self):
        """Test is_free property."""
        youtube = Transcript(
            segments=[],
            source="youtube",
            episode_url="https://example.com/episode",
        )
        assert youtube.is_free is True

        cached = Transcript(
            segments=[],
            source="cached",
            episode_url="https://example.com/episode",
        )
        assert cached.is_free is True

        gemini = Transcript(
            segments=[],
            source="gemini",
            episode_url="https://example.com/episode",
        )
        assert gemini.is_free is False

    def test_cost_tracking(self):
        """Test cost tracking for paid transcriptions."""
        transcript = Transcript(
            segments=[],
            source="gemini",
            episode_url="https://example.com/episode",
            cost_usd=0.60,
        )

        assert transcript.cost_usd == 0.60
        assert transcript.is_free is False

    def test_created_at_defaults_to_now(self):
        """Test that created_at defaults to current time."""
        before = now_utc()
        transcript = Transcript(
            segments=[],
            source="youtube",
            episode_url="https://example.com/episode",
        )
        after = now_utc()

        assert before <= transcript.created_at <= after

    def test_model_serialization(self):
        """Test that model can be serialized to dict/JSON."""
        segment = TranscriptSegment(text="Test", start=0.0, duration=1.0)
        transcript = Transcript(
            segments=[segment],
            source="youtube",
            episode_url="https://example.com/episode",
            language="en",
        )

        # Serialize to dict
        data = transcript.model_dump()
        assert data["source"] == "youtube"
        assert data["language"] == "en"
        assert len(data["segments"]) == 1

        # Serialize to JSON
        json_str = transcript.model_dump_json()
        assert "youtube" in json_str
        assert "Test" in json_str


class TestTranscriptionResult:
    """Tests for TranscriptionResult model."""

    def test_successful_result(self):
        """Test creating a successful transcription result."""
        transcript = Transcript(
            segments=[TranscriptSegment(text="Test", start=0.0, duration=1.0)],
            source="youtube",
            episode_url="https://example.com/episode",
        )

        result = TranscriptionResult(
            success=True,
            transcript=transcript,
            attempts=["youtube"],
            duration_seconds=2.5,
        )

        assert result.success is True
        assert result.transcript is not None
        assert result.error is None
        assert result.attempts == ["youtube"]
        assert result.duration_seconds == 2.5

    def test_failed_result(self):
        """Test creating a failed transcription result."""
        result = TranscriptionResult(
            success=False,
            error="Transcription failed: 403 Forbidden",
            attempts=["youtube_failed", "gemini_failed"],
        )

        assert result.success is False
        assert result.transcript is None
        assert result.error is not None
        assert "403" in result.error

    def test_success_requires_transcript(self):
        """Test that success=True requires a transcript."""
        with pytest.raises(ValidationError) as exc_info:
            TranscriptionResult(
                success=True,
                transcript=None,  # Missing!
                attempts=["youtube"],
            )

        errors = exc_info.value.errors()
        assert any("transcript" in str(e["msg"]).lower() for e in errors)

    def test_failure_requires_error(self):
        """Test that success=False requires an error message."""
        with pytest.raises(ValidationError) as exc_info:
            TranscriptionResult(
                success=False,
                error=None,  # Missing!
                attempts=["youtube"],
            )

        errors = exc_info.value.errors()
        assert any("error" in str(e["msg"]).lower() for e in errors)

    def test_primary_source_property(self):
        """Test primary_source property."""
        transcript = Transcript(
            segments=[],
            source="gemini",
            episode_url="https://example.com/episode",
        )

        result = TranscriptionResult(
            success=True,
            transcript=transcript,
            attempts=["youtube_failed", "gemini"],
        )

        assert result.primary_source == "gemini"

    def test_primary_source_none_on_failure(self):
        """Test that primary_source is None on failure."""
        result = TranscriptionResult(
            success=False,
            error="Failed",
            attempts=["youtube_failed"],
        )

        assert result.primary_source is None

    def test_had_fallback_property(self):
        """Test had_fallback property."""
        # No fallback (first attempt succeeded)
        result1 = TranscriptionResult(
            success=True,
            transcript=Transcript(
                segments=[],
                source="youtube",
                episode_url="https://example.com/episode",
            ),
            attempts=["youtube"],
        )
        assert result1.had_fallback is False

        # Had fallback (second attempt succeeded)
        result2 = TranscriptionResult(
            success=True,
            transcript=Transcript(
                segments=[],
                source="gemini",
                episode_url="https://example.com/episode",
            ),
            attempts=["youtube_failed", "gemini"],
        )
        assert result2.had_fallback is True

    def test_from_cache_property(self):
        """Test from_cache tracking."""
        result = TranscriptionResult(
            success=True,
            transcript=Transcript(
                segments=[],
                source="cached",
                episode_url="https://example.com/episode",
            ),
            attempts=["cache"],
            from_cache=True,
        )

        assert result.from_cache is True

    def test_cost_tracking(self):
        """Test cost tracking in result."""
        result = TranscriptionResult(
            success=True,
            transcript=Transcript(
                segments=[],
                source="gemini",
                episode_url="https://example.com/episode",
                cost_usd=0.60,
            ),
            attempts=["youtube_failed", "gemini"],
            cost_usd=0.60,
        )

        assert result.cost_usd == 0.60

    def test_cost_saved_by_cache(self):
        """Test cost_saved_by_cache calculation."""
        # Cache hit - cost saved
        cached_result = TranscriptionResult(
            success=True,
            transcript=Transcript(
                segments=[],
                source="cached",
                episode_url="https://example.com/episode",
                cost_usd=0.60,
            ),
            attempts=["cache"],
            from_cache=True,
        )
        assert cached_result.cost_saved_by_cache == 0.60

        # Not from cache - no savings
        fresh_result = TranscriptionResult(
            success=True,
            transcript=Transcript(
                segments=[],
                source="gemini",
                episode_url="https://example.com/episode",
                cost_usd=0.60,
            ),
            attempts=["gemini"],
            from_cache=False,
        )
        assert fresh_result.cost_saved_by_cache == 0.0

    def test_negative_cost_rejected(self):
        """Test that negative costs are rejected."""
        with pytest.raises(ValidationError):
            TranscriptionResult(
                success=False,
                error="Failed",
                attempts=[],
                cost_usd=-1.0,
            )

    def test_negative_duration_rejected(self):
        """Test that negative duration is rejected."""
        with pytest.raises(ValidationError):
            TranscriptionResult(
                success=False,
                error="Failed",
                attempts=[],
                duration_seconds=-1.0,
            )
