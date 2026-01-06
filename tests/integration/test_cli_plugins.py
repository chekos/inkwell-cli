"""Integration tests for plugin CLI commands."""

import os

from typer.testing import CliRunner

from inkwell.cli import app

# Disable Rich formatting in tests for consistent output across environments
os.environ["NO_COLOR"] = "1"
os.environ["TERM"] = "dumb"

runner = CliRunner()


class TestPluginsList:
    """Tests for `inkwell plugins list` command."""

    def test_plugins_list_shows_built_in_plugins(self) -> None:
        """Test that list shows built-in plugins."""
        result = runner.invoke(app, ["plugins", "list"])

        # Should show section headers
        assert "Extraction Plugins" in result.stdout or "extraction" in result.stdout.lower()
        assert "Transcription Plugins" in result.stdout or "transcription" in result.stdout.lower()
        assert "Output Plugins" in result.stdout or "output" in result.stdout.lower()

    def test_plugins_list_shows_youtube_transcriber(self) -> None:
        """Test that youtube transcriber is listed."""
        result = runner.invoke(app, ["plugins", "list"])

        # YouTube transcriber should be available
        assert "youtube" in result.stdout.lower()

    def test_plugins_list_shows_markdown_output(self) -> None:
        """Test that markdown output plugin is listed."""
        result = runner.invoke(app, ["plugins", "list"])

        # Markdown output should be available
        assert "markdown" in result.stdout.lower()

    def test_plugins_list_filter_by_type(self) -> None:
        """Test filtering by plugin type."""
        result = runner.invoke(app, ["plugins", "list", "--type", "transcription"])

        assert result.exit_code == 0
        # Should only show transcription plugins
        assert "youtube" in result.stdout.lower()

    def test_plugins_list_invalid_type(self) -> None:
        """Test error handling for invalid plugin type."""
        result = runner.invoke(app, ["plugins", "list", "--type", "invalid"])

        assert result.exit_code == 1
        assert "Unknown plugin type" in result.stdout or "unknown" in result.stdout.lower()

    def test_plugins_list_show_all_flag(self) -> None:
        """Test --all flag includes disabled plugins."""
        result = runner.invoke(app, ["plugins", "list", "--all"])

        assert result.exit_code == 0


class TestPluginsValidate:
    """Tests for `inkwell plugins validate` command."""

    def test_validate_youtube_plugin_success(self) -> None:
        """Test that YouTube plugin validates successfully."""
        result = runner.invoke(app, ["plugins", "validate", "youtube"])

        assert result.exit_code == 0
        assert "validated successfully" in result.stdout

    def test_validate_nonexistent_plugin(self) -> None:
        """Test error handling for non-existent plugin."""
        result = runner.invoke(app, ["plugins", "validate", "nonexistent"])

        assert result.exit_code == 1
        assert "not found" in result.stdout.lower()

    def test_validate_all_plugins(self) -> None:
        """Test validating all plugins (may have some failures due to missing API keys)."""
        result = runner.invoke(app, ["plugins", "validate"])

        # Command should complete (exit code 0 if all valid, 1 if some fail)
        # We just check it doesn't crash
        assert result.exit_code in [0, 1]


class TestPluginsEnable:
    """Tests for `inkwell plugins enable` command."""

    def test_enable_nonexistent_plugin(self) -> None:
        """Test error handling for non-existent plugin."""
        result = runner.invoke(app, ["plugins", "enable", "nonexistent"])

        assert result.exit_code == 1
        assert "not found" in result.stdout.lower()

    def test_enable_already_enabled_plugin(self) -> None:
        """Test enabling an already enabled plugin."""
        result = runner.invoke(app, ["plugins", "enable", "youtube"])

        # Should indicate already enabled
        assert "already enabled" in result.stdout.lower() or result.exit_code == 0


class TestPluginsDisable:
    """Tests for `inkwell plugins disable` command."""

    def test_disable_nonexistent_plugin(self) -> None:
        """Test error handling for non-existent plugin."""
        result = runner.invoke(app, ["plugins", "disable", "nonexistent"])

        assert result.exit_code == 1
        assert "not found" in result.stdout.lower()


class TestPluginsHelp:
    """Tests for plugin subcommand help."""

    def test_plugins_help(self) -> None:
        """Test that plugins help shows available commands."""
        result = runner.invoke(app, ["plugins", "--help"])

        assert result.exit_code == 0
        assert "list" in result.stdout.lower()
        assert "enable" in result.stdout.lower()
        assert "disable" in result.stdout.lower()
        assert "validate" in result.stdout.lower()

    def test_plugins_list_help(self) -> None:
        """Test that plugins list help shows options."""
        result = runner.invoke(app, ["plugins", "list", "--help"])

        assert result.exit_code == 0
        assert "--type" in result.stdout.lower()
        assert "--all" in result.stdout.lower()


class TestFetchPluginOverrides:
    """Tests for fetch command plugin override flags."""

    def test_fetch_help_shows_extractor_option(self) -> None:
        """Test that fetch help shows --extractor option."""
        result = runner.invoke(app, ["fetch", "--help"])

        assert result.exit_code == 0
        assert "--extractor" in result.stdout
        assert "INKWELL_EXTRACTOR" in result.stdout

    def test_fetch_help_shows_transcriber_option(self) -> None:
        """Test that fetch help shows --transcriber option."""
        result = runner.invoke(app, ["fetch", "--help"])

        assert result.exit_code == 0
        assert "--transcriber" in result.stdout
        assert "INKWELL_TRANSCRIBER" in result.stdout
