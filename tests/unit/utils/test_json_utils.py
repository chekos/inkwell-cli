"""Unit tests for safe JSON utilities.

Tests cover:
- Size limit enforcement
- Depth limit enforcement
- Valid JSON parsing
- Invalid JSON handling
- JSON extraction from text
- Edge cases and security scenarios
"""

import json

import pytest

from inkwell.utils.json_utils import (
    JSONParsingError,
    extract_json_from_text,
    get_json_depth,
    safe_json_loads,
)


class TestGetJsonDepth:
    """Tests for get_json_depth function."""

    def test_depth_primitive_values(self):
        """Test depth calculation for primitive values."""
        assert get_json_depth(None) == 0
        assert get_json_depth(42) == 0
        assert get_json_depth("string") == 0
        assert get_json_depth(True) == 0
        assert get_json_depth(3.14) == 0

    def test_depth_empty_containers(self):
        """Test depth calculation for empty containers."""
        assert get_json_depth({}) == 0
        assert get_json_depth([]) == 0

    def test_depth_flat_dict(self):
        """Test depth calculation for flat dictionary."""
        data = {"a": 1, "b": 2, "c": 3}
        assert get_json_depth(data) == 1

    def test_depth_flat_list(self):
        """Test depth calculation for flat list."""
        data = [1, 2, 3, 4, 5]
        assert get_json_depth(data) == 1

    def test_depth_nested_dict(self):
        """Test depth calculation for nested dictionaries."""
        data = {"level1": {"level2": {"level3": 1}}}
        assert get_json_depth(data) == 3

    def test_depth_nested_list(self):
        """Test depth calculation for nested lists."""
        data = [[[1, 2], [3, 4]], [[5, 6], [7, 8]]]
        assert get_json_depth(data) == 3

    def test_depth_mixed_nesting(self):
        """Test depth calculation for mixed dict/list nesting."""
        data = {"a": [{"b": [{"c": 1}]}]}
        # Depth: dict(1) -> list(2) -> dict(3) -> list(4) -> dict(5)
        assert get_json_depth(data) == 5

    def test_depth_multiple_branches_different_depths(self):
        """Test that maximum depth is returned across branches."""
        data = {
            "shallow": {"level": 1},
            "deep": {"level2": {"level3": {"level4": 1}}},
        }
        assert get_json_depth(data) == 4


class TestSafeJsonLoads:
    """Tests for safe_json_loads function."""

    def test_valid_simple_json(self):
        """Test parsing valid simple JSON."""
        json_str = '{"key": "value"}'
        result = safe_json_loads(json_str)
        assert result == {"key": "value"}

    def test_valid_complex_json(self):
        """Test parsing valid complex JSON."""
        data = {
            "string": "value",
            "number": 42,
            "boolean": True,
            "null": None,
            "array": [1, 2, 3],
            "object": {"nested": "data"},
        }
        json_str = json.dumps(data)
        result = safe_json_loads(json_str)
        assert result == data

    def test_invalid_json_syntax(self):
        """Test that invalid JSON syntax raises JSONParsingError."""
        with pytest.raises(JSONParsingError, match="Invalid JSON"):
            safe_json_loads('{"invalid": ')

    def test_size_limit_enforcement(self):
        """Test that JSON exceeding size limit is rejected."""
        # Create JSON string larger than limit
        large_json = '{"data": "' + ("x" * 1_000_000) + '"}'
        with pytest.raises(JSONParsingError, match="exceeds maximum"):
            safe_json_loads(large_json, max_size=500_000)

    def test_size_limit_exact_boundary(self):
        """Test JSON at exact size limit is accepted."""
        # Create JSON at exact limit
        json_str = '{"data": "x"}'
        size = len(json_str.encode("utf-8"))
        # Should succeed at exact limit
        result = safe_json_loads(json_str, max_size=size)
        assert result == {"data": "x"}

    def test_size_limit_one_byte_over(self):
        """Test JSON one byte over limit is rejected."""
        json_str = '{"data": "x"}'
        size = len(json_str.encode("utf-8"))
        # Should fail at one byte over
        with pytest.raises(JSONParsingError, match="exceeds maximum"):
            safe_json_loads(json_str, max_size=size - 1)

    def test_depth_limit_enforcement(self):
        """Test that deeply nested JSON is rejected."""
        # Create deeply nested structure
        data = {"level": 1}
        current = data
        for i in range(20):
            current["nested"] = {"level": i + 2}
            current = current["nested"]

        json_str = json.dumps(data)

        with pytest.raises(JSONParsingError, match="depth.*exceeds"):
            safe_json_loads(json_str, max_depth=10)

    def test_depth_limit_exact_boundary(self):
        """Test JSON at exact depth limit is accepted."""
        # Create structure at exact depth
        data = {"level": 1}
        current = data
        for i in range(4):
            current["nested"] = {"level": i + 2}
            current = current["nested"]

        json_str = json.dumps(data)
        # Depth is 5, should succeed with limit of 5
        result = safe_json_loads(json_str, max_depth=5)
        assert result["level"] == 1

    def test_depth_limit_one_over(self):
        """Test JSON one level over depth limit is rejected."""
        # Create structure one level over
        data = {"level": 1}
        current = data
        for i in range(5):
            current["nested"] = {"level": i + 2}
            current = current["nested"]

        json_str = json.dumps(data)
        # Depth is 6, should fail with limit of 5
        with pytest.raises(JSONParsingError, match="depth.*exceeds"):
            safe_json_loads(json_str, max_depth=5)

    def test_billion_laughs_style_attack(self):
        """Test protection against JSON bomb with large strings."""
        # Create many large strings (JSON bomb pattern)
        large_strings = [{"name": "x" * 100000} for _ in range(100)]
        json_str = json.dumps({"tags": large_strings})

        with pytest.raises(JSONParsingError, match="exceeds maximum"):
            safe_json_loads(json_str, max_size=1_000_000)

    def test_custom_size_limit(self):
        """Test custom size limit can be specified."""
        json_str = '{"data": "' + ("x" * 100) + '"}'
        # Should succeed with high limit
        result = safe_json_loads(json_str, max_size=10_000)
        assert "data" in result

    def test_custom_depth_limit(self):
        """Test custom depth limit can be specified."""
        data = {"a": {"b": {"c": 1}}}
        json_str = json.dumps(data)
        # Should succeed with depth of 3
        result = safe_json_loads(json_str, max_depth=3)
        assert result == data

    def test_unicode_size_calculation(self):
        """Test that size is calculated correctly for Unicode."""
        # Unicode characters may be multiple bytes
        json_str = '{"emoji": "😀😀😀"}'
        # Should use UTF-8 byte length, not character count
        size_bytes = len(json_str.encode("utf-8"))
        result = safe_json_loads(json_str, max_size=size_bytes)
        assert result["emoji"] == "😀😀😀"

    def test_array_at_root(self):
        """Test that arrays at root level are parsed correctly."""
        json_str = "[1, 2, 3]"
        result = safe_json_loads(json_str)
        assert result == [1, 2, 3]

    def test_primitive_at_root(self):
        """Test that primitives at root level are parsed correctly."""
        assert safe_json_loads('"string"') == "string"
        assert safe_json_loads("42") == 42
        assert safe_json_loads("true") is True
        assert safe_json_loads("null") is None


class TestExtractJsonFromText:
    """Tests for extract_json_from_text function."""

    def test_extract_json_with_prefix(self):
        """Test extracting JSON with text before it."""
        text = 'Here is the data: {"key": "value"}'
        result = extract_json_from_text(text)
        assert result == {"key": "value"}

    def test_extract_json_with_suffix(self):
        """Test extracting JSON with text after it."""
        text = '{"key": "value"} and some more text'
        result = extract_json_from_text(text)
        assert result == {"key": "value"}

    def test_extract_json_with_prefix_and_suffix(self):
        """Test extracting JSON with text before and after."""
        text = 'Before: {"key": "value"} After'
        result = extract_json_from_text(text)
        assert result == {"key": "value"}

    def test_extract_json_only(self):
        """Test extracting JSON with no surrounding text."""
        text = '{"key": "value"}'
        result = extract_json_from_text(text)
        assert result == {"key": "value"}

    def test_extract_complex_json_with_text(self):
        """Test extracting complex JSON from LLM-style response."""
        text = """
Here are the tags I found:

{
  "tags": [
    {"name": "python", "category": "topic"},
    {"name": "testing", "category": "concept"}
  ]
}

I hope this helps!
"""
        result = extract_json_from_text(text)
        assert "tags" in result
        assert len(result["tags"]) == 2

    def test_no_json_in_text(self):
        """Test that missing JSON raises JSONParsingError."""
        text = "This text has no JSON in it"
        with pytest.raises(JSONParsingError, match="No JSON object found"):
            extract_json_from_text(text)

    def test_only_opening_brace(self):
        """Test that incomplete JSON raises JSONParsingError."""
        text = "Here is incomplete: {"
        with pytest.raises(JSONParsingError, match="No JSON object found"):
            extract_json_from_text(text)

    def test_only_closing_brace(self):
        """Test that only closing brace raises JSONParsingError."""
        text = "Only closing: }"
        with pytest.raises(JSONParsingError, match="No JSON object found"):
            extract_json_from_text(text)

    def test_reversed_braces(self):
        """Test that reversed braces raises JSONParsingError."""
        text = "} reversed {"
        with pytest.raises(JSONParsingError, match="No JSON object found"):
            extract_json_from_text(text)

    def test_size_limit_applied(self):
        """Test that size limit is applied during extraction."""
        large_json = '{"data": "' + ("x" * 1_000_000) + '"}'
        text = f"Data: {large_json}"
        with pytest.raises(JSONParsingError, match="exceeds maximum"):
            extract_json_from_text(text, max_size=500_000)

    def test_depth_limit_applied(self):
        """Test that depth limit is applied during extraction."""
        # Create deeply nested structure
        data = {"level": 1}
        current = data
        for i in range(20):
            current["nested"] = {"level": i + 2}
            current = current["nested"]

        text = f"Here's the data: {json.dumps(data)}"
        with pytest.raises(JSONParsingError, match="depth.*exceeds"):
            extract_json_from_text(text, max_depth=10)

    def test_custom_limits(self):
        """Test that custom limits can be specified."""
        text = 'Data: {"key": "value"}'
        result = extract_json_from_text(text, max_size=1000, max_depth=5)
        assert result == {"key": "value"}

    def test_malformed_json_in_text(self):
        """Test that malformed JSON in text raises JSONParsingError."""
        text = 'Here is bad JSON: {"key": }'
        with pytest.raises(JSONParsingError, match="Invalid JSON"):
            extract_json_from_text(text)


class TestSecurityScenarios:
    """Tests for specific security scenarios."""

    def test_protection_against_memory_exhaustion(self):
        """Test protection against memory exhaustion attacks."""
        # Attempt to create very large JSON
        attack_json = '{"attack": "' + ("A" * 50_000_000) + '"}'

        # Should be rejected before memory allocation
        with pytest.raises(JSONParsingError, match="exceeds maximum"):
            safe_json_loads(attack_json)

    def test_protection_against_stack_overflow(self):
        """Test protection against stack overflow attacks."""
        # Create deep nesting (50 levels - enough to be malicious but not hit Python's recursion limit during testing)
        data = {"level": 0}
        current = data
        for i in range(49):
            current["nested"] = {"level": i + 1}
            current = current["nested"]

        json_str = json.dumps(data)

        # Should be rejected due to depth limit (depth is 50, limit is 10)
        with pytest.raises(JSONParsingError, match="depth.*exceeds"):
            safe_json_loads(json_str, max_depth=10)

    def test_reasonable_limits_for_tags(self):
        """Test that reasonable tag responses work within limits."""
        # Simulate realistic tag response (100 tags)
        tags = [{"name": f"tag-{i}", "category": "topic", "confidence": 0.8} for i in range(100)]
        data = {"tags": tags}
        json_str = json.dumps(data)

        # Should succeed with 1MB limit (typical for tags)
        result = safe_json_loads(json_str, max_size=1_000_000, max_depth=5)
        assert len(result["tags"]) == 100

    def test_reasonable_limits_for_extraction(self):
        """Test that reasonable extraction results work within limits."""
        # Simulate realistic extraction result
        data = {
            "summary": "A long summary... " * 1000,
            "key_points": [f"Point {i}" for i in range(50)],
            "quotes": [
                {"text": f"Quote {i}", "speaker": "Guest", "timestamp": "00:00:00"}
                for i in range(20)
            ],
        }
        json_str = json.dumps(data)

        # Should succeed with 5MB limit (typical for extraction)
        result = safe_json_loads(json_str, max_size=5_000_000, max_depth=10)
        assert len(result["quotes"]) == 20

    def test_malicious_llm_response_simulation(self):
        """Test protection against a simulated malicious LLM response."""
        # Simulate prompt injection causing LLM to return massive JSON
        malicious_text = """
I will now return the tags as requested:

{
  "tags": [
"""
        # Add 1000 large tags
        for i in range(1000):
            malicious_text += f'    {{"name": "{"x" * 10000}", "category": "topic"}},\n'

        malicious_text += "  ]\n}"

        # Should be rejected due to size limit
        with pytest.raises(JSONParsingError, match="exceeds maximum"):
            extract_json_from_text(malicious_text, max_size=1_000_000)


class TestErrorMessages:
    """Tests for error message quality."""

    def test_size_error_message_contains_details(self):
        """Test that size limit error contains useful information."""
        large_json = '{"data": "' + ("x" * 1_000_000) + '"}'
        with pytest.raises(JSONParsingError) as exc_info:
            safe_json_loads(large_json, max_size=500_000)

        error_msg = str(exc_info.value)
        assert "exceeds maximum" in error_msg
        assert "bytes" in error_msg
        assert "malicious or malformed" in error_msg

    def test_depth_error_message_contains_details(self):
        """Test that depth limit error contains useful information."""
        data = {"a": {"b": {"c": {"d": {"e": 1}}}}}
        json_str = json.dumps(data)

        with pytest.raises(JSONParsingError) as exc_info:
            safe_json_loads(json_str, max_depth=3)

        error_msg = str(exc_info.value)
        assert "depth" in error_msg.lower()
        assert "exceeds maximum" in error_msg
        assert "malicious or malformed" in error_msg

    def test_invalid_json_error_message(self):
        """Test that invalid JSON error is clear."""
        with pytest.raises(JSONParsingError) as exc_info:
            safe_json_loads('{"invalid":')

        error_msg = str(exc_info.value)
        assert "Invalid JSON" in error_msg

    def test_no_json_found_error_message(self):
        """Test that missing JSON error is clear."""
        with pytest.raises(JSONParsingError) as exc_info:
            extract_json_from_text("No JSON here")

        error_msg = str(exc_info.value)
        assert "No JSON object found" in error_msg
