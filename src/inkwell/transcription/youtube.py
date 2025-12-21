"""YouTube transcript extraction.

This module provides functionality to extract existing transcripts from
YouTube videos using the youtube-transcript-api library.
"""

import logging
import re
from urllib.parse import parse_qs, urlparse

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    CouldNotRetrieveTranscript,
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
)

from inkwell.transcription.models import Transcript, TranscriptSegment
from inkwell.utils.errors import APIError

logger = logging.getLogger(__name__)


class TranscriptionError(APIError):
    """Error during transcription process."""

    pass


class YouTubeTranscriber:
    """Extract transcripts from YouTube videos.

    This is the primary (Tier 1) transcription method in our multi-tier
    strategy. It attempts to fetch existing transcripts from YouTube,
    which is free and fast when available.

    Usage:
        transcriber = YouTubeTranscriber()
        if await transcriber.can_transcribe(url):
            transcript = await transcriber.transcribe(url)
    """

    def __init__(self, preferred_languages: list[str] | None = None):
        """Initialize YouTube transcriber.

        Args:
            preferred_languages: List of language codes in preference order.
                                Defaults to ["en"].
        """
        self.preferred_languages = preferred_languages or ["en"]
        self.api = YouTubeTranscriptApi()

    async def can_transcribe(self, url: str) -> bool:
        """Check if URL is a YouTube video.

        Args:
            url: Episode URL to check

        Returns:
            True if URL is from YouTube, False otherwise
        """
        return self._is_youtube_url(url)

    def _is_youtube_url(self, url: str) -> bool:
        """Detect if URL is from YouTube.

        Supports various YouTube URL formats:
        - https://www.youtube.com/watch?v=VIDEO_ID
        - https://youtu.be/VIDEO_ID
        - https://youtube.com/embed/VIDEO_ID
        - https://m.youtube.com/watch?v=VIDEO_ID

        Args:
            url: URL to check

        Returns:
            True if YouTube URL, False otherwise
        """
        patterns = [
            r"youtube\.com/watch",
            r"youtu\.be/",
            r"youtube\.com/embed/",
            r"m\.youtube\.com/watch",
        ]
        return any(re.search(pattern, url, re.IGNORECASE) for pattern in patterns)

    def _extract_video_id(self, url: str) -> str | None:
        """Extract video ID from various YouTube URL formats.

        Args:
            url: YouTube URL

        Returns:
            Video ID if found, None otherwise

        Examples:
            >>> transcriber._extract_video_id("https://youtube.com/watch?v=abc123")
            'abc123'
            >>> transcriber._extract_video_id("https://youtu.be/xyz789")
            'xyz789'
        """
        # Parse URL
        parsed = urlparse(url)

        # Format: youtube.com/watch?v=VIDEO_ID
        if "youtube.com" in parsed.netloc and "/watch" in parsed.path:
            query = parse_qs(parsed.query)
            if "v" in query and query["v"]:
                return query["v"][0]

        # Format: youtu.be/VIDEO_ID
        if "youtu.be" in parsed.netloc:
            # Path is /VIDEO_ID
            video_id = parsed.path.strip("/")
            if video_id:
                return video_id

        # Format: youtube.com/embed/VIDEO_ID
        embed_match = re.search(r"youtube\.com/embed/([^/?]+)", url)
        if embed_match:
            return embed_match.group(1)

        return None

    async def transcribe(self, url: str, audio_path: str | None = None) -> Transcript:
        """Fetch transcript from YouTube.

        Args:
            url: YouTube video URL
            audio_path: Not used for YouTube transcription (required by interface)

        Returns:
            Transcript object with segments and metadata

        Raises:
            TranscriptionError: If transcript cannot be retrieved
        """
        # Extract video ID
        video_id = self._extract_video_id(url)
        if not video_id:
            raise APIError(
                f"Could not extract video ID from URL: {url}. "
                "Supported formats: youtube.com/watch?v=..., youtu.be/..., "
                "youtube.com/embed/..."
            )

        logger.info(f"Fetching YouTube transcript for video: {video_id}")

        try:
            # List available transcripts
            transcript_list = self.api.list(video_id)

            # Try to find transcript in preferred languages
            transcript_obj = None
            for lang in self.preferred_languages:
                try:
                    transcript_obj = transcript_list.find_transcript([lang])
                    logger.info(f"Found transcript in language: {lang}")
                    break
                except NoTranscriptFound:
                    continue

            # If no preferred language found, try generated transcript
            if transcript_obj is None:
                try:
                    transcript_obj = transcript_list.find_generated_transcript(
                        self.preferred_languages
                    )
                    logger.info("Using auto-generated transcript")
                except NoTranscriptFound as e:
                    raise APIError(
                        f"No transcript found for video {video_id} in languages: "
                        f"{', '.join(self.preferred_languages)}. "
                        "Available languages: "
                        f"{', '.join(t.language_code for t in transcript_list)}"
                    ) from e

            # Fetch transcript data
            transcript_data = transcript_obj.fetch()

            # Convert to our model
            segments = [
                TranscriptSegment(
                    text=entry["text"],
                    start=entry["start"],
                    duration=entry["duration"],
                )
                for entry in transcript_data
            ]

            logger.info(f"Successfully fetched YouTube transcript: {len(segments)} segments")

            return Transcript(
                segments=segments,
                source="youtube",
                language=transcript_obj.language_code,
                episode_url=url,
            )

        except TranscriptsDisabled as e:
            logger.warning(f"Transcripts disabled for video {video_id}")
            raise APIError(
                "Transcripts are disabled for this video. "
                "The video owner has disabled transcript access."
            ) from e

        except VideoUnavailable as e:
            logger.warning(f"Video unavailable: {video_id}")
            raise APIError(
                "Video is unavailable. It may be private, deleted, or region-restricted."
            ) from e

        except CouldNotRetrieveTranscript as e:
            # This includes 403 errors and other network issues
            logger.warning(f"Could not retrieve transcript for {video_id}: {e}")
            raise APIError(
                "Failed to retrieve transcript from YouTube. "
                "This may be due to network issues, rate limiting, or access restrictions. "
                "Will fall back to audio download + Gemini transcription."
            ) from e

        except Exception as e:
            logger.error(f"Unexpected error fetching YouTube transcript: {e}")
            raise APIError(f"Unexpected error while fetching transcript: {e}") from e

    def estimate_cost(self, duration_seconds: float) -> float:
        """Estimate transcription cost.

        YouTube transcripts are always free.

        Args:
            duration_seconds: Duration of audio (not used)

        Returns:
            0.0 (YouTube transcripts are free)
        """
        return 0.0
