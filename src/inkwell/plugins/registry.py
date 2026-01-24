"""Plugin registry for managing loaded plugins.

This module provides the PluginRegistry class for type-safe plugin
management with conflict detection and priority-based selection.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Generic, Literal, TypeVar

from .base import InkwellPlugin

T = TypeVar("T", bound=InkwellPlugin)


class PluginConflictError(Exception):
    """Raised when two plugins have the same name.

    This is a hard error - users must resolve conflicts by uninstalling
    one of the conflicting packages.

    Attributes:
        name: The conflicting plugin name.
        sources: List of sources (entry point strings) that provide this name.
    """

    def __init__(self, name: str, source1: str, source2: str) -> None:
        self.name = name
        self.sources = [source1, source2]
        super().__init__(
            f"Plugin name conflict: '{name}' registered by both:\n"
            f"  1. {source1}\n"
            f"  2. {source2}\n"
            "Resolve by uninstalling one of the conflicting packages."
        )


@dataclass
class PluginEntry(Generic[T]):
    """Full plugin entry with status information.

    Tracks not just the plugin instance but also its load status,
    error information, priority, and source.

    Attributes:
        name: Plugin name (from NAME class attribute).
        plugin: Plugin instance, or None if broken/disabled.
        status: Current status of the plugin.
        error: Error message if status is "broken".
        priority: Selection priority (higher = preferred).
        source: Entry point string showing where plugin came from.
    """

    name: str
    plugin: T | None
    status: Literal["loaded", "broken", "disabled"]
    error: str | None = None
    priority: int = 0
    source: str = ""
    recovery_hint: str | None = field(default=None)

    @property
    def is_usable(self) -> bool:
        """Whether this plugin can be used (loaded and not disabled)."""
        return self.status == "loaded" and self.plugin is not None


class PluginRegistry(Generic[T]):
    """Type-safe registry for plugin management with conflict detection.

    Manages a collection of plugins of a specific type, handling:
    - Registration with conflict detection
    - Priority-based selection
    - Enable/disable toggling
    - Capability-based filtering

    Standard Priority Ranges (document for plugin authors):
        - 150: User override - explicitly requested plugin
        - 100: Built-in defaults
        - 50: Third-party production plugins
        - 0: Community/experimental plugins

    Example:
        >>> registry = PluginRegistry[ExtractionPlugin](ExtractionPlugin)
        >>> registry.register(
        ...     "claude", claude_plugin, priority=100, source="inkwell:claude"
        ... )
        >>> extractor = registry.get("claude")
    """

    # Standard priority ranges (document for plugin authors)
    PRIORITY_USER_OVERRIDE = 150
    PRIORITY_BUILTIN = 100
    PRIORITY_THIRDPARTY = 50
    PRIORITY_EXPERIMENTAL = 0

    def __init__(self, plugin_type: type[T]) -> None:
        """Initialize registry for a specific plugin type.

        Args:
            plugin_type: The base plugin class this registry manages.
        """
        self._plugin_type = plugin_type
        self._entries: dict[str, PluginEntry[T]] = {}
        self._enabled_cache: list[tuple[str, T]] | None = None

    def _invalidate_cache(self) -> None:
        """Invalidate the enabled plugins cache.

        Called when registry state changes (register/enable/disable).
        """
        self._enabled_cache = None

    def register(
        self,
        name: str,
        plugin: T | None,
        priority: int = 0,
        source: str = "",
        error: str | None = None,
        recovery_hint: str | None = None,
    ) -> None:
        """Register a plugin with conflict detection.

        Args:
            name: Plugin name (should match plugin's NAME attribute).
            plugin: Plugin instance, or None if load failed.
            priority: Selection priority (higher = preferred).
            source: Entry point string (e.g., "inkwell.plugins.extraction:claude").
            error: Error message if plugin failed to load.
            recovery_hint: Suggestion for fixing broken plugins.

        Raises:
            PluginConflictError: If a plugin with the same name already exists.
        """
        if name in self._entries:
            existing = self._entries[name]
            raise PluginConflictError(name, existing.source, source)

        self._invalidate_cache()

        status: Literal["loaded", "broken", "disabled"]
        if plugin is not None:
            status = "loaded"
        else:
            status = "broken"

        self._entries[name] = PluginEntry(
            name=name,
            plugin=plugin,
            status=status,
            error=error,
            priority=priority,
            source=source,
            recovery_hint=recovery_hint,
        )

    def get(self, name: str) -> T | None:
        """Get plugin by name.

        Args:
            name: Plugin name to look up.

        Returns:
            Plugin instance if found, enabled, and not broken; None otherwise.
        """
        entry = self._entries.get(name)
        if entry and entry.is_usable:
            return entry.plugin
        return None

    def get_entry(self, name: str) -> PluginEntry[T] | None:
        """Get full plugin entry including status information.

        Args:
            name: Plugin name to look up.

        Returns:
            PluginEntry if found, None otherwise.
        """
        return self._entries.get(name)

    def get_enabled(self) -> list[tuple[str, T]]:
        """Get all enabled plugins in priority order (highest first).

        Results are cached until the registry is modified (register/enable/disable).

        Returns:
            List of (name, plugin) tuples sorted by priority descending.
        """
        if self._enabled_cache is None:
            usable: list[tuple[str, T]] = [
                (e.name, e.plugin)  # type: ignore[misc]  # is_usable guarantees plugin is not None
                for e in self._entries.values()
                if e.is_usable
            ]
            self._enabled_cache = sorted(
                usable,
                key=lambda x: (-self._entries[x[0]].priority, x[0]),
            )
        return self._enabled_cache

    def find_capable(self, predicate: Callable[[T], bool]) -> list[tuple[str, T]]:
        """Find plugins matching a predicate, in priority order.

        Useful for finding plugins that can handle specific inputs.

        Args:
            predicate: Function that returns True for matching plugins.

        Returns:
            List of (name, plugin) tuples matching the predicate.

        Example:
            >>> capable = registry.find_capable(lambda p: p.can_handle(request))
        """
        return [(n, p) for n, p in self.get_enabled() if predicate(p)]

    def disable(self, name: str) -> bool:
        """Disable a plugin (keep registered but don't use).

        Args:
            name: Plugin name to disable.

        Returns:
            True if plugin was found and disabled, False if not found.
        """
        if name in self._entries:
            self._invalidate_cache()
            self._entries[name].status = "disabled"
            return True
        return False

    def enable(self, name: str) -> bool:
        """Re-enable a disabled plugin (if it was loaded successfully).

        Args:
            name: Plugin name to enable.

        Returns:
            True if plugin was found and enabled, False if not found or broken.
        """
        entry = self._entries.get(name)
        if entry and entry.plugin is not None:
            self._invalidate_cache()
            entry.status = "loaded"
            return True
        return False

    def all_entries(self) -> list[PluginEntry[T]]:
        """Get all plugin entries for display (e.g., `plugins list`).

        Returns:
            List of all entries sorted by priority (desc) then name (asc).
        """
        return sorted(
            self._entries.values(),
            key=lambda e: (-e.priority, e.name),
        )

    def get_broken(self) -> list[PluginEntry[T]]:
        """Get all broken plugins for error reporting.

        Returns:
            List of entries with status "broken".
        """
        return [e for e in self._entries.values() if e.status == "broken"]

    def __len__(self) -> int:
        """Return total number of registered plugins (including broken)."""
        return len(self._entries)

    def __contains__(self, name: str) -> bool:
        """Check if a plugin name is registered."""
        return name in self._entries
