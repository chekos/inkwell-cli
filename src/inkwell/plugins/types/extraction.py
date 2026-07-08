"""ExtractionPlugin base class for LLM-based content extraction.

This module defines the base class that all extraction plugins must implement.
It combines the plugin lifecycle with the BaseExtractor interface.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, ClassVar

from inkwell.extraction.extractors.base import BaseExtractor
from inkwell.plugins.base import InkwellPlugin
from inkwell.utils.errors import ValidationError
from inkwell.utils.json_utils import JSONParsingError, safe_json_loads

if TYPE_CHECKING:
    from inkwell.utils.costs import CostTracker


@dataclass(frozen=True)
class ExtractionCapabilities:
    """Typed capability metadata for extraction providers."""

    model_name: str = "unknown"
    can_extract_text: bool = True
    supports_structured_output: bool = True
    supports_json_mode: bool = True
    requires_internet: bool = True
    max_input_tokens: int | None = None
    input_price_per_m: float = 0.0
    output_price_per_m: float = 0.0
    estimated_cost_label: str | None = None

    @classmethod
    def from_legacy(
        cls,
        capabilities: dict[str, Any] | None,
        *,
        model_name: str = "unknown",
        input_price_per_m: float = 0.0,
        output_price_per_m: float = 0.0,
    ) -> "ExtractionCapabilities":
        """Build typed metadata from legacy class attributes or dictionaries."""
        caps = capabilities or {}
        return cls(
            model_name=str(caps.get("model_name") or model_name),
            can_extract_text=bool(caps.get("can_extract_text", True)),
            supports_structured_output=bool(caps.get("supports_structured_output", True)),
            supports_json_mode=bool(caps.get("supports_json_mode", True)),
            requires_internet=bool(caps.get("requires_internet", True)),
            max_input_tokens=(
                int(caps["max_input_tokens"]) if caps.get("max_input_tokens") is not None else None
            ),
            input_price_per_m=float(caps.get("input_price_per_m", input_price_per_m)),
            output_price_per_m=float(caps.get("output_price_per_m", output_price_per_m)),
            estimated_cost_label=(
                str(caps["estimated_cost_label"])
                if caps.get("estimated_cost_label") is not None
                else None
            ),
        )

    def to_legacy_dict(self) -> dict[str, Any]:
        """Return a compatibility dictionary for existing plugin code."""
        return {
            "model_name": self.model_name,
            "can_extract_text": self.can_extract_text,
            "supports_structured_output": self.supports_structured_output,
            "supports_json_mode": self.supports_json_mode,
            "requires_internet": self.requires_internet,
            "max_input_tokens": self.max_input_tokens,
            "input_price_per_m": self.input_price_per_m,
            "output_price_per_m": self.output_price_per_m,
            "estimated_cost_label": self.estimated_cost_label,
        }

    def display_parts(self) -> list[str]:
        """Return concise, safe capability labels for CLI display."""
        parts: list[str] = []
        if self.can_extract_text:
            parts.append("text")
        if self.supports_structured_output:
            parts.append("structured")
        if self.supports_json_mode:
            parts.append("json")
        if not self.requires_internet:
            parts.append("offline")
        if self.max_input_tokens is not None:
            parts.append(f"context={self._format_count(self.max_input_tokens)}")
        if self.model_name != "unknown":
            parts.append(f"model={self.model_name}")
        if self.estimated_cost_label:
            parts.append(self.estimated_cost_label)
        elif self.input_price_per_m or self.output_price_per_m:
            parts.append(f"${self.input_price_per_m:g}/${self.output_price_per_m:g} per 1M tokens")
        return parts

    @staticmethod
    def _format_count(value: int) -> str:
        if value >= 1_000_000 and value % 1_000_000 == 0:
            return f"{value // 1_000_000}M"
        if value >= 1_000 and value % 1_000 == 0:
            return f"{value // 1_000}K"
        return str(value)


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

    CAPABILITIES: ClassVar[dict[str, Any]] = {}
    CAPABILITY_INFO: ClassVar[ExtractionCapabilities | None] = None

    def __init__(self) -> None:
        """Initialize the extraction plugin.

        The plugin is not ready for use until configure() is called.
        """
        InkwellPlugin.__init__(self)

    @property
    def model(self) -> str:
        """Get the model identifier for this extractor."""
        return self.MODEL

    @classmethod
    def capability_info(cls) -> ExtractionCapabilities:
        """Return typed capability metadata for this provider class."""
        if cls.CAPABILITY_INFO is not None:
            return cls.CAPABILITY_INFO
        return ExtractionCapabilities.from_legacy(
            cls.CAPABILITIES,
            model_name=cls.MODEL,
            input_price_per_m=cls.INPUT_PRICE_PER_M,
            output_price_per_m=cls.OUTPUT_PRICE_PER_M,
        )

    def get_capabilities(self) -> ExtractionCapabilities:
        """Return typed capability metadata for this provider instance."""
        return self.__class__.capability_info()

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
