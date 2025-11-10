"""Data models for Obsidian integration."""

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class EntityType(str, Enum):
    """Type of entity for wikilink generation."""

    PERSON = "person"
    BOOK = "book"
    TOOL = "tool"
    CONCEPT = "concept"
    EPISODE = "episode"


class WikilinkStyle(str, Enum):
    """Style for wikilink formatting."""

    SIMPLE = "simple"  # [[Name]]
    PREFIXED = "prefixed"  # [[Type - Name]]


class Entity(BaseModel):
    """Represents an extracted entity for wikilink generation.

    Attributes:
        name: Entity name (e.g., "Cal Newport", "Deep Work")
        type: Entity type (person, book, tool, concept, episode)
        confidence: Confidence score (0.0-1.0) from extraction
        context: Original context where entity was found
        aliases: Alternative names/spellings for this entity
        metadata: Additional metadata (e.g., author for books, role for people)
    """

    name: str = Field(..., min_length=1, description="Entity name")
    type: EntityType = Field(..., description="Type of entity")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Confidence score")
    context: str = Field(default="", description="Context where entity was mentioned")
    aliases: list[str] = Field(default_factory=list, description="Alternative names")
    metadata: dict[str, str] = Field(default_factory=dict, description="Additional metadata")

    def to_wikilink(self, style: WikilinkStyle = WikilinkStyle.SIMPLE, display_text: str | None = None) -> str:
        """Convert entity to wikilink format.

        Args:
            style: Wikilink style (simple or prefixed)
            display_text: Optional custom display text

        Returns:
            Formatted wikilink string

        Examples:
            >>> entity = Entity(name="Cal Newport", type=EntityType.PERSON)
            >>> entity.to_wikilink()
            '[[Cal Newport]]'

            >>> entity.to_wikilink(style=WikilinkStyle.PREFIXED)
            '[[Person - Cal Newport]]'

            >>> entity.to_wikilink(display_text="Cal")
            '[[Cal Newport|Cal]]'
        """
        # Build base name
        if style == WikilinkStyle.PREFIXED:
            base_name = f"{self.type.value.title()} - {self.name}"
        else:
            base_name = self.name

        # Add display text if provided
        if display_text:
            return f"[[{base_name}|{display_text}]]"

        return f"[[{base_name}]]"

    def __hash__(self) -> int:
        """Make Entity hashable for deduplication."""
        return hash((self.name.lower(), self.type))

    def __eq__(self, other: object) -> bool:
        """Compare entities for equality."""
        if not isinstance(other, Entity):
            return False
        return self.name.lower() == other.name.lower() and self.type == other.type


class WikilinkConfig(BaseModel):
    """Configuration for wikilink generation.

    Attributes:
        enabled: Enable wikilink generation
        style: Wikilink style (simple or prefixed)
        min_confidence: Minimum confidence threshold for including entities
        cross_episode_linking: Enable linking to other episodes
        deduplicate: Remove duplicate entities
    """

    enabled: bool = Field(default=True, description="Enable wikilink generation")
    style: WikilinkStyle = Field(default=WikilinkStyle.SIMPLE, description="Wikilink style")
    min_confidence: float = Field(
        default=0.7, ge=0.0, le=1.0, description="Minimum confidence threshold"
    )
    cross_episode_linking: bool = Field(
        default=True, description="Enable cross-episode linking"
    )
    deduplicate: bool = Field(default=True, description="Remove duplicate entities")
    max_entities_per_type: int = Field(
        default=20, ge=1, description="Maximum entities per type to avoid clutter"
    )
