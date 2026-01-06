"""Tests for plugin testing utilities."""

import pytest

from inkwell.plugins.base import PluginValidationError
from inkwell.plugins.testing import (
    MockCostTracker,
    MockPlugin,
    assert_plugin_configured,
    assert_plugin_valid,
    create_mock_entry_point,
    create_test_plugin,
)


class TestMockCostTracker:
    """Tests for MockCostTracker."""

    def test_add_cost(self) -> None:
        """Test adding costs."""
        tracker = MockCostTracker()

        cost = tracker.add_cost(
            provider="gemini",
            model="gemini-2.5-flash",
            operation="extraction",
            input_tokens=1000,
            output_tokens=500,
            episode_title="Test Episode",
        )

        assert cost > 0
        assert len(tracker.usage_history) == 1
        assert tracker.usage_history[0].provider == "gemini"
        assert tracker.usage_history[0].episode_title == "Test Episode"

    def test_session_cost(self) -> None:
        """Test session cost tracking."""
        tracker = MockCostTracker()

        tracker.add_cost("gemini", "flash", "extraction", 1000, 500)
        tracker.add_cost("claude", "sonnet", "extraction", 2000, 1000)

        assert tracker.get_session_cost() > 0
        assert tracker.total_cost > 0

    def test_reset_session_cost(self) -> None:
        """Test resetting session cost."""
        tracker = MockCostTracker()
        tracker.add_cost("gemini", "flash", "extraction", 1000, 500)

        tracker.reset_session_cost()

        assert tracker.get_session_cost() == 0
        # Total cost still tracked
        assert tracker.total_cost > 0

    def test_call_count(self) -> None:
        """Test call count property."""
        tracker = MockCostTracker()

        assert tracker.call_count == 0

        tracker.add_cost("gemini", "flash", "extraction", 100, 50)
        tracker.add_cost("claude", "sonnet", "extraction", 200, 100)

        assert tracker.call_count == 2


class TestMockPlugin:
    """Tests for MockPlugin."""

    def test_lifecycle_tracking(self) -> None:
        """Test that lifecycle calls are tracked."""
        plugin = MockPlugin()

        assert not plugin.configure_called
        assert not plugin.validate_called
        assert not plugin.cleanup_called

        plugin.configure({})
        assert plugin.configure_called

        plugin.validate()
        assert plugin.validate_called

        plugin.cleanup()
        assert plugin.cleanup_called

    def test_configurable_failure(self) -> None:
        """Test plugin can be configured to fail validation."""
        plugin = MockPlugin()
        plugin.configure({"should_fail": True})

        with pytest.raises(PluginValidationError):
            plugin.validate()

    def test_custom_validation_errors(self) -> None:
        """Test custom validation error messages."""
        plugin = MockPlugin()
        plugin.configure({
            "should_fail": True,
            "validation_errors": ["Error 1", "Error 2"],
        })

        with pytest.raises(PluginValidationError) as exc:
            plugin.validate()

        assert "Error 1" in exc.value.errors
        assert "Error 2" in exc.value.errors


class TestCreateMockPlugin:
    """Tests for create_test_plugin factory."""

    def test_default_values(self) -> None:
        """Test default plugin attributes."""
        plugin = create_test_plugin()

        assert plugin.NAME == "test-plugin"
        assert plugin.VERSION == "1.0.0"
        assert plugin.DESCRIPTION == "Test plugin"
        assert plugin.API_VERSION == "1.0"
        assert plugin.DEPENDS_ON == []

    def test_custom_values(self) -> None:
        """Test custom plugin attributes."""
        plugin = create_test_plugin(
            name="custom-plugin",
            version="2.0.0",
            description="My custom plugin",
            api_version="1.1",
            depends_on=["other-plugin"],
        )

        assert plugin.NAME == "custom-plugin"
        assert plugin.VERSION == "2.0.0"
        assert plugin.DESCRIPTION == "My custom plugin"
        assert plugin.API_VERSION == "1.1"
        assert plugin.DEPENDS_ON == ["other-plugin"]

    def test_failing_validation(self) -> None:
        """Test creating plugin that fails validation."""
        plugin = create_test_plugin(should_fail_validation=True)

        with pytest.raises(PluginValidationError):
            plugin.validate()


class TestAssertPluginValid:
    """Tests for assert_plugin_valid helper."""

    def test_passes_for_valid_plugin(self) -> None:
        """Test passes for plugin that validates successfully."""
        plugin = create_test_plugin()
        plugin.configure({})

        # Should not raise
        assert_plugin_valid(plugin)

    def test_fails_for_invalid_plugin(self) -> None:
        """Test fails for plugin that fails validation."""
        plugin = create_test_plugin(should_fail_validation=True)
        plugin.configure({})

        with pytest.raises(AssertionError, match="failed validation"):
            assert_plugin_valid(plugin)


class TestAssertPluginConfigured:
    """Tests for assert_plugin_configured helper."""

    def test_passes_for_configured_plugin(self) -> None:
        """Test passes for configured plugin."""
        plugin = create_test_plugin()
        plugin.configure({"key": "value"})

        # Should not raise
        assert_plugin_configured(plugin)

    def test_fails_for_unconfigured_plugin(self) -> None:
        """Test fails for unconfigured plugin."""
        plugin = create_test_plugin()

        with pytest.raises(AssertionError, match="not initialized"):
            assert_plugin_configured(plugin)

    def test_checks_expected_config(self) -> None:
        """Test checks expected config values."""
        plugin = create_test_plugin()
        plugin.configure({"key": "value", "number": 42})

        # Should pass with matching config
        assert_plugin_configured(plugin, {"key": "value"})

        # Should fail with mismatched config
        with pytest.raises(AssertionError, match="mismatch"):
            assert_plugin_configured(plugin, {"key": "wrong"})


class TestCreateMockEntryPoint:
    """Tests for create_mock_entry_point helper."""

    def test_creates_loadable_entry_point(self) -> None:
        """Test mock entry point is loadable."""
        mock_ep = create_mock_entry_point("test", MockPlugin)

        assert mock_ep.name == "test"
        plugin_class = mock_ep.load()
        assert plugin_class is MockPlugin

    def test_custom_group(self) -> None:
        """Test custom group name."""
        mock_ep = create_mock_entry_point(
            "test",
            MockPlugin,
            group="inkwell.plugins.transcription",
        )

        assert mock_ep.group == "inkwell.plugins.transcription"
