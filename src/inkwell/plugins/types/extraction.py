"""ExtractionPlugin base class for LLM-based content extraction.

This module defines the base class that all extraction plugins must implement.
It combines the plugin lifecycle with the BaseExtractor interface.
"""

from typing import TYPE_CHECKING, Any, ClassVar

from inkwell.extraction.extractors.base import BaseExtractor
from inkwell.plugins.base import InkwellPlugin
from inkwell.utils.errors import ValidationError
from inkwell.utils.json_utils import JSONParsingError, safe_json_loads

if TYPE_CHECKING:
    from inkwell.utils.costs import CostTracker


class ExtractionPlugin(InkwellPlugin, BaseExtractor):
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

    # Abstract methods (extract, estimate_cost, supports_structured_output)
    # and helper methods (build_prompt, _count_tokens) are inherited from BaseExtractor

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

    # track_cost() is inherited from InkwellPlugin base class

    def _validate_json_output(self, output: str, schema: dict[str, Any]) -> None:
        """Validate JSON output against schema.

        Shared implementation for all extraction plugins. Uses self.NAME
        to include the provider name in error messages.

        Args:
            output: JSON string from LLM
            schema: JSON Schema to validate against

        Raises:
            ValidationError: If JSON parsing fails or required fields are missing
        """
        try:
            # 5MB for extraction results, depth of 10 for structured data
            data = safe_json_loads(output, max_size=5_000_000, max_depth=10)
        except JSONParsingError as e:
            raise ValidationError(f"Invalid JSON from {self.NAME}: {str(e)}") from e

        # Basic schema validation
        # For production, would use jsonschema library
        if "required" in schema:
            for field in schema["required"]:
                if field not in data:
                    raise ValidationError(
                        f"Missing required field '{field}' in {self.NAME} output",
                        details={"schema": schema},
                    )
