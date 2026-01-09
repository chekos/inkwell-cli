"""Plugin configuration manager for persisting plugin state.

This module provides the PluginConfigManager class for persisting
plugin enable/disable state to the configuration file.
"""

from inkwell.config.manager import ConfigManager
from inkwell.config.schema import PluginConfig


class PluginConfigManager:
    """Manages persistent plugin configuration.

    Provides a programmatic API for persisting plugin enable/disable
    state to the config file, ensuring state survives application restarts.

    Example:
        >>> from inkwell.config.manager import ConfigManager
        >>> from inkwell.plugins.config import PluginConfigManager
        >>>
        >>> config_manager = ConfigManager()
        >>> plugin_config = PluginConfigManager(config_manager)
        >>>
        >>> # Disable a plugin persistently
        >>> plugin_config.set_plugin_enabled("whisper", False)
        >>>
        >>> # Check plugin configuration
        >>> config = plugin_config.get_plugin_config("whisper")
        >>> print(config.enabled)  # False
    """

    def __init__(self, config_manager: ConfigManager) -> None:
        """Initialize the plugin configuration manager.

        Args:
            config_manager: The ConfigManager instance for loading/saving config.
        """
        self._config = config_manager

    def set_plugin_enabled(self, name: str, enabled: bool) -> None:
        """Persist plugin enabled state to config file.

        If the plugin has no existing configuration, creates a new
        PluginConfig entry with default settings.

        Args:
            name: Plugin name to configure.
            enabled: Whether the plugin should be enabled.
        """
        config = self._config.load_config()
        if name not in config.plugins:
            config.plugins[name] = PluginConfig(enabled=enabled)
        else:
            config.plugins[name].enabled = enabled
        self._config.save_config(config)

    def get_plugin_config(self, name: str) -> PluginConfig | None:
        """Get plugin configuration from config file.

        Args:
            name: Plugin name to look up.

        Returns:
            PluginConfig if found, None otherwise.
        """
        config = self._config.load_config()
        return config.plugins.get(name)

    def set_plugin_priority(self, name: str, priority: int) -> None:
        """Persist plugin priority to config file.

        Args:
            name: Plugin name to configure.
            priority: Priority value (0-200, higher = preferred).
        """
        config = self._config.load_config()
        if name not in config.plugins:
            config.plugins[name] = PluginConfig(priority=priority)
        else:
            config.plugins[name].priority = priority
        self._config.save_config(config)

    def set_plugin_config_value(self, name: str, key: str, value: object) -> None:
        """Set a plugin-specific configuration value.

        Args:
            name: Plugin name to configure.
            key: Configuration key within the plugin's config dict.
            value: Configuration value to set.
        """
        config = self._config.load_config()
        if name not in config.plugins:
            config.plugins[name] = PluginConfig(config={key: value})
        else:
            config.plugins[name].config[key] = value
        self._config.save_config(config)

    def remove_plugin_config(self, name: str) -> bool:
        """Remove all configuration for a plugin.

        Args:
            name: Plugin name to remove configuration for.

        Returns:
            True if configuration was removed, False if not found.
        """
        config = self._config.load_config()
        if name in config.plugins:
            del config.plugins[name]
            self._config.save_config(config)
            return True
        return False

    def list_configured_plugins(self) -> dict[str, PluginConfig]:
        """List all plugins with persistent configuration.

        Returns:
            Dictionary mapping plugin names to their configurations.
        """
        config = self._config.load_config()
        return config.plugins.copy()

    def is_plugin_enabled(self, name: str) -> bool:
        """Check if a plugin is enabled in persistent config.

        Returns True if the plugin has no config (default enabled)
        or if explicitly enabled.

        Args:
            name: Plugin name to check.

        Returns:
            True if enabled or not configured (default), False if disabled.
        """
        plugin_config = self.get_plugin_config(name)
        if plugin_config is None:
            return True  # Default is enabled
        return plugin_config.enabled
