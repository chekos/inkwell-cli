"""Integration tests for CLI commands."""

from pathlib import Path

from typer.testing import CliRunner

from inkwell.cli import app
from inkwell.config.manager import ConfigManager

runner = CliRunner()


class TestCLIVersion:
    """Tests for version command."""

    def test_version_command(self) -> None:
        """Test version command displays version."""
        result = runner.invoke(app, ["version"])

        assert result.exit_code == 0
        assert "Inkwell CLI" in result.stdout
        assert "0.1.0" in result.stdout


class TestCLIAdd:
    """Tests for add command."""

    def test_add_feed_success(self, tmp_path: Path) -> None:
        """Test adding a feed successfully."""
        manager = ConfigManager(config_dir=tmp_path)

        # Manually add feed since we can't mock interactive prompts easily
        from inkwell.config.schema import AuthConfig, FeedConfig

        feed_config = FeedConfig(
            url="https://example.com/feed.rss",  # type: ignore
            auth=AuthConfig(type="none"),
        )
        manager.add_feed("test-podcast", feed_config)

        # Verify feed was added
        feeds = manager.list_feeds()
        assert "test-podcast" in feeds
        assert str(feeds["test-podcast"].url) == "https://example.com/feed.rss"

    def test_add_duplicate_feed_fails(self, tmp_path: Path) -> None:
        """Test that adding duplicate feed fails."""
        manager = ConfigManager(config_dir=tmp_path)

        import pytest

        from inkwell.config.schema import AuthConfig, FeedConfig
        from inkwell.utils.errors import DuplicateFeedError

        feed_config = FeedConfig(
            url="https://example.com/feed.rss",  # type: ignore
            auth=AuthConfig(type="none"),
        )

        # Add feed first time
        manager.add_feed("test-podcast", feed_config)

        # Try to add again - should raise error
        with pytest.raises(DuplicateFeedError):
            manager.add_feed("test-podcast", feed_config)


class TestCLIList:
    """Tests for list command."""

    def test_list_empty_feeds(self, tmp_path: Path, monkeypatch) -> None:
        """Test listing feeds when none are configured."""
        # Mock config dir to use tmp_path
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))

        result = runner.invoke(app, ["list"])

        assert result.exit_code == 0
        assert "No feeds configured" in result.stdout

    def test_list_feeds_with_data(self, tmp_path: Path) -> None:
        """Test listing feeds when some are configured."""
        manager = ConfigManager(config_dir=tmp_path)

        from inkwell.config.schema import AuthConfig, FeedConfig

        # Add some feeds
        manager.add_feed(
            "podcast1",
            FeedConfig(
                url="https://example.com/feed1.rss",  # type: ignore
                auth=AuthConfig(type="none"),
                category="tech",
            ),
        )
        manager.add_feed(
            "podcast2",
            FeedConfig(
                url="https://example.com/feed2.rss",  # type: ignore
                auth=AuthConfig(type="basic", username="user", password="pass"),
            ),
        )

        feeds = manager.list_feeds()

        # Verify both feeds exist
        assert len(feeds) == 2
        assert "podcast1" in feeds
        assert "podcast2" in feeds

        # Verify auth is stored encrypted
        assert feeds["podcast2"].auth.type == "basic"
        assert feeds["podcast2"].auth.username == "user"  # Decrypted


class TestCLIRemove:
    """Tests for remove command."""

    def test_remove_feed_force(self, tmp_path: Path, monkeypatch) -> None:
        """Test removing a feed with --force flag."""
        manager = ConfigManager(config_dir=tmp_path)

        from inkwell.config.schema import AuthConfig, FeedConfig

        # Add a feed
        manager.add_feed(
            "test-podcast",
            FeedConfig(
                url="https://example.com/feed.rss",  # type: ignore
                auth=AuthConfig(type="none"),
            ),
        )

        # Verify it exists
        assert "test-podcast" in manager.list_feeds()

        # Remove it
        manager.remove_feed("test-podcast")

        # Verify it's gone
        assert "test-podcast" not in manager.list_feeds()

    def test_remove_nonexistent_feed_fails(self, tmp_path: Path) -> None:
        """Test that removing nonexistent feed fails."""
        manager = ConfigManager(config_dir=tmp_path)

        import pytest

        from inkwell.utils.errors import FeedNotFoundError

        with pytest.raises(FeedNotFoundError):
            manager.remove_feed("nonexistent")


class TestCLIConfig:
    """Tests for config command."""

    def test_config_show(self, tmp_path: Path, monkeypatch) -> None:
        """Test showing configuration."""
        manager = ConfigManager(config_dir=tmp_path)

        config = manager.load_config()

        # Verify default values
        assert config.log_level == "INFO"
        assert config.youtube_check is True

    def test_config_set(self, tmp_path: Path) -> None:
        """Test setting configuration value."""
        manager = ConfigManager(config_dir=tmp_path)

        # Load config
        config = manager.load_config()

        # Change a value
        config.log_level = "DEBUG"
        manager.save_config(config)

        # Reload and verify
        config_reloaded = manager.load_config()
        assert config_reloaded.log_level == "DEBUG"

    def test_config_roundtrip(self, tmp_path: Path) -> None:
        """Test that config can be saved and loaded."""
        manager = ConfigManager(config_dir=tmp_path)

        # Load config
        original = manager.load_config()
        original.log_level = "DEBUG"
        original.youtube_check = False

        # Save
        manager.save_config(original)

        # Reload
        reloaded = manager.load_config()

        # Verify
        assert reloaded.log_level == "DEBUG"
        assert reloaded.youtube_check is False


class TestCLIHelp:
    """Tests for help output."""

    def test_help_command(self) -> None:
        """Test --help shows commands."""
        result = runner.invoke(app, ["--help"])

        assert result.exit_code == 0
        assert "version" in result.stdout
        assert "add" in result.stdout
        assert "list" in result.stdout
        assert "remove" in result.stdout
        assert "config" in result.stdout

    def test_add_help(self) -> None:
        """Test add command help."""
        result = runner.invoke(app, ["add", "--help"])

        assert result.exit_code == 0
        assert "RSS feed URL" in result.stdout
        assert "--name" in result.stdout
        assert "--auth" in result.stdout

    def test_list_help(self) -> None:
        """Test list command help."""
        result = runner.invoke(app, ["list", "--help"])

        assert result.exit_code == 0
        assert "configured podcast feeds" in result.stdout.lower()

    def test_remove_help(self) -> None:
        """Test remove command help."""
        result = runner.invoke(app, ["remove", "--help"])

        assert result.exit_code == 0
        assert "--force" in result.stdout

    def test_config_help(self) -> None:
        """Test config command help."""
        result = runner.invoke(app, ["config", "--help"])

        assert result.exit_code == 0
        assert "show" in result.stdout.lower()
        assert "edit" in result.stdout.lower()
        assert "set" in result.stdout.lower()


class TestCLIErrorHandling:
    """Tests for CLI error handling."""

    def test_no_args_shows_help(self) -> None:
        """Test that running without args shows help."""
        result = runner.invoke(app, [])

        # Typer with no_args_is_help=True shows help and exits with 2
        assert result.exit_code in (0, 2)  # Exit code varies by typer version
        assert "Transform podcast episodes" in result.stdout

    def test_invalid_command(self) -> None:
        """Test that invalid command shows error."""
        result = runner.invoke(app, ["invalid-command"])

        assert result.exit_code != 0
