"""Tests for config validation error handling."""

from pathlib import Path

import pytest

from inkwell.config.manager import ConfigManager
from inkwell.utils.errors import ConfigError


class TestConfigValidationErrors:
    """Tests for friendly config validation error messages."""

    def test_invalid_log_level_shows_friendly_error(self, tmp_path: Path) -> None:
        """Test that invalid log level shows user-friendly error."""
        # Create config with invalid log_level
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            """
version: "1"
log_level: INVALID_LEVEL
default_output_dir: ~/podcasts
"""
        )

        manager = ConfigManager(config_dir=tmp_path)

        with pytest.raises(ConfigError) as exc_info:
            manager.load_config()

        error_msg = str(exc_info.value)
        # Should mention the field
        assert "log_level" in error_msg
        # Should mention how to fix
        assert "inkwell config edit" in error_msg
        # Should not be a raw ValidationError
        assert "ValidationError" not in error_msg

    def test_invalid_url_in_feeds_shows_friendly_error(self, tmp_path: Path) -> None:
        """Test that invalid feed URL shows user-friendly error."""
        feeds_file = tmp_path / "feeds.yaml"
        feeds_file.write_text(
            """
feeds:
  test-feed:
    url: not-a-valid-url
    auth:
      type: none
"""
        )

        manager = ConfigManager(config_dir=tmp_path)

        with pytest.raises(ConfigError) as exc_info:
            manager.load_feeds()

        error_msg = str(exc_info.value)
        # Should mention the problematic field
        assert "url" in error_msg
        # Should provide guidance
        assert "feeds.yaml" in error_msg

    def test_invalid_auth_type_shows_friendly_error(self, tmp_path: Path) -> None:
        """Test that invalid auth type shows user-friendly error."""
        feeds_file = tmp_path / "feeds.yaml"
        feeds_file.write_text(
            """
feeds:
  test-feed:
    url: https://example.com/feed.rss
    auth:
      type: invalid_auth_type
"""
        )

        manager = ConfigManager(config_dir=tmp_path)

        with pytest.raises(ConfigError) as exc_info:
            manager.load_feeds()

        error_msg = str(exc_info.value)
        assert "auth" in error_msg or "type" in error_msg

    def test_yaml_syntax_error_shows_friendly_message(self, tmp_path: Path) -> None:
        """Test that YAML syntax errors show friendly message."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            """
version: "1"
log_level: INFO
invalid yaml syntax here: [unclosed bracket
"""
        )

        manager = ConfigManager(config_dir=tmp_path)

        with pytest.raises(ConfigError) as exc_info:
            manager.load_config()

        error_msg = str(exc_info.value)
        # Should mention YAML syntax
        assert "YAML" in error_msg or "syntax" in error_msg
        # Should provide guidance
        assert "inkwell config edit" in error_msg

    def test_missing_required_field_shows_friendly_error(self, tmp_path: Path) -> None:
        """Test that missing required fields show friendly error."""
        feeds_file = tmp_path / "feeds.yaml"
        feeds_file.write_text(
            """
feeds:
  test-feed:
    auth:
      type: none
    # Missing required 'url' field
"""
        )

        manager = ConfigManager(config_dir=tmp_path)

        with pytest.raises(ConfigError) as exc_info:
            manager.load_feeds()

        error_msg = str(exc_info.value)
        # Should indicate the problem
        assert "url" in error_msg or "required" in error_msg.lower()


class TestConfigEdgeCases:
    """Tests for configuration edge cases."""

    def test_config_with_unicode_category(self, tmp_path: Path) -> None:
        """Test feed with unicode characters in category."""
        from inkwell.config.schema import AuthConfig, FeedConfig

        manager = ConfigManager(config_dir=tmp_path)

        feed_config = FeedConfig(
            url="https://example.com/feed.rss",  # type: ignore
            auth=AuthConfig(type="none"),
            category="技術 (Tech)",  # Japanese characters
        )

        # Should save and load successfully
        manager.add_feed("unicode-test", feed_config)
        loaded_feed = manager.get_feed("unicode-test")

        assert loaded_feed.category == "技術 (Tech)"

    def test_config_with_very_long_url(self, tmp_path: Path) -> None:
        """Test feed with very long URL."""
        from inkwell.config.schema import AuthConfig, FeedConfig

        manager = ConfigManager(config_dir=tmp_path)

        # Create a very long URL
        long_url = "https://example.com/" + "a" * 500 + "/feed.rss"

        feed_config = FeedConfig(
            url=long_url,  # type: ignore
            auth=AuthConfig(type="none"),
        )

        # Should save and load successfully
        manager.add_feed("long-url-test", feed_config)
        loaded_feed = manager.get_feed("long-url-test")

        assert str(loaded_feed.url) == long_url

    def test_config_with_special_characters_in_name(self, tmp_path: Path) -> None:
        """Test feed with special characters in name."""
        from inkwell.config.schema import AuthConfig, FeedConfig

        manager = ConfigManager(config_dir=tmp_path)

        feed_config = FeedConfig(
            url="https://example.com/feed.rss",  # type: ignore
            auth=AuthConfig(type="none"),
        )

        # Use name with hyphens, underscores
        feed_name = "my-podcast_v2.0"

        manager.add_feed(feed_name, feed_config)
        loaded_feed = manager.get_feed(feed_name)

        assert str(loaded_feed.url) == "https://example.com/feed.rss"

    def test_empty_config_file(self, tmp_path: Path) -> None:
        """Test loading empty config file."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("")

        manager = ConfigManager(config_dir=tmp_path)
        config = manager.load_config()

        # Should load with defaults
        assert config.version == "1"
        assert config.log_level == "INFO"

    def test_config_with_only_feeds(self, tmp_path: Path) -> None:
        """Test feeds file with only feeds section."""
        feeds_file = tmp_path / "feeds.yaml"
        feeds_file.write_text(
            """
feeds:
  test-feed:
    url: https://example.com/feed.rss
    auth:
      type: none
"""
        )

        manager = ConfigManager(config_dir=tmp_path)
        feeds = manager.load_feeds()

        assert "test-feed" in feeds.feeds
        assert str(feeds.feeds["test-feed"].url) == "https://example.com/feed.rss"

    def test_config_roundtrip_preserves_comments(self, tmp_path: Path) -> None:
        """Test that config saves cleanly (comments are lost but data preserved)."""
        from inkwell.config.schema import AuthConfig, FeedConfig

        manager = ConfigManager(config_dir=tmp_path)

        feed_config = FeedConfig(
            url="https://example.com/feed.rss",  # type: ignore
            auth=AuthConfig(type="none"),
            category="tech",
        )

        manager.add_feed("test", feed_config)

        # Reload and verify
        reloaded_feeds = manager.load_feeds()
        assert "test" in reloaded_feeds.feeds
        assert reloaded_feeds.feeds["test"].category == "tech"
