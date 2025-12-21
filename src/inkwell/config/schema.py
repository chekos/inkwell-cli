"""Configuration schema models using Pydantic."""

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator

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

    model_name: str = Field(
        default="gemini-2.5-flash",
        min_length=1,
        max_length=100,
        description="Gemini model name (e.g., gemini-2.5-flash)",
    )
    api_key: str | None = Field(
        default=None,
        min_length=20,
        max_length=500,
        description="Google AI API key (if None, uses environment variable)",
    )
    cost_threshold_usd: float = Field(
        default=1.0,
        ge=0.0,
        le=1000.0,
        description="Maximum cost in USD before requiring confirmation",
    )
    youtube_check: bool = True  # Try YouTube transcripts first (free tier)

    @field_validator("model_name")
    @classmethod
    def validate_model_name(cls, v: str) -> str:
        """Validate Gemini model name format."""
        if not v.startswith("gemini-"):
            raise ValueError('Model name must start with "gemini-"')
        return v


class ExtractionConfig(BaseModel):
    """Extraction service configuration."""

    default_provider: Literal["claude", "gemini"] = "gemini"
    claude_api_key: str | None = Field(
        default=None,
        min_length=20,
        max_length=500,
        description="Anthropic API key (if None, uses environment variable)",
    )
    gemini_api_key: str | None = Field(
        default=None,
        min_length=20,
        max_length=500,
        description="Google AI API key (if None, uses environment variable)",
    )


class InterviewConfig(BaseModel):
    """Interview mode configuration."""

    enabled: bool = True
    auto_start: bool = False  # If true, always interview (no --interview flag needed)

    # Style
    default_template: str = "reflective"  # reflective, analytical, creative
    question_count: int = Field(
        default=5,
        ge=1,
        le=100,
        description="Number of interview questions (1-100)",
    )
    max_depth: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum depth for follow-up questions (1-10)",
    )

    # User preferences
    guidelines: str = Field(
        default="",
        max_length=10000,
        description="User guidelines for interview style",
    )

    # Session
    save_raw_transcript: bool = True
    resume_enabled: bool = True
    session_timeout_minutes: int = Field(
        default=60,
        ge=1,
        le=1440,
        description="Session timeout in minutes (1-1440, max 24 hours)",
    )

    # Output
    include_action_items: bool = True
    include_key_insights: bool = True
    format_style: Literal["structured", "narrative", "qa"] = "structured"

    # Cost
    max_cost_per_interview: float = Field(
        default=0.50,
        ge=0.0,
        le=100.0,
        description="Maximum cost per interview in USD (0.0-100.0)",
    )
    confirm_high_cost: bool = True

    # Advanced
    model: str = Field(
        default="claude-sonnet-4-5",
        min_length=1,
        max_length=100,
        description="Claude model for interview",
    )
    temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="Model temperature for response variability (0.0-2.0)",
    )
    streaming: bool = True


class GlobalConfig(BaseModel):
    """Global Inkwell configuration."""

    version: str = "1"
    default_output_dir: Path = Field(default_factory=lambda: Path("~/podcasts"))
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

    @model_validator(mode="after")
    def expand_user_path(self) -> "GlobalConfig":
        """Expand ~ in default_output_dir to user home directory."""
        self.default_output_dir = self.default_output_dir.expanduser()
        return self

    def model_post_init(self, __context: Any) -> None:
        """Handle deprecated config fields.

        Migration strategy: Only apply deprecated fields if the user didn't
        explicitly provide the new nested config. Uses model_fields_set to
        detect which fields were explicitly provided during initialization.

        This allows users to explicitly set new config values without being
        overridden by deprecated fields, enabling safe gradual migration.
        """
        # Migrate transcription_model only if user didn't explicitly set transcription config
        if self.transcription_model is not None:
            # Check if 'transcription' was explicitly provided during initialization
            if "transcription" not in self.model_fields_set:
                self.transcription.model_name = self.transcription_model
            # else: User explicitly set new config, respect their choice

        # Migrate interview_model only if user didn't explicitly set interview config
        if self.interview_model is not None:
            if "interview" not in self.model_fields_set:
                self.interview.model = self.interview_model

        # Migrate youtube_check only if user didn't explicitly set transcription config
        if self.youtube_check is not None:
            if "transcription" not in self.model_fields_set:
                self.transcription.youtube_check = self.youtube_check


class Feeds(BaseModel):
    """Collection of podcast feeds."""

    feeds: dict[str, FeedConfig] = Field(default_factory=dict)
