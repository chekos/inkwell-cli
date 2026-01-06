"""Plugin loading with dependency resolution and configuration.

This module provides high-level plugin loading functionality including:
- BrokenPlugin wrapper for failed loads
- Topological sort for dependency resolution
- Configuration and validation orchestration
"""

from typing import TYPE_CHECKING, Any, TypeVar

from inkwell.utils.logging import get_logger

from .base import InkwellPlugin, PluginValidationError
from .discovery import discover_plugins, get_entry_point_group
from .registry import PluginRegistry

if TYPE_CHECKING:
    from inkwell.utils.costs import CostTracker

logger = get_logger()

T = TypeVar("T", bound=InkwellPlugin)


class BrokenPlugin(InkwellPlugin):
    """Placeholder for plugins that failed to load.

    This allows the system to track and display information about
    failed plugins without crashing.

    Attributes:
        NAME: Original plugin name that failed to load.
        VERSION: "0.0.0" (unknown).
        DESCRIPTION: Error description.
        error_message: Full error message.
        recovery_hint: Suggestion for fixing the issue.
    """

    NAME: str = "broken"  # type: ignore[misc]  # Will be overridden per-instance
    VERSION: str = "0.0.0"  # type: ignore[misc]
    DESCRIPTION: str = "Plugin failed to load"  # type: ignore[misc]

    def __init__(
        self,
        name: str,
        error_message: str,
        recovery_hint: str | None = None,
    ) -> None:
        super().__init__()
        # Override class attributes with instance attributes
        self.NAME = name  # type: ignore[misc]
        self.DESCRIPTION = f"Failed to load: {error_message}"  # type: ignore[misc]
        self.error_message = error_message
        self.recovery_hint = recovery_hint

    def validate(self) -> None:
        """Always fails validation since plugin is broken."""
        raise PluginValidationError(
            self.NAME,
            [self.error_message],
        )


class DependencyError(Exception):
    """Raised when plugin dependencies cannot be resolved.

    Attributes:
        plugin_name: Plugin with unresolvable dependencies.
        missing: List of missing dependency names.
        cycle: List of plugin names forming a cycle (if cyclic).
    """

    def __init__(
        self,
        plugin_name: str,
        missing: list[str] | None = None,
        cycle: list[str] | None = None,
    ) -> None:
        self.plugin_name = plugin_name
        self.missing = missing or []
        self.cycle = cycle or []

        if self.cycle:
            msg = f"Dependency cycle detected: {' -> '.join(self.cycle)}"
        else:
            msg = f"Plugin '{plugin_name}' has missing dependencies: {', '.join(self.missing)}"
        super().__init__(msg)


def resolve_dependencies(plugins: list[InkwellPlugin]) -> list[InkwellPlugin]:
    """Sort plugins by dependencies using topological sort.

    Ensures plugins are configured in an order where dependencies
    come before dependents.

    Args:
        plugins: List of plugins to sort.

    Returns:
        Plugins sorted so dependencies come first.

    Raises:
        DependencyError: If dependencies are missing or cyclic.
    """
    if not plugins:
        return []

    # Build dependency graph
    plugin_map = {p.NAME: p for p in plugins}
    in_degree: dict[str, int] = {p.NAME: 0 for p in plugins}
    dependents: dict[str, list[str]] = {p.NAME: [] for p in plugins}

    # Check for missing dependencies and build graph
    for plugin in plugins:
        for dep_name in plugin.DEPENDS_ON:
            if dep_name not in plugin_map:
                raise DependencyError(plugin.NAME, missing=[dep_name])
            dependents[dep_name].append(plugin.NAME)
            in_degree[plugin.NAME] += 1

    # Kahn's algorithm for topological sort
    queue = [name for name, degree in in_degree.items() if degree == 0]
    result: list[InkwellPlugin] = []

    while queue:
        # Sort queue for deterministic order
        queue.sort()
        name = queue.pop(0)
        result.append(plugin_map[name])

        for dependent in dependents[name]:
            in_degree[dependent] -= 1
            if in_degree[dependent] == 0:
                queue.append(dependent)

    # Check for cycles
    if len(result) != len(plugins):
        # Find a cycle for error reporting
        remaining = set(in_degree.keys()) - {p.NAME for p in result}
        cycle = _find_cycle(remaining, dependents, plugin_map)
        raise DependencyError(cycle[0], cycle=cycle)

    return result


def _find_cycle(
    remaining: set[str],
    dependents: dict[str, list[str]],
    plugin_map: dict[str, InkwellPlugin],
) -> list[str]:
    """Find a cycle in the dependency graph for error reporting."""
    # Simple DFS to find a cycle
    visited: set[str] = set()
    path: list[str] = []

    def dfs(name: str) -> list[str] | None:
        if name in path:
            cycle_start = path.index(name)
            return path[cycle_start:] + [name]
        if name in visited:
            return None

        visited.add(name)
        path.append(name)

        plugin = plugin_map.get(name)
        if plugin:
            for dep in plugin.DEPENDS_ON:
                if dep in remaining:
                    result = dfs(dep)
                    if result:
                        return result

        path.pop()
        return None

    for name in remaining:
        cycle = dfs(name)
        if cycle:
            return cycle

    return list(remaining)[:3]  # Fallback


def load_plugins_into_registry(
    registry: PluginRegistry[T],
    plugin_type: str,
    config: dict[str, dict[str, Any]] | None = None,
    cost_tracker: "CostTracker | None" = None,
    default_priority: int = PluginRegistry.PRIORITY_BUILTIN,
) -> None:
    """Discover, load, and configure plugins into a registry.

    This is the main entry point for loading plugins. It:
    1. Discovers plugins from entry points
    2. Registers them (detecting conflicts)
    3. Resolves dependencies
    4. Configures each plugin
    5. Validates each plugin

    Args:
        registry: Registry to load plugins into.
        plugin_type: Short type name ("extraction", "transcription", "output").
        config: Per-plugin configuration dict, keyed by plugin name.
            Each value should have optional "enabled", "priority", "config" keys.
        cost_tracker: Optional cost tracker for plugins that track API usage.
        default_priority: Default priority for plugins without explicit config.

    Raises:
        PluginConflictError: If two plugins have the same name.
    """
    config = config or {}
    group = get_entry_point_group(plugin_type)

    # Phase 1: Discover and register
    loaded_plugins: list[InkwellPlugin] = []

    for result in discover_plugins(group):
        plugin_config = config.get(result.name, {})

        # Check if plugin is disabled
        if not plugin_config.get("enabled", True):
            logger.debug("Plugin %s is disabled in config", result.name)
            continue

        # Get priority from config or use default
        priority = plugin_config.get("priority", default_priority)

        if result.success and result.plugin is not None:
            registry.register(
                name=result.name,
                plugin=result.plugin,  # type: ignore[arg-type]  # Generic variance
                priority=priority,
                source=result.source,
            )
            loaded_plugins.append(result.plugin)
        else:
            # Register as broken
            registry.register(
                name=result.name,
                plugin=None,
                priority=priority,
                source=result.source,
                error=result.error,
                recovery_hint=result.recovery_hint,
            )

    # Phase 2: Resolve dependencies
    try:
        sorted_plugins = resolve_dependencies(loaded_plugins)
    except DependencyError as e:
        logger.error("Dependency resolution failed: %s", e)
        # Mark affected plugins as broken
        for plugin in loaded_plugins:
            if plugin.NAME == e.plugin_name or plugin.NAME in e.missing:
                entry = registry.get_entry(plugin.NAME)
                if entry:
                    entry.status = "broken"
                    entry.error = str(e)
        return

    # Phase 3: Configure and validate
    for plugin in sorted_plugins:
        plugin_config = config.get(plugin.NAME, {})
        plugin_specific_config = plugin_config.get("config", {})

        try:
            # Configure
            plugin.configure(plugin_specific_config, cost_tracker)

            # Validate
            plugin.validate()

            logger.debug("Plugin %s configured and validated", plugin.NAME)

        except PluginValidationError as e:
            logger.warning("Plugin %s failed validation: %s", plugin.NAME, e)
            entry = registry.get_entry(plugin.NAME)
            if entry:
                entry.status = "broken"
                entry.error = str(e)

        except Exception as e:
            logger.error("Plugin %s configuration failed: %s", plugin.NAME, e)
            entry = registry.get_entry(plugin.NAME)
            if entry:
                entry.status = "broken"
                entry.error = f"{type(e).__name__}: {e}"


def cleanup_registry(registry: PluginRegistry[T]) -> None:
    """Call cleanup() on all loaded plugins in a registry.

    Should be called when shutting down to release resources.

    Args:
        registry: Registry containing plugins to clean up.
    """
    for name, plugin in registry.get_enabled():
        try:
            plugin.cleanup()
            logger.debug("Cleaned up plugin %s", name)
        except Exception as e:
            logger.warning("Error cleaning up plugin %s: %s", name, e)
