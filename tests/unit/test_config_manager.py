"""Tests for ConfigManager."""

from pathlib import Path

import pytest
import yaml

from inkwell.config.manager import ConfigManager
from inkwell.config.schema import AuthConfig, FeedConfig, GlobalConfig
from inkwell.utils.errors import DuplicateFeedError, FeedNotFoundError, InvalidConfigError


class TestConfigManager:
    """Tests for ConfigManager class."""

    def test_init_with_custom_dir(self, tmp_path: Path) -> None:
        """Test ConfigManager initialization with custom directory."""
        manager = ConfigManager(config_dir=tmp_path)
        assert manager.config_dir == tmp_path
        assert manager.config_file == tmp_path / "config.yaml"
        assert manager.feeds_file == tmp_path / "feeds.yaml"
        assert manager.key_file == tmp_path / ".keyfile"

    def test_load_config_creates_default_if_missing(self, tmp_path: Path) -> None:
        """Test that load_config creates default config if file doesn't exist."""
        manager = ConfigManager(config_dir=tmp_path)
        config = manager.load_config()

        assert isinstance(config, GlobalConfig)
        assert manager.config_file.exists()

    def test_load_config_from_existing_file(self, tmp_path: Path, sample_config_dict: dict) -> None:
        """Test loading config from existing file."""
        config_file = tmp_path / "config.yaml"
        with open(config_file, "w") as f:
            yaml.safe_dump(sample_config_dict, f)

        manager = ConfigManager(config_dir=tmp_path)
        config = manager.load_config()

        assert config.version == "1"
        assert config.log_level == "INFO"

    def test_save_config(self, tmp_path: Path) -> None:
        """Test saving configuration."""
        manager = ConfigManager(config_dir=tmp_path)
        config = GlobalConfig(log_level="DEBUG")

        manager.save_config(config)

        assert manager.config_file.exists()

        # Read back and verify
        with open(manager.config_file) as f:
            data = yaml.safe_load(f)
        assert data["log_level"] == "DEBUG"

    def test_load_feeds_creates_default_if_missing(self, tmp_path: Path) -> None:
        """Test that load_feeds creates default feeds file if missing."""
        manager = ConfigManager(config_dir=tmp_path)
        feeds = manager.load_feeds()

        assert len(feeds.feeds) == 0
        assert manager.feeds_file.exists()

    def test_save_and_load_feeds(self, tmp_path: Path) -> None:
        """Test saving and loading feeds."""
        manager = ConfigManager(config_dir=tmp_path)

        # Create a feed
        feed_config = FeedConfig(
            url="https://example.com/feed.rss",  # type: ignore
            category="tech",
        )

        # Add feed
        manager.add_feed("test-podcast", feed_config)

        # Load feeds
        feeds = manager.load_feeds()

        assert "test-podcast" in feeds.feeds
        assert str(feeds.feeds["test-podcast"].url) == "https://example.com/feed.rss"
        assert feeds.feeds["test-podcast"].category == "tech"

    def test_add_feed(self, tmp_path: Path) -> None:
        """Test adding a feed."""
        manager = ConfigManager(config_dir=tmp_path)
        feed_config = FeedConfig(url="https://example.com/feed.rss")  # type: ignore

        manager.add_feed("my-podcast", feed_config)

        feeds = manager.list_feeds()
        assert "my-podcast" in feeds

    def test_add_duplicate_feed_raises(self, tmp_path: Path) -> None:
        """Test that adding duplicate feed raises DuplicateFeedError."""
        manager = ConfigManager(config_dir=tmp_path)
        feed_config = FeedConfig(url="https://example.com/feed.rss")  # type: ignore

        manager.add_feed("my-podcast", feed_config)

        with pytest.raises(DuplicateFeedError, match="already exists"):
            manager.add_feed("my-podcast", feed_config)

    def test_update_feed(self, tmp_path: Path) -> None:
        """Test updating an existing feed."""
        manager = ConfigManager(config_dir=tmp_path)

        # Add feed
        feed_config = FeedConfig(url="https://example.com/feed.rss", category="tech")  # type: ignore
        manager.add_feed("my-podcast", feed_config)

        # Update feed
        updated_config = FeedConfig(url="https://example.com/feed.rss", category="interview")  # type: ignore
        manager.update_feed("my-podcast", updated_config)

        # Verify update
        feed = manager.get_feed("my-podcast")
        assert feed.category == "interview"

    def test_update_nonexistent_feed_raises(self, tmp_path: Path) -> None:
        """Test that updating nonexistent feed raises FeedNotFoundError."""
        manager = ConfigManager(config_dir=tmp_path)
        feed_config = FeedConfig(url="https://example.com/feed.rss")  # type: ignore

        with pytest.raises(FeedNotFoundError, match="not found"):
            manager.update_feed("nonexistent", feed_config)

    def test_remove_feed(self, tmp_path: Path) -> None:
        """Test removing a feed."""
        manager = ConfigManager(config_dir=tmp_path)

        # Add feed
        feed_config = FeedConfig(url="https://example.com/feed.rss")  # type: ignore
        manager.add_feed("my-podcast", feed_config)

        # Remove feed
        manager.remove_feed("my-podcast")

        # Verify removal
        feeds = manager.list_feeds()
        assert "my-podcast" not in feeds

    def test_remove_nonexistent_feed_raises(self, tmp_path: Path) -> None:
        """Test that removing nonexistent feed raises FeedNotFoundError."""
        manager = ConfigManager(config_dir=tmp_path)

        with pytest.raises(FeedNotFoundError, match="not found"):
            manager.remove_feed("nonexistent")

    def test_get_feed(self, tmp_path: Path) -> None:
        """Test getting a single feed."""
        manager = ConfigManager(config_dir=tmp_path)

        # Add feed
        feed_config = FeedConfig(url="https://example.com/feed.rss")  # type: ignore
        manager.add_feed("my-podcast", feed_config)

        # Get feed
        feed = manager.get_feed("my-podcast")

        assert str(feed.url) == "https://example.com/feed.rss"

    def test_get_nonexistent_feed_raises(self, tmp_path: Path) -> None:
        """Test that getting nonexistent feed raises FeedNotFoundError."""
        manager = ConfigManager(config_dir=tmp_path)

        with pytest.raises(FeedNotFoundError, match="not found"):
            manager.get_feed("nonexistent")

    def test_list_feeds_empty(self, tmp_path: Path) -> None:
        """Test listing feeds when none exist."""
        manager = ConfigManager(config_dir=tmp_path)
        feeds = manager.list_feeds()

        assert len(feeds) == 0

    def test_list_feeds_multiple(self, tmp_path: Path) -> None:
        """Test listing multiple feeds."""
        manager = ConfigManager(config_dir=tmp_path)

        # Add multiple feeds
        for i in range(3):
            feed_config = FeedConfig(url=f"https://example.com/feed{i}.rss")  # type: ignore
            manager.add_feed(f"podcast-{i}", feed_config)

        feeds = manager.list_feeds()
        assert len(feeds) == 3

    def test_credentials_are_encrypted_on_disk(self, tmp_path: Path) -> None:
        """Test that credentials are encrypted when saved to disk."""
        manager = ConfigManager(config_dir=tmp_path)

        # Add feed with auth
        feed_config = FeedConfig(
            url="https://example.com/feed.rss",  # type: ignore
            auth=AuthConfig(type="basic", username="user", password="secret"),
        )
        manager.add_feed("private-podcast", feed_config)

        # Read raw YAML file
        with open(manager.feeds_file) as f:
            raw_data = yaml.safe_load(f)

        # Credentials should be encrypted (not plaintext)
        auth = raw_data["feeds"]["private-podcast"]["auth"]
        assert auth["username"] != "user"  # Should be encrypted
        assert auth["password"] != "secret"  # Should be encrypted

    def test_credentials_are_decrypted_when_loaded(self, tmp_path: Path) -> None:
        """Test that credentials are decrypted when loaded."""
        manager = ConfigManager(config_dir=tmp_path)

        # Add feed with auth
        feed_config = FeedConfig(
            url="https://example.com/feed.rss",  # type: ignore
            auth=AuthConfig(type="basic", username="user", password="secret"),
        )
        manager.add_feed("private-podcast", feed_config)

        # Load feed
        feed = manager.get_feed("private-podcast")

        # Credentials should be decrypted
        assert feed.auth.username == "user"
        assert feed.auth.password == "secret"

    def test_bearer_token_encryption(self, tmp_path: Path) -> None:
        """Test that bearer tokens are encrypted."""
        manager = ConfigManager(config_dir=tmp_path)

        # Add feed with bearer token
        feed_config = FeedConfig(
            url="https://example.com/feed.rss",  # type: ignore
            auth=AuthConfig(type="bearer", token="secret-token-123"),
        )
        manager.add_feed("private-podcast", feed_config)

        # Read raw YAML
        with open(manager.feeds_file) as f:
            raw_data = yaml.safe_load(f)

        # Token should be encrypted
        auth = raw_data["feeds"]["private-podcast"]["auth"]
        assert auth["token"] != "secret-token-123"

        # But should decrypt correctly
        feed = manager.get_feed("private-podcast")
        assert feed.auth.token == "secret-token-123"

    def test_invalid_config_yaml_raises_error(self, tmp_path: Path) -> None:
        """Test that invalid config.yaml raises InvalidConfigError."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("invalid: yaml: content: [[[")

        manager = ConfigManager(config_dir=tmp_path)

        with pytest.raises(InvalidConfigError, match="Invalid configuration"):
            manager.load_config()

    def test_config_roundtrip_preserves_data(self, tmp_path: Path) -> None:
        """Test that saving and loading config preserves all data."""
        manager = ConfigManager(config_dir=tmp_path)

        # Create custom config
        original = GlobalConfig(
            log_level="DEBUG",
            youtube_check=False,
            default_templates=["summary", "quotes"],
        )

        manager.save_config(original)
        loaded = manager.load_config()

        assert loaded.log_level == "DEBUG"
        assert loaded.youtube_check is False
        assert loaded.default_templates == ["summary", "quotes"]
