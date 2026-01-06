"""Base plugin infrastructure for Inkwell.

This module defines the abstract base class that all Inkwell plugins
must inherit from, along with the plugin API version constant.
"""

from abc import ABC
from typing import TYPE_CHECKING, Any, ClassVar

from pydantic import BaseModel

if TYPE_CHECKING:
    from inkwell.utils.costs import CostTracker

# Plugin API version - only changes when plugin interface has breaking changes.
# This is separate from package version (managed via git tags/releases).
# Format: "major.minor" - major must match, minor is backward compatible.
PLUGIN_API_VERSION = "1.0"


class PluginValidationError(Exception):
    """Raised when plugin configuration is invalid.

    Plugins should raise this from their validate() method when
    configuration is invalid or required resources are unavailable.

    Attributes:
        plugin_name: Name of the plugin that failed validation.
        errors: List of validation error messages.
    """

    def __init__(self, plugin_name: str, errors: list[str]) -> None:
        self.plugin_name = plugin_name
        self.errors = errors
        error_list = "; ".join(errors)
        super().__init__(f"Plugin '{plugin_name}' validation failed: {error_list}")


class InkwellPlugin(ABC):
    """Base class for all Inkwell plugins.

    All plugins must inherit from this class and define the required
    class attributes (NAME, VERSION, DESCRIPTION).

    Plugin Lifecycle:
        1. configure(config, cost_tracker) - Called with validated config
        2. validate() - Raise PluginValidationError if invalid
        3. [use plugin methods] - Plugin is now ready for use
        4. cleanup() - Called when plugin is no longer needed

    Example:
        >>> class MyExtractor(InkwellPlugin):
        ...     NAME = "my-extractor"
        ...     VERSION = "1.0.0"
        ...     DESCRIPTION = "My custom extractor"
        ...
        ...     def validate(self) -> None:
        ...         if not os.environ.get("MY_API_KEY"):
        ...             raise PluginValidationError(
        ...                 self.NAME, ["MY_API_KEY environment variable not set"]
        ...             )
    """

    # Required metadata (class attributes)
    NAME: ClassVar[str]
    VERSION: ClassVar[str]
    DESCRIPTION: ClassVar[str]

    # Plugin API version - should match PLUGIN_API_VERSION major version
    API_VERSION: ClassVar[str] = PLUGIN_API_VERSION

    # Optional metadata
    AUTHOR: ClassVar[str] = ""
    HOMEPAGE: ClassVar[str | None] = None

    # Optional: Pydantic model for config validation
    CONFIG_SCHEMA: ClassVar[type[BaseModel] | None] = None

    # Optional: Other plugin names this depends on (resolved via topological sort)
    DEPENDS_ON: ClassVar[list[str]] = []

    def __init__(self) -> None:
        self._initialized = False
        self._config: BaseModel | dict[str, Any] = {}
        self._cost_tracker: CostTracker | None = None

    def configure(
        self,
        config: dict[str, Any],
        cost_tracker: "CostTracker | None" = None,
    ) -> None:
        """Called with validated config before first use.

        This is the primary setup method. Override to perform additional
        initialization after config is set.

        Args:
            config: Plugin-specific configuration dict. If CONFIG_SCHEMA
                is defined, this will be validated against it.
            cost_tracker: Optional cost tracker for API usage tracking.
                Passed via direct dependency injection (no service locator).
        """
        if self.CONFIG_SCHEMA:
            self._config = self.CONFIG_SCHEMA(**config)
        else:
            self._config = config
        self._cost_tracker = cost_tracker
        self._initialized = True

    def validate(self) -> None:  # noqa: B027
        """Validate plugin state after configuration.

        Called after configure() but before first use. Override to add
        custom validation such as:
        - Check API keys are set
        - Verify required binaries exist
        - Test external service connectivity

        Raises:
            PluginValidationError: If plugin state is invalid.
        """
        # Default: no additional validation (intentionally not abstract)

    def cleanup(self) -> None:  # noqa: B027
        """Called when plugin is no longer needed.

        Override to release resources like:
        - Close network connections
        - Clean up temporary files
        - Stop background tasks
        """
        # Default: no cleanup needed (intentionally not abstract)

    @property
    def is_initialized(self) -> bool:
        """Whether configure() has been called."""
        return self._initialized

    @property
    def config(self) -> BaseModel | dict[str, Any]:
        """Access validated configuration.

        Raises:
            RuntimeError: If accessed before configure() is called.
        """
        if not self._initialized:
            raise RuntimeError(f"Plugin {self.NAME} not configured")
        return self._config

    @property
    def cost_tracker(self) -> "CostTracker | None":
        """Access cost tracker for API usage tracking."""
        return self._cost_tracker


def check_api_version_compatible(plugin_api_version: str) -> bool:
    """Check if a plugin's API version is compatible with current API.

    Compatibility rule: Major version must match exactly.
    Minor versions are backward compatible.

    Args:
        plugin_api_version: The plugin's declared API_VERSION.

    Returns:
        True if compatible, False otherwise.
    """
    try:
        current_major = PLUGIN_API_VERSION.split(".")[0]
        plugin_major = plugin_api_version.split(".")[0]
        return current_major == plugin_major
    except (IndexError, AttributeError):
        return False
