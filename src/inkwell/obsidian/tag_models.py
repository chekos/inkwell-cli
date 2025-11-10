"""Data models for tag generation.

Defines tag structures, configuration, and normalization for Obsidian-compatible tags.
"""

import re
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class TagStyle(str, Enum):
    """Tag formatting style."""

    FLAT = "flat"  # #tag
    HIERARCHICAL = "hierarchical"  # #category/tag


class TagCategory(str, Enum):
    """Predefined tag categories for hierarchical organization."""

    PODCAST = "podcast"  # #podcast/name
    TOPIC = "topic"  # #topic/ai
    PERSON = "person"  # #person/cal-newport
    CONCEPT = "concept"  # #concept/deep-work
    TOOL = "tool"  # #tool/obsidian
    BOOK = "book"  # #book/atomic-habits
    THEME = "theme"  # #theme/productivity
    INDUSTRY = "industry"  # #industry/tech
    CUSTOM = "custom"  # User-defined


class Tag(BaseModel):
    """Represents an Obsidian tag.

    Attributes:
        name: Tag name (normalized to lowercase kebab-case)
        category: Tag category for hierarchical organization
        confidence: Confidence score (0-1)
        source: Where tag came from (llm, entity, manual)
        raw_name: Original name before normalization
    """

    name: str
    category: TagCategory | None = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    source: Literal["llm", "entity", "manual"] = "llm"
    raw_name: str = ""

    @field_validator("name")
    @classmethod
    def normalize_tag_name(cls, v: str) -> str:
        """Normalize tag name to Obsidian-compatible format.

        Rules:
        - Lowercase
        - Replace spaces with hyphens
        - Remove special characters except hyphens and underscores
        - Remove leading/trailing hyphens
        - Collapse multiple hyphens

        Examples:
            "Deep Work" -> "deep-work"
            "AI & ML" -> "ai-ml"
            "Cal Newport, PhD" -> "cal-newport-phd"
        """
        # Lowercase
        normalized = v.lower()

        # Replace spaces with hyphens
        normalized = normalized.replace(" ", "-")

        # Remove special characters except hyphens and underscores
        normalized = re.sub(r"[^a-z0-9\-_]", "", normalized)

        # Collapse multiple hyphens
        normalized = re.sub(r"-+", "-", normalized)

        # Remove leading/trailing hyphens
        normalized = normalized.strip("-")

        return normalized

    def to_obsidian_tag(self, style: TagStyle = TagStyle.HIERARCHICAL) -> str:
        """Convert to Obsidian tag format.

        Args:
            style: Tag style (flat or hierarchical)

        Returns:
            Formatted tag string

        Examples:
            Tag(name="ai", category="topic") -> "#topic/ai" (hierarchical)
            Tag(name="ai", category="topic") -> "#ai" (flat)
        """
        if style == TagStyle.HIERARCHICAL and self.category:
            return f"#{self.category.value}/{self.name}"
        return f"#{self.name}"

    def __eq__(self, other: object) -> bool:
        """Case-insensitive equality for deduplication."""
        if not isinstance(other, Tag):
            return False
        return (
            self.name.lower() == other.name.lower()
            and self.category == other.category
        )

    def __hash__(self) -> int:
        """Hash for set operations."""
        return hash((self.name.lower(), self.category))


class TagConfig(BaseModel):
    """Configuration for tag generation.

    Attributes:
        enabled: Enable/disable tag generation
        style: Tag style (flat or hierarchical)
        max_tags: Maximum number of tags to generate
        min_confidence: Minimum confidence threshold
        include_entity_tags: Generate tags from extracted entities
        include_llm_tags: Generate tags using LLM
        custom_categories: User-defined tag categories
        llm_provider: LLM provider for tag generation (gemini, claude)
        llm_model: Model to use for tag generation
    """

    enabled: bool = True
    style: TagStyle = TagStyle.HIERARCHICAL
    max_tags: int = 7
    min_confidence: float = 0.6
    include_entity_tags: bool = True
    include_llm_tags: bool = True
    custom_categories: list[str] = Field(default_factory=list)
    llm_provider: Literal["gemini", "claude"] = "gemini"
    llm_model: str = "gemini-2.0-flash-exp"


class TagSuggestion(BaseModel):
    """LLM-generated tag suggestion.

    Attributes:
        tags: List of suggested tags
        reasoning: LLM's reasoning for suggestions
        confidence: Overall confidence in suggestions
        cost_usd: Cost of LLM call
    """

    tags: list[Tag]
    reasoning: str = ""
    confidence: float = 1.0
    cost_usd: float = 0.0
