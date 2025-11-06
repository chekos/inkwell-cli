"""Configuration manager for loading and saving Inkwell config."""

from pathlib import Path


class ConfigManager:
    """Manages Inkwell configuration files."""

    def __init__(self, config_dir: Path | None = None) -> None:
        """Initialize the config manager.

        Args:
            config_dir: Optional custom config directory. Defaults to XDG config dir.
        """
        self.config_dir = config_dir
