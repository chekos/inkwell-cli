"""Extraction engine for orchestrating LLM-based content extraction.

Coordinates template selection, provider selection, caching, and result parsing.
"""

import logging
import re
import time
import warnings

# Type-only import to avoid circular dependency
from typing import TYPE_CHECKING, Any

from ..config.precedence import resolve_config_value
from ..config.schema import ExtractionConfig
from ..utils.errors import ValidationError
from ..utils.json_utils import JSONParsingError, safe_json_loads
from .cache import ExtractionCache
from .extractors import BaseExtractor, ClaudeExtractor, GeminiExtractor
from .models import (
    ExtractedContent,
    ExtractionAttempt,
    ExtractionResult,
    ExtractionStatus,
    ExtractionSummary,
    ExtractionTemplate,
)

if TYPE_CHECKING:
    from ..utils.costs import CostTracker

logger = logging.getLogger(__name__)


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
    ) -> None:
        """Initialize extraction engine.

        Args:
            config: Extraction configuration (recommended, new approach)
            claude_api_key: Anthropic API key (defaults to env var) [deprecated, use config]
            gemini_api_key: Google AI API key (defaults to env var) [deprecated, use config]
            cache: Cache instance (defaults to new ExtractionCache)
            default_provider: Default provider ("claude" or "gemini") [deprecated]
            cost_tracker: Cost tracker for recording API usage (optional, for DI)

        Note:
            Prefer passing `config` over individual parameters. Individual parameters
            are maintained for backward compatibility but will be deprecated in v2.0.
        """
        # Warn if using deprecated individual parameters
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

        # Store API keys for lazy initialization
        self._claude_api_key = effective_claude_key
        self._gemini_api_key = effective_gemini_key
        self._claude_extractor: ClaudeExtractor | None = None
        self._gemini_extractor: GeminiExtractor | None = None

        self.cache = cache or ExtractionCache()
        self.default_provider = effective_provider
        self.cost_tracker = cost_tracker

    @property
    def claude_extractor(self) -> ClaudeExtractor:
        """Lazily initialize Claude extractor."""
        if self._claude_extractor is None:
            self._claude_extractor = ClaudeExtractor(api_key=self._claude_api_key)
        return self._claude_extractor

    @property
    def gemini_extractor(self) -> GeminiExtractor:
        """Lazily initialize Gemini extractor."""
        if self._gemini_extractor is None:
            self._gemini_extractor = GeminiExtractor(api_key=self._gemini_api_key)
        return self._gemini_extractor

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
        # Get episode URL from metadata
        episode_url = metadata.get("episode_url", "")

        # Check cache first
        if use_cache:
            cached = await self.cache.get(template.name, template.version, transcript)
            if cached:
                # Parse cached result
                content = self._parse_output(cached, template)
                return ExtractionResult(
                    episode_url=episode_url,
                    template_name=template.name,
                    success=True,
                    extracted_content=content,
                    cost_usd=0.0,  # Cached, no cost
                    provider="cache",
                    from_cache=True,
                )

        # Select provider
        extractor = self._select_extractor(template)
        provider_name = "claude" if extractor.__class__.__name__ == "ClaudeExtractor" else "gemini"

        # Estimate cost
        estimated_cost = extractor.estimate_cost(template, len(transcript))

        try:
            # Extract
            raw_output = await extractor.extract(template, transcript, metadata)

            # Parse output
            content = self._parse_output(raw_output, template)

            # Cache result
            if use_cache:
                await self.cache.set(template.name, template.version, transcript, raw_output)

            # Track cost in CostTracker if available
            if self.cost_tracker:
                # Estimate token counts based on transcript length
                # This is an approximation; real token counts would come from API response
                input_tokens = len(transcript) // 4  # Rough approximation
                output_tokens = len(raw_output) // 4

                self.cost_tracker.add_cost(
                    provider=provider_name,
                    model=extractor.model if hasattr(extractor, "model") else "unknown",
                    operation="extraction",
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    episode_title=metadata.get("episode_title"),
                    template_name=template.name,
                )

            return ExtractionResult(
                episode_url=episode_url,
                template_name=template.name,
                success=True,
                extracted_content=content,
                cost_usd=estimated_cost,
                provider=provider_name,
            )

        except Exception as e:
            # Return failed result instead of raising
            # Sanitize error message to prevent API key leakage
            error_msg = _sanitize_error_message(str(e))
            return ExtractionResult(
                episode_url=episode_url,
                template_name=template.name,
                success=False,
                extracted_content=None,
                error=error_msg,
                cost_usd=0.0,
                provider=provider_name,
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

        # Track timing for each extraction
        start_times = {}

        async def extract_with_tracking(template: ExtractionTemplate) -> ExtractionResult:
            """Extract and track timing."""
            start_times[template.name] = time.time()
            return await self.extract(template, transcript, metadata, use_cache)

        # Extract concurrently
        tasks = [extract_with_tracking(template) for template in templates]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Build detailed summary
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

        # Build summary
        summary = ExtractionSummary(
            total=len(templates),
            successful=sum(1 for a in attempts if a.status == ExtractionStatus.SUCCESS),
            failed=sum(1 for a in attempts if a.status == ExtractionStatus.FAILED),
            cached=sum(1 for a in attempts if a.status == ExtractionStatus.CACHED),
            attempts=attempts,
        )

        # Log summary
        logger.info(
            f"Extraction complete: {summary.successful}/{summary.total} successful, "
            f"{summary.failed} failed, {summary.cached} cached"
        )

        return successful_results, summary

    async def _batch_cache_lookup(
        self,
        templates: list[ExtractionTemplate],
        transcript: str,
        episode_url: str,
    ) -> dict[str, ExtractionResult]:
        """Lookup multiple templates in cache concurrently.

        Args:
            templates: List of templates to check
            transcript: Episode transcript for cache key
            episode_url: Episode URL for results

        Returns:
            Dict mapping template name to ExtractionResult (only cache hits)
        """
        import asyncio

        async def lookup_one(
            template: ExtractionTemplate,
        ) -> tuple[ExtractionTemplate, str | None]:
            """Lookup single template in cache."""
            result = await self.cache.get(
                template.name,
                template.version,
                transcript,
            )
            return (template, result)

        # Run all lookups in parallel
        results = await asyncio.gather(*[lookup_one(t) for t in templates])

        # Filter to only cache hits and parse results
        cached_results = {}
        for template, cached_raw in results:
            if cached_raw is not None:
                # Parse cached result
                content = self._parse_output(cached_raw, template)
                cached_results[template.name] = ExtractionResult(
                    episode_url=episode_url,
                    template_name=template.name,
                    success=True,
                    extracted_content=content,
                    cost_usd=0.0,
                    provider="cache",
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

        # Track timing
        batch_start_time = time.time()

        # Get episode URL from metadata
        episode_url = metadata.get("episode_url", "")

        # Check cache for all templates in parallel
        cached_results = {}
        uncached_templates = []

        if use_cache:
            # Batch lookup all templates at once
            cache_start = time.time()
            cached_results = await self._batch_cache_lookup(templates, transcript, episode_url)
            cache_duration = time.time() - cache_start

            # Log cache performance
            logger.debug(
                f"Cache lookup took {cache_duration:.3f}s for {len(templates)} templates "
                f"({len(cached_results)} hits, {len(templates) - len(cached_results)} misses)"
            )

            # Separate cached from uncached
            for template in templates:
                if template.name not in cached_results:
                    uncached_templates.append(template)
        else:
            uncached_templates = templates

        # If all cached, return early with summary
        if not uncached_templates:
            logger.info("All templates found in cache, returning cached results")
            results_list = [cached_results[t.name] for t in templates]

            # Build summary for all-cached scenario
            attempts = [
                ExtractionAttempt(
                    template_name=t.name,
                    status=ExtractionStatus.CACHED,
                    result=cached_results[t.name],
                    duration_seconds=0.0,
                )
                for t in templates
            ]
            summary = ExtractionSummary(
                total=len(templates),
                successful=0,
                failed=0,
                cached=len(templates),
                attempts=attempts,
            )
            return results_list, summary

        # Build batched prompt
        logger.info(f"Batching {len(uncached_templates)} templates in single API call")
        batched_prompt = self._create_batch_prompt(uncached_templates, transcript, metadata)

        # Select provider (use first template's preference or default)
        extractor = self._select_extractor(uncached_templates[0])
        provider_name = "claude" if extractor.__class__.__name__ == "ClaudeExtractor" else "gemini"

        # Estimate cost (slightly higher than sum of individual calls due to larger prompt)
        estimated_cost = (
            sum(extractor.estimate_cost(t, len(transcript)) for t in uncached_templates) * 1.1
        )  # 10% overhead for batch prompt

        # Single API call for all templates
        batch_results = {}
        try:
            # Calculate total max_tokens for all templates
            total_max_tokens = sum(t.max_tokens for t in uncached_templates)

            # Call LLM with batched prompt
            # Force JSON mode since batch responses must be JSON
            response = await extractor.extract(
                uncached_templates[0],  # Use first template for LLM config
                batched_prompt,
                metadata,
                force_json=True,
                max_tokens_override=total_max_tokens,
            )

            # Parse batch response
            batch_results = self._parse_batch_response(
                response, uncached_templates, episode_url, provider_name, estimated_cost
            )

            # Cache individual results
            if use_cache:
                for template in uncached_templates:
                    result = batch_results.get(template.name)
                    if result and result.success and result.extracted_content:
                        # Cache the raw output for this template
                        raw_output = self._serialize_extracted_content(result.extracted_content)
                        await self.cache.set(
                            template.name, template.version, transcript, raw_output
                        )

            # Track cost in CostTracker if available
            if self.cost_tracker:
                # Estimate token counts for batch operation
                input_tokens = len(batched_prompt) // 4
                output_tokens = len(response) // 4

                # Track once for the batch (distributed across templates)
                for template in uncached_templates:
                    self.cost_tracker.add_cost(
                        provider=provider_name,
                        model=extractor.model if hasattr(extractor, "model") else "unknown",
                        operation="extraction",
                        input_tokens=input_tokens // len(uncached_templates),
                        output_tokens=output_tokens // len(uncached_templates),
                        episode_title=metadata.get("episode_title"),
                        template_name=template.name,
                    )

            logger.info(f"Batch extraction successful for {len(batch_results)} templates")

        except Exception as e:
            # Sanitize error message to prevent API key leakage in logs
            sanitized_error_msg = _sanitize_error_message(str(e))
            logger.error(f"Batch extraction failed: {sanitized_error_msg}", exc_info=True)
            # Fallback to individual extraction
            batch_results = await self._extract_individually(
                uncached_templates, transcript, metadata, episode_url
            )

        # Combine cached and new results in original order and build summary
        all_results = []
        attempts = []
        batch_duration = time.time() - batch_start_time

        for template in templates:
            if template.name in cached_results:
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
                    success=False,
                    error="Template not found in batch results",
                    cost_usd=0.0,
                    provider=provider_name,
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

        # Build summary
        summary = ExtractionSummary(
            total=len(templates),
            successful=sum(1 for a in attempts if a.status == ExtractionStatus.SUCCESS),
            failed=sum(1 for a in attempts if a.status == ExtractionStatus.FAILED),
            cached=sum(1 for a in attempts if a.status == ExtractionStatus.CACHED),
            attempts=attempts,
        )

        # Log summary
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

        Uses template's model_preference if specified, otherwise uses heuristics.

        Args:
            template: Extraction template

        Returns:
            Extractor instance (Claude or Gemini)
        """
        # Check which extractors are available (have API keys)
        claude_available = self._claude_api_key is not None
        gemini_available = self._gemini_api_key is not None

        # Explicit preference (only if available, fallback otherwise)
        if template.model_preference == "claude":
            if claude_available:
                return self.claude_extractor
            # Fall through to use gemini if claude not available
        elif template.model_preference == "gemini":
            if gemini_available:
                return self.gemini_extractor
            # Fall through to use claude if gemini not available

        # Heuristics for auto-selection (only if extractor is available)
        # Use Claude for:
        # - Quote extraction (precision critical)
        # - Complex structured data (many required fields)
        if claude_available:
            if "quote" in template.name.lower():
                return self.claude_extractor

            if template.expected_format == "json" and template.output_schema:
                required_fields = template.output_schema.get("required", [])
                if len(required_fields) > 5:  # Complex schema
                    return self.claude_extractor

        # Default provider (if available)
        if self.default_provider == "claude" and claude_available:
            return self.claude_extractor
        elif gemini_available:
            return self.gemini_extractor
        elif claude_available:
            return self.claude_extractor
        else:
            raise ValueError(
                "No extraction provider available. Set GOOGLE_API_KEY or ANTHROPIC_API_KEY."
            )

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
                # Use safe JSON parsing with size/depth limits
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

        # Build combined instructions
        instructions = []
        for i, template in enumerate(templates, 1):
            task_name = template.name.upper().replace("-", " ").replace("_", " ")
            instructions.append(f"{i}. {task_name}:")
            instructions.append(f"   Description: {template.description}")

            # Use the template's user prompt
            user_prompt = self._select_extractor(template).build_prompt(
                template, "{{transcript}}", metadata
            )
            instructions.append(f"   Instructions: {user_prompt}")

            # Add format hint
            if template.expected_format == "json" and template.output_schema:
                schema_str = json.dumps(template.output_schema, indent=2)
                instructions.append(f"   Expected format: {schema_str}")
            else:
                instructions.append(f"   Expected format: {template.expected_format}")

            instructions.append("")

        # Build JSON schema showing expected structure
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

            # Create results for each template
            results = {}
            cost_per_template = estimated_cost / len(templates)

            for template in templates:
                template_data = data.get(template.name)

                if template_data is None:
                    # Template not in response
                    results[template.name] = ExtractionResult(
                        episode_url=episode_url,
                        template_name=template.name,
                        success=False,
                        error=f"Missing '{template.name}' in batch response",
                        cost_usd=0.0,
                        provider=provider_name,
                    )
                else:
                    # Convert to ExtractedContent
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
        """Fallback: extract templates individually if batch fails.

        Args:
            templates: Templates to extract
            transcript: Episode transcript
            metadata: Episode metadata
            episode_url: Episode URL for results

        Returns:
            Dict mapping template name to ExtractionResult
        """
        import asyncio

        logger.warning(
            f"Batch extraction failed, falling back to individual extraction "
            f"for {len(templates)} templates"
        )

        tasks = [
            self.extract(template, transcript, metadata, use_cache=False) for template in templates
        ]

        results_list = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert to dict
        results = {}
        for template, result in zip(templates, results_list, strict=False):
            if isinstance(result, ExtractionResult):
                results[template.name] = result
            elif isinstance(result, Exception):
                # Create error result
                results[template.name] = ExtractionResult(
                    episode_url=episode_url,
                    template_name=template.name,
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
