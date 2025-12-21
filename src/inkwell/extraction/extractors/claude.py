"""Claude (Anthropic) extractor implementation."""

from typing import Any

from anthropic import Anthropic, AsyncAnthropic
from anthropic.types import Message

from ...utils.api_keys import get_validated_api_key
from ...utils.errors import APIError, ValidationError
from ...utils.json_utils import JSONParsingError, safe_json_loads
from ...utils.rate_limiter import get_rate_limiter
from ..models import ExtractionTemplate
from .base import BaseExtractor


class ClaudeExtractor(BaseExtractor):
    """Extractor using Claude (Anthropic) API.

    Supports Claude 3.5 Sonnet with:
    - High quality extraction (best for quotes, precise data)
    - Native JSON mode for structured output
    - Function calling capability (not used currently)

    Cost (as of Nov 2024):
    - Input: $3.00 per million tokens
    - Output: $15.00 per million tokens
    """

    # Model to use
    MODEL = "claude-3-5-sonnet-20241022"

    # Pricing per million tokens (USD)
    INPUT_PRICE_PER_M = 3.00
    OUTPUT_PRICE_PER_M = 15.00

    def __init__(self, api_key: str | None = None) -> None:
        """Initialize Claude extractor.

        Args:
            api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)

        Raises:
            APIKeyError: If API key not provided or invalid
        """
        # Validate API key
        if api_key:
            # If provided directly, still validate it
            from ...utils.api_keys import validate_api_key

            self.api_key = validate_api_key(api_key, "claude", "ANTHROPIC_API_KEY")
        else:
            # Get from environment and validate
            self.api_key = get_validated_api_key("ANTHROPIC_API_KEY", "claude")

        self.client = AsyncAnthropic(api_key=self.api_key)
        self._sync_client = Anthropic(api_key=self.api_key)

    async def extract(
        self,
        template: ExtractionTemplate,
        transcript: str,
        metadata: dict[str, Any],
        force_json: bool = False,
        max_tokens_override: int | None = None,
    ) -> str:
        """Extract content using Claude.

        Args:
            template: Extraction template configuration
            transcript: Full transcript text
            metadata: Episode metadata
            force_json: Force JSON response mode (for batch extraction)
            max_tokens_override: Override template's max_tokens (for batch extraction)

        Returns:
            Raw LLM response string

        Raises:
            ProviderError: If API call fails
            ValidationError: If response format invalid
        """
        # Build prompt
        user_prompt = self.build_prompt(template, transcript, metadata)

        # Prepare request parameters
        request_params: dict[str, Any] = {
            "model": self.MODEL,
            "max_tokens": template.max_tokens,
            "temperature": template.temperature,
            "system": template.system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
        }

        # Add JSON mode if expected format is JSON
        if template.expected_format == "json" and template.output_schema:
            request_params["response_format"] = {"type": "json_object"}

        try:
            # Apply rate limiting before API call
            limiter = get_rate_limiter("claude")
            limiter.acquire()

            # Make API call
            response: Message = await self.client.messages.create(**request_params)

            # Extract text from response
            if not response.content:
                raise ValidationError("Empty response from Claude")

            # Claude returns list of content blocks
            text_content = []
            for block in response.content:
                if hasattr(block, "text"):
                    text_content.append(block.text)

            result = "".join(text_content)

            # Validate JSON if schema provided
            if template.expected_format == "json" and template.output_schema:
                self._validate_json_output(result, template.output_schema)

            return result

        except Exception as e:
            if isinstance(e, ValidationError):
                raise

            # Wrap API errors
            status_code = getattr(e, "status_code", None)
            raise APIError(
                f"Claude API error: {str(e)}", provider="claude", status_code=status_code
            ) from e

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
        # System prompt + user prompt template (without transcript) + transcript
        system_tokens = self._count_tokens(template.system_prompt)
        user_prompt_base = self._count_tokens(template.user_prompt_template)
        transcript_tokens = self._count_tokens(" " * transcript_length)  # Approximate

        # Add tokens for few-shot examples
        examples_tokens = 0
        if template.few_shot_examples:
            for example in template.few_shot_examples:
                examples_tokens += self._count_tokens(str(example))

        input_tokens = system_tokens + user_prompt_base + transcript_tokens + examples_tokens

        # Output tokens from template config
        output_tokens = template.max_tokens

        # Calculate costs
        input_cost = (input_tokens / 1_000_000) * self.INPUT_PRICE_PER_M
        output_cost = (output_tokens / 1_000_000) * self.OUTPUT_PRICE_PER_M

        return input_cost + output_cost

    def supports_structured_output(self) -> bool:
        """Whether Claude supports structured output.

        Returns:
            True (Claude supports JSON mode)
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
            raise ValidationError(f"Invalid JSON from Claude: {str(e)}") from e

        # Basic schema validation
        # For production, would use jsonschema library
        if "required" in schema:
            for field in schema["required"]:
                if field not in data:
                    raise ValidationError(
                        f"Missing required field '{field}' in Claude output",
                        details={"schema": schema},
                    )
