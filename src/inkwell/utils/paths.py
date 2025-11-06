"""XDG-compliant path utilities for Inkwell."""

from pathlib import Path

from platformdirs import user_cache_dir, user_config_dir, user_data_dir


def get_config_dir() -> Path:
    """Get the configuration directory path.

    Returns XDG_CONFIG_HOME/inkwell or ~/.config/inkwell on Linux/macOS.

    Returns:
        Path to the config directory
    """
    config_dir = Path(user_config_dir("inkwell", appauthor=False))
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_data_dir() -> Path:
    """Get the data directory path.

    Returns XDG_DATA_HOME/inkwell or ~/.local/share/inkwell on Linux/macOS.

    Returns:
        Path to the data directory
    """
    data_dir = Path(user_data_dir("inkwell", appauthor=False))
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def get_cache_dir() -> Path:
    """Get the cache directory path.

    Returns XDG_CACHE_HOME/inkwell or ~/.cache/inkwell on Linux/macOS.

    Returns:
        Path to the cache directory
    """
    cache_dir = Path(user_cache_dir("inkwell", appauthor=False))
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def get_config_file() -> Path:
    """Get the global config file path.

    Returns:
        Path to config.yaml
    """
    return get_config_dir() / "config.yaml"


def get_feeds_file() -> Path:
    """Get the feeds configuration file path.

    Returns:
        Path to feeds.yaml
    """
    return get_config_dir() / "feeds.yaml"


def get_key_file() -> Path:
    """Get the encryption key file path.

    Returns:
        Path to .keyfile
    """
    return get_config_dir() / ".keyfile"


def get_log_file() -> Path:
    """Get the log file path.

    Returns:
        Path to inkwell.log in cache directory
    """
    return get_cache_dir() / "inkwell.log"


def ensure_config_files_exist() -> None:
    """Ensure all configuration directories and files exist.

    Creates directories if they don't exist. Does not create config files
    themselves - that's handled by ConfigManager.
    """
    get_config_dir()
    get_data_dir()
    get_cache_dir()
