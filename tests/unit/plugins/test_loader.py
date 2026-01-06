"""Tests for plugin loader and dependency resolution."""

from typing import ClassVar

import pytest

from inkwell.plugins.base import InkwellPlugin, PluginValidationError
from inkwell.plugins.loader import (
    BrokenPlugin,
    DependencyError,
    resolve_dependencies,
)
from inkwell.plugins.registry import PluginRegistry


class PluginA(InkwellPlugin):
    NAME: ClassVar[str] = "plugin-a"
    VERSION: ClassVar[str] = "1.0.0"
    DESCRIPTION: ClassVar[str] = "Plugin A (no deps)"


class PluginB(InkwellPlugin):
    NAME: ClassVar[str] = "plugin-b"
    VERSION: ClassVar[str] = "1.0.0"
    DESCRIPTION: ClassVar[str] = "Plugin B depends on A"
    DEPENDS_ON: ClassVar[list[str]] = ["plugin-a"]


class PluginC(InkwellPlugin):
    NAME: ClassVar[str] = "plugin-c"
    VERSION: ClassVar[str] = "1.0.0"
    DESCRIPTION: ClassVar[str] = "Plugin C depends on B"
    DEPENDS_ON: ClassVar[list[str]] = ["plugin-b"]


class CyclicPluginX(InkwellPlugin):
    NAME: ClassVar[str] = "plugin-x"
    VERSION: ClassVar[str] = "1.0.0"
    DESCRIPTION: ClassVar[str] = "Plugin X depends on Y"
    DEPENDS_ON: ClassVar[list[str]] = ["plugin-y"]


class CyclicPluginY(InkwellPlugin):
    NAME: ClassVar[str] = "plugin-y"
    VERSION: ClassVar[str] = "1.0.0"
    DESCRIPTION: ClassVar[str] = "Plugin Y depends on X"
    DEPENDS_ON: ClassVar[list[str]] = ["plugin-x"]


class FailingValidationPlugin(InkwellPlugin):
    NAME: ClassVar[str] = "failing"
    VERSION: ClassVar[str] = "1.0.0"
    DESCRIPTION: ClassVar[str] = "Always fails validation"

    def validate(self) -> None:
        raise PluginValidationError(self.NAME, ["Always fails"])


class TestBrokenPlugin:
    """Tests for BrokenPlugin wrapper."""

    def test_creates_with_error_info(self) -> None:
        """Test BrokenPlugin stores error information."""
        broken = BrokenPlugin(
            name="failed-plugin",
            error_message="ImportError: missing torch",
            recovery_hint="uv add torch",
        )
        assert broken.NAME == "failed-plugin"
        assert broken.error_message == "ImportError: missing torch"
        assert broken.recovery_hint == "uv add torch"
        assert "ImportError" in broken.DESCRIPTION

    def test_validate_raises(self) -> None:
        """Test BrokenPlugin.validate() always raises."""
        broken = BrokenPlugin(
            name="failed",
            error_message="Some error",
        )
        with pytest.raises(PluginValidationError) as exc:
            broken.validate()
        assert exc.value.plugin_name == "failed"


class TestDependencyError:
    """Tests for DependencyError."""

    def test_missing_deps_message(self) -> None:
        """Test error message for missing dependencies."""
        error = DependencyError("plugin-b", missing=["plugin-a", "plugin-c"])
        assert error.plugin_name == "plugin-b"
        assert error.missing == ["plugin-a", "plugin-c"]
        assert "plugin-a" in str(error)
        assert "plugin-c" in str(error)

    def test_cycle_message(self) -> None:
        """Test error message for dependency cycle."""
        error = DependencyError("plugin-x", cycle=["plugin-x", "plugin-y", "plugin-x"])
        assert "cycle" in str(error).lower()
        assert "plugin-x" in str(error)


class TestResolveDependencies:
    """Tests for resolve_dependencies()."""

    def test_empty_list(self) -> None:
        """Test resolving empty list returns empty."""
        result = resolve_dependencies([])
        assert result == []

    def test_no_dependencies(self) -> None:
        """Test resolving plugins with no dependencies."""
        plugin_a = PluginA()
        result = resolve_dependencies([plugin_a])
        assert len(result) == 1
        assert result[0] is plugin_a

    def test_simple_dependency(self) -> None:
        """Test resolving simple A -> B dependency."""
        plugin_a = PluginA()
        plugin_b = PluginB()

        # Input order shouldn't matter
        result = resolve_dependencies([plugin_b, plugin_a])

        assert len(result) == 2
        # A must come before B (B depends on A)
        names = [p.NAME for p in result]
        assert names.index("plugin-a") < names.index("plugin-b")

    def test_chain_dependency(self) -> None:
        """Test resolving A -> B -> C chain."""
        plugin_a = PluginA()
        plugin_b = PluginB()
        plugin_c = PluginC()

        result = resolve_dependencies([plugin_c, plugin_a, plugin_b])

        names = [p.NAME for p in result]
        assert names.index("plugin-a") < names.index("plugin-b")
        assert names.index("plugin-b") < names.index("plugin-c")

    def test_missing_dependency_raises(self) -> None:
        """Test missing dependency raises DependencyError."""
        plugin_b = PluginB()  # Depends on plugin-a which isn't provided

        with pytest.raises(DependencyError) as exc:
            resolve_dependencies([plugin_b])

        assert exc.value.plugin_name == "plugin-b"
        assert "plugin-a" in exc.value.missing

    def test_cyclic_dependency_raises(self) -> None:
        """Test cyclic dependency raises DependencyError."""
        plugin_x = CyclicPluginX()
        plugin_y = CyclicPluginY()

        with pytest.raises(DependencyError) as exc:
            resolve_dependencies([plugin_x, plugin_y])

        assert len(exc.value.cycle) > 0

    def test_deterministic_order(self) -> None:
        """Test that output order is deterministic."""
        plugin_a = PluginA()
        plugin_b = PluginB()
        plugin_c = PluginC()

        # Run multiple times with different input orders
        orders = [
            [plugin_a, plugin_b, plugin_c],
            [plugin_c, plugin_b, plugin_a],
            [plugin_b, plugin_a, plugin_c],
        ]

        results = [
            [p.NAME for p in resolve_dependencies(order)]
            for order in orders
        ]

        # All results should be the same
        assert all(r == results[0] for r in results)


class TestCleanupRegistry:
    """Tests for cleanup_registry()."""

    def test_calls_cleanup_on_all_plugins(self) -> None:
        """Test cleanup is called on all enabled plugins."""
        from inkwell.plugins.loader import cleanup_registry

        registry: PluginRegistry[InkwellPlugin] = PluginRegistry(InkwellPlugin)

        class TrackingPlugin(InkwellPlugin):
            NAME: ClassVar[str] = "tracking"
            VERSION: ClassVar[str] = "1.0.0"
            DESCRIPTION: ClassVar[str] = "Tracks cleanup calls"
            cleanup_called: bool = False

            def cleanup(self) -> None:
                self.cleanup_called = True

        plugin = TrackingPlugin()
        registry.register("tracking", plugin)

        cleanup_registry(registry)

        assert plugin.cleanup_called

    def test_handles_cleanup_errors(self) -> None:
        """Test cleanup continues even if a plugin raises."""
        from inkwell.plugins.loader import cleanup_registry

        registry: PluginRegistry[InkwellPlugin] = PluginRegistry(InkwellPlugin)

        class FailingCleanupPlugin(InkwellPlugin):
            NAME: ClassVar[str] = "failing"
            VERSION: ClassVar[str] = "1.0.0"
            DESCRIPTION: ClassVar[str] = "Fails on cleanup"

            def cleanup(self) -> None:
                raise RuntimeError("Cleanup failed")

        class GoodPlugin(InkwellPlugin):
            NAME: ClassVar[str] = "good"
            VERSION: ClassVar[str] = "1.0.0"
            DESCRIPTION: ClassVar[str] = "Good plugin"
            cleanup_called: bool = False

            def cleanup(self) -> None:
                self.cleanup_called = True

        failing = FailingCleanupPlugin()
        good = GoodPlugin()
        registry.register("failing", failing, priority=100)  # Called first
        registry.register("good", good, priority=50)

        # Should not raise, even though failing plugin raises
        cleanup_registry(registry)

        # Good plugin's cleanup should still be called
        assert good.cleanup_called
