"""YouTube transcript extraction.

This module provides functionality to extract existing transcripts from
YouTube videos using the youtube-transcript-api library.
"""

import logging
import re
import warnings
from typing import TYPE_CHECKING, Any, ClassVar
from urllib.parse import parse_qs, urlparse

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    CouldNotRetrieveTranscript,
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
)

from inkwell.plugins.types.transcription import TranscriptionPlugin, TranscriptionRequest
from inkwell.transcription.models import Transcript, TranscriptSegment
from inkwell.utils.errors import APIError

if TYPE_CHECKING:
    from inkwell.utils.costs import CostTracker

logger = logging.getLogger(__name__)


class TranscriptionError(APIError):
    """Error during transcription process."""

    pass


class YouTubeTranscriber(TranscriptionPlugin):
    """Extract transcripts from YouTube videos.

    This is the primary (Tier 1) transcription method in our multi-tier
    strategy. It attempts to fetch existing transcripts from YouTube,
    which is free and fast when available.

    Usage:
        transcriber = YouTubeTranscriber()
        if await transcriber.can_transcribe(url):
            transcript = await transcriber.transcribe(url)

        # Or via plugin system:
        request = TranscriptionRequest(url="https://youtube.com/watch?v=abc123")
        if transcriber.can_handle(request):
            transcript = await transcriber.transcribe(request)
    """

    # Plugin metadata (required by TranscriptionPlugin)
    NAME: ClassVar[str] = "youtube"
    VERSION: ClassVar[str] = "1.0.0"
    DESCRIPTION: ClassVar[str] = "YouTube transcript extraction (free, fast)"

    # Transcription-specific metadata
    HANDLES_URLS: ClassVar[list[str]] = ["youtube.com", "youtu.be", "m.youtube.com"]
    CAPABILITIES: ClassVar[dict[str, Any]] = {
        "formats": [],  # YouTube handles its own formats
        "max_duration_hours": None,
        "requires_internet": True,
        "supports_file": False,
        "supports_url": True,
        "supports_bytes": False,
    }

    def __init__(
        self,
        preferred_languages: list[str] | None = None,
        lazy_init: bool = False,
    ):
        """Initialize YouTube transcriber.

        Args:
            preferred_languages: List of language codes in preference order.
                                Defaults to ["en"].
            lazy_init: If True, defer API initialization until configure() is called.
                      Used by plugin system. Default: False for backward compatibility.
        """
        TranscriptionPlugin.__init__(self)
        self._preferred_languages_param = preferred_languages
        self._lazy_init = lazy_init

        if not lazy_init:
            # Immediate initialization for backward compatibility
            self._initialize_api(preferred_languages)

    def _initialize_api(self, preferred_languages: list[str] | None = None) -> None:
        """Initialize the YouTube API client.

        Args:
            preferred_languages: List of language codes in preference order.
        """
        self.preferred_languages = preferred_languages or ["en"]
        self.api = YouTubeTranscriptApi()

    def configure(
        self,
        config: dict[str, Any],
        cost_tracker: "CostTracker | None" = None,
    ) -> None:
        """Configure the plugin.

        Args:
            config: Plugin configuration (may include 'preferred_languages')
            cost_tracker: Optional cost tracker (not used for YouTube)
        """
        super().configure(config, cost_tracker)

        preferred_languages = config.get("preferred_languages", self._preferred_languages_param)
        self._initialize_api(preferred_languages)

    async def can_transcribe(self, url: str) -> bool:
        """Check if URL is a YouTube video.

        This is the legacy interface. For new code, use can_handle() with
        a TranscriptionRequest.

        Args:
            url: Episode URL to check

        Returns:
            True if URL is from YouTube, False otherwise
        """
        return self._is_youtube_url(url)

    def can_handle(self, request: TranscriptionRequest) -> bool:
        """Check if this plugin can handle the given request.

        YouTube transcriber only handles URLs from YouTube domains.

        Args:
            request: The transcription request to check

        Returns:
            True if this is a YouTube URL
        """
        # Only handle URL-based requests
        if request.source_type != "url" or request.url is None:
            return False
        return self._is_youtube_url(request.url)

    def _is_youtube_url(self, url: str) -> bool:
        """Detect if URL is from YouTube.

        Supports various YouTube URL formats:
        - https://www.youtube.com/watch?v=VIDEO_ID
        - https://youtu.be/VIDEO_ID
        - https://youtube.com/embed/VIDEO_ID
        - https://m.youtube.com/watch?v=VIDEO_ID
        - https://www.youtube.com/shorts/VIDEO_ID
        - https://www.youtube.com/live/VIDEO_ID

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
            r"youtube\.com/shorts/",
            r"youtube\.com/live/",
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
            >>> transcriber._extract_video_id("https://www.youtube.com/shorts/sID")
            'sID'
        """
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

        # Format: youtube.com/shorts/VIDEO_ID (parser emits this for Shorts
        # entries in YouTube media-RSS feeds — see parser._extract_enclosure_url).
        shorts_match = re.search(r"youtube\.com/shorts/([^/?]+)", url)
        if shorts_match:
            return shorts_match.group(1)

        # Format: youtube.com/live/VIDEO_ID (live VOD permalinks).
        live_match = re.search(r"youtube\.com/live/([^/?]+)", url)
        if live_match:
            return live_match.group(1)

        return None

    def _language_matches_preference(self, language_code: str, preferred_language: str) -> bool:
        """Return True when a transcript language satisfies a preference.

        Treat a base language preference like ``en`` as matching regional variants
        such as ``en-US`` or ``en-GB``.
        """
        return language_code == preferred_language or language_code.startswith(
            f"{preferred_language}-"
        )

    def _translation_language_code(self, translation_language: Any) -> str | None:
        """Extract a language code from youtube-transcript-api translation metadata."""
        if isinstance(translation_language, dict):
            value = translation_language.get("language_code")
            return str(value) if value else None

        value = getattr(translation_language, "language_code", None)
        return str(value) if value else None

    def _transcript_candidates(
        self,
        transcript_list: Any,
        available_transcripts: list[Any],
    ) -> list[tuple[Any, str]]:
        """Build transcript candidates from most preferred to broadest fallback."""
        candidates: list[tuple[Any, str]] = []
        seen_ids: set[int] = set()

        def add_candidate(transcript_obj: Any, reason: str) -> None:
            transcript_id = id(transcript_obj)
            if transcript_id in seen_ids:
                return

            seen_ids.add(transcript_id)
            candidates.append((transcript_obj, reason))

        found_preferred_transcript = False
        for lang in self.preferred_languages:
            try:
                add_candidate(
                    transcript_list.find_transcript([lang]),
                    f"preferred language {lang}",
                )
                found_preferred_transcript = True
                break
            except NoTranscriptFound:
                continue

        if not found_preferred_transcript:
            try:
                add_candidate(
                    transcript_list.find_generated_transcript(self.preferred_languages),
                    "generated preferred language",
                )
            except NoTranscriptFound:
                pass

        for lang in self.preferred_languages:
            for transcript_obj in available_transcripts:
                language_code = getattr(transcript_obj, "language_code", "")
                if self._language_matches_preference(language_code, lang):
                    add_candidate(transcript_obj, f"language variant {language_code}")

        for lang in self.preferred_languages:
            for transcript_obj in available_transcripts:
                if not getattr(transcript_obj, "is_translatable", False):
                    continue

                translation_languages = getattr(transcript_obj, "translation_languages", [])
                if not any(
                    self._translation_language_code(translation_language) == lang
                    for translation_language in translation_languages
                ):
                    continue

                try:
                    source_language_code = getattr(transcript_obj, "language_code", "unknown")
                    add_candidate(
                        transcript_obj.translate(lang),
                        f"{source_language_code} translated to {lang}",
                    )
                except Exception as e:
                    logger.warning(
                        "Could not prepare translated transcript candidate for %s: %s",
                        lang,
                        e,
                    )

        for transcript_obj in available_transcripts:
            add_candidate(
                transcript_obj,
                f"available language {getattr(transcript_obj, 'language_code', 'unknown')}",
            )

        return candidates

    async def transcribe(
        self,
        url_or_request: str | TranscriptionRequest,
        audio_path: str | None = None,
    ) -> Transcript:
        """Fetch transcript from YouTube.

        Supports both the legacy interface (URL string) and the new plugin
        interface (TranscriptionRequest).

        Args:
            url_or_request: YouTube video URL (str) or TranscriptionRequest.
                           The TranscriptionRequest form is preferred for new code.
            audio_path: Not used for YouTube transcription (deprecated, for compatibility)

        Returns:
            Transcript object with segments and metadata

        Raises:
            TranscriptionError: If transcript cannot be retrieved
            APIError: If URL is invalid or video ID cannot be extracted
        """
        if isinstance(url_or_request, TranscriptionRequest):
            if url_or_request.url is None:
                raise APIError(
                    "YouTubeTranscriber requires a URL. "
                    "Use TranscriptionRequest(url='...') for YouTube transcription."
                )
            url = url_or_request.url
        else:
            # Legacy string URL interface
            url = url_or_request
            if audio_path is not None:
                warnings.warn(
                    "audio_path parameter is deprecated and ignored for YouTube transcription. "
                    "Use TranscriptionRequest(url='...') instead.",
                    DeprecationWarning,
                    stacklevel=2,
                )

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
            try:
                available_transcripts = list(transcript_list)
            except TypeError:
                available_transcripts = []
            candidates = self._transcript_candidates(transcript_list, available_transcripts)
            last_retrieval_error: CouldNotRetrieveTranscript | None = None

            for transcript_obj, reason in candidates:
                try:
                    # Fetch transcript data. youtube-transcript-api >= 1.0 returns a
                    # FetchedTranscript whose entries are FetchedTranscriptSnippet
                    # dataclasses (attribute access, not dict subscript). Prior code
                    # used entry["text"] + # type: ignore[index]; that silently broke
                    # every YouTube-caption fetch and forced fallback to paid Gemini.
                    transcript_data = transcript_obj.fetch()
                except (TranscriptsDisabled, VideoUnavailable):
                    raise
                except CouldNotRetrieveTranscript as e:
                    last_retrieval_error = e
                    logger.warning(
                        "Could not fetch YouTube transcript candidate (%s) for %s: %s",
                        reason,
                        video_id,
                        e,
                    )
                    continue

                segments = [
                    TranscriptSegment(
                        text=entry.text,
                        start=entry.start,
                        duration=entry.duration,
                    )
                    for entry in transcript_data
                ]

                language_code = getattr(transcript_obj, "language_code", "unknown")
                logger.info(
                    "Successfully fetched YouTube transcript: %s segments (%s, %s)",
                    len(segments),
                    language_code,
                    reason,
                )

                return Transcript(
                    segments=segments,
                    source="youtube",
                    language=language_code,
                    episode_url=url,
                )

            available_languages = (
                ", ".join(t.language_code for t in available_transcripts) or "none"
            )
            message = (
                f"No usable transcript found for video {video_id}. "
                f"Preferred languages: {', '.join(self.preferred_languages)}. "
                f"Available languages: {available_languages}."
            )
            if last_retrieval_error is not None:
                raise APIError(message) from last_retrieval_error
            raise APIError(message)

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
