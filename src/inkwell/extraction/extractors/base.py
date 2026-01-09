"""Base abstract extractor for LLM providers.

This module defines the abstract base class that all LLM extractors
must implement, ensuring consistent interface across providers.
"""

from abc import ABC, abstractmethod
from typing import Any

from ..models import ExtractionTemplate


class BaseExtractor(ABC):
    """Abstract base class for LLM extractors.

    All LLM provider implementations (Claude, Gemini, etc.) must
    inherit from this class and implement its abstract methods.

    Example:
        >>> class ClaudeExtractor(BaseExtractor):
        ...     async def extract(self, template, transcript, metadata):
        ...         # Implementation
        ...         pass
    """

    @abstractmethod
    async def extract(
        self,
        template: ExtractionTemplate,
        transcript: str,
        metadata: dict[str, Any],
        force_json: bool = False,
        max_tokens_override: int | None = None,
    ) -> str:
        """Extract content using template and transcript.

        Args:
            template: Extraction template configuration
            transcript: Full transcript text
            metadata: Episode metadata (podcast name, title, etc.)
            force_json: Force JSON response mode (for batch extraction)
            max_tokens_override: Override template's max_tokens (for batch extraction)

        Returns:
            Raw LLM response string

        Raises:
            ExtractionError: If extraction fails
        """
        pass

    @abstractmethod
    def estimate_cost(
        self,
        template: ExtractionTemplate,
        transcript_length: int,
    ) -> float:
        """Estimate extraction cost in USD.

        Args:
            template: Extraction template (for max_tokens)
            transcript_length: Length of transcript in characters

        Returns:
            Estimated cost in USD
        """
        pass

    @abstractmethod
    def supports_structured_output(self) -> bool:
        """Whether provider supports structured output (JSON mode).

        Returns:
            True if provider has native JSON mode, False otherwise
        """
        pass

    def build_prompt(
        self,
        template: ExtractionTemplate,
        transcript: str,
        metadata: dict[str, Any],
    ) -> str:
        """Build user prompt from template.

        Renders the Jinja2 template with transcript and metadata variables.

        Args:
            template: Extraction template
            transcript: Full transcript text
            metadata: Episode metadata

        Returns:
            Rendered prompt string
        """
        from jinja2 import Template

        # Add few-shot examples if present
        examples_text = ""
        if template.few_shot_examples:
            examples_text = "\n\nExamples:\n"
            for i, example in enumerate(template.few_shot_examples, 1):
                examples_text += f"\nExample {i}:\n"
                if "input" in example:
                    examples_text += f"Input: {example['input']}\n"
                if "output" in example:
                    import json

                    output_str = json.dumps(example["output"], indent=2)
                    examples_text += f"Output:\n{output_str}\n"

        # Build context with all variables
        context = {
            "transcript": transcript,
            "metadata": metadata,
            "examples": examples_text,
        }

        # Render template
        jinja_template = Template(template.user_prompt_template)
        prompt = jinja_template.render(**context)

        # Add examples if present
        if examples_text:
            prompt = examples_text + "\n\n" + prompt

        return prompt

    def _count_tokens(self, text: str) -> int:
        """Estimate token count for text.

        Uses rough approximation of 4 characters per token.

        Args:
            text: Text to count tokens for

        Returns:
            Estimated token count
        """
        # Rough approximation: 4 chars per token
        # For production, could use tiktoken library
        return len(text) // 4
