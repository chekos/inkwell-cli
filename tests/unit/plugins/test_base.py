"""Tests for plugin base classes and utilities."""

from typing import ClassVar

import pytest
from pydantic import BaseModel

from inkwell.plugins.base import (
    PLUGIN_API_VERSION,
    InkwellPlugin,
    PluginValidationError,
    check_api_version_compatible,
)


class SampleConfig(BaseModel):
    """Sample config schema for testing."""

    api_key: str
    timeout: int = 30


class SamplePlugin(InkwellPlugin):
    """Sample plugin for testing."""

    NAME: ClassVar[str] = "sample-plugin"
    VERSION: ClassVar[str] = "1.0.0"
    DESCRIPTION: ClassVar[str] = "A sample plugin for testing"
    CONFIG_SCHEMA: ClassVar[type[BaseModel] | None] = SampleConfig


class MinimalPlugin(InkwellPlugin):
    """Minimal plugin with only required attributes."""

    NAME: ClassVar[str] = "minimal"
    VERSION: ClassVar[str] = "0.1.0"
    DESCRIPTION: ClassVar[str] = "Minimal test plugin"


class TestPluginValidationError:
    """Tests for PluginValidationError."""

    def test_error_message_single(self) -> None:
        """Test error message with single error."""
        error = PluginValidationError("test-plugin", ["Missing API key"])
        assert error.plugin_name == "test-plugin"
        assert error.errors == ["Missing API key"]
        assert "test-plugin" in str(error)
        assert "Missing API key" in str(error)

    def test_error_message_multiple(self) -> None:
        """Test error message with multiple errors."""
        errors = ["Missing API key", "Invalid timeout"]
        error = PluginValidationError("test-plugin", errors)
        assert len(error.errors) == 2
        assert "Missing API key" in str(error)
        assert "Invalid timeout" in str(error)


class TestInkwellPlugin:
    """Tests for InkwellPlugin base class."""

    def test_required_attributes(self) -> None:
        """Test that required class attributes are accessible."""
        plugin = MinimalPlugin()
        assert plugin.NAME == "minimal"
        assert plugin.VERSION == "0.1.0"
        assert plugin.DESCRIPTION == "Minimal test plugin"
        assert plugin.API_VERSION == PLUGIN_API_VERSION

    def test_optional_attributes_defaults(self) -> None:
        """Test default values for optional attributes."""
        plugin = MinimalPlugin()
        assert plugin.AUTHOR == ""
        assert plugin.HOMEPAGE is None
        assert plugin.CONFIG_SCHEMA is None
        assert plugin.DEPENDS_ON == []

    def test_not_initialized_before_configure(self) -> None:
        """Test plugin is not initialized before configure()."""
        plugin = MinimalPlugin()
        assert not plugin.is_initialized

    def test_config_raises_before_configure(self) -> None:
        """Test accessing config before configure() raises."""
        plugin = MinimalPlugin()
        with pytest.raises(RuntimeError, match="not configured"):
            _ = plugin.config

    def test_configure_basic(self) -> None:
        """Test basic configure without schema."""
        plugin = MinimalPlugin()
        config = {"key": "value", "number": 42}

        plugin.configure(config)

        assert plugin.is_initialized
        assert plugin.config == config
        assert plugin.cost_tracker is None

    def test_configure_with_cost_tracker(self) -> None:
        """Test configure with cost tracker."""
        from inkwell.plugins.testing import MockCostTracker

        plugin = MinimalPlugin()
        tracker = MockCostTracker()

        plugin.configure({}, tracker)

        assert plugin.cost_tracker is tracker

    def test_configure_with_schema_validation(self) -> None:
        """Test configure validates against CONFIG_SCHEMA."""
        plugin = SamplePlugin()
        config = {"api_key": "test-key", "timeout": 60}

        plugin.configure(config)

        assert plugin.is_initialized
        assert isinstance(plugin.config, SampleConfig)
        assert plugin.config.api_key == "test-key"
        assert plugin.config.timeout == 60

    def test_configure_with_schema_uses_defaults(self) -> None:
        """Test configure uses schema defaults for missing fields."""
        plugin = SamplePlugin()
        config = {"api_key": "test-key"}

        plugin.configure(config)

        assert plugin.config.timeout == 30  # default

    def test_configure_with_schema_validation_error(self) -> None:
        """Test configure raises on invalid config."""
        plugin = SamplePlugin()
        config = {"timeout": 60}  # Missing required api_key

        with pytest.raises(Exception):  # Pydantic ValidationError
            plugin.configure(config)

    def test_validate_default_does_nothing(self) -> None:
        """Test default validate() does nothing."""
        plugin = MinimalPlugin()
        plugin.configure({})
        plugin.validate()  # Should not raise

    def test_cleanup_default_does_nothing(self) -> None:
        """Test default cleanup() does nothing."""
        plugin = MinimalPlugin()
        plugin.configure({})
        plugin.cleanup()  # Should not raise


class TestCheckApiVersionCompatible:
    """Tests for check_api_version_compatible()."""

    def test_same_version_compatible(self) -> None:
        """Test same version is compatible."""
        assert check_api_version_compatible(PLUGIN_API_VERSION)

    def test_same_major_compatible(self) -> None:
        """Test same major version is compatible."""
        assert check_api_version_compatible("1.0")
        assert check_api_version_compatible("1.1")
        assert check_api_version_compatible("1.99")

    def test_different_major_incompatible(self) -> None:
        """Test different major version is incompatible."""
        assert not check_api_version_compatible("2.0")
        assert not check_api_version_compatible("0.1")

    def test_invalid_version_incompatible(self) -> None:
        """Test invalid version strings are incompatible."""
        assert not check_api_version_compatible("")
        assert not check_api_version_compatible("invalid")
