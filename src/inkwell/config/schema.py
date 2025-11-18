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


class TranscriptionConfig(BaseModel):
    """Transcription service configuration."""

    model_name: str = "gemini-2.5-flash"
    api_key: str | None = None  # If None, will use environment variable
    cost_threshold_usd: float = 1.0
    youtube_check: bool = True  # Try YouTube transcripts first (free tier)


class ExtractionConfig(BaseModel):
    """Extraction service configuration."""

    default_provider: Literal["claude", "gemini"] = "gemini"
    claude_api_key: str | None = None  # If None, will use environment variable
    gemini_api_key: str | None = None  # If None, will use environment variable


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

    # Service configurations
    transcription: TranscriptionConfig = Field(default_factory=TranscriptionConfig)
    extraction: ExtractionConfig = Field(default_factory=ExtractionConfig)
    interview: InterviewConfig = Field(default_factory=InterviewConfig)

    # Deprecated fields (for backward compatibility with existing configs)
    transcription_model: str | None = None
    interview_model: str | None = None
    youtube_check: bool | None = None

    def model_post_init(self, __context) -> None:
        """Handle deprecated config fields."""
        # Migrate deprecated transcription_model to transcription.model_name
        if self.transcription_model is not None:
            self.transcription.model_name = self.transcription_model

        # Migrate deprecated interview_model to interview.model
        if self.interview_model is not None:
            self.interview.model = self.interview_model

        # Migrate deprecated youtube_check to transcription.youtube_check
        if self.youtube_check is not None:
            self.transcription.youtube_check = self.youtube_check


class Feeds(BaseModel):
    """Collection of podcast feeds."""

    feeds: dict[str, FeedConfig] = Field(default_factory=dict)
