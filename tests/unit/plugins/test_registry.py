"""Tests for PluginRegistry."""

from typing import ClassVar

import pytest

from inkwell.plugins.base import InkwellPlugin
from inkwell.plugins.registry import PluginConflictError, PluginEntry, PluginRegistry


class SamplePluginA(InkwellPlugin):
    NAME: ClassVar[str] = "plugin-a"
    VERSION: ClassVar[str] = "1.0.0"
    DESCRIPTION: ClassVar[str] = "Test plugin A"


class SamplePluginB(InkwellPlugin):
    NAME: ClassVar[str] = "plugin-b"
    VERSION: ClassVar[str] = "1.0.0"
    DESCRIPTION: ClassVar[str] = "Test plugin B"


class TestPluginConflictError:
    """Tests for PluginConflictError."""

    def test_error_message(self) -> None:
        """Test error message format."""
        error = PluginConflictError(
            "test-plugin",
            "package-a:test-plugin",
            "package-b:test-plugin",
        )
        assert error.name == "test-plugin"
        assert error.sources == ["package-a:test-plugin", "package-b:test-plugin"]
        assert "test-plugin" in str(error)
        assert "package-a" in str(error)
        assert "package-b" in str(error)


class TestPluginEntry:
    """Tests for PluginEntry dataclass."""

    def test_loaded_entry_is_usable(self) -> None:
        """Test loaded entry is usable."""
        plugin = SamplePluginA()
        entry = PluginEntry(
            name="plugin-a",
            plugin=plugin,
            status="loaded",
            source="test:plugin-a",
        )
        assert entry.is_usable

    def test_broken_entry_not_usable(self) -> None:
        """Test broken entry is not usable."""
        entry = PluginEntry(
            name="plugin-a",
            plugin=None,
            status="broken",
            error="ImportError: missing module",
            source="test:plugin-a",
        )
        assert not entry.is_usable

    def test_disabled_entry_not_usable(self) -> None:
        """Test disabled entry is not usable."""
        plugin = SamplePluginA()
        entry = PluginEntry(
            name="plugin-a",
            plugin=plugin,
            status="disabled",
            source="test:plugin-a",
        )
        assert not entry.is_usable


class TestPluginRegistry:
    """Tests for PluginRegistry."""

    def test_register_plugin(self) -> None:
        """Test registering a plugin."""
        registry: PluginRegistry[InkwellPlugin] = PluginRegistry(InkwellPlugin)
        plugin = SamplePluginA()

        registry.register(
            name="plugin-a",
            plugin=plugin,
            priority=100,
            source="test:plugin-a",
        )

        assert "plugin-a" in registry
        assert len(registry) == 1

    def test_get_plugin(self) -> None:
        """Test getting a plugin by name."""
        registry: PluginRegistry[InkwellPlugin] = PluginRegistry(InkwellPlugin)
        plugin = SamplePluginA()
        registry.register("plugin-a", plugin, source="test:plugin-a")

        result = registry.get("plugin-a")

        assert result is plugin

    def test_get_nonexistent_returns_none(self) -> None:
        """Test getting nonexistent plugin returns None."""
        registry: PluginRegistry[InkwellPlugin] = PluginRegistry(InkwellPlugin)

        assert registry.get("nonexistent") is None

    def test_get_entry(self) -> None:
        """Test getting full entry."""
        registry: PluginRegistry[InkwellPlugin] = PluginRegistry(InkwellPlugin)
        plugin = SamplePluginA()
        registry.register(
            "plugin-a",
            plugin,
            priority=100,
            source="test:plugin-a",
        )

        entry = registry.get_entry("plugin-a")

        assert entry is not None
        assert entry.name == "plugin-a"
        assert entry.plugin is plugin
        assert entry.priority == 100
        assert entry.status == "loaded"

    def test_register_conflict_raises(self) -> None:
        """Test registering duplicate name raises PluginConflictError."""
        registry: PluginRegistry[InkwellPlugin] = PluginRegistry(InkwellPlugin)
        plugin1 = SamplePluginA()
        plugin2 = SamplePluginA()

        registry.register("plugin-a", plugin1, source="package-1:plugin-a")

        with pytest.raises(PluginConflictError) as exc:
            registry.register("plugin-a", plugin2, source="package-2:plugin-a")

        assert exc.value.name == "plugin-a"
        assert "package-1" in exc.value.sources[0]
        assert "package-2" in exc.value.sources[1]

    def test_register_broken_plugin(self) -> None:
        """Test registering a broken plugin."""
        registry: PluginRegistry[InkwellPlugin] = PluginRegistry(InkwellPlugin)

        registry.register(
            "broken-plugin",
            plugin=None,
            source="test:broken",
            error="ImportError: missing module",
            recovery_hint="uv add missing-module",
        )

        assert "broken-plugin" in registry
        entry = registry.get_entry("broken-plugin")
        assert entry is not None
        assert entry.status == "broken"
        assert entry.error == "ImportError: missing module"
        assert entry.recovery_hint == "uv add missing-module"

        # get() returns None for broken plugins
        assert registry.get("broken-plugin") is None

    def test_get_enabled_priority_order(self) -> None:
        """Test get_enabled returns plugins in priority order."""
        registry: PluginRegistry[InkwellPlugin] = PluginRegistry(InkwellPlugin)
        plugin_a = SamplePluginA()
        plugin_b = SamplePluginB()

        registry.register("plugin-a", plugin_a, priority=50)
        registry.register("plugin-b", plugin_b, priority=100)

        enabled = registry.get_enabled()

        assert len(enabled) == 2
        assert enabled[0][0] == "plugin-b"  # Higher priority first
        assert enabled[1][0] == "plugin-a"

    def test_get_enabled_excludes_broken(self) -> None:
        """Test get_enabled excludes broken plugins."""
        registry: PluginRegistry[InkwellPlugin] = PluginRegistry(InkwellPlugin)
        plugin_a = SamplePluginA()

        registry.register("plugin-a", plugin_a, priority=100)
        registry.register("broken", None, error="Failed to load")

        enabled = registry.get_enabled()

        assert len(enabled) == 1
        assert enabled[0][0] == "plugin-a"

    def test_disable_plugin(self) -> None:
        """Test disabling a plugin."""
        registry: PluginRegistry[InkwellPlugin] = PluginRegistry(InkwellPlugin)
        plugin = SamplePluginA()
        registry.register("plugin-a", plugin)

        result = registry.disable("plugin-a")

        assert result is True
        assert registry.get("plugin-a") is None
        assert registry.get_entry("plugin-a").status == "disabled"

    def test_disable_nonexistent(self) -> None:
        """Test disabling nonexistent plugin returns False."""
        registry: PluginRegistry[InkwellPlugin] = PluginRegistry(InkwellPlugin)

        assert registry.disable("nonexistent") is False

    def test_enable_plugin(self) -> None:
        """Test re-enabling a disabled plugin."""
        registry: PluginRegistry[InkwellPlugin] = PluginRegistry(InkwellPlugin)
        plugin = SamplePluginA()
        registry.register("plugin-a", plugin)
        registry.disable("plugin-a")

        result = registry.enable("plugin-a")

        assert result is True
        assert registry.get("plugin-a") is plugin

    def test_enable_broken_fails(self) -> None:
        """Test enabling broken plugin returns False."""
        registry: PluginRegistry[InkwellPlugin] = PluginRegistry(InkwellPlugin)
        registry.register("broken", None, error="Failed")

        assert registry.enable("broken") is False

    def test_find_capable(self) -> None:
        """Test find_capable with predicate."""
        registry: PluginRegistry[InkwellPlugin] = PluginRegistry(InkwellPlugin)
        plugin_a = SamplePluginA()
        plugin_b = SamplePluginB()
        registry.register("plugin-a", plugin_a, priority=100)
        registry.register("plugin-b", plugin_b, priority=50)

        # Find plugins with NAME starting with "plugin"
        results = registry.find_capable(lambda p: p.NAME.startswith("plugin"))

        assert len(results) == 2

    def test_find_capable_filters(self) -> None:
        """Test find_capable filters correctly."""
        registry: PluginRegistry[InkwellPlugin] = PluginRegistry(InkwellPlugin)
        plugin_a = SamplePluginA()
        plugin_b = SamplePluginB()
        registry.register("plugin-a", plugin_a)
        registry.register("plugin-b", plugin_b)

        results = registry.find_capable(lambda p: p.NAME == "plugin-a")

        assert len(results) == 1
        assert results[0][0] == "plugin-a"

    def test_all_entries(self) -> None:
        """Test all_entries returns all plugins sorted."""
        registry: PluginRegistry[InkwellPlugin] = PluginRegistry(InkwellPlugin)
        plugin_a = SamplePluginA()
        plugin_b = SamplePluginB()
        registry.register("plugin-a", plugin_a, priority=50)
        registry.register("plugin-b", plugin_b, priority=100)
        registry.register("broken", None, error="Failed", priority=75)

        entries = registry.all_entries()

        assert len(entries) == 3
        # Sorted by priority desc, then name asc
        assert entries[0].name == "plugin-b"  # priority 100
        assert entries[1].name == "broken"  # priority 75
        assert entries[2].name == "plugin-a"  # priority 50

    def test_get_broken(self) -> None:
        """Test get_broken returns only broken plugins."""
        registry: PluginRegistry[InkwellPlugin] = PluginRegistry(InkwellPlugin)
        plugin = SamplePluginA()
        registry.register("good", plugin)
        registry.register("broken-1", None, error="Error 1")
        registry.register("broken-2", None, error="Error 2")

        broken = registry.get_broken()

        assert len(broken) == 2
        names = {e.name for e in broken}
        assert names == {"broken-1", "broken-2"}
