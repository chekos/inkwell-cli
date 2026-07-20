"""Integration tests for plugin CLI commands."""

import json
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
        assert "OCR Plugins" in result.stdout or "ocr" in result.stdout.lower()

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

    def test_plugins_list_shows_capabilities(self) -> None:
        """Test that plugin list includes capability labels."""
        result = runner.invoke(app, ["plugins", "list", "--type", "transcription"])

        assert result.exit_code == 0
        assert "direct-youtube" in result.stdout
        assert "timestamps" in result.stdout

    def test_plugins_list_shows_local_ocr_capabilities(self) -> None:
        """Test that the built-in OCR plugin advertises local-only behavior."""
        result = runner.invoke(app, ["plugins", "list", "--type", "ocr"])

        assert result.exit_code == 0
        assert "tessera" in result.stdout.lower()
        assert "local" in result.stdout.lower()
        assert "orientation" in result.stdout.lower()

    def test_plugins_list_shows_explicit_codex_extractor(self) -> None:
        result = runner.invoke(app, ["plugins", "list", "--type", "extraction", "--all"])

        assert result.exit_code == 0
        assert "codex" in result.stdout.lower()

    def test_plugins_list_invalid_type(self) -> None:
        """Test error handling for invalid plugin type."""
        result = runner.invoke(app, ["plugins", "list", "--type", "invalid"])

        assert result.exit_code == 1, result.stdout
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

    def test_validate_codex_json_is_secret_free_and_stdout_clean(
        self, tmp_path, monkeypatch
    ) -> None:
        from inkwell.agent_runtime.codex import CodexRuntimeBackend
        from inkwell.agent_runtime.models import RuntimeReadiness

        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
        monkeypatch.setenv("OPENAI_API_KEY", "must-not-appear")

        async def fake_probe(_self):
            return RuntimeReadiness(
                runtime="codex-cli",
                ready=True,
                installed=True,
                authenticated=True,
                supported=True,
                executable="/fake/codex",
                version="0.144.6",
                auth_class="chatgpt",
                required_capabilities=["shell_tool"],
            )

        monkeypatch.setattr(CodexRuntimeBackend, "probe", fake_probe)
        configured = runner.invoke(
            app,
            ["plugins", "configure", "codex", "model", "explicit-model"],
        )
        result = runner.invoke(app, ["plugins", "validate", "codex", "--json"])

        assert configured.exit_code == 0
        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        assert payload["ready"] is True
        assert payload["configured_model"] == "explicit-model"
        assert payload["auth_class"] == "chatgpt"
        assert "must-not-appear" not in result.stdout

    def test_validate_codex_json_failure_is_one_clean_object(self, tmp_path, monkeypatch) -> None:
        from inkwell.agent_runtime.codex import CodexRuntimeBackend
        from inkwell.agent_runtime.models import RuntimeReadiness
        from inkwell.config.manager import ConfigManager

        monkeypatch.setattr(
            "inkwell.cli_plugins.ConfigManager",
            lambda: ConfigManager(config_dir=tmp_path / "config"),
        )

        async def fake_probe(_self):
            return RuntimeReadiness(
                runtime="codex-cli",
                ready=True,
                installed=True,
                authenticated=True,
                supported=True,
                executable="/fake/codex",
                version="0.144.6",
                auth_class="chatgpt",
            )

        monkeypatch.setattr(CodexRuntimeBackend, "probe", fake_probe)
        result = runner.invoke(app, ["plugins", "validate", "codex", "--json"])

        assert result.exit_code == 1, result.stdout
        payload = json.loads(result.stdout)
        assert payload["ready"] is False
        assert payload["error_code"] == "runtime_model_required"
        assert "validation error" not in result.stdout


class TestPluginsConfigure:
    def test_configure_codex_rejects_out_of_bounds_value(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))

        result = runner.invoke(
            app,
            ["plugins", "configure", "codex", "timeout_seconds", "0"],
        )

        assert result.exit_code == 1
        assert "at least" in result.stdout


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

    def test_fetch_help_shows_local_ocr_options(self) -> None:
        """Test that image/PDF OCR controls are discoverable on fetch."""
        result = runner.invoke(app, ["fetch", "--help"])

        assert result.exit_code == 0
        assert "--ocr-mode" in result.stdout
        assert "--ocr-engine" in result.stdout
        assert "--ocr-language" in result.stdout
        assert "INKWELL_OCR" in result.stdout
