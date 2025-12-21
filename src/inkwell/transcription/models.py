"""Data models for transcription.

This module defines Pydantic models for representing podcast transcripts,
including individual segments with timing information and complete transcripts.
"""

from datetime import datetime, timedelta
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from inkwell.utils.datetime import now_utc


class TranscriptSegment(BaseModel):
    """Single segment of transcript with timing information.

    Represents a continuous piece of text with start time and duration.
    Typically corresponds to a sentence or phrase in the transcript.
    """

    text: str = Field(..., description="The transcript text for this segment")
    start: float = Field(..., ge=0, description="Start time in seconds from beginning")
    duration: float = Field(..., ge=0, description="Duration of segment in seconds")

    @property
    def end(self) -> float:
        """Calculate end time of segment."""
        return self.start + self.duration

    def __str__(self) -> str:
        """Format segment as '[MM:SS] text' for display."""
        minutes, seconds = divmod(int(self.start), 60)
        return f"[{minutes:02d}:{seconds:02d}] {self.text}"

    def contains_time(self, time_seconds: float) -> bool:
        """Check if a given time falls within this segment.

        Args:
            time_seconds: Time in seconds to check

        Returns:
            True if the time is within this segment's range
        """
        return self.start <= time_seconds < self.end

    @field_validator("text")
    @classmethod
    def text_not_empty(cls, v: str) -> str:
        """Validate that text is not empty."""
        if not v or not v.strip():
            raise ValueError("Segment text cannot be empty")
        return v


class Transcript(BaseModel):
    """Complete transcript for a podcast episode.

    Contains all segments, metadata, and helper methods for working with
    the transcript data.
    """

    segments: list[TranscriptSegment] = Field(
        default_factory=list, description="List of transcript segments with timing"
    )
    source: Literal["youtube", "gemini", "cached"] = Field(
        ..., description="Source of the transcript"
    )
    language: str = Field(default="en", description="Language code (ISO 639-1)")
    episode_url: str = Field(..., description="URL of the episode that was transcribed")
    created_at: datetime = Field(
        default_factory=now_utc,
        description="When this transcript was created",
    )

    # Optional metadata
    duration_seconds: float | None = Field(
        None, ge=0, description="Total duration of audio in seconds"
    )
    word_count: int | None = Field(None, ge=0, description="Total word count in transcript")
    cost_usd: float | None = Field(
        None, ge=0, description="Cost in USD for this transcription (if applicable)"
    )

    @property
    def full_text(self) -> str:
        """Concatenate all segments into single text string.

        Returns:
            Complete transcript text with spaces between segments
        """
        return " ".join(seg.text for seg in self.segments)

    @property
    def total_duration(self) -> timedelta:
        """Calculate total duration of transcript.

        Returns from duration_seconds if available, otherwise calculates
        from last segment's end time.

        Returns:
            Total duration as timedelta
        """
        if self.duration_seconds is not None:
            return timedelta(seconds=self.duration_seconds)

        if self.segments:
            last_segment = self.segments[-1]
            return timedelta(seconds=last_segment.end)

        return timedelta(0)

    @property
    def segment_count(self) -> int:
        """Get number of segments in transcript."""
        return len(self.segments)

    @property
    def is_cached(self) -> bool:
        """Check if this transcript came from cache."""
        return self.source == "cached"

    @property
    def is_free(self) -> bool:
        """Check if this transcript was free (YouTube) or cost money (Gemini)."""
        return self.source in ("youtube", "cached")

    def get_segment_at_time(self, time_seconds: float) -> TranscriptSegment | None:
        """Get segment containing a specific timestamp.

        Args:
            time_seconds: Time in seconds to look up

        Returns:
            TranscriptSegment if found, None otherwise
        """
        for segment in self.segments:
            if segment.contains_time(time_seconds):
                return segment
        return None

    def get_segments_in_range(
        self, start_seconds: float, end_seconds: float
    ) -> list[TranscriptSegment]:
        """Get all segments that overlap with a time range.

        Args:
            start_seconds: Start of time range
            end_seconds: End of time range

        Returns:
            List of segments that overlap the range
        """
        result = []
        for segment in self.segments:
            # Segment overlaps if it starts before range ends and ends after range starts
            if segment.start < end_seconds and segment.end > start_seconds:
                result.append(segment)
        return result

    def calculate_word_count(self) -> int:
        """Calculate word count from all segments.

        Returns:
            Total number of words in transcript
        """
        return sum(len(seg.text.split()) for seg in self.segments)

    @field_validator("segments")
    @classmethod
    def segments_sorted(cls, v: list[TranscriptSegment]) -> list[TranscriptSegment]:
        """Ensure segments are sorted by start time."""
        if not v:
            return v

        # Check if sorted
        for i in range(len(v) - 1):
            if v[i].start > v[i + 1].start:
                # Not sorted, sort them
                return sorted(v, key=lambda seg: seg.start)

        return v

    def model_post_init(self, __context: Any) -> None:
        """Post-initialization hook to calculate optional fields."""
        # Calculate word count if not provided
        if self.word_count is None and self.segments:
            self.word_count = self.calculate_word_count()

        # Calculate duration if not provided
        if self.duration_seconds is None and self.segments:
            self.duration_seconds = self.segments[-1].end


class TranscriptionResult(BaseModel):
    """Result of a transcription operation.

    Contains the transcript (if successful), error information (if failed),
    and metadata about the operation.
    """

    success: bool = Field(..., description="Whether transcription succeeded")
    transcript: Transcript | None = Field(None, description="The transcript if successful")
    error: str | None = Field(None, description="Error message if failed")
    attempts: list[str] = Field(
        default_factory=list,
        description="List of transcription methods attempted (e.g., ['youtube', 'gemini'])",
    )

    # Operation metadata
    duration_seconds: float = Field(
        default=0.0, ge=0, description="Time taken for transcription operation"
    )
    cost_usd: float = Field(default=0.0, ge=0, description="Cost in USD for this operation")
    from_cache: bool = Field(default=False, description="Whether result came from cache")

    @field_validator("transcript")
    @classmethod
    def transcript_required_if_success(cls, v: Transcript | None, info: Any) -> Transcript | None:
        """Validate that transcript is provided if success is True."""
        if info.data.get("success") and v is None:
            raise ValueError("transcript is required when success is True")
        return v

    @field_validator("error")
    @classmethod
    def error_required_if_failure(cls, v: str | None, info: Any) -> str | None:
        """Validate that error is provided if success is False."""
        if not info.data.get("success") and not v:
            raise ValueError("error message is required when success is False")
        return v

    @property
    def primary_source(self) -> str | None:
        """Get the primary source that succeeded.

        Returns:
            Source name (e.g., 'youtube', 'gemini') or None if failed
        """
        if self.success and self.transcript:
            return self.transcript.source
        return None

    @property
    def had_fallback(self) -> bool:
        """Check if fallback was needed.

        Returns:
            True if more than one method was attempted
        """
        return len(self.attempts) > 1

    @property
    def cost_saved_by_cache(self) -> float:
        """Calculate cost saved by using cache.

        Returns:
            Cost in USD that would have been charged without cache
        """
        if self.from_cache and self.transcript and self.transcript.cost_usd:
            return self.transcript.cost_usd
        return 0.0
