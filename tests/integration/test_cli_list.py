"""Integration tests for list subcommands."""

import os
from pathlib import Path

from typer.testing import CliRunner

from inkwell.cli import app

# Disable Rich formatting in tests for consistent output across environments
os.environ["NO_COLOR"] = "1"
os.environ["TERM"] = "dumb"

runner = CliRunner()


class TestListDefault:
    """Tests for `inkwell list` (default behavior)."""

    def test_list_no_args_shows_feeds(self, tmp_path: Path, monkeypatch) -> None:
        """inkwell list with no args should show feeds (backward compat)."""
        monkeypatch.setattr("inkwell.utils.paths.get_config_dir", lambda: tmp_path)

        result = runner.invoke(app, ["list"])

        assert result.exit_code == 0
        # Should show empty state or feeds table
        assert "No feeds configured" in result.stdout or "Configured" in result.stdout


class TestListFeeds:
    """Tests for `inkwell list feeds`."""

    def test_list_feeds_empty(self, tmp_path: Path, monkeypatch) -> None:
        """Empty feeds should show helpful message."""
        monkeypatch.setattr("inkwell.utils.paths.get_config_dir", lambda: tmp_path)

        result = runner.invoke(app, ["list", "feeds"])

        assert result.exit_code == 0
        assert "No feeds configured" in result.stdout

    def test_list_feeds_with_data(self, tmp_path: Path, monkeypatch) -> None:
        """Should show feeds when configured."""
        monkeypatch.setattr("inkwell.utils.paths.get_config_dir", lambda: tmp_path)

        from inkwell.config.manager import ConfigManager
        from inkwell.config.schema import AuthConfig, FeedConfig

        manager = ConfigManager(config_dir=tmp_path)
        manager.add_feed(
            "test-podcast",
            FeedConfig(
                url="https://example.com/feed.rss",  # type: ignore
                auth=AuthConfig(type="none"),
                category="tech",
            ),
        )

        result = runner.invoke(app, ["list", "feeds"])

        assert result.exit_code == 0
        assert "test-podcast" in result.stdout
        assert "example.com" in result.stdout


class TestListTemplates:
    """Tests for `inkwell list templates`."""

    def test_list_templates_shows_builtin(self) -> None:
        """Should show built-in templates."""
        result = runner.invoke(app, ["list", "templates"])

        assert result.exit_code == 0
        # Check for known built-in templates
        assert "summary" in result.stdout.lower()
        assert "Extraction Templates" in result.stdout

    def test_list_templates_shows_count(self) -> None:
        """Should show template count."""
        result = runner.invoke(app, ["list", "templates"])

        assert result.exit_code == 0
        assert "template(s)" in result.stdout


class TestListEpisodes:
    """Tests for `inkwell list episodes <feed>`."""

    def test_list_episodes_requires_feed(self) -> None:
        """inkwell list episodes requires feed argument."""
        result = runner.invoke(app, ["list", "episodes"])

        # Should fail because feed argument is missing
        assert result.exit_code != 0

    def test_list_episodes_unknown_feed(self, tmp_path: Path, monkeypatch) -> None:
        """Unknown feed should show error."""
        monkeypatch.setattr("inkwell.utils.paths.get_config_dir", lambda: tmp_path)

        result = runner.invoke(app, ["list", "episodes", "nonexistent"])

        assert result.exit_code == 1
        assert "not found" in result.stdout.lower()


class TestListHelp:
    """Tests for help text."""

    def test_list_help_shows_subcommands(self) -> None:
        """inkwell list --help should show all subcommands."""
        result = runner.invoke(app, ["list", "--help"])

        assert result.exit_code == 0
        assert "feeds" in result.stdout
        assert "templates" in result.stdout
        assert "episodes" in result.stdout


class TestEpisodesCommandRemoved:
    """Test that old episodes command is removed."""

    def test_episodes_command_not_available(self) -> None:
        """inkwell episodes should not be available as a top-level command."""
        result = runner.invoke(app, ["episodes", "test"])

        # Should fail because 'episodes' is no longer a top-level command
        assert result.exit_code != 0


class TestListLatest:
    """Tests for `inkwell list latest`."""

    def test_list_latest_no_feeds(self, tmp_path: Path, monkeypatch) -> None:
        """Should show helpful message when no feeds configured."""
        monkeypatch.setattr("inkwell.utils.paths.get_config_dir", lambda: tmp_path)

        result = runner.invoke(app, ["list", "latest"])

        assert result.exit_code == 0
        assert "No feeds configured" in result.stdout

    def test_list_latest_json_no_feeds(self, tmp_path: Path, monkeypatch) -> None:
        """JSON output should return empty array when no feeds."""
        import json

        monkeypatch.setattr("inkwell.utils.paths.get_config_dir", lambda: tmp_path)

        result = runner.invoke(app, ["list", "latest", "--json"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["latest_episodes"] == []
        assert data["total_feeds"] == 0
        assert data["successful"] == 0
        assert data["failed"] == 0

    def test_list_latest_help_shows_command(self) -> None:
        """inkwell list --help should show latest subcommand."""
        result = runner.invoke(app, ["list", "--help"])

        assert "latest" in result.stdout

    def test_list_latest_short_flag(self, tmp_path: Path, monkeypatch) -> None:
        """Should support -j short flag for JSON output."""
        import json

        monkeypatch.setattr("inkwell.utils.paths.get_config_dir", lambda: tmp_path)

        result = runner.invoke(app, ["list", "latest", "-j"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert "latest_episodes" in data
