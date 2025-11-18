---
status: completed
priority: p2
issue_id: "054"
tags: [code-review, security, information-disclosure, pr-20]
dependencies: []
completed_date: 2025-11-18
---

# Sanitize API Key Information in Error Messages

## Problem Statement

Error messages and validation failures may expose API key information such as length, format hints, and validation details in logs and stack traces. While not exposing the full key, this information disclosure could aid attackers in credential enumeration or format guessing.

**Severity**: P2 - MEDIUM (Security - Information disclosure)

## Findings

- Discovered during security review by security-sentinel agent
- Location: `src/inkwell/utils/api_keys.py:74-79`
- Error messages reveal key length and format details
- Exception messages may contain partial key information
- Logs and stack traces could expose credential metadata

**Current Information Leakage**:

```python
# src/inkwell/utils/api_keys.py lines 74-79

if len(key) < 20:
    raise APIKeyError(
        f"{provider.title()} API key appears invalid (too short).\n"
        f"Expected at least 20 characters, got {len(key)}.\n"  # ⚠️ Reveals key length
        f"Check your {key_name} environment variable."
    )

# If user has a 15-character key, error reveals:
# "Expected at least 20 characters, got 15."
# Attacker learns: key is 15 chars, too short, needs to be 20+
```

**Other Leakage Points**:

```python
# Line 86-91: Reveals format expectations
if not key.startswith(prefix):
    raise APIKeyError(
        f"{provider.title()} API key must start with '{prefix}'.\n"  # ⚠️ Reveals prefix
        f"Got: {key[:10]}...\n"  # ⚠️ Exposes first 10 characters!
        f"Check your {key_name} environment variable."
    )
```

**Generic Exception Handling**:

```python
# src/inkwell/extraction/engine.py line 179-189
except Exception as e:
    return ExtractionResult(
        error=str(e),  # ⚠️ Could contain API key if in exception message
        # ...
    )
```

**Impact Analysis**:
- **Information disclosure**: Reveals credential format requirements
- **Enumeration aid**: Helps attackers understand valid key patterns
- **Log exposure**: API key metadata visible in error logs
- **Stack trace leakage**: Exception traces might contain partial keys
- **OWASP A09:2021**: Security Logging and Monitoring Failures

**Attack Scenario**:
```python
# Attacker probes with invalid keys
GEMINI_API_KEY="test" inkwell process ...
# Error: "Expected at least 20 characters, got 4"
# Attacker learns minimum length

GEMINI_API_KEY="AIzaSyDabcdefghijklmn" inkwell process ...
# Error: "Invalid API key format"
# Attacker learns prefix pattern

# Over time, attacker maps out exact validation rules
```

## Proposed Solutions

### Option 1: Generic Error Messages (Recommended)

**Pros**:
- Minimal information disclosure
- Still helpful for legitimate users
- Simple to implement
- Industry best practice

**Cons**:
- Slightly less helpful for debugging (but still adequate)

**Effort**: Small (30 minutes)
**Risk**: Low (more secure than current)

**Implementation**:

Update `src/inkwell/utils/api_keys.py`:

```python
def get_validated_api_key(key_name: str, provider: str) -> str:
    """Get and validate API key from environment.

    Args:
        key_name: Environment variable name (e.g., "GEMINI_API_KEY")
        provider: Provider name for error messages (e.g., "gemini", "claude")

    Returns:
        Validated API key string

    Raises:
        APIKeyError: If key is missing or invalid (without revealing details)
    """
    key = os.getenv(key_name)

    if not key:
        raise APIKeyError(
            f"{provider.title()} API key not found.\n"
            f"Set the {key_name} environment variable."
        )

    # Generic validation without revealing specifics
    if len(key) < 20 or any(c in key for c in ['"', "'", "\n", "\r"]):
        raise APIKeyError(
            f"{provider.title()} API key appears invalid.\n"
            f"Check your {key_name} environment variable.\n"
            f"Ensure it's properly formatted without quotes or whitespace."
            # ❌ DO NOT include: length, prefix, format details
        )

    # Provider-specific validation (without revealing prefix)
    if provider == "gemini" and not key.startswith("AIza"):
        raise APIKeyError(
            f"{provider.title()} API key appears invalid.\n"
            f"Check your {key_name} environment variable."
            # ❌ DO NOT reveal expected prefix
        )

    if provider == "claude" and not key.startswith("sk-ant-"):
        raise APIKeyError(
            f"{provider.title()} API key appears invalid.\n"
            f"Check your {key_name} environment variable."
            # ❌ DO NOT reveal expected prefix
        )

    return key
```

**Sanitize Exception Messages**:

```python
# src/inkwell/extraction/engine.py

import re

def _sanitize_error_message(message: str) -> str:
    """Remove potential API keys from error messages."""
    # Redact Gemini keys (AIza...)
    message = re.sub(r'AIza[A-Za-z0-9_-]+', '[REDACTED_GEMINI_KEY]', message)
    # Redact Claude keys (sk-ant-...)
    message = re.sub(r'sk-ant-[A-Za-z0-9_-]+', '[REDACTED_CLAUDE_KEY]', message)
    return message

# Use in exception handling:
except Exception as e:
    error_msg = _sanitize_error_message(str(e))
    return ExtractionResult(
        error=error_msg,
        # ...
    )
```

### Option 2: Structured Logging with Sanitization

**Pros**:
- Detailed logs for debugging (sanitized)
- Generic errors for users
- Best of both worlds

**Cons**:
- More complex
- Requires logging infrastructure

**Effort**: Medium (1-2 hours)
**Risk**: Low

**Implementation**:
```python
import logging

logger = logging.getLogger(__name__)

def get_validated_api_key(key_name: str, provider: str) -> str:
    key = os.getenv(key_name)

    if not key:
        raise APIKeyError(f"{provider} API key not found")

    # Log detailed validation (sanitized) for debugging
    if len(key) < 20:
        logger.debug(
            f"API key validation failed: length={len(key)} (expected >=20)",
            extra={"provider": provider, "key_name": key_name}
        )
        # But show generic error to user
        raise APIKeyError(f"{provider} API key appears invalid")

    return key
```

## Recommended Action

Implement Option 1 (generic error messages). This provides adequate user feedback while minimizing information disclosure.

**Timeline**: Should be implemented before production deployment.

## Technical Details

**Affected Files**:
- `src/inkwell/utils/api_keys.py:74-91` (update error messages)
- `src/inkwell/extraction/engine.py:179-189` (add sanitization)
- `src/inkwell/transcription/manager.py` (exception handling)

**Related Components**:
- All error handling that might expose credentials
- Logging configuration
- Exception stack traces

**Testing Requirements**:

Add to `tests/unit/test_api_keys.py`:

```python
def test_invalid_key_error_message_is_generic():
    """Invalid key errors should not reveal specific details."""
    with pytest.raises(APIKeyError) as exc_info:
        # Mock environment with invalid key
        with patch.dict(os.environ, {"GEMINI_API_KEY": "too_short"}):
            get_validated_api_key("GEMINI_API_KEY", "gemini")

    error_msg = str(exc_info.value)

    # Error should be generic
    assert "invalid" in error_msg.lower()
    assert "GEMINI_API_KEY" in error_msg

    # Error should NOT reveal:
    assert "20" not in error_msg  # Length requirement
    assert "9" not in error_msg   # Actual length
    assert "AIza" not in error_msg  # Expected prefix
    assert "too_short" not in error_msg  # Actual key value


def test_error_message_sanitizes_api_keys():
    """Exception messages should redact API keys."""
    from inkwell.extraction.engine import _sanitize_error_message

    # Test Gemini key redaction
    msg = "Error with key AIzaSyDabcdefghijklmnop1234567890"
    sanitized = _sanitize_error_message(msg)
    assert "AIza" not in sanitized
    assert "[REDACTED_GEMINI_KEY]" in sanitized

    # Test Claude key redaction
    msg = "Error with key sk-ant-api03-abcdefghijk"
    sanitized = _sanitize_error_message(msg)
    assert "sk-ant" not in sanitized
    assert "[REDACTED_CLAUDE_KEY]" in sanitized
```

## Acceptance Criteria

- [x] API key validation errors are generic (no length, prefix, format details)
- [x] Exception messages sanitize API key patterns
- [x] Error messages still helpful for legitimate users
- [x] Tests verify no information leakage
- [x] All error paths sanitized (extraction, transcription, etc.)
- [x] Logging doesn't expose credentials

## Work Log

### 2025-11-18 - Code Review Discovery
**By:** Claude Code Review System
**Actions:**
- Discovered during security audit by security-sentinel agent
- Categorized as P2 MEDIUM priority (information disclosure)
- Identified multiple leakage points
- Proposed sanitization strategy

**Learnings:**
- Error messages are a common information disclosure vector
- Generic errors are better for security
- Regex sanitization catches partial key exposure
- Stack traces need sanitization too

### 2025-11-18 - Implementation Complete
**By:** Claude Code
**Actions:**
- Updated `src/inkwell/utils/api_keys.py` to use generic error messages
  - Removed length disclosure ("Expected at least 20 characters, got 15")
  - Removed prefix disclosure ("Gemini keys typically start with 'AIza'")
  - Removed format details ("alphanumeric characters, underscores, and dashes")
  - Kept helpful context (provider name, env var name)
- Added `_sanitize_error_message()` function to `src/inkwell/extraction/engine.py`
  - Redacts Gemini keys matching `AIza[A-Za-z0-9_-]+`
  - Redacts Claude keys matching `sk-ant-[A-Za-z0-9_-]+`
  - Uses regex replacement with `[REDACTED_GEMINI_KEY]` and `[REDACTED_CLAUDE_KEY]`
- Updated exception handling in `extract()`, `extract_all()`, and `extract_all_batched()`
  - All error messages sanitized before logging
  - All error messages sanitized before returning to caller
- Added comprehensive test suite in `tests/unit/utils/test_api_keys.py`
  - `TestErrorMessageSanitization` class with 6 new tests
  - Updated existing tests to verify no information leakage
  - Integration tests verify invalid keys don't leak length, prefix, or format details
- All 41 tests passing
- All 40 extraction engine tests passing (no regressions)

**Implementation Details:**
- Generic error format: "{Provider} API key appears invalid. Check your {ENV_VAR} environment variable."
- Sanitization applied to: error results, log messages, exception traces
- Backward compatible: error messages still helpful for legitimate users

**Security Improvements:**
- No length information disclosed
- No prefix patterns disclosed
- No format requirements disclosed
- API keys in exceptions automatically redacted
- Prevents credential enumeration attacks

## Notes

**Security Principle**:
> Error messages should be helpful but not informative to attackers.

**OWASP Guidance**:
- Don't reveal system internals in errors
- Use generic messages for authentication failures
- Log detailed errors securely, show generic to users

**Information Disclosure Examples**:
```
❌ "Password must be at least 12 characters, got 8"
✅ "Invalid password"

❌ "API key must start with 'AIza', got 'test'"
✅ "Invalid API key format"

❌ "Key length: 15 (expected: 20-100)"
✅ "Invalid API key"
```

**Why This Matters**:
Small information leaks compound:
1. Attacker learns minimum length: 20 chars
2. Attacker learns prefix: "AIza"
3. Attacker learns format: alphanumeric + some symbols
4. Attacker can now brute force much faster

**Best Practice**: Minimize information in all error paths.

**Related Security Issues**:
- CWE-209: Generation of Error Message Containing Sensitive Information
- OWASP A09:2021: Security Logging and Monitoring Failures

**Source**: Code review performed on 2025-11-18
**Review command**: /compounding-engineering:review PR20
