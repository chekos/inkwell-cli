"""Plugin discovery via importlib.metadata entry points.

This module handles automatic plugin discovery from installed packages
using Python's standard entry point mechanism.

Entry Point Groups:
    - inkwell.plugins.extraction: ExtractionPlugin implementations
    - inkwell.plugins.transcription: TranscriptionPlugin implementations
    - inkwell.plugins.output: OutputPlugin implementations
"""

from collections.abc import Iterator
from importlib.metadata import entry_points

from inkwell.utils.logging import get_logger

from .base import PLUGIN_API_VERSION, InkwellPlugin, check_api_version_compatible

logger = get_logger()


# Entry point group names
ENTRY_POINT_GROUPS = {
    "extraction": "inkwell.plugins.extraction",
    "transcription": "inkwell.plugins.transcription",
    "output": "inkwell.plugins.output",
}


class PluginLoadResult:
    """Result of attempting to load a single plugin.

    Attributes:
        name: Plugin name (from entry point).
        plugin: Loaded plugin instance, or None if load failed.
        error: Error message if load failed.
        recovery_hint: Suggestion for fixing the issue.
        source: Entry point source string.
    """

    def __init__(
        self,
        name: str,
        plugin: InkwellPlugin | None,
        error: str | None = None,
        recovery_hint: str | None = None,
        source: str = "",
    ) -> None:
        self.name = name
        self.plugin = plugin
        self.error = error
        self.recovery_hint = recovery_hint
        self.source = source

    @property
    def success(self) -> bool:
        """Whether the plugin loaded successfully."""
        return self.plugin is not None and self.error is None


def _generate_recovery_hint(error: Exception) -> str | None:
    """Generate a recovery hint based on the error type.

    Args:
        error: The exception that occurred during plugin load.

    Returns:
        A helpful suggestion for fixing the issue, or None.
    """
    error_str = str(error).lower()
    error_type = type(error).__name__

    # ModuleNotFoundError / ImportError
    if isinstance(error, ModuleNotFoundError):
        module_name = getattr(error, "name", None)
        if module_name:
            return f"uv add {module_name}"
        return "Check that all plugin dependencies are installed"

    if isinstance(error, ImportError):
        if "torch" in error_str:
            return "uv add torch"
        if "cuda" in error_str:
            return "Install CUDA toolkit or use CPU-only version"
        return "Check import paths and dependencies"

    # AttributeError often means missing class attributes
    if error_type == "AttributeError":
        if "NAME" in str(error) or "VERSION" in str(error):
            return "Plugin class missing required NAME or VERSION attribute"
        return "Plugin class may be incorrectly defined"

    # TypeError often means __init__ signature issues
    if error_type == "TypeError" and "__init__" in error_str:
        return "Plugin __init__ must accept no required arguments"

    return None


def discover_plugins(group: str) -> Iterator[PluginLoadResult]:
    """Discover and yield plugins from a specific entry point group.

    Lazily loads each plugin, yielding results as they're discovered.
    Failed loads yield results with error information instead of raising.

    Args:
        group: Entry point group name (e.g., "inkwell.plugins.extraction").

    Yields:
        PluginLoadResult for each discovered entry point.

    Example:
        >>> for result in discover_plugins("inkwell.plugins.extraction"):
        ...     if result.success:
        ...         print(f"Loaded: {result.name}")
        ...     else:
        ...         print(f"Failed: {result.name} - {result.error}")
    """
    eps = entry_points(group=group)

    for ep in eps:
        source = f"{group}:{ep.name}"
        name = ep.name

        try:
            # Load the entry point (imports the module and gets the class)
            plugin_class = ep.load()

            # Validate it's a proper plugin class
            if not isinstance(plugin_class, type) or not issubclass(plugin_class, InkwellPlugin):
                yield PluginLoadResult(
                    name=name,
                    plugin=None,
                    error=(
                        f"Entry point does not point to an InkwellPlugin subclass: {plugin_class}"
                    ),
                    source=source,
                )
                continue

            # Check API version compatibility
            plugin_api_version = getattr(plugin_class, "API_VERSION", PLUGIN_API_VERSION)
            if not check_api_version_compatible(plugin_api_version):
                yield PluginLoadResult(
                    name=name,
                    plugin=None,
                    error=(
                        f"Incompatible API version: plugin requires {plugin_api_version}, "
                        f"but current API is {PLUGIN_API_VERSION}"
                    ),
                    recovery_hint="Update the plugin to a compatible version",
                    source=source,
                )
                continue

            # Instantiate the plugin with lazy_init=True to defer API client
            # initialization until configure() is called with proper credentials.
            # Fall back to no-arg instantiation for plugins that don't support it.
            try:
                plugin = plugin_class(lazy_init=True)
            except TypeError:
                # Plugin doesn't accept lazy_init parameter
                plugin = plugin_class()

            logger.debug("Loaded plugin %s from %s", name, source)
            yield PluginLoadResult(
                name=name,
                plugin=plugin,
                source=source,
            )

        except Exception as e:
            error_msg = f"{type(e).__name__}: {e}"
            recovery_hint = _generate_recovery_hint(e)

            logger.warning("Failed to load plugin %s: %s", name, error_msg)
            yield PluginLoadResult(
                name=name,
                plugin=None,
                error=error_msg,
                recovery_hint=recovery_hint,
                source=source,
            )


def discover_all_plugins() -> dict[str, list[PluginLoadResult]]:
    """Discover all plugins across all entry point groups.

    Returns:
        Dict mapping group short names to lists of load results.

    Example:
        >>> all_plugins = discover_all_plugins()
        >>> for name, plugin in all_plugins["extraction"]:
        ...     if plugin.success:
        ...         print(f"Extractor: {name}")
    """
    results: dict[str, list[PluginLoadResult]] = {}

    for short_name, group in ENTRY_POINT_GROUPS.items():
        results[short_name] = list(discover_plugins(group))

    return results


def get_entry_point_group(plugin_type: str) -> str:
    """Get the entry point group name for a plugin type.

    Args:
        plugin_type: Short name like "extraction", "transcription", "output".

    Returns:
        Full entry point group name.

    Raises:
        ValueError: If plugin_type is not recognized.
    """
    if plugin_type not in ENTRY_POINT_GROUPS:
        valid = ", ".join(ENTRY_POINT_GROUPS.keys())
        raise ValueError(f"Unknown plugin type: {plugin_type}. Valid types: {valid}")
    return ENTRY_POINT_GROUPS[plugin_type]
