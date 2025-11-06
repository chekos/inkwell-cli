"""Utility functions and helpers for Inkwell."""

from inkwell.utils.errors import (
    AuthenticationError,
    ConfigError,
    ConfigNotFoundError,
    DuplicateFeedError,
    EncryptionError,
    FeedError,
    FeedNotFoundError,
    FeedParseError,
    InkwellError,
    InvalidConfigError,
    NetworkConnectionError,
    NetworkError,
    NetworkTimeoutError,
)
from inkwell.utils.paths import (
    ensure_config_files_exist,
    get_cache_dir,
    get_config_dir,
    get_config_file,
    get_data_dir,
    get_feeds_file,
    get_key_file,
    get_log_file,
)

__all__ = [
    # Errors
    "InkwellError",
    "ConfigError",
    "InvalidConfigError",
    "ConfigNotFoundError",
    "EncryptionError",
    "FeedError",
    "FeedNotFoundError",
    "DuplicateFeedError",
    "FeedParseError",
    "AuthenticationError",
    "NetworkError",
    "NetworkConnectionError",
    "NetworkTimeoutError",
    # Paths
    "get_config_dir",
    "get_data_dir",
    "get_cache_dir",
    "get_config_file",
    "get_feeds_file",
    "get_key_file",
    "get_log_file",
    "ensure_config_files_exist",
]
