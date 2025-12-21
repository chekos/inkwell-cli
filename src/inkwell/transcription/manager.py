"""Transcription manager orchestrating multi-tier transcription."""

import asyncio
import logging
import warnings
from collections.abc import Callable
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from inkwell.audio import AudioDownloader
from inkwell.config.precedence import resolve_config_value
from inkwell.config.schema import TranscriptionConfig
from inkwell.transcription.cache import TranscriptCache
from inkwell.transcription.gemini import CostEstimate, GeminiTranscriber
from inkwell.transcription.models import Transcript, TranscriptionResult
from inkwell.transcription.youtube import YouTubeTranscriber
from inkwell.utils.errors import APIError

if TYPE_CHECKING:
    from inkwell.utils.costs import CostTracker

logger = logging.getLogger(__name__)


class TranscriptionManager:
    """High-level orchestrator for multi-tier transcription.

    Orchestrates:
    - Cache lookup
    - Tier 1: YouTube transcript extraction (free, fast)
    - Tier 2: Audio download + Gemini transcription (fallback, costs money)
    - Cache storage

    Follows ADR-009 multi-tier strategy for cost optimization.
    """

    def __init__(
        self,
        config: TranscriptionConfig | None = None,
        cache: TranscriptCache | None = None,
        youtube_transcriber: YouTubeTranscriber | None = None,
        audio_downloader: AudioDownloader | None = None,
        gemini_transcriber: GeminiTranscriber | None = None,
        gemini_api_key: str | None = None,
        model_name: str | None = None,
        cost_confirmation_callback: Callable[[CostEstimate], bool] | None = None,
        cost_tracker: "CostTracker | None" = None,
    ):
        """Initialize transcription manager.

        Args:
            config: Transcription configuration (recommended, new approach)
            cache: Transcript cache (default: new instance)
            youtube_transcriber: YouTube transcriber (default: new instance)
            audio_downloader: Audio downloader (default: new instance)
            gemini_transcriber: Gemini transcriber (default: new instance)
            gemini_api_key: Google AI API key (default: from env) [deprecated]
            model_name: Gemini model (default: gemini-2.5-flash) [deprecated]
            cost_confirmation_callback: Callback for Gemini cost confirmation
            cost_tracker: Cost tracker for recording API usage (optional, for DI)

        Note:
            Prefer passing `config` over individual parameters. Individual parameters
            are maintained for backward compatibility but will be deprecated in v2.0.
        """
        # Warn if using deprecated individual parameters
        if config is None and (gemini_api_key is not None or model_name is not None):
            warnings.warn(
                "Individual parameters (gemini_api_key, model_name) are deprecated. "
                "Use TranscriptionConfig instead. "
                "These parameters will be removed in v2.0.",
                DeprecationWarning,
                stacklevel=2,
            )

        self.cache = cache or TranscriptCache()
        self.youtube_transcriber = youtube_transcriber or YouTubeTranscriber()
        self.audio_downloader = audio_downloader or AudioDownloader()
        self.cost_tracker = cost_tracker

        # Extract config values with standardized precedence
        effective_api_key = resolve_config_value(
            config.api_key if config else None,
            gemini_api_key,
            None,  # Will fall back to environment in GeminiTranscriber
        )
        effective_model = resolve_config_value(
            config.model_name if config else None, model_name, "gemini-2.5-flash"
        )
        effective_cost_threshold = resolve_config_value(
            config.cost_threshold_usd if config else None,
            None,  # No individual param for this
            1.0,
        )

        # Initialize Gemini transcriber if API key available
        self.gemini_transcriber: GeminiTranscriber | None
        if gemini_transcriber:
            self.gemini_transcriber = gemini_transcriber
        elif effective_api_key:
            self.gemini_transcriber = GeminiTranscriber(
                api_key=effective_api_key,
                model_name=effective_model,
                cost_threshold_usd=effective_cost_threshold,
                cost_confirmation_callback=cost_confirmation_callback,
            )
        else:
            # Try to create from environment
            try:
                self.gemini_transcriber = GeminiTranscriber(
                    model_name=effective_model,
                    cost_threshold_usd=effective_cost_threshold,
                    cost_confirmation_callback=cost_confirmation_callback,
                )
            except ValueError:
                # No API key available - Gemini tier will be disabled
                self.gemini_transcriber = None

    async def transcribe(
        self,
        episode_url: str,
        use_cache: bool = True,
        skip_youtube: bool = False,
        auth_username: str | None = None,
        auth_password: str | None = None,
        progress_callback: Callable[[str, dict], None] | None = None,
    ) -> TranscriptionResult:
        """Transcribe episode using multi-tier strategy.

        Strategy:
        1. Check cache (if use_cache=True)
        2. Try YouTube transcript (Tier 1, if not skip_youtube)
        3. Try audio download + Gemini (Tier 2)
        4. Cache result (if successful)

        Args:
            episode_url: Episode URL to transcribe
            use_cache: Whether to use cache (default: True)
            skip_youtube: Skip YouTube tier, go straight to Gemini (default: False)
            auth_username: Username for authenticated audio downloads (private feeds)
            auth_password: Password for authenticated audio downloads (private feeds)
            progress_callback: Optional callback for progress updates.
                             Called with (step: str, data: dict) where step is one of:
                             - "checking_cache": Checking transcript cache
                             - "trying_youtube": Attempting YouTube transcript
                             - "downloading_audio": Downloading audio file
                             - "transcribing_gemini": Transcribing with Gemini API
                             - "caching_result": Caching successful result

        Returns:
            TranscriptionResult with transcript and metadata
        """
        start_time = datetime.now(timezone.utc)
        attempts: list[str] = []
        total_cost = 0.0

        def _progress(step: str, **kwargs: object) -> None:
            if progress_callback:
                progress_callback(step, kwargs)

        # Step 1: Check cache
        if use_cache:
            _progress("checking_cache")
            attempts.append("cache")
            cached = await self.cache.get(episode_url)
            if cached:
                duration = (datetime.now(timezone.utc) - start_time).total_seconds()
                return TranscriptionResult(
                    success=True,
                    transcript=cached,
                    attempts=attempts,
                    duration_seconds=duration,
                    cost_usd=0.0,  # Cache hit is free
                    from_cache=True,
                )

        # Step 2: Try YouTube (Tier 1)
        if not skip_youtube and await self.youtube_transcriber.can_transcribe(episode_url):
            _progress("trying_youtube")
            attempts.append("youtube")
            try:
                transcript = await self.youtube_transcriber.transcribe(episode_url)

                # Cache successful result
                if use_cache:
                    _progress("caching_result")
                    await self.cache.set(episode_url, transcript)

                duration = (datetime.now(timezone.utc) - start_time).total_seconds()
                return TranscriptionResult(
                    success=True,
                    transcript=transcript,
                    attempts=attempts,
                    duration_seconds=duration,
                    cost_usd=0.0,  # YouTube tier is free
                    from_cache=False,
                )

            except APIError:
                # YouTube failed - continue to Gemini tier
                pass

        # Step 3: Try Gemini (Tier 2)
        if self.gemini_transcriber is None:
            # Gemini not available - provide helpful error message
            duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            error_msg = "Transcription failed: No transcript source available.\n\nAttempted:\n"
            if "youtube" in attempts:
                error_msg += "  • YouTube: No transcript found for this video\n"
            error_msg += "  • Gemini: API key not configured\n\n"
            error_msg += (
                "To fix this, configure your Google AI API key:\n"
                "  inkwell config set transcription.api_key YOUR_API_KEY\n\n"
                "Get a free API key at: https://aistudio.google.com/apikey"
            )
            return TranscriptionResult(
                success=False,
                error=error_msg,
                attempts=attempts,
                duration_seconds=duration,
                cost_usd=total_cost,
                from_cache=False,
            )

        attempts.append("gemini")
        try:
            # Download audio (with auth credentials for private feeds)
            _progress("downloading_audio", url=episode_url)
            audio_path = await self.audio_downloader.download(
                episode_url,
                username=auth_username,
                password=auth_password,
            )

            # Transcribe with Gemini
            _progress("transcribing_gemini", audio_path=str(audio_path))
            transcript = await self.gemini_transcriber.transcribe(audio_path, episode_url)

            # Track cost (non-critical - don't fail transcription on cost tracking errors)
            try:
                if transcript.cost_usd:
                    total_cost += transcript.cost_usd

                    # Track in CostTracker if available
                    if self.cost_tracker:
                        # Estimate token counts from transcript
                        # Note: This is approximate; real counts would come from Gemini API
                        transcript_tokens = len(transcript.full_text) // 4
                        self.cost_tracker.add_cost(
                            provider="gemini",
                            model="gemini-2.5-flash",
                            operation="transcription",
                            input_tokens=transcript_tokens,
                            output_tokens=transcript_tokens,
                            episode_title=None,  # Not available here
                        )
            except Exception as e:
                logger.warning(f"Failed to track transcription cost: {e}")

            # Cache successful result
            if use_cache:
                _progress("caching_result")
                await self.cache.set(episode_url, transcript)

            duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            return TranscriptionResult(
                success=True,
                transcript=transcript,
                attempts=attempts,
                duration_seconds=duration,
                cost_usd=total_cost,
                from_cache=False,
            )

        except Exception as e:
            # All tiers failed - provide detailed error message
            duration = (datetime.now(timezone.utc) - start_time).total_seconds()

            # Build helpful error message based on error type
            error_str = str(e)
            error_msg = f"Transcription failed after {duration:.1f}s.\n\n"

            if "timeout" in error_str.lower() or "timed out" in error_str.lower():
                error_msg += (
                    "The operation timed out. This can happen with:\n"
                    "  • Long episodes (try a shorter one first)\n"
                    "  • Slow network connections\n"
                    "  • Gemini API being overloaded\n\n"
                    "Try again, or check your network connection."
                )
            elif "quota" in error_str.lower() or "rate" in error_str.lower():
                error_msg += (
                    "API quota or rate limit exceeded.\n\n"
                    "Wait a few minutes and try again, or check your API key quota at:\n"
                    "  https://console.cloud.google.com/apis/api/generativelanguage.googleapis.com/quotas"
                )
            elif "401" in error_str or "403" in error_str or "invalid" in error_str.lower():
                error_msg += (
                    "API authentication failed. Your API key may be invalid or expired.\n\n"
                    "Verify your API key:\n"
                    "  inkwell config show\n\n"
                    "Get a new key at: https://aistudio.google.com/apikey"
                )
            elif "download" in error_str.lower() or "audio" in error_str.lower():
                error_msg += (
                    "Failed to download the audio file.\n\n"
                    "Possible causes:\n"
                    "  • Episode URL is no longer valid\n"
                    "  • Private feed requires authentication\n"
                    "  • Network connectivity issues\n\n"
                    f"Error details: {e}"
                )
            else:
                error_msg += f"Error details: {e}"

            return TranscriptionResult(
                success=False,
                error=error_msg,
                attempts=attempts,
                duration_seconds=duration,
                cost_usd=total_cost,
                from_cache=False,
            )

    async def get_transcript(
        self,
        episode_url: str,
        force_refresh: bool = False,
    ) -> Transcript | None:
        """Get transcript for episode (convenience method).

        Args:
            episode_url: Episode URL
            force_refresh: Force re-transcription (bypass cache)

        Returns:
            Transcript if successful, None otherwise
        """
        result = await self.transcribe(episode_url, use_cache=not force_refresh)
        return result.transcript if result.success else None

    def clear_cache(self) -> int:
        """Clear all cached transcripts.

        Returns:
            Number of entries cleared
        """
        return asyncio.run(self.cache.clear())

    def clear_expired_cache(self) -> int:
        """Clear expired cache entries.

        Returns:
            Number of expired entries cleared
        """
        return asyncio.run(self.cache.clear_expired())

    def cache_stats(self) -> dict:
        """Get cache statistics.

        Returns:
            Dictionary with cache stats
        """
        return asyncio.run(self.cache.stats())
