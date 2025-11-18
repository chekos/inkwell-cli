"""Configuration parameter precedence resolution.

This module provides a standardized helper for resolving configuration values
following a consistent precedence hierarchy across all services.

Precedence order (highest to lowest):
1. Config object value (if not None)
2. Individual parameter value (if not None)
3. Default value

This ensures consistent behavior when combining new config-based DI
with legacy individual parameters during migration.
"""

from typing import TypeVar

T = TypeVar("T")


def resolve_config_value(
    config_value: T | None,
    param_value: T | None,
    default_value: T,
) -> T:
    """Resolve configuration value with precedence rules.

    Precedence (highest to lowest):
    1. Config object value (if not None)
    2. Individual parameter value (if not None)
    3. Default value

    Note: This uses explicit None checks to ensure that falsy values
    like 0, False, and "" are treated as valid configuration values,
    not as None.

    Args:
        config_value: Value from config object (may be None)
        param_value: Value from individual parameter (may be None)
        default_value: Default fallback value

    Returns:
        Resolved value following precedence rules

    Example:
        >>> resolve_config_value(
        ...     config_value="from-config",
        ...     param_value="from-param",
        ...     default_value="default"
        ... )
        'from-config'  # Config wins

        >>> resolve_config_value(
        ...     config_value=None,
        ...     param_value="from-param",
        ...     default_value="default"
        ... )
        'from-param'  # Param wins when config is None

        >>> resolve_config_value(
        ...     config_value=0,
        ...     param_value=5,
        ...     default_value=10
        ... )
        0  # Zero is valid, not None
    """
    if config_value is not None:
        return config_value
    if param_value is not None:
        return param_value
    return default_value
