"""Tests for API key validation."""

import os

import pytest

from inkwell.utils.api_keys import APIKeyError, get_validated_api_key, validate_api_key


class TestValidateAPIKey:
    """Tests for validate_api_key function."""

    def test_valid_gemini_key(self):
        """Test validation of valid Gemini API key."""
        valid_key = "AIzaSyD" + "X" * 32  # Valid format
        result = validate_api_key(valid_key, "gemini", "GOOGLE_API_KEY")
        assert result == valid_key

    def test_valid_claude_key(self):
        """Test validation of valid Claude API key."""
        valid_key = "sk-ant-api03-" + "X" * 32  # Valid format
        result = validate_api_key(valid_key, "claude", "ANTHROPIC_API_KEY")
        assert result == valid_key

    def test_none_key(self):
        """Test that None key raises APIKeyError."""
        with pytest.raises(APIKeyError, match="API key is required"):
            validate_api_key(None, "gemini", "GOOGLE_API_KEY")

    def test_empty_key(self):
        """Test that empty key raises APIKeyError."""
        with pytest.raises(APIKeyError, match="API key is required"):
            validate_api_key("", "gemini", "GOOGLE_API_KEY")

    def test_whitespace_only_key(self):
        """Test that whitespace-only key raises APIKeyError."""
        with pytest.raises(APIKeyError, match="API key is required"):
            validate_api_key("   ", "gemini", "GOOGLE_API_KEY")

    def test_key_with_leading_trailing_whitespace(self):
        """Test that key is stripped of whitespace."""
        key = "  AIzaSyD" + "X" * 32 + "  "
        result = validate_api_key(key, "gemini", "GOOGLE_API_KEY")
        assert result == key.strip()
        assert not result.startswith(" ")
        assert not result.endswith(" ")

    def test_too_short_key(self):
        """Test that short key raises APIKeyError."""
        with pytest.raises(APIKeyError, match="too short"):
            validate_api_key("short", "gemini", "GOOGLE_API_KEY")

    def test_key_with_newline(self):
        """Test that key with newline raises APIKeyError."""
        key = "AIzaSyD" + "X" * 32 + "\n"
        with pytest.raises(APIKeyError, match="invalid characters"):
            validate_api_key(key, "gemini", "GOOGLE_API_KEY")

    def test_key_with_carriage_return(self):
        """Test that key with carriage return raises APIKeyError."""
        key = "AIzaSyD" + "X" * 32 + "\r"
        with pytest.raises(APIKeyError, match="invalid characters"):
            validate_api_key(key, "gemini", "GOOGLE_API_KEY")

    def test_key_with_null_character(self):
        """Test that key with null character raises APIKeyError."""
        key = "AIzaSyD" + "X" * 32 + "\0"
        with pytest.raises(APIKeyError, match="invalid characters"):
            validate_api_key(key, "gemini", "GOOGLE_API_KEY")

    def test_key_with_tab(self):
        """Test that key with tab raises APIKeyError."""
        key = "AIzaSyD" + "X" * 32 + "\t"
        with pytest.raises(APIKeyError, match="invalid characters"):
            validate_api_key(key, "gemini", "GOOGLE_API_KEY")

    def test_gemini_key_wrong_prefix(self):
        """Test that Gemini key with wrong prefix raises APIKeyError."""
        with pytest.raises(APIKeyError, match="format appears invalid"):
            validate_api_key("sk-ant-" + "X" * 32, "gemini", "GOOGLE_API_KEY")

    def test_claude_key_wrong_prefix(self):
        """Test that Claude key with wrong prefix raises APIKeyError."""
        with pytest.raises(APIKeyError, match="format appears invalid"):
            validate_api_key("AIzaSyD" + "X" * 32, "claude", "ANTHROPIC_API_KEY")

    def test_gemini_key_with_invalid_characters(self):
        """Test that Gemini key with invalid characters raises APIKeyError."""
        with pytest.raises(APIKeyError, match="format appears invalid"):
            validate_api_key("AIzaSyD" + "!" * 32, "gemini", "GOOGLE_API_KEY")

    def test_claude_key_with_invalid_characters(self):
        """Test that Claude key with invalid characters raises APIKeyError."""
        with pytest.raises(APIKeyError, match="format appears invalid"):
            validate_api_key("sk-ant-api03-" + "!" * 32, "claude", "ANTHROPIC_API_KEY")

    def test_double_quoted_key(self):
        """Test that double-quoted key raises APIKeyError."""
        key = '"AIzaSyD' + "X" * 32 + '"'
        with pytest.raises(APIKeyError, match="should not be quoted"):
            validate_api_key(key, "gemini", "GOOGLE_API_KEY")

    def test_single_quoted_key(self):
        """Test that single-quoted key raises APIKeyError."""
        key = "'AIzaSyD" + "X" * 32 + "'"
        with pytest.raises(APIKeyError, match="should not be quoted"):
            validate_api_key(key, "gemini", "GOOGLE_API_KEY")

    def test_youtube_provider_no_format_check(self):
        """Test that youtube provider doesn't enforce specific format."""
        # YouTube keys don't have strict format requirements in our validation
        key = "Y" * 30  # Just needs to be long enough
        result = validate_api_key(key, "youtube", "YOUTUBE_API_KEY")
        assert result == key

    def test_error_message_includes_provider(self):
        """Test that error messages include provider name."""
        with pytest.raises(APIKeyError, match="Gemini"):
            validate_api_key(None, "gemini", "GOOGLE_API_KEY")

        with pytest.raises(APIKeyError, match="Claude"):
            validate_api_key(None, "claude", "ANTHROPIC_API_KEY")

    def test_error_message_includes_env_var(self):
        """Test that error messages include environment variable name."""
        with pytest.raises(APIKeyError, match="GOOGLE_API_KEY"):
            validate_api_key(None, "gemini", "GOOGLE_API_KEY")

        with pytest.raises(APIKeyError, match="ANTHROPIC_API_KEY"):
            validate_api_key(None, "claude", "ANTHROPIC_API_KEY")

    def test_error_message_includes_setup_instructions(self):
        """Test that error messages include setup instructions."""
        with pytest.raises(APIKeyError, match="export"):
            validate_api_key(None, "gemini", "GOOGLE_API_KEY")


class TestGetValidatedAPIKey:
    """Tests for get_validated_api_key function."""

    def test_valid_key_from_environment(self, monkeypatch):
        """Test getting valid key from environment."""
        valid_key = "AIzaSyD" + "X" * 32
        monkeypatch.setenv("GOOGLE_API_KEY", valid_key)

        result = get_validated_api_key("GOOGLE_API_KEY", "gemini")
        assert result == valid_key

    def test_missing_key_from_environment(self, monkeypatch):
        """Test that missing key raises APIKeyError."""
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

        with pytest.raises(APIKeyError, match="API key is required"):
            get_validated_api_key("GOOGLE_API_KEY", "gemini")

    def test_invalid_key_from_environment(self, monkeypatch):
        """Test that invalid key raises APIKeyError."""
        monkeypatch.setenv("GOOGLE_API_KEY", "invalid")

        with pytest.raises(APIKeyError, match="too short"):
            get_validated_api_key("GOOGLE_API_KEY", "gemini")

    def test_key_with_whitespace_from_environment(self, monkeypatch):
        """Test that key is stripped of whitespace."""
        valid_key = "AIzaSyD" + "X" * 32
        monkeypatch.setenv("GOOGLE_API_KEY", f"  {valid_key}  ")

        result = get_validated_api_key("GOOGLE_API_KEY", "gemini")
        assert result == valid_key

    def test_quoted_key_from_environment(self, monkeypatch):
        """Test that quoted key raises APIKeyError."""
        valid_key = "AIzaSyD" + "X" * 32
        monkeypatch.setenv("GOOGLE_API_KEY", f'"{valid_key}"')

        with pytest.raises(APIKeyError, match="should not be quoted"):
            get_validated_api_key("GOOGLE_API_KEY", "gemini")


class TestAPIKeyErrorMessages:
    """Tests for API key error message quality."""

    def test_missing_key_error_is_helpful(self):
        """Test that missing key error provides helpful information."""
        with pytest.raises(APIKeyError) as exc_info:
            validate_api_key(None, "gemini", "GOOGLE_API_KEY")

        error_msg = str(exc_info.value)
        assert "Gemini" in error_msg
        assert "GOOGLE_API_KEY" in error_msg
        assert "export" in error_msg
        assert "your-api-key-here" in error_msg

    def test_short_key_error_shows_length(self):
        """Test that short key error shows actual length."""
        with pytest.raises(APIKeyError) as exc_info:
            validate_api_key("short", "gemini", "GOOGLE_API_KEY")

        error_msg = str(exc_info.value)
        assert "too short" in error_msg
        assert "5" in error_msg  # Actual length
        assert "20" in error_msg  # Minimum length

    def test_invalid_format_error_explains_format(self):
        """Test that invalid format error explains expected format."""
        with pytest.raises(APIKeyError) as exc_info:
            validate_api_key("X" * 40, "gemini", "GOOGLE_API_KEY")

        error_msg = str(exc_info.value)
        assert "format appears invalid" in error_msg
        assert "AIza" in error_msg  # Expected prefix

    def test_quoted_key_error_shows_fix(self):
        """Test that quoted key error shows how to fix."""
        key = '"AIzaSyD' + "X" * 32 + '"'
        with pytest.raises(APIKeyError) as exc_info:
            validate_api_key(key, "gemini", "GOOGLE_API_KEY")

        error_msg = str(exc_info.value)
        assert "should not be quoted" in error_msg
        assert "Remove quotes" in error_msg


class TestAPIKeyValidationIntegration:
    """Integration tests for API key validation in real scenarios."""

    def test_common_user_mistake_newline(self):
        """Test detection of copy-paste with newline."""
        # Simulate user copying key with accidental newline
        key = "AIzaSyD" + "X" * 32 + "\n"

        with pytest.raises(APIKeyError, match="invalid characters"):
            validate_api_key(key, "gemini", "GOOGLE_API_KEY")

    def test_common_user_mistake_shell_quotes(self):
        """Test detection of shell quotes in value."""
        # Simulate user setting: export KEY="value" where quotes get included
        key = '"AIzaSyD' + "X" * 32 + '"'

        with pytest.raises(APIKeyError, match="should not be quoted"):
            validate_api_key(key, "gemini", "GOOGLE_API_KEY")

    def test_common_user_mistake_trailing_space(self):
        """Test that trailing space is handled gracefully."""
        # Simulate user copy-paste with trailing space
        key = "AIzaSyD" + "X" * 32 + " "

        # Should succeed after stripping
        result = validate_api_key(key, "gemini", "GOOGLE_API_KEY")
        assert result == key.strip()

    def test_realistic_gemini_key(self):
        """Test with realistic Gemini API key format."""
        # Based on actual Gemini key format
        key = "AIzaSyDXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"

        result = validate_api_key(key, "gemini", "GOOGLE_API_KEY")
        assert result == key

    def test_realistic_claude_key(self):
        """Test with realistic Claude API key format."""
        # Based on actual Claude key format
        key = "sk-ant-api03-XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"

        result = validate_api_key(key, "claude", "ANTHROPIC_API_KEY")
        assert result == key
