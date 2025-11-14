---
status: completed
priority: p2
issue_id: "011"
tags: [code-review, security, cost-control, high-priority]
dependencies: []
---

# Implement Rate Limiting for API Calls

## Problem Statement

There is no rate limiting mechanism to prevent excessive API calls. A bug or malicious input could cause runaway API usage, leading to large bills and potential API key suspension.

**Severity**: MEDIUM (CVSS 5.0)

## Findings

- Discovered during security audit by security-sentinel agent
- No rate limiting anywhere in the codebase
- Retry logic exists but no throttling
- Bug could cost thousands of dollars
- No circuit breaker for failing APIs

**Risk Scenarios**:

1. **Infinite Loop Bug**:
```python
# Bug: processes same episode repeatedly
while True:
    process_episode(url)  # $0.10 per call
    # Result: $6/minute, $360/hour, $8,640/day
```

2. **Feed Parsing Error**:
```python
# Bug: treats 1000 lines as 1000 episodes
for line in corrupted_feed.split('\n'):
    process_episode(line)  # 1000 API calls instantly
```

3. **Retry Loop**:
```python
# Bug: retry logic doesn't back off properly
for attempt in range(1000):  # Accidental 1000 instead of 3
    try_api_call()
```

**Impact**:
- Financial loss ($100-$10,000+ bills)
- API key rate limits/suspension
- Service disruption
- Angry users

## Proposed Solutions

### Option 1: Token Bucket Rate Limiter (Recommended)
**Pros**:
- Industry standard algorithm
- Allows bursts while maintaining average rate
- Simple to implement
- No external dependencies

**Cons**:
- Adds slight complexity

**Effort**: Medium (2-3 hours)
**Risk**: Low

**Implementation**:

```python
# src/inkwell/utils/rate_limiter.py (NEW FILE)

import time
import threading
from typing import Literal

class RateLimiter:
    """Token bucket rate limiter for API calls.

    Limits the rate of operations using the token bucket algorithm:
    - Tokens are added at a constant rate (rate_limit)
    - Each operation consumes one token
    - Operations block if no tokens available
    - Allows bursts up to bucket capacity

    Example:
        >>> limiter = RateLimiter(max_calls=10, period_seconds=60)
        >>> limiter.acquire()  # Blocks if rate limit exceeded
        >>> # ... make API call ...
    """

    def __init__(self, max_calls: int, period_seconds: int):
        """Initialize rate limiter.

        Args:
            max_calls: Maximum number of calls allowed in period
            period_seconds: Time period in seconds

        Example:
            >>> # Allow 10 calls per minute
            >>> limiter = RateLimiter(max_calls=10, period_seconds=60)
        """
        self.max_calls = max_calls
        self.period = period_seconds
        self.tokens = max_calls  # Start with full bucket
        self.last_update = time.time()
        self.lock = threading.Lock()

    def _refill_tokens(self) -> None:
        """Refill tokens based on time elapsed."""
        now = time.time()
        elapsed = now - self.last_update

        # Calculate tokens to add
        tokens_to_add = elapsed * (self.max_calls / self.period)

        # Add tokens (cap at max_calls)
        self.tokens = min(self.max_calls, self.tokens + tokens_to_add)
        self.last_update = now

    def acquire(self, blocking: bool = True, timeout: float | None = None) -> bool:
        """Acquire a token, blocking if necessary.

        Args:
            blocking: If True, block until token available
            timeout: Maximum time to wait (None = wait forever)

        Returns:
            True if token acquired, False if timeout

        Raises:
            TimeoutError: If timeout exceeded (only in blocking mode)

        Example:
            >>> limiter.acquire()  # Block until token available
            >>> limiter.acquire(blocking=False)  # Return immediately
            >>> limiter.acquire(timeout=5.0)  # Wait max 5 seconds
        """
        start_time = time.time()

        while True:
            with self.lock:
                self._refill_tokens()

                if self.tokens >= 1:
                    self.tokens -= 1
                    return True

                if not blocking:
                    return False

                # Calculate wait time
                if self.tokens <= 0:
                    # Need to wait for one token
                    wait_time = self.period / self.max_calls
                else:
                    wait_time = 0.1  # Check again soon

            # Check timeout
            if timeout is not None:
                elapsed = time.time() - start_time
                if elapsed >= timeout:
                    return False

            # Sleep and retry
            time.sleep(min(wait_time, 0.1))

    def reset(self) -> None:
        """Reset the rate limiter (refill all tokens)."""
        with self.lock:
            self.tokens = self.max_calls
            self.last_update = time.time()


# Global rate limiters for different providers
_rate_limiters: dict[str, RateLimiter] = {}


def get_rate_limiter(
    provider: Literal["gemini", "claude", "youtube"],
    max_calls: int | None = None,
    period_seconds: int | None = None,
) -> RateLimiter:
    """Get or create rate limiter for provider.

    Args:
        provider: API provider name
        max_calls: Maximum calls per period (default: provider-specific)
        period_seconds: Period in seconds (default: 60)

    Returns:
        RateLimiter instance for the provider

    Example:
        >>> limiter = get_rate_limiter("gemini")
        >>> limiter.acquire()
    """
    # Provider-specific defaults
    defaults = {
        "gemini": {"max_calls": 60, "period": 60},    # 60/minute
        "claude": {"max_calls": 50, "period": 60},    # 50/minute
        "youtube": {"max_calls": 100, "period": 60},  # 100/minute (generous)
    }

    if provider not in _rate_limiters:
        config = defaults.get(provider, {"max_calls": 30, "period": 60})
        _rate_limiters[provider] = RateLimiter(
            max_calls=max_calls or config["max_calls"],
            period_seconds=period_seconds or config["period"],
        )

    return _rate_limiters[provider]


# Decorator for automatic rate limiting
from functools import wraps
from typing import Callable, TypeVar, ParamSpec

P = ParamSpec('P')
T = TypeVar('T')


def rate_limited(
    provider: Literal["gemini", "claude", "youtube"]
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Decorator to rate limit function calls.

    Args:
        provider: API provider to rate limit

    Example:
        >>> @rate_limited("gemini")
        ... async def call_gemini_api():
        ...     # API call here
        ...     pass
    """
    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            limiter = get_rate_limiter(provider)
            limiter.acquire()  # Block until token available
            return func(*args, **kwargs)

        return wrapper
    return decorator


# Usage in existing code:

# src/inkwell/extraction/extractors/gemini.py
from inkwell.utils.rate_limiter import rate_limited

class GeminiExtractor(BaseExtractor):
    @rate_limited("gemini")
    async def extract(
        self,
        template: ExtractionTemplate,
        transcript: str,
        metadata: dict[str, Any],
    ) -> ExtractionResult:
        # API call automatically rate limited
        response = await self.model.generate_content_async(...)
        # ...


# src/inkwell/extraction/extractors/claude.py
from inkwell.utils.rate_limiter import rate_limited

class ClaudeExtractor(BaseExtractor):
    @rate_limited("claude")
    async def extract(
        self,
        template: ExtractionTemplate,
        transcript: str,
        metadata: dict[str, Any],
    ) -> ExtractionResult:
        # API call automatically rate limited
        response = await self.client.messages.create(...)
        # ...


# src/inkwell/cli.py - Add rate limit info
@app.command()
def fetch(
    # ... existing params ...
    bypass_rate_limit: bool = typer.Option(
        False,
        "--bypass-rate-limit",
        help="Bypass rate limiting (use carefully)"
    ),
):
    """Process podcast episode."""
    if bypass_rate_limit:
        console.print("[yellow]⚠[/yellow] Rate limiting bypassed")
        # Reset all rate limiters
        from inkwell.utils.rate_limiter import _rate_limiters
        for limiter in _rate_limiters.values():
            limiter.reset()
```

### Option 2: Fixed Window Rate Limiting
**Pros**:
- Simpler algorithm
- Easier to understand

**Cons**:
- Allows bursts at window boundaries
- Less smooth rate limiting

**Effort**: Small (1-2 hours)
**Risk**: Low

### Option 3: Distributed Rate Limiting (Future)
**Pros**:
- Works across multiple processes/machines
- Required for production deployment

**Cons**:
- Requires Redis or similar
- Much more complex

**Effort**: Large (6-8 hours)
**Risk**: High

## Recommended Action

Implement Option 1 (token bucket) immediately for local protection. Consider Option 3 (distributed) if deploying as a service.

## Technical Details

**Affected Files**:
- `src/inkwell/extraction/extractors/gemini.py` (add rate limiting)
- `src/inkwell/extraction/extractors/claude.py` (add rate limiting)
- `src/inkwell/transcription/manager.py` (add rate limiting)
- `src/inkwell/obsidian/tags.py` (add rate limiting)

**New Files**:
- `src/inkwell/utils/rate_limiter.py` (rate limiting utilities)

**Related Components**:
- All LLM API calls
- Cost tracking (rate limits affect costs)
- Retry logic (should respect rate limits)

**Database Changes**: No

## Resources

- Token Bucket Algorithm: https://en.wikipedia.org/wiki/Token_bucket
- Rate Limiting Patterns: https://stripe.com/blog/rate-limiters
- API Rate Limiting Best Practices: https://cloud.google.com/architecture/rate-limiting-strategies-techniques

## Acceptance Criteria

- [x] Token bucket rate limiter implemented
- [x] Provider-specific rate limits configured (Gemini, Claude)
- [x] Rate limiting decorator created
- [x] All API calls protected with rate limiter
- [x] Blocking and non-blocking acquisition modes
- [x] Timeout support for rate limiter
- [ ] CLI option to bypass rate limits (for testing) - Not needed (can use reset_all_rate_limiters())
- [ ] Rate limit status visible in logs - Not needed (silent protection)
- [x] Unit tests for rate limiter
- [x] Unit tests for token refill logic
- [x] Integration tests with rate limit exceeded
- [x] Documentation updated with rate limits
- [x] All existing tests pass

## Work Log

### 2025-11-13 - Code Review Discovery
**By:** Claude Code Review System
**Actions:**
- Discovered during security audit
- Analyzed by security-sentinel agent
- Researched rate limiting algorithms
- Calculated financial risk scenarios
- Categorized as MEDIUM priority

**Learnings**:
- No rate limiting = financial risk
- Token bucket is industry standard
- Must rate limit at API boundary
- Provider-specific limits needed

### 2025-11-13 - Implementation Complete
**By:** Claude Code
**Actions:**
- Created `/Users/sergio/projects/inkwell-cli/src/inkwell/utils/rate_limiter.py` with:
  - RateLimiter class using token bucket algorithm
  - get_rate_limiter() factory with provider-specific defaults
  - reset_all_rate_limiters() for testing
  - Thread-safe token acquisition with blocking/timeout support
- Applied rate limiting to all API calls:
  - GeminiExtractor.extract() in gemini.py
  - ClaudeExtractor.extract() in claude.py
  - TagGenerator._tags_from_llm() in tags.py
  - GeminiTranscriber._transcribe_sync() in gemini.py
- Created comprehensive tests in `/Users/sergio/projects/inkwell-cli/tests/unit/utils/test_rate_limiter.py`:
  - 18 test cases covering all functionality
  - Thread safety tests
  - Integration scenarios (runaway calls, concurrent extraction, cost protection)
  - All tests passing

**Rate Limits Configured:**
- Gemini: 60 calls/minute
- Claude: 50 calls/minute
- YouTube: 100 calls/minute

**Results:**
- 94% cost reduction in worst-case bug scenarios
- Prevents API key suspension from excessive calls
- Thread-safe across concurrent operations
- Allows bursts while maintaining average rate
- All existing tests passing (221 unit tests)

**Learnings**:
- Token bucket provides good balance of burst allowance and rate limiting
- Thread safety critical for concurrent extraction tasks
- Reset functionality essential for testing
- Provider-specific defaults make API simple to use

## Notes

**Why Rate Limiting Matters**:

Real-world scenarios where rate limiting prevents disaster:
1. **Bug in feed parser**: Processes 1000 episodes instead of 10
2. **Infinite retry loop**: Retries forever on transient error
3. **Concurrent processing**: Multiple episodes processed simultaneously
4. **Malicious input**: Crafted feed triggers excessive processing

**Token Bucket Algorithm**:

```
Bucket capacity: 10 tokens
Refill rate: 1 token per 6 seconds (10/minute)

Time 0s:  10 tokens → Make 5 calls → 5 tokens left
Time 6s:  6 tokens (refilled 1) → Make 3 calls → 3 tokens
Time 12s: 4 tokens (refilled 1) → Make 4 calls → 0 tokens
Time 18s: 1 token (refilled 1) → Make 1 call → 0 tokens
Time 24s: 1 token (refilled 1) → Make 1 call → 0 tokens

Average rate: 10 calls per 60 seconds ✓
Allows bursts: Yes (up to 10 calls instantly) ✓
```

**Provider Rate Limits**:
- **Gemini**: 60 requests/minute (free tier), 1000/minute (paid)
- **Claude**: 50 requests/minute (tier 1), 5000/minute (tier 4)
- **YouTube**: 10,000/day (generous, unlikely to hit)

**Cost Protection**:
```python
# Worst case without rate limiting:
# Bug causes 1000 API calls/minute

# Gemini: 1000 calls × $0.0001 = $0.10/minute = $6/hour = $144/day
# Claude: 1000 calls × $0.003 = $3/minute = $180/hour = $4,320/day

# With rate limiting (60 calls/minute):
# Gemini: 60 calls × $0.0001 = $0.006/minute = $0.36/hour = $8.64/day
# Claude: 60 calls × $0.003 = $0.18/minute = $10.80/hour = $259/day

# Savings: 94% cost reduction!
```

**Testing**:
```python
def test_rate_limiter():
    """Test rate limiter blocks when limit exceeded."""
    limiter = RateLimiter(max_calls=5, period_seconds=10)

    # First 5 calls succeed immediately
    for _ in range(5):
        assert limiter.acquire(blocking=False)

    # 6th call blocked (no tokens)
    assert not limiter.acquire(blocking=False)

    # Wait for tokens to refill
    time.sleep(2)  # 2 seconds = 1 token

    # Now should succeed
    assert limiter.acquire(blocking=False)


def test_rate_limiter_timeout():
    """Test rate limiter timeout."""
    limiter = RateLimiter(max_calls=1, period_seconds=10)

    # Consume token
    assert limiter.acquire()

    # Next call times out
    assert not limiter.acquire(timeout=0.5)
```

**Source**: Code review performed on 2025-11-13
**Review command**: /review #9
