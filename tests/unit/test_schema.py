"""Tests for configuration schema models."""

from pathlib import Path

import pytest
from pydantic import HttpUrl, ValidationError

from inkwell.config.schema import AuthConfig, FeedConfig, Feeds, GlobalConfig


class TestAuthConfig:
    """Tests for AuthConfig model."""

    def test_auth_config_default_is_none(self) -> None:
        """Test that default auth type is 'none'."""
        auth = AuthConfig()
        assert auth.type == "none"
        assert auth.username is None
        assert auth.password is None
        assert auth.token is None

    def test_auth_config_basic_auth(self) -> None:
        """Test basic authentication configuration."""
        auth = AuthConfig(
            type="basic",
            username="user",
            password="pass",
        )
        assert auth.type == "basic"
        assert auth.username == "user"
        assert auth.password == "pass"
        assert auth.token is None

    def test_auth_config_bearer_auth(self) -> None:
        """Test bearer token authentication configuration."""
        auth = AuthConfig(
            type="bearer",
            token="secret-token",
        )
        assert auth.type == "bearer"
        assert auth.token == "secret-token"
        assert auth.username is None
        assert auth.password is None

    def test_auth_config_invalid_type_raises(self) -> None:
        """Test that invalid auth type raises ValidationError."""
        with pytest.raises(ValidationError):
            AuthConfig(type="invalid")  # type: ignore


class TestFeedConfig:
    """Tests for FeedConfig model."""

    def test_feed_config_minimal(self) -> None:
        """Test FeedConfig with minimal required fields."""
        feed = FeedConfig(url="https://example.com/feed.rss")  # type: ignore
        assert isinstance(feed.url, HttpUrl)
        assert feed.auth.type == "none"
        assert feed.category is None
        assert feed.custom_templates == []

    def test_feed_config_with_all_fields(self, sample_feed_config_dict: dict) -> None:
        """Test FeedConfig with all fields populated."""
        feed = FeedConfig(**sample_feed_config_dict)
        assert str(feed.url) == "https://example.com/feed.rss"
        assert feed.category == "tech"
        assert feed.custom_templates == ["architecture-patterns"]

    def test_feed_config_invalid_url_raises(self) -> None:
        """Test that invalid URL raises ValidationError."""
        with pytest.raises(ValidationError):
            FeedConfig(url="not-a-url")  # type: ignore

    def test_feed_config_with_auth(self) -> None:
        """Test FeedConfig with authentication."""
        feed = FeedConfig(
            url="https://example.com/feed.rss",  # type: ignore
            auth=AuthConfig(type="basic", username="user", password="pass"),
        )
        assert feed.auth.type == "basic"
        assert feed.auth.username == "user"


class TestGlobalConfig:
    """Tests for GlobalConfig model."""

    def test_global_config_defaults(self) -> None:
        """Test GlobalConfig with default values."""
        config = GlobalConfig()
        assert config.version == "1"
        assert config.default_output_dir == Path("~/podcasts")
        assert config.log_level == "INFO"
        assert "summary" in config.default_templates
        assert "quotes" in config.default_templates
        assert "key-concepts" in config.default_templates
        assert "tech" in config.template_categories
        assert "interview" in config.template_categories

        # New nested config structure
        assert config.transcription.model_name == "gemini-2.5-flash"
        assert config.transcription.youtube_check is True
        assert config.transcription.cost_threshold_usd == 1.0
        assert config.interview.model == "claude-sonnet-4-5"
        assert config.extraction.default_provider == "gemini"

    def test_global_config_from_dict(self, sample_config_dict: dict) -> None:
        """Test GlobalConfig created from dictionary."""
        config = GlobalConfig(**sample_config_dict)
        assert config.version == "1"
        assert config.log_level == "INFO"
        assert config.youtube_check is True

    def test_global_config_custom_output_dir(self) -> None:
        """Test GlobalConfig with custom output directory."""
        config = GlobalConfig(default_output_dir=Path("/custom/path"))
        assert config.default_output_dir == Path("/custom/path")

    def test_global_config_invalid_log_level_raises(self) -> None:
        """Test that invalid log level raises ValidationError."""
        with pytest.raises(ValidationError):
            GlobalConfig(log_level="INVALID")  # type: ignore

    def test_global_config_template_categories(self) -> None:
        """Test template categories structure."""
        config = GlobalConfig()
        assert isinstance(config.template_categories, dict)
        assert isinstance(config.template_categories["tech"], list)
        assert "tools-mentioned" in config.template_categories["tech"]
        assert "books-mentioned" in config.template_categories["interview"]

    def test_global_config_backward_compatibility(self) -> None:
        """Test that deprecated fields still work via migration."""
        config = GlobalConfig(
            transcription_model="gemini-1.5-flash",
            interview_model="claude-opus-4",
            youtube_check=False,
        )
        # Deprecated fields should migrate to new structure
        assert config.transcription.model_name == "gemini-1.5-flash"
        assert config.interview.model == "claude-opus-4"
        assert config.transcription.youtube_check is False


class TestFeeds:
    """Tests for Feeds model."""

    def test_feeds_empty_default(self) -> None:
        """Test that Feeds defaults to empty dictionary."""
        feeds = Feeds()
        assert feeds.feeds == {}

    def test_feeds_with_feed(self) -> None:
        """Test Feeds with a single feed."""
        feed_config = FeedConfig(url="https://example.com/feed.rss")  # type: ignore
        feeds = Feeds(feeds={"my-podcast": feed_config})
        assert "my-podcast" in feeds.feeds
        assert isinstance(feeds.feeds["my-podcast"], FeedConfig)

    def test_feeds_multiple_feeds(self) -> None:
        """Test Feeds with multiple feeds."""
        feeds = Feeds(
            feeds={
                "podcast1": FeedConfig(url="https://example.com/feed1.rss"),  # type: ignore
                "podcast2": FeedConfig(url="https://example.com/feed2.rss"),  # type: ignore
            }
        )
        assert len(feeds.feeds) == 2
        assert "podcast1" in feeds.feeds
        assert "podcast2" in feeds.feeds

    def test_feeds_serialization(self) -> None:
        """Test that Feeds can be serialized and deserialized."""
        original = Feeds(
            feeds={"test": FeedConfig(url="https://example.com/feed.rss")}  # type: ignore
        )
        # Serialize to dict
        data = original.model_dump()
        # Deserialize back
        restored = Feeds(**data)
        assert "test" in restored.feeds
        assert str(restored.feeds["test"].url) == "https://example.com/feed.rss"
