"""ExtractionPlugin base class for LLM-based content extraction.

This module defines the base class that all extraction plugins must implement.
It provides the extraction interface directly (no multiple inheritance needed).
"""

from abc import abstractmethod
from typing import TYPE_CHECKING, Any, ClassVar

from jinja2 import Template

from inkwell.plugins.base import InkwellPlugin

if TYPE_CHECKING:
    from inkwell.extraction.models import ExtractionTemplate
    from inkwell.utils.costs import CostTracker


class ExtractionPlugin(InkwellPlugin):
    """Base class for extraction plugins.

    Provides plugin lifecycle management combined with the extraction interface.
    All extraction plugins must inherit from this class and implement the
    abstract methods.

    Class Attributes (required):
        NAME: Unique plugin identifier (e.g., "claude", "gemini")
        VERSION: Plugin version (e.g., "1.0.0")
        DESCRIPTION: Short description of the plugin

    Class Attributes (optional):
        MODEL: Default model to use for extraction
        INPUT_PRICE_PER_M: Cost per million input tokens (USD)
        OUTPUT_PRICE_PER_M: Cost per million output tokens (USD)

    Example:
        >>> class MyExtractor(ExtractionPlugin):
        ...     NAME = "my-extractor"
        ...     VERSION = "1.0.0"
        ...     DESCRIPTION = "Custom LLM extractor"
        ...     MODEL = "my-model-v1"
        ...
        ...     async def extract(self, template, transcript, metadata, **kwargs) -> str:
        ...         # Implementation here
        ...         pass
        ...
        ...     def estimate_cost(self, template, transcript_length) -> float:
        ...         return 0.0  # Free tier
        ...
        ...     def supports_structured_output(self) -> bool:
        ...         return True
    """

    # Optional: Model identifier for tracking
    MODEL: ClassVar[str] = "unknown"

    # Optional: Pricing for cost estimation
    INPUT_PRICE_PER_M: ClassVar[float] = 0.0
    OUTPUT_PRICE_PER_M: ClassVar[float] = 0.0

    def __init__(self) -> None:
        """Initialize the extraction plugin.

        The plugin is not ready for use until configure() is called.
        """
        InkwellPlugin.__init__(self)

    @property
    def model(self) -> str:
        """Get the model identifier for this extractor."""
        return self.MODEL

    @abstractmethod
    async def extract(
        self,
        template: "ExtractionTemplate",
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
        template: "ExtractionTemplate",
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
        template: "ExtractionTemplate",
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
        import json

        # Add few-shot examples if present
        examples_text = ""
        if template.few_shot_examples:
            examples_text = "\n\nExamples:\n"
            for i, example in enumerate(template.few_shot_examples, 1):
                examples_text += f"\nExample {i}:\n"
                if "input" in example:
                    examples_text += f"Input: {example['input']}\n"
                if "output" in example:
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
        return len(text) // 4

    def configure(
        self,
        config: dict[str, Any],
        cost_tracker: "CostTracker | None" = None,
    ) -> None:
        """Configure the plugin with settings and cost tracker.

        Subclasses can override to perform additional initialization,
        such as creating API clients.

        Args:
            config: Plugin-specific configuration dict.
            cost_tracker: Optional cost tracker for API usage tracking.
        """
        super().configure(config, cost_tracker)

    def track_cost(
        self,
        input_tokens: int,
        output_tokens: int,
        operation: str = "extraction",
        episode_title: str | None = None,
        template_name: str | None = None,
    ) -> None:
        """Track cost with the injected cost tracker.

        Convenience method for plugins to track API costs.

        Args:
            input_tokens: Number of input tokens used.
            output_tokens: Number of output tokens generated.
            operation: Type of operation (default: "extraction").
            episode_title: Optional episode title for tracking.
            template_name: Optional template name for tracking.
        """
        if self._cost_tracker:
            self._cost_tracker.add_cost(
                provider=self.NAME,
                model=self.MODEL,
                operation=operation,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                episode_title=episode_title,
                template_name=template_name,
            )
