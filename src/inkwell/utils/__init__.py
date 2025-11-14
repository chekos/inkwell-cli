"""Utility functions and helpers for Inkwell."""

from inkwell.utils.cache import CacheError, FileCache
from inkwell.utils.errors import (
    APIError,
    ConfigError,
    InkwellError,
    NotFoundError,
    SecurityError,
    ValidationError,
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
    # Cache
    "FileCache",
    "CacheError",
    # Errors (5 core types per todo #035)
    "InkwellError",
    "ConfigError",
    "APIError",
    "ValidationError",
    "NotFoundError",
    "SecurityError",
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
