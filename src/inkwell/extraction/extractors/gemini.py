"""Gemini (Google AI) extractor implementation using modern google-genai SDK."""

import asyncio
from typing import Any

from google import genai
from google.genai import types

from ...utils.api_keys import get_validated_api_key
from ...utils.errors import APIError, ValidationError
from ...utils.json_utils import JSONParsingError, safe_json_loads
from ...utils.rate_limiter import get_rate_limiter
from ..models import ExtractionTemplate
from .base import BaseExtractor


class GeminiExtractor(BaseExtractor):
    """Extractor using Gemini (Google AI) API.

    Supports Gemini 2.5 Flash with:
    - Fast, cost-effective extraction
    - Good quality for most tasks
    - Native JSON mode for structured output
    - Long context support (1M tokens)

    Cost (as of Nov 2024):
    - Input: $0.075 per million tokens (<128K tokens)
    - Input: $0.15 per million tokens (>128K tokens)
    - Output: $0.30 per million tokens
    """

    # Model to use
    MODEL = "gemini-2.5-flash"

    # Pricing per million tokens (USD)
    INPUT_PRICE_PER_M_SHORT = 0.075  # < 128K tokens
    INPUT_PRICE_PER_M_LONG = 0.15  # > 128K tokens
    OUTPUT_PRICE_PER_M = 0.30
    CONTEXT_THRESHOLD = 128_000  # Token threshold for pricing

    def __init__(self, api_key: str | None = None) -> None:
        """Initialize Gemini extractor.

        Args:
            api_key: Google AI API key (defaults to GOOGLE_API_KEY env var)

        Raises:
            APIKeyError: If API key not provided or invalid
        """
        # Validate API key
        if api_key:
            # If provided directly, still validate it
            from ...utils.api_keys import validate_api_key

            self.api_key = validate_api_key(api_key, "gemini", "GOOGLE_API_KEY")
        else:
            # Get from environment and validate
            self.api_key = get_validated_api_key("GOOGLE_API_KEY", "gemini")

        # Initialize client with new SDK
        self.client = genai.Client(api_key=self.api_key)

    async def extract(
        self,
        template: ExtractionTemplate,
        transcript: str,
        metadata: dict[str, Any],
        force_json: bool = False,
        max_tokens_override: int | None = None,
    ) -> str:
        """Extract content using Gemini.

        Args:
            template: Extraction template configuration
            transcript: Full transcript text (or pre-built batched prompt)
            metadata: Episode metadata
            force_json: Force JSON response mode (for batch extraction)
            max_tokens_override: Override template's max_tokens (for batch extraction)

        Returns:
            Raw LLM response string

        Raises:
            ProviderError: If API call fails
            ValidationError: If response format invalid
        """
        # For batch extraction (force_json=True), transcript IS the pre-built prompt
        # Otherwise, build prompt from template
        if force_json:
            # Transcript is already the full batched prompt
            full_prompt = transcript
        else:
            # Build prompt normally
            user_prompt = self.build_prompt(template, transcript, metadata)
            # Combine system prompt and user prompt
            # Gemini doesn't have separate system message, so prepend it
            full_prompt = f"{template.system_prompt}\n\n{user_prompt}"

        # Build generation config
        max_tokens = max_tokens_override if max_tokens_override else template.max_tokens
        config_kwargs: dict[str, Any] = {
            "temperature": template.temperature,
            "max_output_tokens": max_tokens,
        }

        # Add JSON mode if expected format is JSON or forced (for batch extraction)
        if force_json or (template.expected_format == "json" and template.output_schema):
            config_kwargs["response_mime_type"] = "application/json"
            # Pass schema if available and not in batch mode (batch has its own schema)
            if not force_json and template.output_schema:
                config_kwargs["response_json_schema"] = template.output_schema

        config = types.GenerateContentConfig(**config_kwargs)

        try:
            # Apply rate limiting before API call
            limiter = get_rate_limiter("gemini")
            limiter.acquire()

            # Make async API call using thread pool (SDK is sync)
            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=self.MODEL,
                contents=full_prompt,
                config=config,
            )

            # Extract text from response
            if not response.text:
                raise ValidationError("Empty response from Gemini")

            result = response.text

            # Validate JSON if schema provided (and not forced - batch handles its own validation)
            if not force_json and template.expected_format == "json" and template.output_schema:
                self._validate_json_output(result, template.output_schema)

            return result

        except Exception as e:
            if isinstance(e, ValidationError):
                raise

            # Wrap API errors
            raise APIError(f"Gemini API error: {str(e)}", provider="gemini") from e

    def estimate_cost(
        self,
        template: ExtractionTemplate,
        transcript_length: int,
    ) -> float:
        """Estimate extraction cost in USD.

        Args:
            template: Extraction template (for system prompt, max_tokens)
            transcript_length: Length of transcript in characters

        Returns:
            Estimated cost in USD
        """
        # Estimate input tokens
        system_tokens = self._count_tokens(template.system_prompt)
        user_prompt_base = self._count_tokens(template.user_prompt_template)
        transcript_tokens = self._count_tokens(" " * transcript_length)

        # Add tokens for few-shot examples
        examples_tokens = 0
        if template.few_shot_examples:
            for example in template.few_shot_examples:
                examples_tokens += self._count_tokens(str(example))

        input_tokens = system_tokens + user_prompt_base + transcript_tokens + examples_tokens

        # Output tokens from template config
        output_tokens = template.max_tokens

        # Calculate input cost (tiered pricing)
        if input_tokens < self.CONTEXT_THRESHOLD:
            input_cost = (input_tokens / 1_000_000) * self.INPUT_PRICE_PER_M_SHORT
        else:
            # First 128K at short rate, rest at long rate
            short_cost = (self.CONTEXT_THRESHOLD / 1_000_000) * self.INPUT_PRICE_PER_M_SHORT
            long_tokens = input_tokens - self.CONTEXT_THRESHOLD
            long_cost = (long_tokens / 1_000_000) * self.INPUT_PRICE_PER_M_LONG
            input_cost = short_cost + long_cost

        # Calculate output cost
        output_cost = (output_tokens / 1_000_000) * self.OUTPUT_PRICE_PER_M

        return input_cost + output_cost

    def supports_structured_output(self) -> bool:
        """Whether Gemini supports structured output.

        Returns:
            True (Gemini supports JSON mode via response_mime_type)
        """
        return True

    def _validate_json_output(self, output: str, schema: dict[str, Any]) -> None:
        """Validate JSON output against schema.

        Args:
            output: JSON string from LLM
            schema: JSON Schema to validate against

        Raises:
            ValidationError: If validation fails
        """
        try:
            # Use safe JSON parsing with size/depth limits
            # 5MB for extraction results, depth of 10 for structured data
            data = safe_json_loads(output, max_size=5_000_000, max_depth=10)
        except JSONParsingError as e:
            raise ValidationError(f"Invalid JSON from Gemini: {str(e)}") from e

        # Basic schema validation
        if "required" in schema:
            for field in schema["required"]:
                if field not in data:
                    raise ValidationError(
                        f"Missing required field '{field}' in Gemini output",
                        details={"schema": schema},
                    )
