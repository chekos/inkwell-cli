"""Extraction engine for orchestrating LLM-based content extraction.

Coordinates template selection, provider selection, caching, and result parsing.
"""

import hashlib
import json
import logging
import os
import re
import time
import warnings
from typing import TYPE_CHECKING, Any, Literal, cast

from ..config.precedence import resolve_config_value
from ..config.schema import ExtractionConfig

# Import from specific submodules to avoid circular import with inkwell.plugins.__init__
# (which imports ExtractionPlugin from .types.extraction, which imports BaseExtractor
# from inkwell.extraction.extractors.base, which triggers inkwell.extraction.__init__)
from ..plugins.discovery import discover_plugins, get_entry_point_group
from ..plugins.registry import PluginRegistry
from ..plugins.types.extraction import ExtractionCapabilities, ExtractionPlugin
from ..utils.errors import ValidationError
from ..utils.json_utils import JSONParsingError, safe_json_loads
from .cache import ExtractionCache
from .extractors import BaseExtractor
from .models import (
    ExtractedContent,
    ExtractionAttempt,
    ExtractionResult,
    ExtractionStatus,
    ExtractionSummary,
    ExtractionTemplate,
    ExtractorOutput,
)
from .routing import ExtractionRoutingAttempt, ExtractionRoutingPolicy

if TYPE_CHECKING:
    from ..utils.costs import CostTracker

logger = logging.getLogger(__name__)
_LOCAL_RUNTIME_PROVIDERS = {"claude-code", "codex"}


def _sanitize_error_message(message: str) -> str:
    """Remove potential API keys from error messages.

    Sanitizes error messages to prevent API key leakage in logs and exception traces.
    Redacts both Gemini and Claude API keys using regex patterns.

    Args:
        message: Error message that may contain API keys

    Returns:
        Sanitized message with API keys redacted

    Example:
        >>> _sanitize_error_message("Error with key AIzaSyDabcdefg123")
        'Error with key [REDACTED_GEMINI_KEY]'
    """
    # Redact Gemini keys (AIza...)
    message = re.sub(r"AIza[A-Za-z0-9_-]+", "[REDACTED_GEMINI_KEY]", message)
    # Redact Claude keys (sk-ant-...)
    message = re.sub(r"sk-ant-[A-Za-z0-9_-]+", "[REDACTED_CLAUDE_KEY]", message)
    return message


class ExtractionEngine:
    """Orchestrates content extraction from transcripts.

    Handles:
    - Provider selection (Claude vs Gemini)
    - Caching to avoid redundant API calls
    - Result parsing and validation
    - Cost tracking
    - Error handling

    Example:
        >>> engine = ExtractionEngine()
        >>> result = await engine.extract(
        ...     template=summary_template,
        ...     transcript="...",
        ...     metadata={"podcast_name": "..."}
        ... )
        >>> print(result.content.data)
    """

    def __init__(
        self,
        config: ExtractionConfig | None = None,
        claude_api_key: str | None = None,
        gemini_api_key: str | None = None,
        cache: ExtractionCache | None = None,
        default_provider: str = "gemini",
        cost_tracker: "CostTracker | None" = None,
        use_plugin_registry: bool = True,
        extractor_override: str | None = None,
        force_extraction: bool = False,
        routing_policy: ExtractionRoutingPolicy | None = None,
        plugin_configs: dict[str, Any] | None = None,
    ) -> None:
        """Initialize extraction engine.

        Args:
            config: Extraction configuration (recommended, new approach)
            claude_api_key: Anthropic API key (defaults to env var) [deprecated, use config]
            gemini_api_key: Google AI API key (defaults to env var) [deprecated, use config]
            cache: Cache instance (defaults to new ExtractionCache)
            default_provider: Default provider ("claude" or "gemini") [deprecated]
            cost_tracker: Cost tracker for recording API usage (optional, for DI)
            use_plugin_registry: Whether to load extractors from plugin registry (default: True)
            extractor_override: Force a specific extractor plugin (e.g., "claude", "gemini").
                               Takes precedence over INKWELL_EXTRACTOR env var.
            force_extraction: Run LLM extraction even when short-content bypass applies.
            routing_policy: Token-aware provider routing policy.

        Note:
            Prefer passing `config` over individual parameters. Individual parameters
            are maintained for backward compatibility but will be deprecated in v2.0.

            Plugin Selection:
            - extractor_override parameter (explicit override, takes precedence)
            - INKWELL_EXTRACTOR env var (environment override)
            - Otherwise, the highest priority available extractor is used
        """
        deprecated_params = []
        if claude_api_key is not None:
            deprecated_params.append("claude_api_key")
        if gemini_api_key is not None:
            deprecated_params.append("gemini_api_key")
        if default_provider != "gemini":  # Non-default value
            deprecated_params.append("default_provider")

        if config is None and deprecated_params:
            warnings.warn(
                f"Individual parameters ({', '.join(deprecated_params)}) are deprecated. "
                f"Use ExtractionConfig instead. "
                f"These parameters will be removed in v2.0.",
                DeprecationWarning,
                stacklevel=2,
            )

        # Extract config values with standardized precedence
        effective_claude_key = resolve_config_value(
            config.claude_api_key if config else None, claude_api_key, None
        )
        effective_gemini_key = resolve_config_value(
            config.gemini_api_key if config else None, gemini_api_key, None
        )
        effective_provider = resolve_config_value(
            config.default_provider if config else None, default_provider, "gemini"
        )

        self._claude_api_key = effective_claude_key
        self._gemini_api_key = effective_gemini_key

        self.cache = cache or ExtractionCache()
        self.default_provider = effective_provider
        self.cost_tracker = cost_tracker

        self._registry: PluginRegistry[ExtractionPlugin] = PluginRegistry(
            ExtractionPlugin  # type: ignore[type-abstract]
        )
        self._use_plugin_registry = use_plugin_registry
        self._plugins_loaded = False

        self._extractor_override = extractor_override
        self._force_extraction = force_extraction
        self._short_content_bypass_enabled = config.short_content_bypass_enabled if config else True
        self._short_content_bypass_tokens = config.short_content_bypass_tokens if config else 500
        self.routing_policy = routing_policy or ExtractionRoutingPolicy()
        self._plugin_configs = plugin_configs or {}

    @staticmethod
    def _estimate_text_tokens(text: str) -> int:
        """Estimate token count from text using the repo's existing rough ratio."""
        return max(1, len(text) // 4)

    def _should_bypass_short_content(
        self,
        template: ExtractionTemplate,
        transcript: str,
        metadata: dict[str, Any],
    ) -> tuple[bool, int, str | None]:
        """Return whether summary extraction should pass through short content."""
        source_tokens = self._estimate_text_tokens(transcript)

        if self._force_extraction:
            return False, source_tokens, None
        if not self._short_content_bypass_enabled:
            return False, source_tokens, None
        if template.name != "summary":
            return False, source_tokens, None
        if not metadata.get("episode_url") and not metadata.get("source_kind"):
            return False, source_tokens, None
        if source_tokens > self._short_content_bypass_tokens:
            return False, source_tokens, None

        reason = f"source_tokens={source_tokens} <= threshold={self._short_content_bypass_tokens}"
        return True, source_tokens, reason

    def _bypass_result(
        self,
        template: ExtractionTemplate,
        transcript: str,
        metadata: dict[str, Any],
        *,
        source_tokens: int,
        reason: str,
    ) -> ExtractionResult:
        """Build a pass-through extraction result for short summary content."""
        content = ExtractedContent(
            template_name=template.name,
            content=transcript.strip(),
            metadata={
                "bypassed": True,
                "bypass_reason": reason,
                "source_tokens": source_tokens,
                "threshold_tokens": self._short_content_bypass_tokens,
            },
        )
        return ExtractionResult(
            episode_url=metadata.get("episode_url", ""),
            template_name=template.name,
            template_version=template.version,
            success=True,
            extracted_content=content,
            cost_usd=0.0,
            provider="bypass",
            model=None,
            bypassed=True,
            bypass_reason=reason,
        )

    def _load_extraction_plugins(self) -> None:
        """Load extraction plugins from entry points into registry.

        This is called lazily when plugins are first needed. Plugins are
        configured with any available API keys and cost tracker.
        """
        if self._plugins_loaded:
            return

        group = get_entry_point_group("extraction")
        discovered_names: set[str] = set()

        for result in discover_plugins(group):
            discovered_names.add(result.name)
            if result.success and isinstance(result.plugin, ExtractionPlugin):
                self._register_extraction_plugin(result.name, result.plugin, result.source)
            else:
                # Register broken plugin for visibility
                error = result.error
                if result.success and result.plugin is not None:
                    error = (
                        f"Entry point did not load an ExtractionPlugin: "
                        f"{type(result.plugin).__name__}"
                    )
                self._registry.register(
                    name=result.name,
                    plugin=None,
                    priority=0,
                    source=result.source,
                    error=error,
                    recovery_hint=result.recovery_hint,
                )

        self._register_builtin_extraction_plugins(discovered_names)
        self._plugins_loaded = True

    def _register_builtin_extraction_plugins(self, discovered_names: set[str]) -> None:
        """Register built-in extractors when package entry points are unavailable."""

        builtin_extractors = {
            "claude": "inkwell.extraction.extractors.claude:ClaudeExtractor",
            "claude-code": ("inkwell.extraction.extractors.claude_code:ClaudeCodeExtractor"),
            "codex": "inkwell.extraction.extractors.codex:CodexExtractor",
            "gemini": "inkwell.extraction.extractors.gemini:GeminiExtractor",
        }

        for name, source in builtin_extractors.items():
            if name in discovered_names:
                continue

            module_name, class_name = source.split(":", 1)
            try:
                module = __import__(module_name, fromlist=[class_name])
                plugin_class = getattr(module, class_name)
                try:
                    plugin = plugin_class(lazy_init=True)
                except TypeError:
                    plugin = plugin_class()
            except Exception as e:
                self._registry.register(
                    name=name,
                    plugin=None,
                    priority=0,
                    source=f"builtin:{source}",
                    error=str(e),
                )
                continue

            self._register_extraction_plugin(name, plugin, f"builtin:{source}")

    def _register_extraction_plugin(
        self,
        name: str,
        plugin: ExtractionPlugin,
        source: str,
    ) -> None:
        """Configure, validate, and register one extraction plugin."""

        plugin_config: dict[str, Any] = {}
        persisted = self._plugin_configs.get(name)
        if persisted is not None:
            if hasattr(persisted, "config"):
                plugin_config.update(dict(persisted.config))
            elif isinstance(persisted, dict):
                plugin_config.update(dict(persisted.get("config", persisted)))

        if name == "claude" and self._claude_api_key:
            plugin_config["api_key"] = self._claude_api_key
        elif name == "gemini" and self._gemini_api_key:
            plugin_config["api_key"] = self._gemini_api_key

        try:
            plugin.configure(plugin_config, self.cost_tracker)
            plugin.validate()
            priority = (
                int(persisted.priority)
                if persisted is not None and hasattr(persisted, "priority")
                else PluginRegistry.PRIORITY_BUILTIN
            )
            self._registry.register(
                name=name,
                plugin=plugin,
                priority=priority,
                source=source,
            )
            if (
                persisted is not None
                and hasattr(persisted, "enabled")
                and not bool(persisted.enabled)
            ):
                self._registry.disable(name)
            logger.debug(f"Registered extraction plugin: {name}")
        except Exception as e:
            self._registry.register(
                name=name,
                plugin=None,
                priority=0,
                source=source,
                error=str(e),
            )
            if name == self.default_provider:
                logger.warning(f"Failed to configure extraction plugin {name}: {e}")
            else:
                logger.debug(f"Extraction plugin {name} not configured: {e}")

    @property
    def extraction_registry(self) -> PluginRegistry[ExtractionPlugin]:
        """Get the extraction plugin registry.

        Lazily loads plugins on first access.
        """
        if self._use_plugin_registry and not self._plugins_loaded:
            self._load_extraction_plugins()
        return self._registry

    def _cache_key_options(
        self,
        template: ExtractionTemplate,
        extractor: BaseExtractor | None = None,
    ) -> dict[str, str]:
        """Build stable extraction cache-key metadata for a template."""
        provider = (
            self._provider_name_for_extractor(extractor)
            if extractor is not None
            else self._cache_provider_for_template(template)
        )
        return {
            "provider": provider,
            "model": (
                self._model_name_for_extractor(extractor)
                if extractor is not None
                else self._cache_model_for_provider(provider)
            ),
            "prompt_hash": self._template_prompt_hash(template),
            "output_schema_version": self._output_schema_version(template),
            "runtime_identity": ("unknown" if provider in _LOCAL_RUNTIME_PROVIDERS else "direct"),
        }

    def _provider_name_for_extractor(self, extractor: BaseExtractor) -> str:
        """Return a provider identity for cache keys and result metadata."""
        plugin_name = getattr(extractor, "NAME", None)
        if isinstance(plugin_name, str) and plugin_name:
            return plugin_name

        class_name = extractor.__class__.__name__
        if class_name == "ClaudeExtractor":
            return "claude"
        if class_name == "GeminiExtractor":
            return "gemini"
        return class_name.removesuffix("Extractor").lower() or "unknown"

    def _model_name_for_extractor(self, extractor: BaseExtractor) -> str:
        """Return a model identity for cache keys."""
        model = getattr(extractor, "model", None) or getattr(extractor, "MODEL", None)
        if isinstance(model, str) and model:
            return model
        return "unknown"

    def _cache_provider_for_template(self, template: ExtractionTemplate) -> str:
        """Mirror provider selection inputs without requiring plugin initialization."""
        override = self._extractor_override or os.environ.get("INKWELL_EXTRACTOR")
        if override:
            return override

        if template.model_preference and template.model_preference not in _LOCAL_RUNTIME_PROVIDERS:
            return template.model_preference

        if "quote" in template.name.lower():
            return "claude"

        if template.expected_format == "json" and template.output_schema:
            required_fields = template.output_schema.get("required", [])
            if len(required_fields) > 5:
                return "claude"

        return self.default_provider

    def _cache_model_for_provider(self, provider: str) -> str:
        """Return the default model identity used for cache-key metadata."""
        default_models = {
            "claude": "claude-3-5-sonnet-20241022",
            "gemini": "gemini-3-pro-preview",
        }
        return default_models.get(provider, "unknown")

    def _cache_key_options_for_provider(
        self,
        template: ExtractionTemplate,
        *,
        provider: str,
        model: str,
        runtime_identity: str = "direct",
    ) -> dict[str, str]:
        """Build cache-key metadata for a selected provider/model."""
        return {
            "provider": provider,
            "model": model,
            "prompt_hash": self._template_prompt_hash(template),
            "output_schema_version": self._output_schema_version(template),
            "runtime_identity": runtime_identity,
        }

    async def _runtime_identity_for_extractor(self, extractor: BaseExtractor) -> str:
        """Resolve runtime compatibility identity before cache access."""
        if self._provider_name_for_extractor(extractor) not in _LOCAL_RUNTIME_PROVIDERS:
            return "direct"
        cache_identity = getattr(extractor, "cache_identity", None)
        if callable(cache_identity):
            identity = await cache_identity()
            if isinstance(identity, str) and identity:
                return identity
        return "direct"

    async def _invoke_extractor(
        self,
        extractor: BaseExtractor,
        template: ExtractionTemplate,
        transcript: str,
        metadata: dict[str, Any],
    ) -> ExtractorOutput:
        """Use the metadata seam for local runtimes and preserve API behavior."""
        provider = self._provider_name_for_extractor(extractor)
        model = self._model_name_for_extractor(extractor)
        if provider in _LOCAL_RUNTIME_PROVIDERS:
            output = await extractor.extract_with_metadata(template, transcript, metadata)
            if not isinstance(output, ExtractorOutput):
                raise TypeError("Local runtime extractor returned invalid typed metadata")
            return output
        raw_content = await extractor.extract(template, transcript, metadata)
        cost = extractor.estimate_cost(template, len(transcript))
        return ExtractorOutput(
            raw_content=raw_content,
            provider=provider,
            model=model,
            input_tokens=max(0, len(transcript) // 4),
            output_tokens=max(0, len(raw_content) // 4),
            cost_usd=cost,
            cost_known=True,
            billing={"mode": "known", "amount_usd": cost},
        )

    @staticmethod
    def _runtime_identity_from_result(result: ExtractionResult) -> str:
        runtime = result.runtime
        if not runtime:
            return "direct"
        return ":".join(
            [
                str(runtime.get("kind", "unknown")),
                str(runtime.get("version", "unknown")),
                f"protocol={runtime.get('protocol_version', 'unknown')}",
                f"requested={runtime.get('requested_model', 'unknown')}",
                f"effective={runtime.get('effective_model', 'unknown')}",
                f"auth={runtime.get('auth_class', 'unknown')}",
                f"billing={runtime.get('billing_class', 'unknown')}",
            ]
        )

    @staticmethod
    def _encode_cache_output(output: ExtractorOutput) -> str:
        """Persist content with its immutable origin metadata."""
        return json.dumps(
            {
                "_inkwell_extraction_cache": 1,
                "output": output.model_dump(mode="json"),
            },
            sort_keys=True,
        )

    @staticmethod
    def _decode_cache_output(
        cached: str,
        *,
        provider: str,
        model: str,
    ) -> ExtractorOutput:
        """Read metadata-aware cache values with legacy string compatibility."""
        try:
            value = json.loads(cached)
        except json.JSONDecodeError:
            value = None
        if (
            isinstance(value, dict)
            and value.get("_inkwell_extraction_cache") == 1
            and isinstance(value.get("output"), dict)
        ):
            output = ExtractorOutput.model_validate(value["output"])
            updates: dict[str, Any] = {"cost_usd": 0.0}
            if output.cost_known:
                updates["billing"] = {"mode": "known", "amount_usd": 0.0}
            return output.model_copy(update=updates)
        return ExtractorOutput(
            raw_content=cached,
            provider=provider,
            model=model,
            cost_usd=0.0,
            cost_known=True,
            billing={"mode": "known", "amount_usd": 0.0},
        )

    @staticmethod
    def _result_from_output(
        *,
        output: ExtractorOutput,
        content: ExtractedContent,
        episode_url: str,
        template: ExtractionTemplate,
        from_cache: bool = False,
    ) -> ExtractionResult:
        """Build the public result without shared mutable extractor state."""
        return ExtractionResult(
            episode_url=episode_url,
            template_name=template.name,
            template_version=template.version,
            success=True,
            extracted_content=content,
            duration_seconds=output.duration_seconds,
            tokens_used=output.input_tokens + output.output_tokens,
            cost_usd=0.0 if from_cache else output.cost_usd,
            cost_known=output.cost_known,
            billing=output.billing,
            provider=output.provider,
            model=output.model,
            runtime=output.runtime,
            from_cache=from_cache,
        )

    def _available_extraction_capabilities(self) -> dict[str, ExtractionCapabilities]:
        """Return enabled extraction provider capabilities."""
        capabilities: dict[str, ExtractionCapabilities] = {}
        for name, plugin in self.extraction_registry.get_enabled():
            get_capabilities = getattr(plugin, "get_capabilities", None)
            if callable(get_capabilities):
                capabilities[name] = get_capabilities()
            else:
                model_name = self._model_name_for_extractor(plugin)
                capabilities[name] = ExtractionCapabilities(model_name=model_name)
        return capabilities

    def _plan_extraction_attempts(
        self,
        template: ExtractionTemplate,
        transcript: str,
        metadata: dict[str, Any],
    ) -> list[ExtractionRoutingAttempt]:
        """Plan ordered extraction attempts for one template."""
        override = self._extractor_override or os.environ.get("INKWELL_EXTRACTOR")
        return self.routing_policy.plan(
            template=template,
            transcript=transcript,
            metadata=metadata,
            available_capabilities=self._available_extraction_capabilities(),
            default_provider=self.default_provider,
            override=override,
        )

    def _template_prompt_hash(self, template: ExtractionTemplate) -> str:
        """Hash prompt/template inputs that affect extraction output."""
        payload = {
            "name": template.name,
            "version": template.version,
            "system_prompt": template.system_prompt,
            "user_prompt_template": template.user_prompt_template,
            "expected_format": template.expected_format,
            "output_schema": template.output_schema,
            "model_preference": template.model_preference,
            "max_tokens": template.max_tokens,
            "temperature": template.temperature,
            "variables": [variable.model_dump(mode="json") for variable in template.variables],
            "few_shot_examples": template.few_shot_examples,
        }
        content = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def _output_schema_version(self, template: ExtractionTemplate) -> str:
        """Build an output schema identity for cache-key metadata."""
        schema_payload = {
            "expected_format": template.expected_format,
            "output_schema": template.output_schema or {},
        }
        content = json.dumps(schema_payload, sort_keys=True, separators=(",", ":"), default=str)
        schema_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        return f"{template.expected_format}:{schema_hash}"

    async def _extract_with_single_extractor(
        self,
        *,
        template: ExtractionTemplate,
        transcript: str,
        metadata: dict[str, Any],
        use_cache: bool,
        episode_url: str,
    ) -> ExtractionResult:
        """Compatibility path for callers/tests that inject `_select_extractor`."""
        extractor = self._select_extractor(template)
        provider_name = self._provider_name_for_extractor(extractor)
        model_name = self._model_name_for_extractor(extractor)
        runtime_identity = await self._runtime_identity_for_extractor(extractor)
        cache_key_options = {
            **self._cache_key_options(template, extractor),
            "runtime_identity": runtime_identity,
        }

        if use_cache:
            cached = await self.cache.get(
                template.name,
                template.version,
                transcript,
                **cache_key_options,
            )
            if cached:
                output = self._decode_cache_output(cached, provider=provider_name, model=model_name)
                content = self._parse_output(output.raw_content, template)
                return self._result_from_output(
                    output=output,
                    content=content,
                    episode_url=episode_url,
                    template=template,
                    from_cache=True,
                )

        try:
            output = await self._invoke_extractor(extractor, template, transcript, metadata)
            content = self._parse_output(output.raw_content, template)

            if use_cache:
                await self.cache.set(
                    template.name,
                    template.version,
                    transcript,
                    self._encode_cache_output(output),
                    **cache_key_options,
                )

            if self.cost_tracker:
                if output.cost_known:
                    self.cost_tracker.add_cost(
                        provider=output.provider,
                        model=output.model,
                        operation="extraction",
                        input_tokens=output.input_tokens,
                        output_tokens=output.output_tokens,
                        episode_title=metadata.get("episode_title"),
                        template_name=template.name,
                    )
                elif output.provider in _LOCAL_RUNTIME_PROVIDERS:
                    self.cost_tracker.add_runtime_usage(
                        provider=cast(Literal["codex", "claude-code"], output.provider),
                        model=output.model,
                        operation="extraction",
                        input_tokens=output.input_tokens,
                        output_tokens=output.output_tokens,
                        episode_title=metadata.get("episode_title"),
                        template_name=template.name,
                    )

            return self._result_from_output(
                output=output,
                content=content,
                episode_url=episode_url,
                template=template,
            )
        except Exception as e:
            error_msg = _sanitize_error_message(str(e))
            return ExtractionResult(
                episode_url=episode_url,
                template_name=template.name,
                template_version=template.version,
                success=False,
                extracted_content=None,
                error=error_msg,
                error_code=getattr(getattr(e, "code", None), "value", None),
                cost_usd=0.0,
                provider=provider_name,
                model=model_name,
            )

    async def extract(
        self,
        template: ExtractionTemplate,
        transcript: str,
        metadata: dict[str, Any],
        use_cache: bool = True,
    ) -> ExtractionResult:
        """Extract content from transcript using template.

        Args:
            template: Extraction template
            transcript: Full transcript text
            metadata: Episode metadata
            use_cache: Whether to use cache (default: True)

        Returns:
            ExtractionResult with parsed content and metadata

        Raises:
            ExtractionError: If extraction fails
        """
        episode_url = metadata.get("episode_url", "")
        should_bypass, source_tokens, bypass_reason = self._should_bypass_short_content(
            template, transcript, metadata
        )
        if should_bypass and bypass_reason is not None:
            return self._bypass_result(
                template,
                transcript,
                metadata,
                source_tokens=source_tokens,
                reason=bypass_reason,
            )

        if "_select_extractor" in self.__dict__:
            return await self._extract_with_single_extractor(
                template=template,
                transcript=transcript,
                metadata=metadata,
                use_cache=use_cache,
                episode_url=episode_url,
            )

        attempts = self._plan_extraction_attempts(template, transcript, metadata)
        if not attempts:
            estimated_tokens = self.routing_policy.estimate_prompt_tokens(
                template=template,
                transcript=transcript,
                metadata=metadata,
            )
            return ExtractionResult(
                episode_url=episode_url,
                template_name=template.name,
                template_version=template.version,
                success=False,
                extracted_content=None,
                error=(
                    "No configured extraction provider can handle the estimated "
                    f"{estimated_tokens} token prompt."
                ),
                cost_usd=0.0,
                provider=None,
                model=None,
            )

        if use_cache:
            for attempt in attempts:
                extractor = self.extraction_registry.get(attempt.provider)
                if extractor is None:
                    continue
                try:
                    runtime_identity = await self._runtime_identity_for_extractor(extractor)
                except Exception:
                    continue
                cache_key_options = self._cache_key_options_for_provider(
                    template,
                    provider=attempt.provider,
                    model=attempt.model,
                    runtime_identity=runtime_identity,
                )
                cached = await self.cache.get(
                    template.name,
                    template.version,
                    transcript,
                    **cache_key_options,
                )
                if cached:
                    output = self._decode_cache_output(
                        cached, provider=attempt.provider, model=attempt.model
                    )
                    content = self._parse_output(output.raw_content, template)
                    return self._result_from_output(
                        output=output,
                        content=content,
                        episode_url=episode_url,
                        template=template,
                        from_cache=True,
                    )

        last_error: str | None = None
        last_error_code: str | None = None
        last_attempt: ExtractionRoutingAttempt | None = None

        for attempt in attempts:
            last_attempt = attempt
            extractor = self.extraction_registry.get(attempt.provider)
            if extractor is None:
                last_error = f"Provider '{attempt.provider}' is not available"
                continue

            try:
                runtime_identity = await self._runtime_identity_for_extractor(extractor)
                cache_key_options = self._cache_key_options_for_provider(
                    template,
                    provider=attempt.provider,
                    model=attempt.model,
                    runtime_identity=runtime_identity,
                )
                output = await self._invoke_extractor(extractor, template, transcript, metadata)
                content = self._parse_output(output.raw_content, template)

                if use_cache:
                    await self.cache.set(
                        template.name,
                        template.version,
                        transcript,
                        self._encode_cache_output(output),
                        **cache_key_options,
                    )

                if self.cost_tracker:
                    if output.cost_known:
                        self.cost_tracker.add_cost(
                            provider=output.provider,
                            model=output.model,
                            operation="extraction",
                            input_tokens=output.input_tokens,
                            output_tokens=output.output_tokens,
                            episode_title=metadata.get("episode_title"),
                            template_name=template.name,
                        )
                    elif output.provider in _LOCAL_RUNTIME_PROVIDERS:
                        self.cost_tracker.add_runtime_usage(
                            provider=cast(Literal["codex", "claude-code"], output.provider),
                            model=output.model,
                            operation="extraction",
                            input_tokens=output.input_tokens,
                            output_tokens=output.output_tokens,
                            episode_title=metadata.get("episode_title"),
                            template_name=template.name,
                        )

                return self._result_from_output(
                    output=output,
                    content=content,
                    episode_url=episode_url,
                    template=template,
                )
            except Exception as e:
                last_error = _sanitize_error_message(str(e))
                last_error_code = getattr(getattr(e, "code", None), "value", None)
                logger.warning(
                    "Extraction attempt failed for template '%s' with provider '%s': %s",
                    template.name,
                    attempt.provider,
                    last_error,
                )
                continue

        return ExtractionResult(
            episode_url=episode_url,
            template_name=template.name,
            template_version=template.version,
            success=False,
            extracted_content=None,
            error=last_error or "All extraction attempts failed",
            error_code=last_error_code,
            cost_usd=0.0,
            provider=last_attempt.provider if last_attempt else None,
            model=last_attempt.model if last_attempt else None,
        )

    async def extract_all(
        self,
        templates: list[ExtractionTemplate],
        transcript: str,
        metadata: dict[str, Any],
        use_cache: bool = True,
    ) -> tuple[list[ExtractionResult], ExtractionSummary]:
        """Extract content using multiple templates.

        Processes templates concurrently for better performance.
        Returns both successful results and a detailed summary of all attempts.

        Args:
            templates: List of extraction templates
            transcript: Full transcript text
            metadata: Episode metadata
            use_cache: Whether to use cache (default: True)

        Returns:
            Tuple of (successful results, extraction summary)
        """
        import asyncio

        start_times = {}

        async def extract_with_tracking(template: ExtractionTemplate) -> ExtractionResult:
            """Extract and track timing."""
            start_times[template.name] = time.time()
            return await self.extract(template, transcript, metadata, use_cache)

        # Extract concurrently
        tasks = [extract_with_tracking(template) for template in templates]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        attempts = []
        successful_results = []

        for template, result in zip(templates, results, strict=False):
            duration = time.time() - start_times.get(template.name, time.time())

            if isinstance(result, ExtractionResult):
                if result.success:
                    # Determine if from cache
                    status = (
                        ExtractionStatus.CACHED if result.from_cache else ExtractionStatus.SUCCESS
                    )

                    attempts.append(
                        ExtractionAttempt(
                            template_name=template.name,
                            status=status,
                            result=result,
                            duration_seconds=duration,
                        )
                    )
                    successful_results.append(result)
                else:
                    # ExtractionResult with success=False
                    attempts.append(
                        ExtractionAttempt(
                            template_name=template.name,
                            status=ExtractionStatus.FAILED,
                            error_message=result.error,
                            duration_seconds=duration,
                        )
                    )
                    logger.warning(
                        f"Extraction failed for template '{template.name}': {result.error}"
                    )

            elif isinstance(result, Exception):
                # Exception during extraction
                # Sanitize error message to prevent API key leakage
                sanitized_error_msg = _sanitize_error_message(str(result))
                attempts.append(
                    ExtractionAttempt(
                        template_name=template.name,
                        status=ExtractionStatus.FAILED,
                        error=result,
                        error_message=sanitized_error_msg,
                        duration_seconds=duration,
                    )
                )
                # Log with sanitized message to prevent key leakage in logs
                logger.error(
                    f"Extraction failed for template '{template.name}': {sanitized_error_msg}",
                    exc_info=result,
                )

        summary = ExtractionSummary(
            total=len(templates),
            successful=sum(1 for a in attempts if a.status == ExtractionStatus.SUCCESS),
            failed=sum(1 for a in attempts if a.status == ExtractionStatus.FAILED),
            cached=sum(1 for a in attempts if a.status == ExtractionStatus.CACHED),
            attempts=attempts,
        )

        logger.info(
            f"Extraction complete: {summary.successful}/{summary.total} successful, "
            f"{summary.failed} failed, {summary.cached} cached"
        )

        return successful_results, summary

    async def _batch_cache_lookup(
        self,
        templates: list[ExtractionTemplate],
        transcript: str,
        metadata: dict[str, Any],
    ) -> dict[str, ExtractionResult]:
        """Lookup multiple templates in cache concurrently.

        Args:
            templates: List of templates to check
            transcript: Episode transcript for cache key
            metadata: Episode/source metadata for routing and results

        Returns:
            Dict mapping template name to ExtractionResult (only cache hits)
        """
        import asyncio

        episode_url = metadata.get("episode_url", "")

        async def lookup_one(
            template: ExtractionTemplate,
        ) -> tuple[ExtractionTemplate, str | None, dict[str, str]]:
            """Lookup single template in cache."""
            if "_select_extractor" not in self.__dict__:
                attempts = self._plan_extraction_attempts(template, transcript, metadata)
                for attempt in attempts:
                    extractor = self.extraction_registry.get(attempt.provider)
                    if extractor is None:
                        continue
                    try:
                        runtime_identity = await self._runtime_identity_for_extractor(extractor)
                    except Exception:
                        continue
                    cache_key_options = self._cache_key_options_for_provider(
                        template,
                        provider=attempt.provider,
                        model=attempt.model,
                        runtime_identity=runtime_identity,
                    )
                    result = await self.cache.get(
                        template.name,
                        template.version,
                        transcript,
                        **cache_key_options,
                    )
                    if result is not None:
                        return (template, result, cache_key_options)
                return (template, None, {})

            policy_cache_key_options = self._cache_key_options(template)
            result = await self.cache.get(
                template.name,
                template.version,
                transcript,
                **policy_cache_key_options,
            )
            if result is not None:
                return (template, result, policy_cache_key_options)

            selected_extractor = self._select_extractor(template)
            try:
                runtime_identity = await self._runtime_identity_for_extractor(selected_extractor)
            except Exception:
                return (template, None, {})
            cache_key_options = {
                **self._cache_key_options(template, selected_extractor),
                "runtime_identity": runtime_identity,
            }
            if cache_key_options != policy_cache_key_options:
                result = await self.cache.get(
                    template.name,
                    template.version,
                    transcript,
                    **cache_key_options,
                )
                if result is not None:
                    return (template, result, cache_key_options)
            return (template, result, policy_cache_key_options)

        results = await asyncio.gather(*[lookup_one(t) for t in templates])

        cached_results = {}
        for template, cached_raw, cache_key_options in results:
            if cached_raw is not None:
                output = self._decode_cache_output(
                    cached_raw,
                    provider=cache_key_options["provider"],
                    model=cache_key_options["model"],
                )
                content = self._parse_output(output.raw_content, template)
                cached_results[template.name] = self._result_from_output(
                    output=output,
                    content=content,
                    episode_url=episode_url,
                    template=template,
                    from_cache=True,
                )

        return cached_results

    async def extract_all_batched(
        self,
        templates: list[ExtractionTemplate],
        transcript: str,
        metadata: dict[str, Any],
        use_cache: bool = True,
    ) -> tuple[list[ExtractionResult], ExtractionSummary]:
        """Extract all templates in a single batched API call.

        Batches multiple template extractions into one API call to reduce
        network overhead by 75% and improve processing speed by 30-40%.

        Args:
            templates: List of extraction templates
            transcript: Full transcript text
            metadata: Episode metadata
            use_cache: Whether to use cache (default: True)

        Returns:
            Tuple of (extraction results, extraction summary)

        Example:
            >>> results, summary = await engine.extract_all_batched(
            ...     [summary_template, quotes_template, concepts_template],
            ...     transcript,
            ...     metadata
            ... )
        """

        if not templates:
            # Empty summary for no templates
            empty_summary = ExtractionSummary(
                total=0, successful=0, failed=0, cached=0, attempts=[]
            )
            return [], empty_summary

        batch_start_time = time.time()

        episode_url = metadata.get("episode_url", "")

        bypassed_results: dict[str, ExtractionResult] = {}
        processable_templates: list[ExtractionTemplate] = []
        for template in templates:
            should_bypass, source_tokens, bypass_reason = self._should_bypass_short_content(
                template,
                transcript,
                metadata,
            )
            if should_bypass and bypass_reason is not None:
                bypassed_results[template.name] = self._bypass_result(
                    template,
                    transcript,
                    metadata,
                    source_tokens=source_tokens,
                    reason=bypass_reason,
                )
            else:
                processable_templates.append(template)

        cached_results = {}
        uncached_templates = []

        if use_cache:
            # Batch lookup all templates at once
            cache_start = time.time()
            cached_results = await self._batch_cache_lookup(
                processable_templates,
                transcript,
                metadata,
            )
            cache_duration = time.time() - cache_start

            logger.debug(
                f"Cache lookup took {cache_duration:.3f}s for {len(processable_templates)} "
                f"templates ({len(cached_results)} hits, "
                f"{len(processable_templates) - len(cached_results)} misses)"
            )

            # Separate cached from uncached
            for template in processable_templates:
                if template.name not in cached_results:
                    uncached_templates.append(template)
        else:
            uncached_templates = processable_templates

        # Extract each template individually for focused, reliable results
        batch_results = {}
        if uncached_templates:
            logger.info(f"Extracting {len(uncached_templates)} templates individually")
            batch_results = await self._extract_individually(
                uncached_templates, transcript, metadata, episode_url
            )
        else:
            logger.info("No uncached templates require LLM extraction")

        if use_cache:
            for template in uncached_templates:
                result = batch_results.get(template.name)
                provider = result.provider if result else None
                if (
                    result
                    and result.success
                    and result.extracted_content
                    and provider is not None
                    and provider not in {"cache", "bypass"}
                ):
                    raw_output = self._encode_cache_output(
                        ExtractorOutput(
                            raw_content=self._serialize_extracted_content(result.extracted_content),
                            provider=provider,
                            model=result.model or "unknown",
                            input_tokens=max(0, result.tokens_used),
                            output_tokens=0,
                            cost_usd=result.cost_usd,
                            cost_known=result.cost_known,
                            billing=result.billing,
                            runtime=result.runtime,
                            duration_seconds=result.duration_seconds,
                        )
                    )
                    await self.cache.set(
                        template.name,
                        template.version,
                        transcript,
                        raw_output,
                        **self._cache_key_options_for_provider(
                            template,
                            provider=provider,
                            model=result.model or self._cache_model_for_provider(provider),
                            runtime_identity=self._runtime_identity_from_result(result),
                        ),
                    )

        # Combine cached and new results in original order and build summary
        all_results = []
        attempts = []
        batch_duration = time.time() - batch_start_time

        for template in templates:
            if template.name in bypassed_results:
                result = bypassed_results[template.name]
                all_results.append(result)
                attempts.append(
                    ExtractionAttempt(
                        template_name=template.name,
                        status=ExtractionStatus.SUCCESS,
                        result=result,
                        duration_seconds=0.0,
                    )
                )
            elif template.name in cached_results:
                result = cached_results[template.name]
                all_results.append(result)
                attempts.append(
                    ExtractionAttempt(
                        template_name=template.name,
                        status=ExtractionStatus.CACHED,
                        result=result,
                        duration_seconds=0.0,
                    )
                )
            elif template.name in batch_results:
                result = batch_results[template.name]
                all_results.append(result)

                # Determine status based on result success
                if result.success:
                    status = ExtractionStatus.SUCCESS
                else:
                    status = ExtractionStatus.FAILED

                attempts.append(
                    ExtractionAttempt(
                        template_name=template.name,
                        status=status,
                        result=result if result.success else None,
                        error_message=result.error if not result.success else None,
                        duration_seconds=batch_duration / len(uncached_templates),
                    )
                )
            else:
                # Template failed, create error result
                error_result = ExtractionResult(
                    episode_url=episode_url,
                    template_name=template.name,
                    template_version=template.version,
                    success=False,
                    error="Template not found in batch results",
                    cost_usd=0.0,
                    provider="gemini",  # Default to gemini for batched extraction
                )
                all_results.append(error_result)
                attempts.append(
                    ExtractionAttempt(
                        template_name=template.name,
                        status=ExtractionStatus.FAILED,
                        error_message="Template not found in batch results",
                        duration_seconds=batch_duration / len(templates),
                    )
                )

        summary = ExtractionSummary(
            total=len(templates),
            successful=sum(1 for a in attempts if a.status == ExtractionStatus.SUCCESS),
            failed=sum(1 for a in attempts if a.status == ExtractionStatus.FAILED),
            cached=sum(1 for a in attempts if a.status == ExtractionStatus.CACHED),
            attempts=attempts,
        )

        logger.info(
            f"Batch extraction complete: {summary.successful}/{summary.total} successful, "
            f"{summary.failed} failed, {summary.cached} cached"
        )

        return all_results, summary

    def estimate_total_cost(
        self,
        templates: list[ExtractionTemplate],
        transcript: str,
    ) -> float:
        """Estimate total cost for extracting all templates.

        Args:
            templates: List of extraction templates
            transcript: Full transcript text

        Returns:
            Estimated total cost in USD
        """
        total = 0.0
        for template in templates:
            extractor = self._select_extractor(template)
            cost = extractor.estimate_cost(template, len(transcript))
            total += cost
        return total

    def _select_extractor(self, template: ExtractionTemplate) -> BaseExtractor:
        """Select appropriate extractor for template.

        Selection priority:
        1. extractor_override parameter (explicit override)
        2. INKWELL_EXTRACTOR environment variable (environment override)
        3. Template's model_preference if specified
        4. Heuristics based on template type
        5. Default provider
        6. Highest priority plugin from registry

        Args:
            template: Extraction template

        Returns:
            Extractor instance (Claude, Gemini, or plugin)

        Raises:
            ValueError: If no extractor is available
        """
        override = self._extractor_override or os.environ.get("INKWELL_EXTRACTOR")
        if override:
            plugin = self.extraction_registry.get(override)
            if plugin:
                return plugin
            raise ValueError(
                f"Extractor '{override}' not found. "
                f"Available: {', '.join(n for n, _ in self.extraction_registry.get_enabled())}"
            )

        return self._select_extractor_from_registry(template)

    def _select_extractor_from_registry(self, template: ExtractionTemplate) -> BaseExtractor:
        """Select extractor using plugin registry.

        Args:
            template: Extraction template

        Returns:
            Extractor instance from registry

        Raises:
            ValueError: If no extractor plugins are available
        """
        # Template's explicit preference
        if template.model_preference and template.model_preference not in _LOCAL_RUNTIME_PROVIDERS:
            plugin = self.extraction_registry.get(template.model_preference)
            if plugin:
                return plugin

        enabled_plugins = [
            (name, plugin)
            for name, plugin in self.extraction_registry.get_enabled()
            if name not in _LOCAL_RUNTIME_PROVIDERS
        ]

        if not enabled_plugins:
            raise ValueError(
                "No extraction plugins available. "
                "Set GOOGLE_API_KEY or ANTHROPIC_API_KEY environment variable."
            )

        # Heuristics for auto-selection
        # Use Claude for quote extraction (precision critical)
        if "quote" in template.name.lower():
            claude_plugin = self.extraction_registry.get("claude")
            if claude_plugin:
                return claude_plugin

        if template.expected_format == "json" and template.output_schema:
            required_fields = template.output_schema.get("required", [])
            if len(required_fields) > 5:
                claude_plugin = self.extraction_registry.get("claude")
                if claude_plugin:
                    return claude_plugin

        # Default provider preference
        default_plugin = self.extraction_registry.get(self.default_provider)
        if default_plugin:
            return default_plugin

        return enabled_plugins[0][1]

    def _parse_output(self, raw_output: str, template: ExtractionTemplate) -> ExtractedContent:
        """Parse raw LLM output into ExtractedContent.

        Args:
            raw_output: Raw string from LLM
            template: Template used for extraction

        Returns:
            ExtractedContent with parsed data

        Raises:
            ValidationError: If parsing fails
        """
        if template.expected_format == "json":
            try:
                # 5MB for extraction results, depth of 10 for structured data
                data = safe_json_loads(raw_output, max_size=5_000_000, max_depth=10)
                return ExtractedContent(
                    template_name=template.name,
                    content=data,
                )
            except JSONParsingError as e:
                raise ValidationError(f"Invalid JSON output: {str(e)}") from e

        elif template.expected_format == "markdown":
            return ExtractedContent(
                template_name=template.name,
                content=raw_output,
            )

        elif template.expected_format == "yaml":
            import yaml

            try:
                data = yaml.safe_load(raw_output)
                return ExtractedContent(
                    template_name=template.name,
                    content=data,
                )
            except yaml.YAMLError as e:
                raise ValidationError(f"Invalid YAML output: {str(e)}") from e

        else:  # text
            return ExtractedContent(
                template_name=template.name,
                content=raw_output,
            )

    def get_total_cost(self) -> float:
        """Get total cost accumulated so far.

        Returns:
            Total cost in USD
        """
        if self.cost_tracker:
            return self.cost_tracker.get_session_cost()
        return 0.0

    def reset_cost_tracking(self) -> None:
        """Reset cost tracking to zero."""
        if self.cost_tracker:
            self.cost_tracker.reset_session_cost()

    def _create_batch_prompt(
        self,
        templates: list[ExtractionTemplate],
        transcript: str,
        metadata: dict[str, Any],
    ) -> str:
        """Create combined prompt for multiple templates.

        Args:
            templates: Templates to extract
            transcript: Episode transcript
            metadata: Episode metadata

        Returns:
            Combined prompt string

        Example:
            Prompt format:
            '''
            Analyze this podcast transcript and provide multiple extractions:

            1. SUMMARY:
            [template instructions]

            2. QUOTES:
            [template instructions]

            3. KEY CONCEPTS:
            [template instructions]

            TRANSCRIPT:
            [full transcript]

            Provide your response as JSON:
            {
                "summary": "...",
                "quotes": [...],
                "key-concepts": [...]
            }
            '''
        """
        import json

        instructions = []
        for i, template in enumerate(templates, 1):
            task_name = template.name.upper().replace("-", " ").replace("_", " ")
            instructions.append(f"{i}. {task_name}:")
            instructions.append(f"   Description: {template.description}")

            user_prompt = self._select_extractor(template).build_prompt(
                template, "{{transcript}}", metadata
            )
            instructions.append(f"   Instructions: {user_prompt}")

            if template.expected_format == "json" and template.output_schema:
                schema_str = json.dumps(template.output_schema, indent=2)
                instructions.append(f"   Expected format: {schema_str}")
            else:
                instructions.append(f"   Expected format: {template.expected_format}")

            instructions.append("")

        schema = {template.name: f"<{template.expected_format} content>" for template in templates}

        prompt = f"""
Analyze this podcast transcript and provide multiple extractions.

PODCAST INFORMATION:
- Title: {metadata.get("episode_title", "Unknown")}
- Podcast: {metadata.get("podcast_name", "Unknown")}
- URL: {metadata.get("episode_url", "Unknown")}

EXTRACTION TASKS:
{chr(10).join(instructions)}

TRANSCRIPT:
{transcript}

IMPORTANT: Provide your response as a single JSON object with the following structure:
{json.dumps(schema, indent=2)}

Each field should contain the extracted information for that task.
Use the exact template names as JSON keys.
""".strip()

        return prompt

    def _parse_batch_response(
        self,
        response: str,
        templates: list[ExtractionTemplate],
        episode_url: str,
        provider_name: str,
        estimated_cost: float,
    ) -> dict[str, ExtractionResult]:
        """Parse batched LLM response into individual results.

        Args:
            response: LLM response text
            templates: Templates that were batched
            episode_url: Episode URL for results
            provider_name: Provider used for extraction
            estimated_cost: Total estimated cost for batch

        Returns:
            Dict mapping template name to ExtractionResult

        Raises:
            ValueError: If response cannot be parsed
        """
        import json

        try:
            # Extract JSON from response
            json_start = response.find("{")
            json_end = response.rfind("}") + 1

            if json_start == -1 or json_end == 0:
                raise ValueError("No JSON object found in response")

            json_str = response[json_start:json_end]
            data = safe_json_loads(json_str, max_size=5_000_000, max_depth=10)

            results = {}
            cost_per_template = estimated_cost / len(templates)

            for template in templates:
                template_data = data.get(template.name)

                if template_data is None:
                    # Template not in response
                    results[template.name] = ExtractionResult(
                        episode_url=episode_url,
                        template_name=template.name,
                        template_version=template.version,
                        success=False,
                        error=f"Missing '{template.name}' in batch response",
                        cost_usd=0.0,
                        provider=provider_name,
                    )
                else:
                    if template.expected_format == "json":
                        # Data is already parsed, but ensure it's str or dict
                        if isinstance(template_data, (str, dict)):
                            content_data = template_data
                        elif isinstance(template_data, list):
                            # Wrap list in dict with template name as key
                            content_data = {template.name: template_data}
                        else:
                            content_data = {"data": template_data}

                        content = ExtractedContent(
                            template_name=template.name,
                            content=content_data,
                        )
                    else:
                        # For text/markdown/yaml, data should be string
                        if not isinstance(template_data, str):
                            template_data = json.dumps(template_data)

                        content = ExtractedContent(
                            template_name=template.name,
                            content=template_data,
                        )

                    results[template.name] = ExtractionResult(
                        episode_url=episode_url,
                        template_name=template.name,
                        template_version=template.version,
                        success=True,
                        extracted_content=content,
                        cost_usd=cost_per_template,
                        provider=provider_name,
                    )

            return results

        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to parse batch response: {e}")
            raise ValueError(f"Invalid batch response format: {e}") from e

    async def _extract_individually(
        self,
        templates: list[ExtractionTemplate],
        transcript: str,
        metadata: dict[str, Any],
        episode_url: str,
    ) -> dict[str, ExtractionResult]:
        """Extract templates individually in parallel.

        Each template gets its own focused LLM call for better reliability.

        Args:
            templates: Templates to extract
            transcript: Episode transcript
            metadata: Episode metadata
            episode_url: Episode URL for results

        Returns:
            Dict mapping template name to ExtractionResult
        """
        import asyncio

        tasks = [
            self.extract(template, transcript, metadata, use_cache=False) for template in templates
        ]

        results_list = await asyncio.gather(*tasks, return_exceptions=True)

        results = {}
        for template, result in zip(templates, results_list, strict=False):
            if isinstance(result, ExtractionResult):
                results[template.name] = result
            elif isinstance(result, Exception):
                results[template.name] = ExtractionResult(
                    episode_url=episode_url,
                    template_name=template.name,
                    template_version=template.version,
                    success=False,
                    error=str(result),
                    cost_usd=0.0,
                    provider="unknown",
                )

        return results

    def _serialize_extracted_content(self, content: ExtractedContent) -> str:
        """Serialize ExtractedContent for caching.

        Args:
            content: Extracted content to serialize

        Returns:
            String representation suitable for caching
        """
        import json

        if isinstance(content.content, dict):
            return json.dumps(content.content)
        elif isinstance(content.content, str):
            return content.content
        else:
            return str(content.content)
