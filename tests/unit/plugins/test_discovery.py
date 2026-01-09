"""Tests for plugin discovery."""

from typing import ClassVar
from unittest.mock import MagicMock, patch

import pytest

from inkwell.plugins.base import InkwellPlugin
from inkwell.plugins.discovery import (
    ENTRY_POINT_GROUPS,
    PluginLoadResult,
    _generate_recovery_hint,
    discover_plugins,
    get_entry_point_group,
)


class GoodPlugin(InkwellPlugin):
    NAME: ClassVar[str] = "good-plugin"
    VERSION: ClassVar[str] = "1.0.0"
    DESCRIPTION: ClassVar[str] = "A good test plugin"


class IncompatiblePlugin(InkwellPlugin):
    NAME: ClassVar[str] = "incompatible"
    VERSION: ClassVar[str] = "1.0.0"
    DESCRIPTION: ClassVar[str] = "Incompatible API version"
    API_VERSION: ClassVar[str] = "99.0"  # Way in the future


class TestPluginLoadResult:
    """Tests for PluginLoadResult."""

    def test_success_when_plugin_present(self) -> None:
        """Test success is True when plugin is present."""
        plugin = GoodPlugin()
        result = PluginLoadResult(
            name="good",
            plugin=plugin,
            source="test:good",
        )
        assert result.success
        assert result.plugin is plugin
        assert result.error is None

    def test_not_success_when_error(self) -> None:
        """Test success is False when error present."""
        result = PluginLoadResult(
            name="bad",
            plugin=None,
            error="ImportError: missing module",
            source="test:bad",
        )
        assert not result.success
        assert result.plugin is None
        assert result.error is not None


class TestGenerateRecoveryHint:
    """Tests for _generate_recovery_hint()."""

    def test_module_not_found(self) -> None:
        """Test recovery hint for ModuleNotFoundError."""
        error = ModuleNotFoundError("No module named 'torch'")
        error.name = "torch"
        hint = _generate_recovery_hint(error)
        assert hint == "uv add torch"

    def test_import_error_torch(self) -> None:
        """Test recovery hint for torch ImportError."""
        error = ImportError("cannot import CUDA from torch")
        hint = _generate_recovery_hint(error)
        assert "torch" in hint.lower()

    def test_attribute_error(self) -> None:
        """Test recovery hint for AttributeError."""
        error = AttributeError("type object 'Plugin' has no attribute 'NAME'")
        hint = _generate_recovery_hint(error)
        assert "NAME" in hint

    def test_generic_error_no_hint(self) -> None:
        """Test no hint for generic errors."""
        error = ValueError("Some random error")
        hint = _generate_recovery_hint(error)
        assert hint is None


class TestDiscoverPlugins:
    """Tests for discover_plugins()."""

    @patch("inkwell.plugins.discovery.entry_points")
    def test_discovers_valid_plugin(self, mock_entry_points: MagicMock) -> None:
        """Test discovering a valid plugin."""
        mock_ep = MagicMock()
        mock_ep.name = "good-plugin"
        mock_ep.load.return_value = GoodPlugin
        mock_entry_points.return_value = [mock_ep]

        results = list(discover_plugins("inkwell.plugins.extraction"))

        assert len(results) == 1
        assert results[0].success
        assert results[0].name == "good-plugin"
        assert isinstance(results[0].plugin, GoodPlugin)

    @patch("inkwell.plugins.discovery.entry_points")
    def test_handles_import_error(self, mock_entry_points: MagicMock) -> None:
        """Test handling import errors gracefully."""
        mock_ep = MagicMock()
        mock_ep.name = "bad-plugin"
        mock_ep.load.side_effect = ImportError("No module named 'missing'")
        mock_entry_points.return_value = [mock_ep]

        results = list(discover_plugins("inkwell.plugins.extraction"))

        assert len(results) == 1
        assert not results[0].success
        assert "ImportError" in results[0].error

    @patch("inkwell.plugins.discovery.entry_points")
    def test_rejects_non_plugin_class(self, mock_entry_points: MagicMock) -> None:
        """Test rejecting classes that aren't InkwellPlugin subclasses."""
        mock_ep = MagicMock()
        mock_ep.name = "not-a-plugin"
        mock_ep.load.return_value = dict  # Not a plugin class
        mock_entry_points.return_value = [mock_ep]

        results = list(discover_plugins("inkwell.plugins.extraction"))

        assert len(results) == 1
        assert not results[0].success
        assert "InkwellPlugin" in results[0].error

    @patch("inkwell.plugins.discovery.entry_points")
    def test_rejects_incompatible_api_version(self, mock_entry_points: MagicMock) -> None:
        """Test rejecting plugins with incompatible API version."""
        mock_ep = MagicMock()
        mock_ep.name = "incompatible"
        mock_ep.load.return_value = IncompatiblePlugin
        mock_entry_points.return_value = [mock_ep]

        results = list(discover_plugins("inkwell.plugins.extraction"))

        assert len(results) == 1
        assert not results[0].success
        assert "API version" in results[0].error
        assert results[0].recovery_hint is not None

    @patch("inkwell.plugins.discovery.entry_points")
    def test_empty_group(self, mock_entry_points: MagicMock) -> None:
        """Test discovering from empty entry point group."""
        mock_entry_points.return_value = []

        results = list(discover_plugins("inkwell.plugins.extraction"))

        assert len(results) == 0


class TestGetEntryPointGroup:
    """Tests for get_entry_point_group()."""

    def test_extraction(self) -> None:
        """Test extraction group name."""
        assert get_entry_point_group("extraction") == "inkwell.plugins.extraction"

    def test_transcription(self) -> None:
        """Test transcription group name."""
        assert get_entry_point_group("transcription") == "inkwell.plugins.transcription"

    def test_output(self) -> None:
        """Test output group name."""
        assert get_entry_point_group("output") == "inkwell.plugins.output"

    def test_invalid_raises(self) -> None:
        """Test invalid type raises ValueError."""
        with pytest.raises(ValueError, match="Unknown plugin type"):
            get_entry_point_group("invalid")


class TestEntryPointGroups:
    """Tests for ENTRY_POINT_GROUPS constant."""

    def test_all_groups_defined(self) -> None:
        """Test all expected groups are defined."""
        assert "extraction" in ENTRY_POINT_GROUPS
        assert "transcription" in ENTRY_POINT_GROUPS
        assert "output" in ENTRY_POINT_GROUPS

    def test_group_names_follow_convention(self) -> None:
        """Test group names follow inkwell.plugins.* convention."""
        for group in ENTRY_POINT_GROUPS.values():
            assert group.startswith("inkwell.plugins.")
