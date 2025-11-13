"""Gemini (Google AI) extractor implementation."""

from typing import Any

import google.generativeai as genai
from google.generativeai import GenerativeModel
from google.generativeai.types import GenerateContentResponse

from ...utils.api_keys import get_validated_api_key
from ...utils.json_utils import JSONParsingError, safe_json_loads
from ...utils.rate_limiter import get_rate_limiter
from ..errors import ProviderError, ValidationError
from ..models import ExtractionTemplate
from .base import BaseExtractor


class GeminiExtractor(BaseExtractor):
    """Extractor using Gemini (Google AI) API.

    Supports Gemini 1.5 Flash with:
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
    MODEL = "gemini-1.5-flash-latest"

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

        # Configure API
        genai.configure(api_key=self.api_key)
        self.model = GenerativeModel(self.MODEL)

    async def extract(
        self,
        template: ExtractionTemplate,
        transcript: str,
        metadata: dict[str, Any],
    ) -> str:
        """Extract content using Gemini.

        Args:
            template: Extraction template configuration
            transcript: Full transcript text
            metadata: Episode metadata

        Returns:
            Raw LLM response string

        Raises:
            ProviderError: If API call fails
            ValidationError: If response format invalid
        """
        # Build prompt
        user_prompt = self.build_prompt(template, transcript, metadata)

        # Combine system prompt and user prompt
        # Gemini doesn't have separate system message, so prepend it
        full_prompt = f"{template.system_prompt}\n\n{user_prompt}"

        # Configure generation
        generation_config = {
            "temperature": template.temperature,
            "max_output_tokens": template.max_tokens,
        }

        # Add JSON mode if expected format is JSON
        if template.expected_format == "json" and template.output_schema:
            generation_config["response_mime_type"] = "application/json"

        try:
            # Make API call (Gemini SDK doesn't have async version for generate_content)
            # We'll use the sync version and await it
            response: GenerateContentResponse = await self._generate_async(
                full_prompt, generation_config
            )

            # Extract text from response
            if not response.text:
                raise ValidationError("Empty response from Gemini")

            result = response.text

            # Validate JSON if schema provided
            if template.expected_format == "json" and template.output_schema:
                self._validate_json_output(result, template.output_schema)

            return result

        except Exception as e:
            if isinstance(e, ValidationError):
                raise

            # Wrap API errors
            raise ProviderError(f"Gemini API error: {str(e)}", provider="gemini") from e

    async def _generate_async(
        self, prompt: str, generation_config: dict[str, Any]
    ) -> GenerateContentResponse:
        """Wrap sync generate_content in async.

        The Gemini SDK doesn't provide async version, so we need to wrap it.
        For production, would use asyncio.to_thread or similar.

        Args:
            prompt: Full prompt text
            generation_config: Generation configuration

        Returns:
            Response from Gemini
        """
        # Apply rate limiting before API call
        limiter = get_rate_limiter("gemini")
        limiter.acquire()

        # For now, just call sync version
        # In production, would use: await asyncio.to_thread(...)
        return self.model.generate_content(prompt, generation_config=generation_config)

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
                        f"Missing required field '{field}' in Gemini output", schema=schema
                    )
