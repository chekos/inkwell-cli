"""Testing utilities for plugin authors.

This module provides mock implementations and fixtures to help plugin
authors write tests without needing real API keys or network access.

Example usage in a plugin's test file:

    from inkwell.plugins.testing import (
        MockCostTracker,
        create_test_plugin,
        assert_plugin_valid,
    )

    def test_my_plugin_configures():
        plugin = MyPlugin()
        tracker = MockCostTracker()

        plugin.configure({"api_key": "test"}, tracker)

        assert plugin.is_initialized
        assert_plugin_valid(plugin)
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, ClassVar
from unittest.mock import MagicMock

from .base import InkwellPlugin, PluginValidationError


@dataclass
class MockAPIUsage:
    """Mock API usage record for testing.

    Mirrors the structure of inkwell.utils.costs.APIUsage.
    """

    provider: str
    model: str
    operation: str
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    episode_title: str | None = None
    template_name: str | None = None


class MockCostTracker:
    """Mock cost tracker for testing plugins.

    Records all tracked costs without persisting to disk.
    Useful for testing plugins that track API usage.

    Example:
        >>> tracker = MockCostTracker()
        >>> plugin.configure({}, tracker)
        >>> # ... use plugin ...
        >>> assert tracker.total_cost > 0
        >>> assert len(tracker.usage_history) == 1
    """

    def __init__(self) -> None:
        self.usage_history: list[MockAPIUsage] = []
        self._session_cost = 0.0

    def track(self, usage: MockAPIUsage) -> None:
        """Track a new API usage."""
        self.usage_history.append(usage)
        self._session_cost += usage.cost_usd

    def add_cost(
        self,
        provider: str,
        model: str,
        operation: str,
        input_tokens: int,
        output_tokens: int,
        episode_title: str | None = None,
        template_name: str | None = None,
    ) -> float:
        """Add a cost record and return the calculated cost."""
        # Simple cost calculation for testing
        cost_usd = (input_tokens + output_tokens) * 0.00001

        usage = MockAPIUsage(
            provider=provider,
            model=model,
            operation=operation,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            cost_usd=cost_usd,
            episode_title=episode_title,
            template_name=template_name,
        )
        self.track(usage)
        return cost_usd

    def get_session_cost(self) -> float:
        """Get total cost for current session."""
        return self._session_cost

    def reset_session_cost(self) -> None:
        """Reset session cost tracking."""
        self._session_cost = 0.0

    def get_total_cost(self) -> float:
        """Get total cost across all usage."""
        return sum(u.cost_usd for u in self.usage_history)

    @property
    def total_cost(self) -> float:
        """Alias for get_total_cost()."""
        return self.get_total_cost()

    @property
    def call_count(self) -> int:
        """Number of times add_cost was called."""
        return len(self.usage_history)


class MockPlugin(InkwellPlugin):
    """A simple mock plugin for testing infrastructure.

    Can be configured to succeed or fail validation for testing
    error handling paths.

    Example:
        >>> plugin = MockPlugin()
        >>> plugin.configure({"should_fail": True}, None)
        >>> plugin.validate()  # Raises PluginValidationError
    """

    NAME: ClassVar[str] = "mock-plugin"
    VERSION: ClassVar[str] = "1.0.0"
    DESCRIPTION: ClassVar[str] = "Test plugin for testing infrastructure"

    def __init__(self) -> None:
        super().__init__()
        self.configure_called = False
        self.validate_called = False
        self.cleanup_called = False
        self._should_fail_validation = False
        self._validation_errors: list[str] = []

    def configure(
        self,
        config: dict[str, Any],
        cost_tracker: Any = None,
    ) -> None:
        """Configure the test plugin."""
        super().configure(config, cost_tracker)
        self.configure_called = True
        self._should_fail_validation = config.get("should_fail", False)
        self._validation_errors = config.get("validation_errors", ["Test failure"])

    def validate(self) -> None:
        """Validate the test plugin."""
        self.validate_called = True
        if self._should_fail_validation:
            raise PluginValidationError(self.NAME, self._validation_errors)

    def cleanup(self) -> None:
        """Clean up the test plugin."""
        self.cleanup_called = True


class DependentMockPlugin(InkwellPlugin):
    """Mock plugin with dependencies for testing dependency resolution."""

    NAME: ClassVar[str] = "dependent-plugin"
    VERSION: ClassVar[str] = "1.0.0"
    DESCRIPTION: ClassVar[str] = "Mock plugin with dependencies"
    DEPENDS_ON: ClassVar[list[str]] = ["mock-plugin"]


def create_test_plugin(
    name: str = "test-plugin",
    version: str = "1.0.0",
    description: str = "Test plugin",
    api_version: str = "1.0",
    depends_on: list[str] | None = None,
    should_fail_validation: bool = False,
) -> InkwellPlugin:
    """Factory function to create test plugins with custom attributes.

    Args:
        name: Plugin name.
        version: Plugin version.
        description: Plugin description.
        api_version: Plugin API version.
        depends_on: List of plugin dependencies.
        should_fail_validation: If True, validate() will raise.

    Returns:
        A configured test plugin instance.

    Example:
        >>> plugin = create_test_plugin(name="my-test", version="2.0.0")
        >>> assert plugin.NAME == "my-test"
    """

    class CustomTestPlugin(InkwellPlugin):
        NAME = name
        VERSION = version
        DESCRIPTION = description
        API_VERSION = api_version
        DEPENDS_ON = depends_on or []

        def validate(self) -> None:
            if should_fail_validation:
                raise PluginValidationError(self.NAME, ["Configured to fail"])

    return CustomTestPlugin()


def assert_plugin_valid(plugin: InkwellPlugin) -> None:
    """Assert that a plugin passes validation.

    Calls validate() and raises AssertionError with details if it fails.

    Args:
        plugin: Plugin to validate.

    Raises:
        AssertionError: If plugin fails validation.
    """
    try:
        plugin.validate()
    except PluginValidationError as e:
        raise AssertionError(
            f"Plugin '{e.plugin_name}' failed validation:\n  Errors: {e.errors}"
        ) from e


def assert_plugin_configured(
    plugin: InkwellPlugin,
    expected_config: dict[str, Any] | None = None,
) -> None:
    """Assert that a plugin is properly configured.

    Args:
        plugin: Plugin to check.
        expected_config: Optional expected config values to verify.

    Raises:
        AssertionError: If plugin is not configured or config doesn't match.
    """
    if not plugin.is_initialized:
        raise AssertionError(f"Plugin '{plugin.NAME}' is not initialized")

    if expected_config:
        actual = plugin.config
        if isinstance(actual, dict):
            for key, value in expected_config.items():
                if actual.get(key) != value:
                    raise AssertionError(
                        f"Plugin config mismatch for '{key}': "
                        f"expected {value!r}, got {actual.get(key)!r}"
                    )


def create_mock_entry_point(
    name: str,
    plugin_class: type[InkwellPlugin],
    group: str = "inkwell.plugins.extraction",
) -> MagicMock:
    """Create a mock entry point for testing discovery.

    Args:
        name: Entry point name.
        plugin_class: Plugin class to return from load().
        group: Entry point group.

    Returns:
        Mock object that behaves like importlib.metadata.EntryPoint.

    Example:
        >>> ep = create_mock_entry_point("test", TestPlugin)
        >>> ep.load()()  # Returns TestPlugin instance
    """
    mock_ep = MagicMock()
    mock_ep.name = name
    mock_ep.group = group
    mock_ep.load.return_value = plugin_class
    return mock_ep
