"""Extraction engine for orchestrating LLM-based content extraction.

Coordinates template selection, provider selection, caching, and result parsing.
"""

import json
from typing import Any

from .cache import ExtractionCache
from .errors import ExtractionError, ValidationError
from .extractors import BaseExtractor, ClaudeExtractor, GeminiExtractor
from .models import ExtractedContent, ExtractionResult, ExtractionTemplate


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
        claude_api_key: str | None = None,
        gemini_api_key: str | None = None,
        cache: ExtractionCache | None = None,
        default_provider: str = "gemini",
    ) -> None:
        """Initialize extraction engine.

        Args:
            claude_api_key: Anthropic API key (defaults to env var)
            gemini_api_key: Google AI API key (defaults to env var)
            cache: Cache instance (defaults to new ExtractionCache)
            default_provider: Default provider to use ("claude" or "gemini")
        """
        self.claude_extractor = ClaudeExtractor(api_key=claude_api_key)
        self.gemini_extractor = GeminiExtractor(api_key=gemini_api_key)
        self.cache = cache or ExtractionCache()
        self.default_provider = default_provider

        # Track total cost
        self.total_cost_usd = 0.0

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
        # Check cache first
        if use_cache:
            cached = self.cache.get(template.name, template.version, transcript)
            if cached:
                # Parse cached result
                content = self._parse_output(cached, template)
                return ExtractionResult(
                    template_name=template.name,
                    content=content,
                    cost_usd=0.0,  # Cached, no cost
                    provider="cache",
                )

        # Select provider
        extractor = self._select_extractor(template)
        provider_name = "claude" if isinstance(extractor, ClaudeExtractor) else "gemini"

        # Estimate cost
        estimated_cost = extractor.estimate_cost(template, len(transcript))

        try:
            # Extract
            raw_output = await extractor.extract(template, transcript, metadata)

            # Parse output
            content = self._parse_output(raw_output, template)

            # Cache result
            if use_cache:
                self.cache.set(template.name, template.version, transcript, raw_output)

            # Track cost
            self.total_cost_usd += estimated_cost

            return ExtractionResult(
                template_name=template.name,
                content=content,
                cost_usd=estimated_cost,
                provider=provider_name,
            )

        except Exception as e:
            # Wrap errors
            if isinstance(e, ExtractionError):
                raise
            raise ExtractionError(f"Extraction failed: {str(e)}") from e

    async def extract_all(
        self,
        templates: list[ExtractionTemplate],
        transcript: str,
        metadata: dict[str, Any],
        use_cache: bool = True,
    ) -> list[ExtractionResult]:
        """Extract content using multiple templates.

        Processes templates concurrently for better performance.

        Args:
            templates: List of extraction templates
            transcript: Full transcript text
            metadata: Episode metadata
            use_cache: Whether to use cache (default: True)

        Returns:
            List of ExtractionResults (one per template)
        """
        import asyncio

        # Extract concurrently
        tasks = [
            self.extract(template, transcript, metadata, use_cache) for template in templates
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out exceptions (return successful results only)
        # TODO: Better error handling - log failures, allow partial success
        successful_results = []
        for result in results:
            if isinstance(result, ExtractionResult):
                successful_results.append(result)
            elif isinstance(result, Exception):
                # Log error but continue
                # In production, would use proper logging
                print(f"Warning: Extraction failed: {result}")

        return successful_results

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
        # Explicit preference
        if template.model_preference == "claude":
            return self.claude_extractor
        elif template.model_preference == "gemini":
            return self.gemini_extractor

        # Heuristics for auto-selection
        # Use Claude for:
        # - Quote extraction (precision critical)
        # - Complex structured data (many required fields)
        if "quote" in template.name.lower():
            return self.claude_extractor

        if template.expected_format == "json" and template.output_schema:
            required_fields = template.output_schema.get("required", [])
            if len(required_fields) > 5:  # Complex schema
                return self.claude_extractor

        # Default provider
        if self.default_provider == "claude":
            return self.claude_extractor
        else:
            return self.gemini_extractor

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
                data = json.loads(raw_output)
                return ExtractedContent(
                    format="json",
                    data=data,
                    raw=raw_output,
                )
            except json.JSONDecodeError as e:
                raise ValidationError(f"Invalid JSON output: {str(e)}") from e

        elif template.expected_format == "markdown":
            return ExtractedContent(
                format="markdown",
                data={"text": raw_output},
                raw=raw_output,
            )

        elif template.expected_format == "yaml":
            import yaml

            try:
                data = yaml.safe_load(raw_output)
                return ExtractedContent(
                    format="yaml",
                    data=data,
                    raw=raw_output,
                )
            except yaml.YAMLError as e:
                raise ValidationError(f"Invalid YAML output: {str(e)}") from e

        else:  # text
            return ExtractedContent(
                format="text",
                data={"text": raw_output},
                raw=raw_output,
            )

    def get_total_cost(self) -> float:
        """Get total cost accumulated so far.

        Returns:
            Total cost in USD
        """
        return self.total_cost_usd

    def reset_cost_tracking(self) -> None:
        """Reset cost tracking to zero."""
        self.total_cost_usd = 0.0
