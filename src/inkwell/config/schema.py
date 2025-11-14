"""Configuration schema models using Pydantic."""

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl

AuthType = Literal["none", "basic", "bearer"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR"]


class AuthConfig(BaseModel):
    """Authentication configuration for a feed."""

    type: AuthType = "none"
    username: str | None = None  # Encrypted when stored
    password: str | None = None  # Encrypted when stored
    token: str | None = None  # Encrypted when stored (for bearer)


class FeedConfig(BaseModel):
    """Configuration for a single podcast feed."""

    url: HttpUrl
    auth: AuthConfig = Field(default_factory=AuthConfig)
    category: str | None = None
    custom_templates: list[str] = Field(default_factory=list)


class ObsidianConfig(BaseModel):
    """Obsidian integration configuration."""

    # Global enable/disable
    enabled: bool = True

    # Wikilinks
    wikilinks_enabled: bool = True
    wikilink_style: Literal["simple", "prefixed"] = "simple"  # [[Name]] or [[Type - Name]]
    min_confidence: float = 0.7  # Minimum confidence for entity extraction
    max_entities_per_type: int = 10  # Limit entities per type to avoid clutter

    # Tags (Unit 4 - implemented)
    tags_enabled: bool = True
    tag_style: Literal["flat", "hierarchical"] = "hierarchical"
    max_tags: int = 7
    min_tag_confidence: float = 0.6
    include_entity_tags: bool = True  # Generate tags from entities
    include_llm_tags: bool = True  # Generate tags using LLM

    # Dataview (Unit 5 - implemented)
    dataview_enabled: bool = True
    include_episode_number: bool = True
    include_duration: bool = True
    include_word_count: bool = True
    include_ratings: bool = True
    include_status: bool = True
    default_status: Literal["inbox", "reading", "completed", "archived"] = "inbox"
    default_priority: Literal["low", "medium", "high"] = "medium"


class InterviewConfig(BaseModel):
    """Interview mode configuration."""

    enabled: bool = True
    auto_start: bool = False  # If true, always interview (no --interview flag needed)

    # Style
    default_template: str = "reflective"  # reflective, analytical, creative
    question_count: int = 5
    max_depth: int = 3

    # User preferences
    guidelines: str = ""

    # Session
    save_raw_transcript: bool = True
    resume_enabled: bool = True
    session_timeout_minutes: int = 60

    # Output
    include_action_items: bool = True
    include_key_insights: bool = True
    format_style: Literal["structured", "narrative", "qa"] = "structured"

    # Cost
    max_cost_per_interview: float = 0.50
    confirm_high_cost: bool = True

    # Advanced
    model: str = "claude-sonnet-4-5"
    temperature: float = 0.7
    streaming: bool = True


class GlobalConfig(BaseModel):
    """Global Inkwell configuration."""

    version: str = "1"
    default_output_dir: Path = Field(default=Path("~/podcasts"))
    transcription_model: str = "gemini-2.0-flash-exp"
    interview_model: str = "claude-sonnet-4-5"
    youtube_check: bool = True
    log_level: LogLevel = "INFO"
    default_templates: list[str] = Field(
        default_factory=lambda: ["summary", "quotes", "key-concepts"]
    )
    template_categories: dict[str, list[str]] = Field(
        default_factory=lambda: {
            "tech": ["tools-mentioned", "frameworks-mentioned"],
            "interview": ["books-mentioned", "people-mentioned"],
        }
    )
    obsidian: ObsidianConfig = Field(default_factory=ObsidianConfig)
    interview: InterviewConfig = Field(default_factory=InterviewConfig)


class Feeds(BaseModel):
    """Collection of podcast feeds."""

    feeds: dict[str, FeedConfig] = Field(default_factory=dict)
