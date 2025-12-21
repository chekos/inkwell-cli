"""Tests for API key validation."""

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
        """Test that short key raises APIKeyError with generic message."""
        with pytest.raises(APIKeyError, match="invalid"):
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
        """Test that Gemini key with wrong prefix raises APIKeyError with generic message."""
        with pytest.raises(APIKeyError, match="invalid"):
            validate_api_key("sk-ant-" + "X" * 32, "gemini", "GOOGLE_API_KEY")

    def test_claude_key_wrong_prefix(self):
        """Test that Claude key with wrong prefix raises APIKeyError with generic message."""
        with pytest.raises(APIKeyError, match="invalid"):
            validate_api_key("AIzaSyD" + "X" * 32, "claude", "ANTHROPIC_API_KEY")

    def test_gemini_key_with_invalid_characters(self):
        """Test that Gemini key with invalid characters raises APIKeyError with generic message."""
        with pytest.raises(APIKeyError, match="invalid"):
            validate_api_key("AIzaSyD" + "!" * 32, "gemini", "GOOGLE_API_KEY")

    def test_claude_key_with_invalid_characters(self):
        """Test that Claude key with invalid characters raises APIKeyError with generic message."""
        with pytest.raises(APIKeyError, match="invalid"):
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
        """Test that invalid key raises APIKeyError with generic message."""
        monkeypatch.setenv("GOOGLE_API_KEY", "invalid")

        with pytest.raises(APIKeyError, match="invalid"):
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

    def test_short_key_error_is_generic(self):
        """Test that short key error does not reveal length details (security fix)."""
        with pytest.raises(APIKeyError) as exc_info:
            validate_api_key("short", "gemini", "GOOGLE_API_KEY")

        error_msg = str(exc_info.value)
        assert "invalid" in error_msg.lower()
        assert "GOOGLE_API_KEY" in error_msg

        # SECURITY: Error should NOT reveal specific length details
        assert "5" not in error_msg  # Actual length should not be exposed
        assert "20" not in error_msg  # Minimum length should not be exposed
        assert "too short" not in error_msg  # Specific validation reason should not be exposed

    def test_invalid_format_error_is_generic(self):
        """Test that invalid format error does not reveal prefix details (security fix)."""
        with pytest.raises(APIKeyError) as exc_info:
            validate_api_key("X" * 40, "gemini", "GOOGLE_API_KEY")

        error_msg = str(exc_info.value)
        assert "invalid" in error_msg.lower()
        assert "GOOGLE_API_KEY" in error_msg

        # SECURITY: Error should NOT reveal expected prefix or format
        assert "AIza" not in error_msg  # Expected prefix should not be exposed
        assert "start with" not in error_msg  # Format hint should not be exposed

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


class TestErrorMessageSanitization:
    """Tests for API key sanitization in error messages (TODO #054)."""

    def test_sanitize_gemini_key_in_error_message(self):
        """Test that Gemini API keys are redacted from error messages."""
        from inkwell.extraction.engine import _sanitize_error_message

        # Test Gemini key redaction
        msg = "Error with key AIzaSyDabcdefghijklmnop1234567890"
        sanitized = _sanitize_error_message(msg)

        # Key should be redacted
        assert "AIza" not in sanitized
        assert "[REDACTED_GEMINI_KEY]" in sanitized
        assert "Error with key" in sanitized

    def test_sanitize_claude_key_in_error_message(self):
        """Test that Claude API keys are redacted from error messages."""
        from inkwell.extraction.engine import _sanitize_error_message

        # Test Claude key redaction
        msg = "Error with key sk-ant-api03-abcdefghijklmnopqrstuvwxyz"
        sanitized = _sanitize_error_message(msg)

        # Key should be redacted
        assert "sk-ant" not in sanitized
        assert "[REDACTED_CLAUDE_KEY]" in sanitized
        assert "Error with key" in sanitized

    def test_sanitize_multiple_keys_in_error_message(self):
        """Test that multiple API keys are redacted from error messages."""
        from inkwell.extraction.engine import _sanitize_error_message

        # Test multiple keys
        msg = "Failed: AIzaSyD123456 and sk-ant-api03-abcdef both invalid"
        sanitized = _sanitize_error_message(msg)

        # Both keys should be redacted
        assert "AIza" not in sanitized
        assert "sk-ant" not in sanitized
        assert "[REDACTED_GEMINI_KEY]" in sanitized
        assert "[REDACTED_CLAUDE_KEY]" in sanitized
        assert "Failed:" in sanitized
        assert "both invalid" in sanitized

    def test_sanitize_preserves_non_key_content(self):
        """Test that sanitization preserves non-key content."""
        from inkwell.extraction.engine import _sanitize_error_message

        msg = "Connection failed: timeout after 30 seconds"
        sanitized = _sanitize_error_message(msg)

        # Content should be unchanged
        assert sanitized == msg

    def test_sanitize_handles_partial_keys(self):
        """Test that partial key patterns matching the regex are also redacted."""
        from inkwell.extraction.engine import _sanitize_error_message

        # Test with partial keys that match the pattern
        msg = "Invalid key AIzaSy (too short)"
        sanitized = _sanitize_error_message(msg)

        # Partial keys that match the pattern ARE redacted (intentional)
        # The regex AIza[A-Za-z0-9_-]+ will match "AIzaSy"
        assert "[REDACTED_GEMINI_KEY]" in sanitized
        assert "AIza" not in sanitized

        # Test with a string that doesn't match the pattern
        msg2 = "Invalid key AIz (incomplete prefix)"
        sanitized2 = _sanitize_error_message(msg2)
        # This should NOT be redacted (doesn't match AIza pattern)
        assert sanitized2 == msg2

    def test_error_messages_dont_leak_key_details(self):
        """Integration test: verify invalid keys don't leak details."""
        # Test with various invalid keys
        test_cases = [
            ("too_short", "gemini", "GEMINI_API_KEY"),
            ("X" * 40, "gemini", "GEMINI_API_KEY"),
            ("AIzaSyD" + "!" * 32, "gemini", "GEMINI_API_KEY"),
            ("short", "claude", "ANTHROPIC_API_KEY"),
            ("Y" * 40, "claude", "ANTHROPIC_API_KEY"),
        ]

        for key, provider, env_var in test_cases:
            with pytest.raises(APIKeyError) as exc_info:
                validate_api_key(key, provider, env_var)

            error_msg = str(exc_info.value)

            # Error should be helpful but generic
            assert provider.title() in error_msg
            assert env_var in error_msg

            # SECURITY: Error should NOT reveal:
            # 1. Actual key value
            assert (
                key not in error_msg or len(key) < 10
            )  # Short test strings might appear in generic messages

            # 2. Specific length requirements
            assert "20" not in error_msg
            assert len(key) not in [int(s) for s in error_msg.split() if s.isdigit()]

            # 3. Specific format requirements (prefix patterns)
            if provider == "gemini":
                assert "AIza" not in error_msg
            elif provider == "claude":
                assert "sk-ant" not in error_msg

            # 4. Character requirements
            assert "alphanumeric" not in error_msg.lower()
            assert "underscore" not in error_msg.lower()
            assert "dash" not in error_msg.lower()
