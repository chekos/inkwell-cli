"""Transcription manager orchestrating multi-tier transcription."""

import asyncio
import logging
import os
import warnings
from collections.abc import Callable
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from inkwell.audio import AudioDownloader
from inkwell.config.precedence import resolve_config_value
from inkwell.config.schema import TranscriptionConfig
from inkwell.plugins import PluginRegistry, discover_plugins
from inkwell.plugins.types.transcription import TranscriptionPlugin, TranscriptionRequest
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
        use_plugin_registry: bool = True,
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
            use_plugin_registry: Whether to load transcribers from plugin registry (default: True)

        Note:
            Prefer passing `config` over individual parameters. Individual parameters
            are maintained for backward compatibility but will be deprecated in v2.0.

            Plugin Selection:
            - Set INKWELL_TRANSCRIBER env var to force a specific transcriber
            - Otherwise, the multi-tier strategy is used (YouTube → Gemini fallback)
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
        self.audio_downloader = audio_downloader or AudioDownloader()
        self.cost_tracker = cost_tracker
        self._use_plugin_registry = use_plugin_registry

        # Store config for plugin configuration
        self._config = config
        self._gemini_api_key = gemini_api_key
        self._model_name = model_name
        self._cost_confirmation_callback = cost_confirmation_callback

        # Initialize plugin registry
        self._registry: PluginRegistry[TranscriptionPlugin] = PluginRegistry(
            TranscriptionPlugin  # type: ignore[type-abstract]
        )
        self._plugins_loaded = False

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

        # Initialize transcribers directly (legacy mode or when explicitly passed)
        # These will also be available via the plugin registry if loaded
        self.youtube_transcriber = youtube_transcriber or YouTubeTranscriber()
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

    def _load_transcription_plugins(self) -> None:
        """Load transcription plugins from entry points into registry.

        This is called lazily when plugins are first needed. Plugins are
        configured with any available API keys and cost tracker.
        """
        if self._plugins_loaded:
            return

        for result in discover_plugins("inkwell.plugins.transcription"):
            if result.success and result.plugin:
                # Register the plugin
                self._registry.register(
                    name=result.name,
                    plugin=result.plugin,  # type: ignore[arg-type]
                    priority=PluginRegistry.PRIORITY_BUILTIN,
                    source=result.source,
                )

                # Configure the plugin
                plugin_config = self._get_plugin_config(result.name)
                try:
                    result.plugin.configure(plugin_config, self.cost_tracker)
                except Exception as e:
                    logger.warning(f"Failed to configure plugin {result.name}: {e}")
            else:
                # Register as broken for visibility
                self._registry.register(
                    name=result.name,
                    plugin=None,
                    source=result.source,
                    error=result.error,
                )

        self._plugins_loaded = True

    def _get_plugin_config(self, plugin_name: str) -> dict:
        """Get configuration for a specific plugin.

        Args:
            plugin_name: Name of the plugin

        Returns:
            Configuration dict for the plugin
        """
        config_dict: dict = {}

        if plugin_name == "gemini":
            # Extract config values with standardized precedence
            effective_api_key = resolve_config_value(
                self._config.api_key if self._config else None,
                self._gemini_api_key,
                None,
            )
            effective_model = resolve_config_value(
                self._config.model_name if self._config else None,
                self._model_name,
                "gemini-2.5-flash",
            )
            effective_cost_threshold = resolve_config_value(
                self._config.cost_threshold_usd if self._config else None,
                None,
                1.0,
            )

            if effective_api_key:
                config_dict["api_key"] = effective_api_key
            config_dict["model_name"] = effective_model
            config_dict["cost_threshold_usd"] = effective_cost_threshold

        elif plugin_name == "youtube":
            # YouTube doesn't need special config
            pass

        return config_dict

    @property
    def transcription_registry(self) -> PluginRegistry[TranscriptionPlugin]:
        """Get the transcription plugin registry.

        Lazily loads plugins on first access.
        """
        if self._use_plugin_registry and not self._plugins_loaded:
            self._load_transcription_plugins()
        return self._registry

    async def transcribe(
        self,
        episode_url: str,
        use_cache: bool = True,
        skip_youtube: bool = False,
        auth_username: str | None = None,
        auth_password: str | None = None,
        progress_callback: Callable[[str, dict], None] | None = None,
        transcriber_override: str | None = None,
    ) -> TranscriptionResult:
        """Transcribe episode using multi-tier strategy.

        Strategy:
        1. Check cache (if use_cache=True)
        2. Check for transcriber override (parameter or INKWELL_TRANSCRIBER env var)
        3. Try YouTube transcript (Tier 1, if not skip_youtube)
        4. Try audio download + Gemini (Tier 2)
        5. Cache result (if successful)

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
            transcriber_override: Force a specific transcriber plugin (e.g., "youtube", "gemini").
                                 Falls back to INKWELL_TRANSCRIBER env var if not provided.

        Returns:
            TranscriptionResult with transcript and metadata
        """
        start_time = datetime.now(timezone.utc)
        attempts: list[str] = []
        total_cost = 0.0

        def _progress(step: str, **kwargs: object) -> None:
            if progress_callback:
                progress_callback(step, kwargs)

        # Check for transcriber override (parameter takes precedence over env var)
        override = transcriber_override or os.environ.get("INKWELL_TRANSCRIBER")
        if override:
            return await self._transcribe_with_override(
                override,
                episode_url,
                use_cache,
                auth_username,
                auth_password,
                progress_callback,
            )

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

    async def _transcribe_with_override(
        self,
        transcriber_name: str,
        episode_url: str,
        use_cache: bool,
        auth_username: str | None,
        auth_password: str | None,
        progress_callback: Callable[[str, dict], None] | None,
    ) -> TranscriptionResult:
        """Transcribe using a specific plugin (environment variable override).

        Args:
            transcriber_name: Name of the transcriber plugin to use
            episode_url: Episode URL to transcribe
            use_cache: Whether to use cache
            auth_username: Authentication username
            auth_password: Authentication password
            progress_callback: Progress callback

        Returns:
            TranscriptionResult
        """
        start_time = datetime.now(timezone.utc)
        attempts: list[str] = [transcriber_name]

        def _progress(step: str, **kwargs: object) -> None:
            if progress_callback:
                progress_callback(step, kwargs)

        # Check cache first
        if use_cache:
            _progress("checking_cache")
            cached = await self.cache.get(episode_url)
            if cached:
                duration = (datetime.now(timezone.utc) - start_time).total_seconds()
                return TranscriptionResult(
                    success=True,
                    transcript=cached,
                    attempts=["cache"],
                    duration_seconds=duration,
                    cost_usd=0.0,
                    from_cache=True,
                )

        # Get the plugin from registry
        plugin = self.transcription_registry.get(transcriber_name)
        if not plugin:
            # Unknown transcriber
            duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            available = [name for name, _ in self.transcription_registry.get_enabled()]
            return TranscriptionResult(
                success=False,
                error=(
                    f"Transcriber '{transcriber_name}' not found (set via INKWELL_TRANSCRIBER). "
                    f"Available: {', '.join(available) or 'none'}"
                ),
                attempts=attempts,
                duration_seconds=duration,
                cost_usd=0.0,
                from_cache=False,
            )

        try:
            # YouTube plugin handles URLs directly
            if transcriber_name == "youtube":
                _progress("trying_youtube")
                request = TranscriptionRequest(url=episode_url)
                if not plugin.can_handle(request):
                    raise APIError(
                        f"Plugin '{transcriber_name}' cannot handle URL: {episode_url}"
                    )
                transcript = await plugin.transcribe(request)
            # Gemini and other file-based plugins need audio download first
            else:
                _progress("downloading_audio", url=episode_url)
                audio_path = await self.audio_downloader.download(
                    episode_url,
                    username=auth_username,
                    password=auth_password,
                )
                _progress(f"transcribing_{transcriber_name}", audio_path=str(audio_path))
                request = TranscriptionRequest(file_path=audio_path)
                transcript = await plugin.transcribe(request)

            # Cache result
            if use_cache:
                _progress("caching_result")
                await self.cache.set(episode_url, transcript)

            duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            return TranscriptionResult(
                success=True,
                transcript=transcript,
                attempts=attempts,
                duration_seconds=duration,
                cost_usd=transcript.cost_usd or 0.0,
                from_cache=False,
            )

        except Exception as e:
            duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            return TranscriptionResult(
                success=False,
                error=f"Transcription with '{transcriber_name}' failed: {e}",
                attempts=attempts,
                duration_seconds=duration,
                cost_usd=0.0,
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
