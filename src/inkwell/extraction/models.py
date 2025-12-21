"""Data models for the extraction system.

This module defines Pydantic models for:
- Extraction templates (YAML-based configuration)
- Template variables (for prompt customization)
- Extracted content (validated results)
- Extraction results (operation envelope)
- Extraction tracking (summary and attempt records)
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from inkwell.utils.datetime import now_utc


class TemplateVariable(BaseModel):
    """Variable that can be used in prompt template.

    Variables allow templates to be customized with dynamic values
    like podcast name, episode title, metadata, etc.

    Example:
        >>> var = TemplateVariable(
        ...     name="podcast_name",
        ...     description="Name of the podcast",
        ...     required=True
        ... )
    """

    name: str = Field(..., description="Variable name (e.g., 'podcast_name')")
    description: str = Field(..., description="Human-readable description")
    default: str | None = Field(None, description="Default value if not provided")
    required: bool = Field(True, description="Whether this variable is required")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Ensure variable name is valid Python identifier."""
        if not v.isidentifier():
            raise ValueError(f"Variable name must be valid identifier: {v}")
        return v


class ExtractionTemplate(BaseModel):
    """Template for extracting content from transcript.

    Templates define how content should be extracted from podcast transcripts
    using LLM prompts, output formats, and validation schemas.

    Example:
        >>> template = ExtractionTemplate(
        ...     name="summary",
        ...     version="1.0",
        ...     description="Generate episode summary",
        ...     system_prompt="You are an expert podcast analyst.",
        ...     user_prompt_template="Summarize: {{ transcript }}",
        ...     expected_format="markdown"
        ... )
    """

    # Required fields
    name: str = Field(..., description="Template name (filesystem-safe)")
    version: str = Field(..., description="Semantic version (e.g., '1.0', '2.1.3')")
    description: str = Field(..., description="Human-readable description")

    # LLM prompts
    system_prompt: str = Field(..., description="System message for LLM")
    user_prompt_template: str = Field(
        ..., description="User prompt template (supports Jinja2 variables)"
    )

    # Output configuration
    expected_format: Literal["json", "markdown", "yaml", "text"] = Field(
        ..., description="Expected output format"
    )
    output_schema: dict[str, Any] | None = Field(
        None, description="JSON schema for validation (optional)"
    )

    # Template metadata
    category: str | None = Field(None, description="Template category (e.g., 'tech')")
    applies_to: list[str] = Field(
        default_factory=lambda: ["all"], description="Conditions for template application"
    )
    priority: int = Field(0, description="Execution order (lower = earlier)")

    # LLM configuration
    model_preference: str | None = Field(
        None, description="Preferred LLM provider (e.g., 'claude', 'gemini')"
    )
    max_tokens: int = Field(2000, description="Maximum tokens for LLM response", ge=1)
    temperature: float = Field(
        0.3, description="LLM temperature (0-1, lower = more deterministic)", ge=0, le=1
    )

    # Variables
    variables: list[TemplateVariable] = Field(
        default_factory=list, description="Template variables"
    )

    # Few-shot examples
    few_shot_examples: list[dict[str, Any]] = Field(
        default_factory=list, description="Few-shot examples for prompting"
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Ensure template name is filesystem-safe."""
        # Allow alphanumeric, hyphens, and underscores
        if not v.replace("-", "").replace("_", "").isalnum():
            raise ValueError(f"Template name must be alphanumeric (or - _): {v}")
        return v

    @field_validator("user_prompt_template")
    @classmethod
    def validate_jinja_template(cls, v: str) -> str:
        """Ensure Jinja2 template is syntactically valid."""
        try:
            from jinja2 import Template

            Template(v)
        except Exception as e:
            raise ValueError(f"Invalid Jinja2 template: {e}") from e
        return v

    @property
    def cache_key_base(self) -> str:
        """Generate base cache key for this template."""
        return f"{self.name}:{self.version}"


class ExtractedContent(BaseModel):
    """Content extracted by a template.

    Represents the result of applying an extraction template to a transcript.
    Includes the extracted content, metadata, and quality indicators.

    Example:
        >>> content = ExtractedContent(
        ...     template_name="summary",
        ...     content={"summary": "...", "takeaways": [...]},
        ...     confidence=0.95
        ... )

    Technical Debt:
        The 'content' field accepts both str and dict[str, Any], which requires
        runtime type checking everywhere it's used. Consider refactoring to use
        discriminated unions in Phase 4:

        Option 1 - Tagged Union:
            class TextContent(BaseModel):
                type: Literal["text"] = "text"
                template_name: str
                text: str

            class StructuredContent(BaseModel):
                type: Literal["structured"] = "structured"
                template_name: str
                data: dict[str, Any]

            ExtractedContentType = TextContent | StructuredContent

        This would provide compile-time type safety and eliminate the need for
        isinstance() checks in consumers (markdown.py, etc.).

        See: https://docs.pydantic.dev/latest/concepts/unions/#discriminated-unions
    """

    template_name: str = Field(..., description="Name of template that produced this")
    content: str | dict[str, Any] = Field(
        ..., description="Extracted content (format depends on template)"
    )
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    # Quality metrics
    confidence: float | None = Field(None, description="Confidence score (0-1)", ge=0, le=1)
    warnings: list[str] = Field(default_factory=list, description="Validation warnings")

    # Timestamps
    extracted_at: datetime = Field(default_factory=now_utc, description="When extraction occurred")

    @property
    def is_valid(self) -> bool:
        """Check if content meets quality thresholds.

        Returns:
            True if no warnings and confidence >= 0.7
        """
        return len(self.warnings) == 0 and (self.confidence is None or self.confidence >= 0.7)

    @property
    def has_warnings(self) -> bool:
        """Check if extraction has any warnings."""
        return len(self.warnings) > 0


class ExtractionResult(BaseModel):
    """Result of extraction operation.

    Wraps the extraction result with success/failure status,
    metrics, and cost tracking.

    Example:
        >>> result = ExtractionResult(
        ...     episode_url="https://example.com/ep123",
        ...     template_name="summary",
        ...     success=True,
        ...     extracted_content=content,
        ...     cost_usd=0.23
        ... )
    """

    episode_url: str = Field(..., description="URL of the episode")
    template_name: str = Field(..., description="Template used for extraction")

    # Result status
    success: bool = Field(..., description="Whether extraction succeeded")
    extracted_content: ExtractedContent | None = Field(
        None, description="Extracted content (if successful)"
    )
    error: str | None = Field(None, description="Error message (if failed)")

    # Metrics
    duration_seconds: float = Field(0.0, description="Extraction duration", ge=0)
    tokens_used: int = Field(0, description="Total tokens used (input + output)", ge=0)
    cost_usd: float = Field(0.0, description="Cost in USD", ge=0)
    provider: str | None = Field(None, description="LLM provider used")

    # Cache information
    from_cache: bool = Field(False, description="Whether result came from cache")
    cache_key: str | None = Field(None, description="Cache key if cached")

    # Timestamp
    completed_at: datetime = Field(default_factory=now_utc, description="When extraction completed")

    @property
    def is_successful(self) -> bool:
        """Check if extraction was successful."""
        return self.success and self.extracted_content is not None

    @property
    def is_cached(self) -> bool:
        """Check if result came from cache."""
        return self.from_cache

    def get_summary(self) -> str:
        """Get human-readable summary of result."""
        if self.success:
            cache_status = " (cached)" if self.from_cache else ""
            return (
                f"✓ {self.template_name}: Success{cache_status} "
                f"({self.duration_seconds:.1f}s, ${self.cost_usd:.3f})"
            )
        else:
            return f"✗ {self.template_name}: Failed - {self.error}"


class ExtractionStatus(str, Enum):
    """Status of an extraction attempt."""

    SUCCESS = "success"
    FAILED = "failed"
    CACHED = "cached"


@dataclass
class ExtractionAttempt:
    """Record of a single extraction attempt.

    Tracks the outcome of attempting to extract content using a template,
    including success/failure status, timing, and error details.

    Example:
        >>> attempt = ExtractionAttempt(
        ...     template_name="summary",
        ...     status=ExtractionStatus.SUCCESS,
        ...     result=extraction_result,
        ...     duration_seconds=2.5
        ... )
    """

    template_name: str
    status: ExtractionStatus
    result: ExtractionResult | None = None
    error: Exception | None = None
    error_message: str | None = None
    duration_seconds: float | None = None


@dataclass
class ExtractionSummary:
    """Summary of all extraction attempts.

    Aggregates results from multiple extraction attempts, providing
    statistics and helper methods for reporting.

    Example:
        >>> summary = ExtractionSummary(
        ...     total=4,
        ...     successful=3,
        ...     failed=1,
        ...     cached=1,
        ...     attempts=[...]
        ... )
        >>> print(summary.format_summary())
    """

    total: int
    successful: int
    failed: int
    cached: int
    attempts: list[ExtractionAttempt]

    @property
    def success_rate(self) -> float:
        """Calculate success rate percentage.

        Returns:
            Success rate as percentage (0-100)
        """
        if self.total == 0:
            return 0.0
        return (self.successful / self.total) * 100

    @property
    def failed_templates(self) -> list[str]:
        """Get list of failed template names.

        Returns:
            List of template names that failed extraction
        """
        return [
            attempt.template_name
            for attempt in self.attempts
            if attempt.status == ExtractionStatus.FAILED
        ]

    def format_summary(self) -> str:
        """Format summary for user display.

        Returns:
            Formatted string with extraction statistics and error details
        """
        lines = [
            "\nExtraction Summary:",
            f"  Total: {self.total}",
            f"  Successful: {self.successful}",
            f"  Failed: {self.failed}",
            f"  Cached: {self.cached}",
            f"  Success Rate: {self.success_rate:.1f}%",
        ]

        if self.failed > 0:
            lines.append("\nFailed Templates:")
            for attempt in self.attempts:
                if attempt.status == ExtractionStatus.FAILED:
                    error_msg = attempt.error_message or str(attempt.error)
                    lines.append(f"  - {attempt.template_name}: {error_msg}")

        return "\n".join(lines)
