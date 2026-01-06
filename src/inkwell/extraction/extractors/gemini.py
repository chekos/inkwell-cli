"""Gemini (Google AI) extractor implementation using modern google-genai SDK."""

import asyncio
from typing import Any

from google import genai
from google.genai import types

from ...plugins.types.extraction import ExtractionPlugin
from ...utils.api_keys import get_validated_api_key
from ...utils.errors import APIError, ValidationError
from ...utils.rate_limiter import get_rate_limiter
from ..models import ExtractionTemplate


class GeminiExtractor(ExtractionPlugin):
    """Extractor using Gemini (Google AI) API.

    Supports Gemini 3 Pro with:
    - Advanced reasoning capabilities
    - High quality extraction
    - Native JSON mode for structured output
    - Long context support (1M tokens)

    Cost (as of Dec 2025):
    - Input: $2.00 per million tokens (<200K tokens)
    - Input: $4.00 per million tokens (>200K tokens)
    - Output: $12.00 per million tokens (<200K tokens)
    - Output: $18.00 per million tokens (>200K tokens)
    """

    # Plugin metadata (required by InkwellPlugin)
    NAME = "gemini"
    VERSION = "1.0.0"
    DESCRIPTION = "Google Gemini API extractor with long context support"

    # Model to use
    MODEL = "gemini-3-pro-preview"

    # Pricing per million tokens (USD)
    INPUT_PRICE_PER_M_SHORT = 2.00  # < 200K tokens
    INPUT_PRICE_PER_M_LONG = 4.00  # > 200K tokens
    INPUT_PRICE_PER_M = 2.00  # Default for base class (short context)
    OUTPUT_PRICE_PER_M = 12.00  # < 200K tokens (using base rate)
    CONTEXT_THRESHOLD = 200_000  # Token threshold for pricing

    def __init__(self, api_key: str | None = None, *, lazy_init: bool = False) -> None:
        """Initialize Gemini extractor.

        Args:
            api_key: Google AI API key (defaults to GOOGLE_API_KEY env var).
                    Can also be provided via configure() for plugin lifecycle.
            lazy_init: If True, defer client initialization until first use.
                      Used internally by plugin system. Default False maintains
                      backward compatibility.

        Raises:
            APIKeyError: If API key not provided or invalid (unless lazy_init)
        """
        super().__init__()

        # Store provided key for lazy initialization
        self._provided_api_key = api_key
        self._client: genai.Client | None = None

        # Initialize immediately unless lazy_init requested (backward compat)
        if not lazy_init:
            self._init_client(api_key)

    def _init_client(self, api_key: str | None = None) -> None:
        """Initialize API client with the given or configured API key."""
        if api_key:
            from ...utils.api_keys import validate_api_key

            self.api_key = validate_api_key(api_key, "gemini", "GOOGLE_API_KEY")
        else:
            self.api_key = get_validated_api_key("GOOGLE_API_KEY", "gemini")

        self._client = genai.Client(api_key=self.api_key)

    @property
    def client(self) -> genai.Client:
        """Get client, initializing if needed."""
        if self._client is None:
            self._init_client(self._provided_api_key)
        return self._client  # type: ignore[return-value]

    def configure(
        self,
        config: dict[str, Any],
        cost_tracker: "Any | None" = None,
    ) -> None:
        """Configure the plugin with settings and cost tracker.

        Args:
            config: Plugin configuration. May include 'api_key'.
            cost_tracker: Optional cost tracker for API usage tracking.
        """
        super().configure(config, cost_tracker)

        # Initialize client with config API key if provided
        api_key = config.get("api_key") or self._provided_api_key
        if api_key or self._client is None:
            self._init_client(api_key)

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
