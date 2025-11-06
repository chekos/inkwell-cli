"""Configuration schema models using Pydantic."""

from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, Field, HttpUrl

AuthType = Literal["none", "basic", "bearer"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR"]


class AuthConfig(BaseModel):
    """Authentication configuration for a feed."""

    type: AuthType = "none"
    username: Optional[str] = None  # Encrypted when stored
    password: Optional[str] = None  # Encrypted when stored
    token: Optional[str] = None  # Encrypted when stored (for bearer)


class FeedConfig(BaseModel):
    """Configuration for a single podcast feed."""

    url: HttpUrl
    auth: AuthConfig = Field(default_factory=AuthConfig)
    category: Optional[str] = None
    custom_templates: list[str] = Field(default_factory=list)


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


class Feeds(BaseModel):
    """Collection of podcast feeds."""

    feeds: dict[str, FeedConfig] = Field(default_factory=dict)
