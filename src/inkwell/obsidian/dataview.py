"""Dataview-compatible frontmatter schema for Obsidian integration.

Provides rich, queryable metadata for podcast episode notes.
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class DataviewFrontmatter(BaseModel):
    """Enhanced frontmatter schema for Dataview queries.

    All fields are designed to be queryable in Dataview, following
    best practices for field naming and data types.

    Example usage in Dataview:
        TABLE podcast, episode-date, duration-minutes
        FROM "podcasts"
        WHERE podcast = "Lex Fridman Podcast"
        SORT episode-date DESC
    """

    # Core identification
    template: str = Field(description="Template used for extraction")
    podcast: str = Field(description="Podcast name")
    episode: str = Field(description="Episode title")
    episode_number: int | None = Field(default=None, description="Episode number if available")

    # Dates (ISO format for sorting)
    created_date: str = Field(description="File creation date (YYYY-MM-DD)")
    episode_date: str | None = Field(default=None, description="Episode publication date (YYYY-MM-DD)")
    last_modified: str = Field(description="Last modification date (YYYY-MM-DD)")

    # URLs
    url: str | None = Field(default=None, description="Episode URL")
    podcast_url: str | None = Field(default=None, description="Podcast homepage URL")

    # Media info
    duration_minutes: int | None = Field(default=None, description="Episode duration in minutes")
    audio_url: str | None = Field(default=None, description="Direct audio file URL")

    # People
    host: str | None = Field(default=None, description="Podcast host name")
    guest: str | None = Field(default=None, description="Guest name (if applicable)")
    people: list[str] = Field(default_factory=list, description="All people mentioned")

    # Content categorization
    tags: list[str] = Field(default_factory=list, description="Tags for categorization")
    topics: list[str] = Field(default_factory=list, description="Main topics discussed")
    categories: list[str] = Field(default_factory=list, description="Content categories")

    # Ratings & status
    rating: int | None = Field(default=None, ge=1, le=5, description="User rating (1-5)")
    status: Literal["inbox", "reading", "completed", "archived"] = Field(
        default="inbox", description="Processing status"
    )
    priority: Literal["low", "medium", "high"] = Field(
        default="medium", description="Priority level"
    )

    # Metadata
    extracted_with: str = Field(description="Extraction provider (gemini, claude, cache)")
    cost_usd: float = Field(default=0.0, description="Extraction cost in USD")
    word_count: int | None = Field(default=None, description="Transcript word count")

    # Obsidian integration
    has_wikilinks: bool = Field(default=False, description="Contains wikilinks")
    has_interview: bool = Field(default=False, description="Interview mode used")
    related_notes: list[str] = Field(default_factory=list, description="Related note links")

    # Custom fields (user extensible)
    custom: dict[str, Any] = Field(default_factory=dict, description="User-defined fields")


class DataviewConfig(BaseModel):
    """Configuration for Dataview integration."""

    enabled: bool = True
    include_episode_number: bool = True
    include_duration: bool = True
    include_word_count: bool = True
    include_ratings: bool = True
    include_status: bool = True
    default_status: Literal["inbox", "reading", "completed", "archived"] = "inbox"
    default_priority: Literal["low", "medium", "high"] = "medium"


def create_frontmatter_dict(
    template_name: str,
    episode_metadata: dict[str, Any],
    extraction_result: Any,
    tags: list[str] | None = None,
    entities: list[Any] | None = None,
    interview_conducted: bool = False,
    config: DataviewConfig | None = None,
) -> dict[str, Any]:
    """Create Dataview-compatible frontmatter dictionary.

    Args:
        template_name: Extraction template name
        episode_metadata: Episode metadata dict
        extraction_result: ExtractionResult object
        tags: Generated tags (from TagGenerator)
        entities: Extracted entities (from WikilinkGenerator)
        interview_conducted: Whether interview mode was used
        config: Dataview configuration

    Returns:
        Dict suitable for YAML frontmatter
    """
    from datetime import timezone

    config = config or DataviewConfig()
    now = datetime.now(timezone.utc)

    # Build frontmatter
    frontmatter: dict[str, Any] = {
        # Core
        "template": template_name,
        "podcast": episode_metadata.get("podcast_name", "Unknown"),
        "episode": episode_metadata.get("episode_title", "Unknown"),

        # Dates
        "created_date": now.strftime("%Y-%m-%d"),
        "last_modified": now.strftime("%Y-%m-%d"),
    }

    # Episode number
    if config.include_episode_number and "episode_number" in episode_metadata:
        frontmatter["episode_number"] = episode_metadata["episode_number"]

    # Episode publication date
    if "episode_date" in episode_metadata:
        frontmatter["episode_date"] = episode_metadata["episode_date"]

    # URLs
    if "episode_url" in episode_metadata:
        frontmatter["url"] = episode_metadata["episode_url"]
    if "podcast_url" in episode_metadata:
        frontmatter["podcast_url"] = episode_metadata["podcast_url"]

    # Media info
    if config.include_duration and "duration_minutes" in episode_metadata:
        frontmatter["duration_minutes"] = episode_metadata["duration_minutes"]
    if "audio_url" in episode_metadata:
        frontmatter["audio_url"] = episode_metadata["audio_url"]

    # People
    if "host" in episode_metadata:
        frontmatter["host"] = episode_metadata["host"]
    if "guest" in episode_metadata:
        frontmatter["guest"] = episode_metadata["guest"]

    # Extract people from entities
    if entities:
        from inkwell.obsidian.models import EntityType
        people = [e.name for e in entities if e.type == EntityType.PERSON]
        if people:
            frontmatter["people"] = people[:5]  # Limit to top 5

    # Tags (from TagGenerator)
    if tags:
        frontmatter["tags"] = tags

    # Topics (extract from tags)
    if tags:
        topics = [t.replace("topic/", "").replace("#", "") for t in tags if "topic/" in t]
        if topics:
            frontmatter["topics"] = topics

    # Status and ratings
    if config.include_status:
        frontmatter["status"] = config.default_status
    if config.include_ratings:
        frontmatter["rating"] = None  # User can fill in
        frontmatter["priority"] = config.default_priority

    # Metadata
    if extraction_result:
        frontmatter["extracted_with"] = extraction_result.provider
        frontmatter["cost_usd"] = round(extraction_result.cost_usd, 4)

    # Word count
    if config.include_word_count and "word_count" in episode_metadata:
        frontmatter["word_count"] = episode_metadata["word_count"]

    # Obsidian integration flags
    frontmatter["has_wikilinks"] = entities is not None and len(entities) > 0
    frontmatter["has_interview"] = interview_conducted

    return frontmatter


def format_frontmatter_yaml(frontmatter: dict[str, Any]) -> str:
    """Format frontmatter dict as YAML with proper delimiters.

    Args:
        frontmatter: Frontmatter dictionary

    Returns:
        Formatted YAML string with --- delimiters
    """
    import yaml

    yaml_str = yaml.dump(
        frontmatter,
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
    )
    return f"---\n{yaml_str}---"
