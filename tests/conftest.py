"""Pytest configuration and shared fixtures."""

import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest


@pytest.fixture
def tmp_config_dir() -> Generator[Path, None, None]:
    """Create a temporary config directory for testing.

    Yields:
        Path to temporary config directory
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_config_dict() -> dict:
    """Sample configuration dictionary for testing.

    Returns:
        Dictionary with sample config data
    """
    return {
        "version": "1",
        "default_output_dir": "~/podcasts",
        "transcription_model": "gemini-2.0-flash-exp",
        "interview_model": "claude-sonnet-4-5",
        "youtube_check": True,
        "log_level": "INFO",
        "default_templates": ["summary", "quotes", "key-concepts"],
        "template_categories": {
            "tech": ["tools-mentioned", "frameworks-mentioned"],
            "interview": ["books-mentioned", "people-mentioned"],
        },
    }


@pytest.fixture
def sample_feed_config_dict() -> dict:
    """Sample feed configuration dictionary for testing.

    Returns:
        Dictionary with sample feed config data
    """
    return {
        "url": "https://example.com/feed.rss",
        "auth": {"type": "none"},
        "category": "tech",
        "custom_templates": ["architecture-patterns"],
    }
