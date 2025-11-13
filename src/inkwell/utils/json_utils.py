"""Safe JSON parsing utilities with size and depth limits.

This module provides safe JSON parsing for untrusted input (e.g., LLM responses)
with configurable limits to prevent denial-of-service attacks.

Security Considerations:
    - LLM responses are untrusted input that could be malicious
    - JSON bombs can consume arbitrary memory through large strings or deep nesting
    - Size limits prevent memory exhaustion
    - Depth limits prevent stack overflow

Example:
    >>> from inkwell.utils.json_utils import safe_json_loads, extract_json_from_text
    >>> data = safe_json_loads('{"key": "value"}')
    >>> data
    {'key': 'value'}
    >>> text = 'Here is the data: {"key": "value"} and more text'
    >>> extract_json_from_text(text)
    {'key': 'value'}
"""

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


class JSONParsingError(ValueError):
    """Raised when JSON parsing fails validation.

    This includes:
    - Invalid JSON syntax
    - JSON exceeding size limits
    - JSON exceeding depth limits
    - No JSON found in text
    """

    pass


# Configuration constants
# Default maximum JSON size: 10MB (generous for most LLM responses)
MAX_JSON_SIZE = 10_000_000

# Default maximum nesting depth: 10 levels (sufficient for structured data)
MAX_JSON_DEPTH = 10


def get_json_depth(data: Any, current_depth: int = 0) -> int:
    """Calculate maximum depth of nested JSON structure.

    Recursively traverses the JSON structure to find the maximum
    nesting level. Empty dicts/lists count as leaf nodes.

    Args:
        data: JSON data to analyze (dict, list, or primitive)
        current_depth: Current nesting level (used internally for recursion)

    Returns:
        Maximum depth found in the structure

    Example:
        >>> get_json_depth({"a": {"b": {"c": 1}}})
        3
        >>> get_json_depth({"a": 1, "b": 2})
        1
        >>> get_json_depth([1, 2, 3])
        1
        >>> get_json_depth([{"a": {"b": 1}}])
        3
    """
    if not isinstance(data, (dict, list)):
        return current_depth

    if isinstance(data, dict):
        if not data:
            return current_depth
        return max(get_json_depth(v, current_depth + 1) for v in data.values())

    if isinstance(data, list):
        if not data:
            return current_depth
        return max(get_json_depth(item, current_depth + 1) for item in data)

    return current_depth


def safe_json_loads(
    json_str: str, max_size: int = MAX_JSON_SIZE, max_depth: int = MAX_JSON_DEPTH
) -> Any:
    """Safely parse JSON with size and depth limits.

    This function protects against JSON bomb attacks by enforcing
    configurable size and depth limits before and after parsing.

    Args:
        json_str: JSON string to parse
        max_size: Maximum allowed JSON size in bytes (default: 10MB)
        max_depth: Maximum allowed nesting depth (default: 10 levels)

    Returns:
        Parsed JSON data (dict, list, or primitive)

    Raises:
        JSONParsingError: If JSON exceeds limits or is invalid

    Example:
        >>> data = safe_json_loads('{"key": "value"}')
        >>> data
        {'key': 'value'}
        >>> # Large JSON will raise an error
        >>> safe_json_loads('{"x": "' + 'a' * 11_000_000 + '"}')
        Traceback (most recent call last):
            ...
        JSONParsingError: JSON size (...) exceeds maximum (10000000 bytes)

    Security:
        - Checks size before parsing to prevent memory allocation attacks
        - Checks depth after parsing to prevent stack overflow
        - Provides clear error messages for limit violations
    """
    # Check size limit BEFORE parsing to prevent memory exhaustion
    size_bytes = len(json_str.encode("utf-8"))
    if size_bytes > max_size:
        raise JSONParsingError(
            f"JSON size ({size_bytes} bytes) exceeds maximum ({max_size} bytes). "
            f"This may indicate a malicious or malformed LLM response."
        )

    # Parse JSON
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        raise JSONParsingError(f"Invalid JSON: {e}") from e

    # Check depth limit AFTER parsing to prevent stack overflow
    depth = get_json_depth(data)
    if depth > max_depth:
        raise JSONParsingError(
            f"JSON depth ({depth}) exceeds maximum ({max_depth}). "
            f"This may indicate a malicious or malformed LLM response."
        )

    return data


def extract_json_from_text(
    text: str, max_size: int = MAX_JSON_SIZE, max_depth: int = MAX_JSON_DEPTH
) -> Any:
    """Extract and parse JSON from text with safety limits.

    Finds the first JSON object in text (delimited by `{` and `}`)
    and parses it with size and depth limits. This is useful for
    parsing LLM responses that may contain explanatory text before
    or after the JSON.

    Args:
        text: Text containing JSON (may have prefix/suffix)
        max_size: Maximum allowed JSON size in bytes (default: 10MB)
        max_depth: Maximum allowed nesting depth (default: 10 levels)

    Returns:
        Parsed JSON data

    Raises:
        JSONParsingError: If no JSON found or validation fails

    Example:
        >>> text = 'Here is the data: {"key": "value"} and some text'
        >>> extract_json_from_text(text)
        {'key': 'value'}
        >>> # Text without JSON raises an error
        >>> extract_json_from_text('No JSON here')
        Traceback (most recent call last):
            ...
        JSONParsingError: No JSON object found in text

    Note:
        This function looks for the first `{` and last `}` in the text.
        It assumes there is only one JSON object. For multiple objects,
        use safe_json_loads() on each separately.
    """
    # Find JSON boundaries
    json_start = text.find("{")
    json_end = text.rfind("}") + 1

    if json_start < 0 or json_end <= json_start:
        raise JSONParsingError("No JSON object found in text")

    json_str = text[json_start:json_end]

    return safe_json_loads(json_str, max_size, max_depth)
