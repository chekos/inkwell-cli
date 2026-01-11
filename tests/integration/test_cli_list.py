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

    def test_list_latest_single_feed_success(self, tmp_path: Path, monkeypatch) -> None:
        """Should display latest episode from a single feed."""
        import json
        from datetime import datetime
        from unittest.mock import AsyncMock, MagicMock, patch

        from inkwell.config.manager import ConfigManager
        from inkwell.config.schema import AuthConfig, FeedConfig
        from inkwell.feeds.models import Episode

        monkeypatch.setattr("inkwell.utils.paths.get_config_dir", lambda: tmp_path)

        # Setup: configure one feed
        manager = ConfigManager(config_dir=tmp_path)
        manager.add_feed(
            "test-podcast",
            FeedConfig(
                url="https://example.com/feed.rss",  # type: ignore
                auth=AuthConfig(type="none"),
            ),
        )

        # Mock the RSS parser
        mock_episode = Episode(
            title="Test Episode Title",
            url="https://example.com/episode.mp3",  # type: ignore
            published=datetime(2026, 1, 10, 12, 0, 0),
            description="Test description",
            duration_seconds=2730,
            podcast_name="test-podcast",
        )

        mock_feed = MagicMock()
        mock_feed.entries = [MagicMock()]

        with patch("inkwell.cli_list.RSSParser") as mock_parser_class:
            mock_parser = MagicMock()
            mock_parser.fetch_feed = AsyncMock(return_value=mock_feed)
            mock_parser.get_latest_episode = MagicMock(return_value=mock_episode)
            mock_parser_class.return_value = mock_parser

            result = runner.invoke(app, ["list", "latest", "--json"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["total_feeds"] == 1
        assert data["successful"] == 1
        assert data["failed"] == 0
        assert len(data["latest_episodes"]) == 1
        assert data["latest_episodes"][0]["status"] == "success"
        assert data["latest_episodes"][0]["episode"]["title"] == "Test Episode Title"

    def test_list_latest_partial_failure(self, tmp_path: Path, monkeypatch) -> None:
        """Should show results from successful feeds even when some fail."""
        import json
        from datetime import datetime
        from unittest.mock import AsyncMock, MagicMock, patch

        from inkwell.config.manager import ConfigManager
        from inkwell.config.schema import AuthConfig, FeedConfig
        from inkwell.feeds.models import Episode

        monkeypatch.setattr("inkwell.utils.paths.get_config_dir", lambda: tmp_path)

        # Setup: configure two feeds
        manager = ConfigManager(config_dir=tmp_path)
        manager.add_feed(
            "good-podcast",
            FeedConfig(url="https://example.com/good.rss", auth=AuthConfig(type="none")),  # type: ignore
        )
        manager.add_feed(
            "bad-podcast",
            FeedConfig(url="https://example.com/bad.rss", auth=AuthConfig(type="none")),  # type: ignore
        )

        mock_episode = Episode(
            title="Good Episode",
            url="https://example.com/episode.mp3",  # type: ignore
            published=datetime(2026, 1, 10, 12, 0, 0),
            description="Test",
            podcast_name="good-podcast",
        )

        mock_feed = MagicMock()
        mock_feed.entries = [MagicMock()]

        async def mock_fetch(url, auth):
            if "bad" in url:
                raise Exception("Network error")
            return mock_feed

        with patch("inkwell.cli_list.RSSParser") as mock_parser_class:
            mock_parser = MagicMock()
            mock_parser.fetch_feed = AsyncMock(side_effect=mock_fetch)
            mock_parser.get_latest_episode = MagicMock(return_value=mock_episode)
            mock_parser_class.return_value = mock_parser

            result = runner.invoke(app, ["list", "latest", "--json"])

        assert result.exit_code == 0  # Partial success = exit 0
        data = json.loads(result.stdout)
        assert data["successful"] == 1
        assert data["failed"] == 1

    def test_list_latest_all_fail_exit_code(self, tmp_path: Path, monkeypatch) -> None:
        """Should exit 1 when all feeds fail."""
        from unittest.mock import AsyncMock, MagicMock, patch

        from inkwell.config.manager import ConfigManager
        from inkwell.config.schema import AuthConfig, FeedConfig

        monkeypatch.setattr("inkwell.utils.paths.get_config_dir", lambda: tmp_path)

        # Setup: configure a feed
        manager = ConfigManager(config_dir=tmp_path)
        manager.add_feed(
            "bad-podcast",
            FeedConfig(url="https://example.com/bad.rss", auth=AuthConfig(type="none")),  # type: ignore
        )

        with patch("inkwell.cli_list.RSSParser") as mock_parser_class:
            mock_parser = MagicMock()
            mock_parser.fetch_feed = AsyncMock(side_effect=Exception("Network error"))
            mock_parser_class.return_value = mock_parser

            result = runner.invoke(app, ["list", "latest"])

        assert result.exit_code == 1

    def test_list_latest_empty_feed(self, tmp_path: Path, monkeypatch) -> None:
        """Should show 'No episodes yet' for feeds with no episodes."""
        import json
        from unittest.mock import AsyncMock, MagicMock, patch

        from inkwell.config.manager import ConfigManager
        from inkwell.config.schema import AuthConfig, FeedConfig
        from inkwell.utils.errors import ValidationError

        monkeypatch.setattr("inkwell.utils.paths.get_config_dir", lambda: tmp_path)

        # Setup: configure a feed
        manager = ConfigManager(config_dir=tmp_path)
        manager.add_feed(
            "empty-podcast",
            FeedConfig(url="https://example.com/empty.rss", auth=AuthConfig(type="none")),  # type: ignore
        )

        mock_feed = MagicMock()
        mock_feed.entries = []

        with patch("inkwell.cli_list.RSSParser") as mock_parser_class:
            mock_parser = MagicMock()
            mock_parser.fetch_feed = AsyncMock(return_value=mock_feed)
            # get_latest_episode raises ValidationError for empty feed
            mock_parser.get_latest_episode = MagicMock(
                side_effect=ValidationError("No episodes found in feed")
            )
            mock_parser_class.return_value = mock_parser

            result = runner.invoke(app, ["list", "latest", "--json"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["successful"] == 1  # Empty feed is still "success"
        assert data["latest_episodes"][0]["status"] == "empty"
        assert "No episodes" in data["latest_episodes"][0]["error"]
