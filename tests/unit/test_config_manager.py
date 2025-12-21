"""Tests for ConfigManager."""

from pathlib import Path

import pytest
import yaml

from inkwell.config.manager import ConfigManager
from inkwell.config.schema import AuthConfig, FeedConfig, GlobalConfig
from inkwell.utils.errors import ConfigError, NotFoundError, ValidationError


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

        with pytest.raises(ValidationError, match="already exists"):
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

        with pytest.raises(NotFoundError, match="not found"):
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

        with pytest.raises(NotFoundError, match="not found"):
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

        with pytest.raises(NotFoundError, match="not found"):
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

        with pytest.raises(ConfigError, match="YAML"):
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

    def test_load_feeds_with_empty_decrypted_username(self, tmp_path: Path, mocker) -> None:
        """Test that empty decrypted username raises InvalidConfigError."""
        manager = ConfigManager(config_dir=tmp_path)

        # Add feed with auth
        feed_config = FeedConfig(
            url="https://example.com/feed.rss",  # type: ignore
            auth=AuthConfig(type="basic", username="user", password="secret"),
        )
        manager.add_feed("test-podcast", feed_config)

        # Mock decryptor to return empty string for username
        original_decrypt = manager.encryptor.decrypt

        def mock_decrypt(value: str) -> str:
            if "user" in original_decrypt(value):
                return ""  # Empty username
            return original_decrypt(value)

        mocker.patch.object(manager.encryptor, "decrypt", side_effect=mock_decrypt)

        with pytest.raises(ConfigError) as exc_info:
            manager.load_feeds()

        assert "empty after decryption" in str(exc_info.value)
        assert "keyfile may be corrupted" in str(exc_info.value)
        assert "test-podcast" in str(exc_info.value)

    def test_load_feeds_with_null_bytes_in_decrypted_password(self, tmp_path: Path, mocker) -> None:
        """Test that null bytes in decrypted password raises InvalidConfigError."""
        manager = ConfigManager(config_dir=tmp_path)

        # Add feed with auth
        feed_config = FeedConfig(
            url="https://example.com/feed.rss",  # type: ignore
            auth=AuthConfig(type="basic", username="user", password="secret"),
        )
        manager.add_feed("test-podcast", feed_config)

        # Mock decryptor to return password with null bytes
        original_decrypt = manager.encryptor.decrypt

        def mock_decrypt(value: str) -> str:
            decrypted = original_decrypt(value)
            if decrypted == "secret":
                return "password\x00\xff\xfe"  # Corrupted password with null bytes
            return decrypted

        mocker.patch.object(manager.encryptor, "decrypt", side_effect=mock_decrypt)

        with pytest.raises(ConfigError) as exc_info:
            manager.load_feeds()

        assert "null bytes" in str(exc_info.value)
        assert "likely corruption" in str(exc_info.value)
        assert "keyfile may be corrupted" in str(exc_info.value)
        assert "test-podcast" in str(exc_info.value)

    def test_load_feeds_with_oversized_token(self, tmp_path: Path, mocker) -> None:
        """Test that oversized token raises InvalidConfigError."""
        manager = ConfigManager(config_dir=tmp_path)

        # Add feed with bearer token
        feed_config = FeedConfig(
            url="https://example.com/feed.rss",  # type: ignore
            auth=AuthConfig(type="bearer", token="secret-token"),
        )
        manager.add_feed("test-podcast", feed_config)

        # Mock decryptor to return oversized token
        original_decrypt = manager.encryptor.decrypt

        def mock_decrypt(value: str) -> str:
            decrypted = original_decrypt(value)
            if decrypted == "secret-token":
                return "x" * 1001  # Token exceeds max length of 1000
            return decrypted

        mocker.patch.object(manager.encryptor, "decrypt", side_effect=mock_decrypt)

        with pytest.raises(ConfigError) as exc_info:
            manager.load_feeds()

        assert "exceeds maximum length" in str(exc_info.value)
        assert "keyfile may be corrupted" in str(exc_info.value)
        assert "test-podcast" in str(exc_info.value)

    def test_load_feeds_with_corrupted_keyfile(self, tmp_path: Path) -> None:
        """Test that corrupted keyfile raises clear InvalidConfigError."""
        manager = ConfigManager(config_dir=tmp_path)

        # Add feed with auth
        feed_config = FeedConfig(
            url="https://example.com/feed.rss",  # type: ignore
            auth=AuthConfig(type="basic", username="user", password="secret"),
        )
        manager.add_feed("test-podcast", feed_config)

        # Corrupt the keyfile
        keyfile_path = tmp_path / ".keyfile"
        keyfile_path.write_text("corrupted-keyfile-data-123")

        # Create a new manager instance to bypass cipher caching
        manager_new = ConfigManager(config_dir=tmp_path)

        with pytest.raises(ConfigError) as exc_info:
            manager_new.load_feeds()

        assert "keyfile may be corrupted" in str(exc_info.value)
        assert "Possible fixes" in str(exc_info.value)
        assert "Restore .keyfile from backup" in str(exc_info.value)
        assert "test-podcast" in str(exc_info.value)

    def test_load_feeds_with_valid_credentials_succeeds(self, tmp_path: Path) -> None:
        """Test that valid credentials decrypt and validate successfully."""
        manager = ConfigManager(config_dir=tmp_path)

        # Add feed with auth (various credential types)
        feed_config = FeedConfig(
            url="https://example.com/feed.rss",  # type: ignore
            auth=AuthConfig(type="basic", username="validuser", password="validpass123"),
        )
        manager.add_feed("test-podcast", feed_config)

        # Load feeds - should not raise
        feeds = manager.load_feeds()

        assert "test-podcast" in feeds.feeds
        assert feeds.feeds["test-podcast"].auth.username == "validuser"
        assert feeds.feeds["test-podcast"].auth.password == "validpass123"

    def test_load_feeds_validates_username_length_limit(self, tmp_path: Path, mocker) -> None:
        """Test that username length limit is enforced."""
        manager = ConfigManager(config_dir=tmp_path)

        # Add feed with auth
        feed_config = FeedConfig(
            url="https://example.com/feed.rss",  # type: ignore
            auth=AuthConfig(type="basic", username="user", password="secret"),
        )
        manager.add_feed("test-podcast", feed_config)

        # Mock decryptor to return oversized username
        original_decrypt = manager.encryptor.decrypt

        def mock_decrypt(value: str) -> str:
            decrypted = original_decrypt(value)
            if decrypted == "user":
                return "x" * 256  # Username exceeds max length of 255
            return decrypted

        mocker.patch.object(manager.encryptor, "decrypt", side_effect=mock_decrypt)

        with pytest.raises(ConfigError) as exc_info:
            manager.load_feeds()

        assert "exceeds maximum length" in str(exc_info.value)
        assert "255" in str(exc_info.value)

    def test_load_feeds_error_message_includes_recovery_steps(self, tmp_path: Path) -> None:
        """Test that error message provides helpful recovery steps."""
        manager = ConfigManager(config_dir=tmp_path)

        # Add feed with auth
        feed_config = FeedConfig(
            url="https://example.com/feed.rss",  # type: ignore
            auth=AuthConfig(type="basic", username="user", password="secret"),
        )
        manager.add_feed("test-podcast", feed_config)

        # Corrupt the keyfile
        keyfile_path = tmp_path / ".keyfile"
        keyfile_path.write_text("corrupted")

        # Create a new manager instance to bypass cipher caching
        manager_new = ConfigManager(config_dir=tmp_path)

        with pytest.raises(ConfigError) as exc_info:
            manager_new.load_feeds()

        error_message = str(exc_info.value)
        assert "Restore .keyfile from backup" in error_message
        assert "Re-add the feed with correct credentials" in error_message
        assert "Check keyfile permissions (should be 0600)" in error_message


class TestAuditLog:
    """Tests for audit logging functionality."""

    def test_audit_log_records_feed_addition(self, tmp_path: Path) -> None:
        """Verify feed addition is logged to audit trail."""
        import json

        manager = ConfigManager(config_dir=tmp_path)
        feed_config = FeedConfig(url="https://example.com/feed.xml")  # type: ignore

        manager.add_feed("test-feed", feed_config)

        # Check audit log
        audit_log = tmp_path / "audit.log"
        assert audit_log.exists()

        with open(audit_log) as f:
            entries = [json.loads(line) for line in f]

        assert len(entries) == 1
        assert entries[0]["operation"] == "add_feed"
        assert entries[0]["details"]["feed_name"] == "test-feed"
        assert entries[0]["details"]["url"] == "https://example.com/feed.xml"
        assert "timestamp" in entries[0]
        assert "user" in entries[0]
        assert "hostname" in entries[0]
        assert "pid" in entries[0]

    def test_audit_log_records_feed_removal_details(self, tmp_path: Path) -> None:
        """Verify feed removal logs include feed details."""
        import json

        manager = ConfigManager(config_dir=tmp_path)

        # Add then remove feed
        feed_config = FeedConfig(url="https://example.com/feed.xml")  # type: ignore
        manager.add_feed("test-feed", feed_config)
        manager.remove_feed("test-feed")

        # Check removal was logged with details
        audit_log = tmp_path / "audit.log"
        with open(audit_log) as f:
            entries = [json.loads(line) for line in f]

        removal_entries = [e for e in entries if e["operation"] == "remove_feed"]
        assert len(removal_entries) == 1

        removal = removal_entries[0]
        assert removal["details"]["feed_name"] == "test-feed"
        assert removal["details"]["url"] == "https://example.com/feed.xml"

    def test_audit_log_records_feed_update(self, tmp_path: Path) -> None:
        """Verify feed updates log what changed."""
        import json

        manager = ConfigManager(config_dir=tmp_path)

        # Add feed
        feed_config = FeedConfig(url="https://example.com/feed.xml")  # type: ignore
        manager.add_feed("test-feed", feed_config)

        # Update feed URL
        new_config = FeedConfig(url="https://newhost.com/feed.xml")  # type: ignore
        manager.update_feed("test-feed", new_config)

        # Check update was logged with changes
        audit_log = tmp_path / "audit.log"
        with open(audit_log) as f:
            entries = [json.loads(line) for line in f]

        update_entries = [e for e in entries if e["operation"] == "update_feed"]
        assert len(update_entries) == 1

        update = update_entries[0]
        assert update["details"]["feed_name"] == "test-feed"
        assert "changes" in update["details"]
        assert "url" in update["details"]["changes"]
        assert update["details"]["changes"]["url"]["old"] == "https://example.com/feed.xml"
        assert update["details"]["changes"]["url"]["new"] == "https://newhost.com/feed.xml"

    def test_audit_log_records_config_changes(self, tmp_path: Path) -> None:
        """Verify global config changes are logged."""
        import json

        manager = ConfigManager(config_dir=tmp_path)

        # Save initial config
        config1 = GlobalConfig(log_level="INFO")
        manager.save_config(config1)

        # Update config
        config2 = GlobalConfig(log_level="DEBUG")
        manager.save_config(config2)

        # Check change was logged
        audit_log = tmp_path / "audit.log"
        assert audit_log.exists()

        with open(audit_log) as f:
            entries = [json.loads(line) for line in f]

        config_entries = [e for e in entries if e["operation"] == "update_config"]
        assert len(config_entries) == 1

        update = config_entries[0]
        assert "changes" in update["details"]
        assert "log_level" in update["details"]["changes"]
        assert update["details"]["changes"]["log_level"]["old"] == "INFO"
        assert update["details"]["changes"]["log_level"]["new"] == "DEBUG"

    def test_get_feed_history(self, tmp_path: Path) -> None:
        """Verify feed history query returns all changes."""
        manager = ConfigManager(config_dir=tmp_path)

        feed_config = FeedConfig(url="https://example.com/feed.xml")  # type: ignore
        manager.add_feed("test-feed", feed_config)

        new_config = FeedConfig(url="https://newhost.com/feed.xml")  # type: ignore
        manager.update_feed("test-feed", new_config)

        history = manager.get_feed_history("test-feed")
        assert len(history) == 2
        assert history[0]["operation"] == "add_feed"
        assert history[1]["operation"] == "update_feed"

    def test_get_feed_history_empty_for_nonexistent_feed(self, tmp_path: Path) -> None:
        """Verify empty history for non-existent feed."""
        manager = ConfigManager(config_dir=tmp_path)
        history = manager.get_feed_history("nonexistent")
        assert history == []

    def test_get_feed_history_empty_when_no_audit_log(self, tmp_path: Path) -> None:
        """Verify empty history when audit log doesn't exist."""
        manager = ConfigManager(config_dir=tmp_path)
        history = manager.get_feed_history("test-feed")
        assert history == []

    def test_get_recent_changes(self, tmp_path: Path) -> None:
        """Verify get_recent_changes returns most recent entries."""
        manager = ConfigManager(config_dir=tmp_path)

        # Add multiple feeds
        for i in range(5):
            feed_config = FeedConfig(url=f"https://example.com/feed{i}.xml")  # type: ignore
            manager.add_feed(f"feed-{i}", feed_config)

        recent = manager.get_recent_changes(limit=3)
        assert len(recent) == 3

        # Should be most recent first
        assert recent[0]["details"]["feed_name"] == "feed-4"
        assert recent[1]["details"]["feed_name"] == "feed-3"
        assert recent[2]["details"]["feed_name"] == "feed-2"

    def test_get_recent_changes_empty_when_no_audit_log(self, tmp_path: Path) -> None:
        """Verify empty list when audit log doesn't exist."""
        manager = ConfigManager(config_dir=tmp_path)
        recent = manager.get_recent_changes()
        assert recent == []

    def test_audit_log_skips_malformed_lines(self, tmp_path: Path) -> None:
        """Verify audit log parsing skips malformed JSON lines."""

        manager = ConfigManager(config_dir=tmp_path)

        # Add valid entry
        feed_config = FeedConfig(url="https://example.com/feed.xml")  # type: ignore
        manager.add_feed("test-feed", feed_config)

        # Manually add malformed line
        audit_log = tmp_path / "audit.log"
        with open(audit_log, "a") as f:
            f.write("this is not valid json\n")

        # Add another valid entry
        feed_config2 = FeedConfig(url="https://example.com/feed2.xml")  # type: ignore
        manager.add_feed("test-feed-2", feed_config2)

        # Should still be able to read history
        recent = manager.get_recent_changes()
        assert len(recent) == 2  # Should skip malformed line
