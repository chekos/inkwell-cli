# ADR-027: Retry and Error Handling Strategy

**Date**: 2025-11-09
**Status**: Accepted
**Context**: Phase 5 Unit 1 - Research & Architecture
**Related**: [Research: Error Handling Best Practices](../research/error-handling-best-practices.md)

## Context

Inkwell makes multiple external API calls that can fail due to:
- Network timeouts and connectivity issues
- API rate limiting (429 responses)
- Temporary service unavailability (500, 502, 503, 504)
- Intermittent failures

Current implementation has **no retry logic**, meaning transient failures require users to manually re-run commands. This results in poor user experience and wasted time.

We need a robust error handling system that:
1. Automatically retries transient failures
2. Fails fast on permanent errors
3. Provides helpful error messages
4. Shows progress during retries
5. Respects API rate limits

## Research Summary

See [Research: Error Handling Best Practices](../research/error-handling-best-practices.md) for detailed findings.

**Key findings:**
1. Exponential backoff with jitter is industry standard
2. Tenacity is the best Python retry library
3. Must classify errors: retry transient, fail on permanent
4. User feedback during retries improves experience
5. Respect `Retry-After` headers for rate limiting

## Decision

We will implement a **comprehensive retry and error handling system** with these components:

### 1. Retry Strategy: Exponential Backoff with Equal Jitter

**Implementation:**
```python
from tenacity import (
    retry,
    wait_random_exponential,
    stop_after_attempt,
    retry_if_exception_type
)

@retry(
    wait=wait_random_exponential(multiplier=1, min=1, max=60),
    stop=stop_after_attempt(3),
    retry=retry_if_exception_type((ConnectionError, TimeoutError, RateLimitError)),
    reraise=True
)
async def api_call():
    # API logic
    pass
```

**Parameters:**
- **Multiplier:** 1 second base
- **Min wait:** 1 second
- **Max wait:** 10 seconds (reduced from 60s for better UX - see TODO #004)
- **Max attempts:** 3 (configurable via config)
- **Jitter:** ±25% jitter (base ± random(0.25 * base))

**Wait times:**
- Attempt 1: 0s (initial)
- Attempt 2: 1s ± 25% = 0.75-1.25s
- Attempt 3: 2s ± 25% = 1.5-2.5s
- Attempt 4: 4s ± 25% = 3-5s
- **Total worst case:** ~9s (vs 150s with old config)

**Rationale:** ±25% jitter is industry standard (AWS, Google) and prevents thundering herd. 10s max wait provides fast user experience while allowing transient issues to resolve.

### 2. Error Classification

**Errors to Retry (Transient):**

| Error Type | HTTP Status | Retry? | Max Attempts |
|------------|-------------|--------|--------------|
| Network timeout | - | ✅ Yes | 3 |
| Connection error | - | ✅ Yes | 3 |
| Request timeout | 408 | ✅ Yes | 3 |
| Rate limit | 429 | ✅ Yes | 3 (with Retry-After) |
| Internal server error | 500 | ✅ Yes | 3 |
| Bad gateway | 502 | ✅ Yes | 3 |
| Service unavailable | 503 | ✅ Yes | 3 |
| Gateway timeout | 504 | ✅ Yes | 3 |

**Errors NOT to Retry (Permanent):**

| Error Type | HTTP Status | Retry? | User Action |
|------------|-------------|--------|-------------|
| Bad request | 400 | ❌ No | Fix input |
| Unauthorized | 401 | ❌ No | Check API key |
| Forbidden | 403 | ❌ No | Check permissions |
| Not found | 404 | ❌ No | Check URL |
| Unprocessable entity | 422 | ❌ No | Fix data format |

### 3. Retry Utility Module

**Location:** `src/inkwell/utils/retry.py`

```python
"""Retry utilities with exponential backoff."""

import asyncio
import logging
from typing import Callable, TypeVar, Optional
from functools import wraps

from tenacity import (
    retry,
    wait_random_exponential,
    stop_after_attempt,
    retry_if_exception_type,
    before_sleep_log,
    RetryCallState
)
from rich.console import Console

from inkwell.utils.errors import (
    TransientError,
    RateLimitError,
    NetworkError
)

logger = logging.getLogger(__name__)
console = Console()

T = TypeVar('T')

def with_retry(
    max_attempts: int = 3,
    max_wait: int = 60,
    retry_on: tuple = (ConnectionError, TimeoutError, TransientError),
    show_progress: bool = True
):
    """
    Decorator for retrying async functions with exponential backoff.

    Args:
        max_attempts: Maximum number of retry attempts (default: 3)
        max_wait: Maximum wait time between retries in seconds (default: 60)
        retry_on: Tuple of exception types to retry on
        show_progress: Show retry progress in console (default: True)

    Example:
        @with_retry(max_attempts=3, retry_on=(ConnectionError, TimeoutError))
        async def fetch_data():
            return await api_call()
    """

    def before_sleep_callback(retry_state: RetryCallState):
        """Log retry attempts and show user feedback."""
        attempt = retry_state.attempt_number
        exception = retry_state.outcome.exception()
        wait_time = retry_state.next_action.sleep

        logger.warning(
            f"Retry attempt {attempt}/{max_attempts} after {exception.__class__.__name__}: "
            f"{str(exception)[:100]}. Waiting {wait_time:.1f}s..."
        )

        if show_progress:
            console.print(
                f"[yellow]⚠ Retry {attempt}/{max_attempts} - waiting {wait_time:.1f}s...[/yellow]"
            )

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        @retry(
            wait=wait_random_exponential(multiplier=1, min=1, max=max_wait),
            stop=stop_after_attempt(max_attempts),
            retry=retry_if_exception_type(retry_on),
            before_sleep=before_sleep_callback,
            reraise=True
        )
        async def wrapper(*args, **kwargs) -> T:
            return await func(*args, **kwargs)

        return wrapper

    return decorator


async def retry_with_rate_limit(
    func: Callable,
    *args,
    max_attempts: int = 3,
    **kwargs
) -> T:
    """
    Retry function with respect for Retry-After header on 429 responses.

    This function handles rate limiting specially by respecting the
    Retry-After header when present.

    Args:
        func: Async function to call
        *args: Positional arguments for func
        max_attempts: Maximum retry attempts
        **kwargs: Keyword arguments for func

    Returns:
        Result from func

    Raises:
        RateLimitError: If rate limit exceeded after all retries
    """
    for attempt in range(1, max_attempts + 1):
        try:
            return await func(*args, **kwargs)

        except RateLimitError as e:
            if attempt >= max_attempts:
                raise

            # Use Retry-After header if available
            wait_time = e.retry_after if e.retry_after else (2 ** attempt)

            logger.warning(f"Rate limited. Waiting {wait_time}s before retry {attempt}/{max_attempts}")
            console.print(f"[yellow]⚠ Rate limited - waiting {wait_time}s...[/yellow]")

            await asyncio.sleep(wait_time)

    raise RateLimitError("Max retries exceeded")
```

### 4. Enhanced Error Classes

**Location:** `src/inkwell/utils/errors.py` (enhance existing)

```python
"""Enhanced error classes with helpful messages."""

from typing import Optional, Dict, Any


class InkwellError(Exception):
    """Base exception for all Inkwell errors."""

    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        suggestion: Optional[str] = None,
        docs_url: Optional[str] = None
    ):
        self.message = message
        self.details = details or {}
        self.suggestion = suggestion
        self.docs_url = docs_url
        super().__init__(self.message)

    def __str__(self):
        """Format error message for display."""
        parts = [f"❌ {self.message}"]

        if self.details:
            parts.append(f"\nDetails: {self.details}")

        if self.suggestion:
            parts.append(f"\n💡 Suggestion: {self.suggestion}")

        if self.docs_url:
            parts.append(f"\n📖 Learn more: {self.docs_url}")

        return "\n".join(parts)


class TransientError(InkwellError):
    """Transient error that should be retried."""
    pass


class NetworkError(TransientError):
    """Network-related error."""

    def __init__(self, operation: str, original_error: Exception):
        super().__init__(
            message=f"Network error during {operation}",
            details={"original_error": str(original_error)},
            suggestion="Check your internet connection and try again"
        )


class RateLimitError(TransientError):
    """API rate limit exceeded."""

    def __init__(
        self,
        provider: str,
        retry_after: Optional[int] = None
    ):
        if retry_after:
            suggestion = f"Wait {retry_after} seconds before retrying"
        else:
            suggestion = "Wait a few minutes before retrying or check your API usage"

        super().__init__(
            message=f"{provider} API rate limit exceeded",
            details={"retry_after": retry_after},
            suggestion=suggestion,
            docs_url="https://docs.inkwell.cli/troubleshooting/rate-limits"
        )
        self.retry_after = retry_after


class APIKeyError(InkwellError):
    """API key missing or invalid."""

    def __init__(self, provider: str):
        super().__init__(
            message=f"Missing or invalid API key for {provider}",
            suggestion=f"Set your API key with: inkwell config set {provider.lower()}_api_key YOUR_KEY",
            docs_url="https://docs.inkwell.cli/setup/api-keys"
        )


class TranscriptionError(InkwellError):
    """Transcription failed."""
    pass


class ExtractionError(InkwellError):
    """Extraction failed."""
    pass


class InterviewError(InkwellError):
    """Interview mode error."""
    pass
```

### 5. Application Points

Apply retry logic to these components:

#### TranscriptionManager
```python
# src/inkwell/transcription/gemini.py

from inkwell.utils.retry import with_retry
from inkwell.utils.errors import TranscriptionError, RateLimitError

class GeminiTranscriber:
    @with_retry(
        max_attempts=3,
        retry_on=(ConnectionError, TimeoutError, RateLimitError)
    )
    async def transcribe(self, audio_path: Path) -> Transcript:
        try:
            # Transcription logic
            pass
        except Exception as e:
            if "rate limit" in str(e).lower():
                raise RateLimitError("Gemini")
            raise TranscriptionError(f"Gemini transcription failed: {e}")
```

#### ExtractionEngine
```python
# src/inkwell/extraction/engine.py

from inkwell.utils.retry import with_retry
from inkwell.utils.errors import ExtractionError, RateLimitError

class ExtractionEngine:
    @with_retry(
        max_attempts=3,
        retry_on=(ConnectionError, TimeoutError, RateLimitError)
    )
    async def extract(self, template: Template, transcript: str) -> ExtractionResult:
        try:
            # Extraction logic
            pass
        except Exception as e:
            if "rate limit" in str(e).lower():
                raise RateLimitError(self.provider)
            raise ExtractionError(f"Extraction failed: {e}")
```

#### InterviewAgent
```python
# src/inkwell/interview/agent.py

from inkwell.utils.retry import with_retry
from inkwell.utils.errors import InterviewError, RateLimitError

class InterviewAgent:
    @with_retry(
        max_attempts=3,
        retry_on=(ConnectionError, TimeoutError, RateLimitError)
    )
    async def generate_question(self, context: InterviewContext) -> Question:
        try:
            # Question generation logic
            pass
        except Exception as e:
            if "rate limit" in str(e).lower():
                raise RateLimitError("Claude")
            raise InterviewError(f"Question generation failed: {e}")
```

#### FeedParser
```python
# src/inkwell/feeds/parser.py

from inkwell.utils.retry import with_retry
from inkwell.utils.errors import FeedError

class FeedParser:
    @with_retry(
        max_attempts=3,
        retry_on=(ConnectionError, TimeoutError)
    )
    async def fetch_feed(self, url: str) -> Feed:
        try:
            # RSS parsing logic
            pass
        except Exception as e:
            raise FeedError(f"Failed to fetch feed: {e}")
```

### 6. Configuration

Allow users to configure retry behavior:

```yaml
# ~/.config/inkwell/config.yaml

retry:
  enabled: true
  max_attempts: 3              # Maximum retry attempts
  max_wait: 10                 # Maximum wait time between retries (seconds)
  show_progress: true          # Show retry progress in terminal

logging:
  log_level: INFO              # DEBUG to see all retry attempts
  log_retries: true            # Log retry attempts
```

## Implementation Plan

### Phase 5 Unit 6: Error Handling & Retry Logic (1 day)

1. **Install Tenacity** (15 min)
   ```bash
   uv add tenacity
   ```

2. **Create retry utility module** (2 hours)
   - Implement `with_retry` decorator
   - Implement `retry_with_rate_limit` function
   - Add progress display with Rich

3. **Enhance error classes** (1 hour)
   - Add helpful error messages
   - Add suggestions and docs URLs
   - Categorize transient vs permanent errors

4. **Apply to existing code** (3 hours)
   - TranscriptionManager (Gemini API)
   - ExtractionEngine (Claude/Gemini APIs)
   - InterviewAgent (Claude Agent SDK)
   - FeedParser (RSS fetch)

5. **Testing** (2 hours)
   - Unit tests for retry logic
   - Mock transient failures
   - Test backoff timing
   - Test error messages

## Consequences

### Positive

1. **Better UX** - Automatic retry on transient failures saves user time
2. **Resilience** - Handles network issues and API hiccups gracefully
3. **Visibility** - Users see retry progress, understand what's happening
4. **Helpful errors** - Clear messages with actionable suggestions
5. **Rate limit respect** - Honors `Retry-After` headers
6. **Configurable** - Users can adjust retry behavior

### Negative

1. **Complexity** - More code to maintain and test
2. **Longer waits** - Failed operations take longer (up to ~9s with 3 retries)
3. **Dependency** - Adds Tenacity library dependency
4. **Logging overhead** - More log messages (can be noisy in DEBUG mode)

### Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Users frustrated by long waits | Show clear progress, allow Ctrl-C to cancel |
| Retrying non-idempotent operations | Only retry safe operations (reads, idempotent writes) |
| Overwhelming recovering service | Use jitter, respect Retry-After headers |
| Masking permanent issues | Fail after max attempts, log all errors |
| Cost increase from retries | Retry only transient errors, cache results |

## Alternatives Considered

### Alternative 1: Manual Retry (Status Quo)
**Pros:** Simple, no code changes
**Cons:** Poor UX, users must manually retry
**Decision:** Rejected - automatic retry is essential

### Alternative 2: backoff Library
**Pros:** Simpler API
**Cons:** Less flexible than Tenacity, weaker async support
**Decision:** Rejected - Tenacity is more powerful

### Alternative 3: Custom Implementation
**Pros:** No dependency, full control
**Cons:** Reinventing wheel, prone to bugs
**Decision:** Rejected - Tenacity is battle-tested

### Alternative 4: Circuit Breaker Pattern
**Pros:** Prevents cascading failures
**Cons:** Overkill for CLI tool, complex
**Decision:** Deferred to future if needed

## Success Metrics

- ✅ 95%+ of transient failures succeed after retry
- ✅ Average retry count: <2 attempts
- ✅ No user complaints about "network errors"
- ✅ Error messages rated "helpful" in user testing
- ✅ Retry progress visible in terminal
- ✅ No retries on permanent errors (400, 401, 403, 404)

## Testing Strategy

### Unit Tests
```python
@pytest.mark.asyncio
async def test_retry_on_transient_error():
    """Test that function retries on transient errors."""
    mock_api = AsyncMock()
    mock_api.side_effect = [
        ConnectionError("Network error"),
        ConnectionError("Network error"),
        {"result": "success"}
    ]

    @with_retry(max_attempts=3, show_progress=False)
    async def api_call():
        return await mock_api()

    result = await api_call()
    assert result == {"result": "success"}
    assert mock_api.call_count == 3


@pytest.mark.asyncio
async def test_no_retry_on_permanent_error():
    """Test that function doesn't retry on permanent errors."""
    mock_api = AsyncMock()
    mock_api.side_effect = ValueError("Bad input")

    @with_retry(
        max_attempts=3,
        retry_on=(ConnectionError,),
        show_progress=False
    )
    async def api_call():
        return await mock_api()

    with pytest.raises(ValueError):
        await api_call()

    assert mock_api.call_count == 1  # No retries


@pytest.mark.asyncio
async def test_exponential_backoff_timing():
    """Test that backoff timing increases exponentially."""
    times = []

    @with_retry(max_attempts=3, show_progress=False)
    async def failing_call():
        times.append(asyncio.get_event_loop().time())
        raise ConnectionError("Fail")

    with pytest.raises(ConnectionError):
        await failing_call()

    # Verify increasing wait times
    assert len(times) == 3
    # Wait between attempt 1 and 2 should be ~1-2s
    # Wait between attempt 2 and 3 should be ~2-4s
```

### Integration Tests
- Test with real API failures (mock server returning 503)
- Test rate limiting (mock server returning 429)
- Test network timeout scenarios

## Implementation Checklist

- [ ] Add tenacity dependency
- [ ] Create `src/inkwell/utils/retry.py`
- [ ] Enhance `src/inkwell/utils/errors.py`
- [ ] Apply retry to TranscriptionManager
- [ ] Apply retry to ExtractionEngine
- [ ] Apply retry to InterviewAgent
- [ ] Apply retry to FeedParser
- [ ] Add retry configuration to config schema
- [ ] Write unit tests (>90% coverage)
- [ ] Write integration tests
- [ ] Update user documentation
- [ ] Test with real API failures

## References

- [Research: Error Handling Best Practices](../research/error-handling-best-practices.md)
- [AWS Builders Library - Backoff with Jitter](https://aws.amazon.com/builders-library/timeouts-retries-and-backoff-with-jitter/)
- [Tenacity Documentation](https://tenacity.readthedocs.io/)
- [Google Cloud - Exponential Backoff](https://cloud.google.com/iot/docs/how-tos/exponential-backoff)

---

**Decision Made By:** Phase 5 Team
**Status:** Accepted
**Next Review:** After Phase 5 Unit 6 completion
