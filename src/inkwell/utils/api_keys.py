"""API key validation utilities.

Provides centralized validation for API keys from environment variables.
Validates format, length, and common mistakes to catch configuration errors early.
"""

import os
import re
from typing import Literal


class APIKeyError(ValueError):
    """Raised when API key is invalid or missing."""

    pass


def validate_api_key(
    key: str | None,
    provider: Literal["gemini", "claude", "youtube"],
    key_name: str,
) -> str:
    """Validate API key format and return cleaned key.

    Args:
        key: The API key to validate (may be None)
        provider: The API provider name
        key_name: Environment variable name (for error messages)

    Returns:
        Validated and stripped API key

    Raises:
        APIKeyError: If key is missing, empty, or malformed

    Example:
        >>> key = validate_api_key(
        ...     os.environ.get("GOOGLE_API_KEY"),
        ...     "gemini",
        ...     "GOOGLE_API_KEY"
        ... )
    """
    # Check if key exists
    if key is None or not key.strip():
        raise APIKeyError(
            f"{provider.title()} API key is required.\n"
            f"Set the {key_name} environment variable.\n"
            f"Example: export {key_name}='your-api-key-here'"
        )

    # Check for common mistakes BEFORE stripping
    # Check for quotes (on original, non-stripped key)
    if (key.strip().startswith('"') and key.strip().endswith('"')) or (
        key.strip().startswith("'") and key.strip().endswith("'")
    ):
        raise APIKeyError(
            f"{provider.title()} API key should not be quoted.\n"
            f"Remove quotes from {key_name} environment variable.\n"
            f"Example: export {key_name}=your-api-key-here"
        )

    # Check for invalid characters BEFORE stripping
    if any(char in key for char in ["\n", "\r", "\0", "\t"]):
        raise APIKeyError(
            f"{provider.title()} API key contains invalid characters.\n"
            f"API keys should not contain newlines or control characters.\n"
            f"Check your {key_name} environment variable."
        )

    # Now strip for further validation
    key = key.strip()

    # Basic length validation (most API keys are 20+ chars)
    # Note: Error message is intentionally generic to avoid information disclosure
    if len(key) < 20:
        raise APIKeyError(
            f"{provider.title()} API key appears invalid.\n"
            f"Check your {key_name} environment variable.\n"
            f"Ensure it's properly formatted without quotes or whitespace."
        )

    # Provider-specific validation
    # Note: Error messages are intentionally generic to avoid revealing key format details
    if provider == "gemini":
        # Gemini keys typically start with "AIza" and are alphanumeric + dash
        if not re.match(r"^AIza[A-Za-z0-9_-]+$", key):
            raise APIKeyError(
                f"{provider.title()} API key appears invalid.\n"
                f"Check your {key_name} environment variable."
            )

    elif provider == "claude":
        # Claude keys start with "sk-ant-" and are alphanumeric
        if not re.match(r"^sk-ant-[A-Za-z0-9_-]+$", key):
            raise APIKeyError(
                f"{provider.title()} API key appears invalid.\n"
                f"Check your {key_name} environment variable."
            )

    return key


def get_validated_api_key(
    env_var: str,
    provider: Literal["gemini", "claude", "youtube"],
) -> str:
    """Get and validate API key from environment.

    Args:
        env_var: Environment variable name
        provider: API provider name

    Returns:
        Validated API key

    Raises:
        APIKeyError: If key is missing or invalid

    Example:
        >>> gemini_key = get_validated_api_key("GOOGLE_API_KEY", "gemini")
    """
    key = os.environ.get(env_var)
    return validate_api_key(key, provider, env_var)
