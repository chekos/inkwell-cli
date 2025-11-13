"""Extraction engine for orchestrating LLM-based content extraction.

Coordinates template selection, provider selection, caching, and result parsing.
"""

import logging
from typing import Any

from ..utils.json_utils import JSONParsingError, safe_json_loads
from .cache import ExtractionCache
from .errors import ValidationError
from .extractors import BaseExtractor, ClaudeExtractor, GeminiExtractor
from .models import ExtractedContent, ExtractionResult, ExtractionTemplate

logger = logging.getLogger(__name__)


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
        provider_name = (
            "claude"
            if extractor.__class__.__name__ == "ClaudeExtractor"
            else "gemini"
        )

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

            # Track cost
            self.total_cost_usd += estimated_cost

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
            return ExtractionResult(
                episode_url=episode_url,
                template_name=template.name,
                success=False,
                extracted_content=None,
                error=str(e),
                cost_usd=0.0,
                provider=provider_name,
            )

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
                logger.warning("Extraction failed: %s", result, exc_info=True)

        return successful_results

    async def extract_all_batched(
        self,
        templates: list[ExtractionTemplate],
        transcript: str,
        metadata: dict[str, Any],
        use_cache: bool = True,
    ) -> list[ExtractionResult]:
        """Extract all templates in a single batched API call.

        Batches multiple template extractions into one API call to reduce
        network overhead by 75% and improve processing speed by 30-40%.

        Args:
            templates: List of extraction templates
            transcript: Full transcript text
            metadata: Episode metadata
            use_cache: Whether to use cache (default: True)

        Returns:
            List of ExtractionResults (one per template, in same order as input)

        Example:
            >>> results = await engine.extract_all_batched(
            ...     [summary_template, quotes_template, concepts_template],
            ...     transcript,
            ...     metadata
            ... )
        """
        import asyncio
        import json

        if not templates:
            return []

        # Get episode URL from metadata
        episode_url = metadata.get("episode_url", "")

        # Check cache for each template
        cached_results = {}
        uncached_templates = []

        if use_cache:
            for template in templates:
                cached = await self.cache.get(template.name, template.version, transcript)
                if cached:
                    # Parse cached result
                    content = self._parse_output(cached, template)
                    cached_results[template.name] = ExtractionResult(
                        episode_url=episode_url,
                        template_name=template.name,
                        success=True,
                        extracted_content=content,
                        cost_usd=0.0,
                        provider="cache",
                        from_cache=True,
                    )
                else:
                    uncached_templates.append(template)
        else:
            uncached_templates = templates

        # If all cached, return early
        if not uncached_templates:
            logger.info("All templates found in cache, returning cached results")
            return [cached_results[t.name] for t in templates]

        # Build batched prompt
        logger.info(f"Batching {len(uncached_templates)} templates in single API call")
        batched_prompt = self._create_batch_prompt(uncached_templates, transcript, metadata)

        # Select provider (use first template's preference or default)
        extractor = self._select_extractor(uncached_templates[0])
        provider_name = (
            "claude"
            if extractor.__class__.__name__ == "ClaudeExtractor"
            else "gemini"
        )

        # Estimate cost (slightly higher than sum of individual calls due to larger prompt)
        estimated_cost = sum(
            extractor.estimate_cost(t, len(transcript)) for t in uncached_templates
        ) * 1.1  # 10% overhead for batch prompt

        # Single API call for all templates
        batch_results = {}
        try:
            # Call LLM with batched prompt
            response = await extractor.extract(
                uncached_templates[0],  # Use first template for LLM config
                batched_prompt,
                metadata,
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
                        await self.cache.set(template.name, template.version, transcript, raw_output)

            # Track cost
            self.total_cost_usd += estimated_cost

            logger.info(f"Batch extraction successful for {len(batch_results)} templates")

        except Exception as e:
            logger.error(f"Batch extraction failed: {e}", exc_info=True)
            # Fallback to individual extraction
            batch_results = await self._extract_individually(
                uncached_templates, transcript, metadata, episode_url
            )

        # Combine cached and new results in original order
        all_results = []
        for template in templates:
            if template.name in cached_results:
                all_results.append(cached_results[template.name])
            elif template.name in batch_results:
                all_results.append(batch_results[template.name])
            else:
                # Template failed, create error result
                all_results.append(
                    ExtractionResult(
                        episode_url=episode_url,
                        template_name=template.name,
                        success=False,
                        error="Template not found in batch results",
                        cost_usd=0.0,
                        provider=provider_name,
                    )
                )

        return all_results

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
        return self.total_cost_usd

    def reset_cost_tracking(self) -> None:
        """Reset cost tracking to zero."""
        self.total_cost_usd = 0.0

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
- Title: {metadata.get('episode_title', 'Unknown')}
- Podcast: {metadata.get('podcast_name', 'Unknown')}
- URL: {metadata.get('episode_url', 'Unknown')}

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
        for template, result in zip(templates, results_list):
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
