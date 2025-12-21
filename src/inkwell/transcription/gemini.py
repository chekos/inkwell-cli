"""Gemini-based audio transcription using modern google-genai SDK."""

import asyncio
import os
from collections.abc import Callable
from pathlib import Path

from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from inkwell.transcription.models import Transcript, TranscriptSegment
from inkwell.utils.errors import APIError
from inkwell.utils.rate_limiter import get_rate_limiter

# Allowed Gemini models for transcription
ALLOWED_GEMINI_MODELS = {
    "gemini-2.5-flash",
    "gemini-2.5-pro",
    "gemini-1.5-flash",
    "gemini-1.5-pro",
}


class CostEstimate(BaseModel):
    """Cost estimate for Gemini transcription."""

    file_size_mb: float = Field(..., ge=0, description="Audio file size in MB")
    estimated_cost_usd: float = Field(..., ge=0, description="Estimated cost in USD")
    rate_per_mb: float = Field(default=0.000125, description="Rate per MB ($0.000125)")

    @property
    def formatted_cost(self) -> str:
        """Format cost for display."""
        if self.estimated_cost_usd < 0.01:
            return f"${self.estimated_cost_usd:.4f}"
        return f"${self.estimated_cost_usd:.2f}"


class GeminiTranscriber:
    """Transcribe audio files using Google Gemini API.

    Uses Gemini 2.5 Flash for cost-effective audio transcription.
    Supports automatic file upload for large files (>10MB).
    Implements cost estimation per ADR-012.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model_name: str = "gemini-2.5-flash",
        cost_threshold_usd: float = 1.0,
        cost_confirmation_callback: Callable[[CostEstimate], bool] | None = None,
    ):
        """Initialize Gemini transcriber.

        Args:
            api_key: Google AI API key (default: GOOGLE_API_KEY env var)
            model_name: Gemini model to use (default: gemini-2.5-flash)
            cost_threshold_usd: Threshold for cost confirmation (default: $1.00)
            cost_confirmation_callback: Callback for cost confirmation (default: auto-approve)
        """
        # Get API key from parameter or environment
        # Try GOOGLE_API_KEY first (standard), then GOOGLE_AI_API_KEY (deprecated)
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY") or os.getenv("GOOGLE_AI_API_KEY")

        # Warn if using deprecated env var
        if os.getenv("GOOGLE_AI_API_KEY") and not os.getenv("GOOGLE_API_KEY"):
            import logging

            logger = logging.getLogger(__name__)
            logger.warning(
                "GOOGLE_AI_API_KEY is deprecated. Please use GOOGLE_API_KEY instead. "
                "GOOGLE_AI_API_KEY will be removed in v2.0.0"
            )

        if not self.api_key:
            raise ValueError(
                "Google AI API key required. "
                "Provide via api_key parameter or GOOGLE_API_KEY environment variable."
            )

        # Validate model name
        if model_name not in ALLOWED_GEMINI_MODELS:
            raise ValueError(
                f"Invalid model name '{model_name}'. "
                f"Allowed models: {', '.join(sorted(ALLOWED_GEMINI_MODELS))}"
            )

        # Initialize client with new SDK
        self.client = genai.Client(api_key=self.api_key)

        self.model_name = model_name
        self.cost_threshold_usd = cost_threshold_usd
        self.cost_confirmation_callback = cost_confirmation_callback

    async def can_transcribe(self, audio_path: Path) -> bool:
        """Check if this transcriber can handle the audio file.

        Args:
            audio_path: Path to audio file

        Returns:
            True if file exists and is supported format
        """
        if not audio_path.exists():
            return False

        # Gemini supports common audio formats
        supported_extensions = {".mp3", ".m4a", ".wav", ".aac", ".ogg", ".flac"}
        return audio_path.suffix.lower() in supported_extensions

    def _estimate_cost(self, audio_path: Path) -> CostEstimate:
        """Estimate transcription cost based on file size.

        Args:
            audio_path: Path to audio file

        Returns:
            Cost estimate
        """
        file_size_bytes = audio_path.stat().st_size
        file_size_mb = file_size_bytes / (1024 * 1024)

        # Gemini pricing: ~$0.000125 per MB for audio
        # (This is approximate - actual pricing may vary)
        rate_per_mb = 0.000125
        estimated_cost = file_size_mb * rate_per_mb

        return CostEstimate(
            file_size_mb=file_size_mb,
            estimated_cost_usd=estimated_cost,
            rate_per_mb=rate_per_mb,
        )

    async def _confirm_cost(self, estimate: CostEstimate) -> bool:
        """Confirm cost with user if above threshold.

        Args:
            estimate: Cost estimate

        Returns:
            True if approved, False if rejected
        """
        # Auto-approve if below threshold
        if estimate.estimated_cost_usd < self.cost_threshold_usd:
            return True

        # If callback provided, use it
        if self.cost_confirmation_callback:
            # Run callback in executor to avoid blocking
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, self.cost_confirmation_callback, estimate)

        # Default: auto-approve
        return True

    async def transcribe(self, audio_path: Path, episode_url: str | None = None) -> Transcript:
        """Transcribe audio file using Gemini.

        Args:
            audio_path: Path to audio file
            episode_url: Optional URL of original episode (for metadata)

        Returns:
            Transcript object

        Raises:
            TranscriptionError: If transcription fails
        """
        # Validate file exists
        if not audio_path.exists():
            raise APIError(f"Audio file not found: {audio_path}")

        # Check format support
        if not await self.can_transcribe(audio_path):
            raise APIError(
                f"Unsupported audio format: {audio_path.suffix}. "
                f"Supported formats: MP3, M4A, WAV, AAC, OGG, FLAC"
            )

        # Estimate cost
        estimate = self._estimate_cost(audio_path)

        # Confirm cost if above threshold
        if not await self._confirm_cost(estimate):
            raise APIError(
                f"Transcription cancelled. Estimated cost: {estimate.formatted_cost} "
                f"(threshold: ${self.cost_threshold_usd:.2f})"
            )

        try:
            # Upload file and generate transcript
            response = await asyncio.to_thread(self._transcribe_sync, audio_path)

            # Parse response to transcript
            transcript = self._parse_response(response, audio_path, episode_url)

            # Add cost metadata
            transcript.cost_usd = estimate.estimated_cost_usd

            return transcript

        except Exception as e:
            raise APIError(
                f"Failed to transcribe audio with Gemini. "
                f"This may be due to API errors, network issues, or file format problems. "
                f"Error: {e}"
            ) from e

    def _transcribe_sync(self, audio_path: Path) -> types.GenerateContentResponse:
        """Synchronous transcription for thread pool execution.

        Args:
            audio_path: Path to audio file

        Returns:
            Gemini API response
        """
        # Apply rate limiting before API call
        limiter = get_rate_limiter("gemini")
        limiter.acquire()

        # Upload audio file using new SDK
        audio_file = self.client.files.upload(file=audio_path)

        # Generate transcript with structured prompt
        prompt = (
            "Please transcribe this audio file. "
            "Provide the transcript with timestamps in the following format:\n\n"
            "[00:00:00] Speaker: Text\n"
            "[00:00:05] Speaker: More text\n\n"
            "If you cannot determine speaker names, use 'Speaker 1', 'Speaker 2', etc. "
            "Be as accurate as possible with timestamps."
        )

        response = self.client.models.generate_content(
            model=self.model_name,
            contents=[audio_file, prompt],
        )

        return response

    def _parse_response(
        self, response: types.GenerateContentResponse, audio_path: Path, episode_url: str | None
    ) -> Transcript:
        """Parse Gemini response into Transcript object.

        Args:
            response: Gemini API response
            audio_path: Path to audio file (for metadata)
            episode_url: Optional episode URL

        Returns:
            Transcript object
        """
        if not response.text:
            raise APIError("Gemini returned empty transcript")

        # Parse transcript text into segments
        # Gemini doesn't provide native segment timestamps, so we create one large segment
        # (Future enhancement: parse timestamp markers from response)
        segments = [
            TranscriptSegment(
                text=response.text.strip(),
                start=0.0,
                duration=0.0,  # Unknown duration
            )
        ]

        return Transcript(
            segments=segments,
            source="gemini",
            language="en",  # Gemini auto-detects, defaulting to English
            episode_url=episode_url or str(audio_path),
        )


class GeminiTranscriberWithSegments(GeminiTranscriber):
    """Enhanced Gemini transcriber that attempts to parse timestamps.

    Extends base GeminiTranscriber to parse timestamp markers from response.
    Falls back to single segment if parsing fails.
    """

    def _parse_response(
        self, response: types.GenerateContentResponse, audio_path: Path, episode_url: str | None
    ) -> Transcript:
        """Parse Gemini response with timestamp extraction.

        Args:
            response: Gemini API response
            audio_path: Path to audio file
            episode_url: Optional episode URL

        Returns:
            Transcript with parsed segments if possible
        """
        if not response.text:
            raise APIError("Gemini returned empty transcript")

        # Try to parse timestamp markers like [00:00:00] or [0:00]
        segments = self._parse_timestamps(response.text)

        # Fall back to single segment if parsing fails
        if not segments:
            segments = [
                TranscriptSegment(
                    text=response.text.strip(),
                    start=0.0,
                    duration=0.0,
                )
            ]

        return Transcript(
            segments=segments,
            source="gemini",
            language="en",
            episode_url=episode_url or str(audio_path),
        )

    def _parse_timestamps(self, text: str) -> list[TranscriptSegment]:
        """Parse timestamp markers from transcript text.

        Args:
            text: Transcript text with potential timestamp markers

        Returns:
            List of segments (empty if parsing fails)
        """
        import re

        # Pattern: [HH:MM:SS] or [H:MM:SS] or [MM:SS] or [M:SS]
        timestamp_pattern = r"\[(\d{1,2}):(\d{2})(?::(\d{2}))?\]"

        segments: list[TranscriptSegment] = []
        lines = text.split("\n")

        current_time = 0.0
        current_text_parts: list[str] = []

        for line in lines:
            match = re.match(timestamp_pattern, line)

            if match:
                # Save previous segment if we have text
                if current_text_parts:
                    segments.append(
                        TranscriptSegment(
                            text=" ".join(current_text_parts).strip(),
                            start=current_time,
                            duration=0.0,  # Will calculate after parsing all
                        )
                    )
                    current_text_parts = []

                # Parse new timestamp
                hours_or_mins = int(match.group(1))
                mins_or_secs = int(match.group(2))
                secs = int(match.group(3)) if match.group(3) is not None else None

                # Determine if format is HH:MM:SS or MM:SS
                if secs is not None:  # HH:MM:SS format
                    current_time = hours_or_mins * 3600 + mins_or_secs * 60 + secs
                else:  # MM:SS format
                    current_time = hours_or_mins * 60 + mins_or_secs

                # Get text after timestamp
                text_after_timestamp = line[match.end() :].strip()
                # Remove "Speaker:" prefix if present
                text_after_timestamp = re.sub(
                    r"^[Ss]peaker\s*\d*\s*:?\s*", "", text_after_timestamp
                )
                if text_after_timestamp:
                    current_text_parts.append(text_after_timestamp)
            else:
                # No timestamp - accumulate text
                if line.strip():
                    current_text_parts.append(line.strip())

        # Add final segment
        if current_text_parts:
            segments.append(
                TranscriptSegment(
                    text=" ".join(current_text_parts).strip(),
                    start=current_time,
                    duration=0.0,
                )
            )

        # Calculate durations (difference between consecutive timestamps)
        for i in range(len(segments) - 1):
            segments[i].duration = segments[i + 1].start - segments[i].start

        return segments if segments else []
