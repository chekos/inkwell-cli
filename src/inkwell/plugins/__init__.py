"""Inkwell Plugin System.

This module provides the public API for Inkwell's plugin architecture.

Plugin Types:
    - ExtractionPlugin: Extract content from transcripts (Claude, Gemini, etc.)
    - TranscriptionPlugin: Convert audio to text (YouTube, Gemini, Whisper, etc.)
    - OutputPlugin: Generate output files (Markdown, Notion, etc.)

Creating a Plugin:
    1. Inherit from the appropriate plugin base class
    2. Define required class attributes (NAME, VERSION, DESCRIPTION)
    3. Implement required methods
    4. Register via entry points in pyproject.toml

Example:
    >>> from inkwell.plugins import InkwellPlugin, PluginValidationError
    >>>
    >>> class MyPlugin(InkwellPlugin):
    ...     NAME = "my-plugin"
    ...     VERSION = "1.0.0"
    ...     DESCRIPTION = "My custom plugin"
    ...
    ...     def validate(self) -> None:
    ...         if not self.config.get("api_key"):
    ...             raise PluginValidationError(self.NAME, ["api_key is required"])

Entry Point Registration (pyproject.toml):
    [project.entry-points."inkwell.plugins.extraction"]
    my-plugin = "my_package:MyPlugin"

For testing plugins, see `inkwell.plugins.testing`.
"""

# Core plugin infrastructure
from .base import (
    PLUGIN_API_VERSION,
    InkwellPlugin,
    PluginValidationError,
    check_api_version_compatible,
)

# Discovery and loading
from .discovery import (
    ENTRY_POINT_GROUPS,
    PluginLoadResult,
    discover_all_plugins,
    discover_plugins,
    get_entry_point_group,
)

# High-level loading with configuration
from .loader import (
    BrokenPlugin,
    DependencyError,
    cleanup_registry,
    load_plugins_into_registry,
    resolve_dependencies,
)

# Registry for plugin management
from .registry import (
    PluginConflictError,
    PluginEntry,
    PluginRegistry,
)

# Plugin type base classes
from .types import ExtractionPlugin

__all__ = [
    # Constants
    "PLUGIN_API_VERSION",
    "ENTRY_POINT_GROUPS",
    # Base classes
    "InkwellPlugin",
    "BrokenPlugin",
    "ExtractionPlugin",
    # Exceptions
    "PluginValidationError",
    "PluginConflictError",
    "DependencyError",
    # Registry
    "PluginRegistry",
    "PluginEntry",
    # Discovery
    "PluginLoadResult",
    "discover_plugins",
    "discover_all_plugins",
    "get_entry_point_group",
    # Loading
    "load_plugins_into_registry",
    "resolve_dependencies",
    "cleanup_registry",
    # Utilities
    "check_api_version_compatible",
]
