# Research: Error Handling & Retry Best Practices

**Date**: 2025-11-09
**Researcher**: Phase 5 Unit 1
**Status**: Complete
**Related**: [ADR-027](../adr/027-retry-and-error-handling-strategy.md)

## Overview

This research document explores best practices for error handling and retry strategies in distributed systems, with focus on API integrations, network failures, and rate limiting. The goal is to design a robust error handling system for Inkwell that gracefully handles transient failures while providing excellent user experience.

---

## 1. Retry Strategies Overview

### Why Retry?

Distributed systems experience **transient failures** that resolve themselves:
- Network timeouts
- Temporary service unavailability
- Rate limiting
- Intermittent connectivity issues

**Goal:** Retry automatically for transient errors, fail fast for permanent errors.

### Common Retry Patterns

#### 1. Fixed Delay
```python
# Wait 1 second between each retry
retry(wait=wait_fixed(1))
```
**Pros:** Simple, predictable
**Cons:** Inefficient, can overwhelm recovering services

#### 2. Linear Backoff
```python
# Wait 1s, 2s, 3s, 4s...
retry(wait=wait_incrementing(start=1, increment=1))
```
**Pros:** Gives service time to recover
**Cons:** Still creates predictable waves

#### 3. Exponential Backoff
```python
# Wait 1s, 2s, 4s, 8s, 16s...
retry(wait=wait_exponential(multiplier=1, min=1, max=60))
```
**Pros:** Quickly backs off, industry standard
**Cons:** Multiple clients retry simultaneously (thundering herd)

#### 4. Exponential Backoff with Jitter (BEST)
```python
# Wait random(1-2s), random(2-4s), random(4-8s)...
retry(wait=wait_random_exponential(multiplier=1, max=60))
```
**Pros:** Spreads load, prevents thundering herd
**Cons:** Slightly more complex

---

## 2. Exponential Backoff with Jitter (Deep Dive)

### The Thundering Herd Problem

**Scenario:** 1000 clients make a request. Service fails. All retry at exactly 1s, 2s, 4s...

**Result:**
- 0s: 1000 requests → service crashes
- 1s: 1000 requests → service still down
- 2s: 1000 requests → service still recovering
- 4s: 1000 requests → service might be up but immediately crashes again

**Problem:** Synchronized retries create waves that prevent service recovery.

### Solution: Jitter (Randomization)

**With jitter:** Each client waits a random time within the backoff window:
- Client 1: waits 1.2s
- Client 2: waits 1.7s
- Client 3: waits 0.8s
- Client 4: waits 1.5s

**Result:** Requests spread out over time, allowing service to recover gracefully.

### Jitter Strategies

#### Full Jitter (AWS Recommendation)
```python
wait_time = random(0, min(cap, base * 2^attempt))
```
**Example:** Attempt 3, base=1s, cap=60s
- Max wait: min(60, 1 * 2^3) = 8s
- Actual wait: random(0, 8s)

**Pros:** Maximum spread
**Cons:** Might retry too quickly

#### Equal Jitter (Balanced)
```python
temp = min(cap, base * 2^attempt)
wait_time = temp/2 + random(0, temp/2)
```
**Example:** Attempt 3, base=1s, cap=60s
- Max wait: 8s
- Actual wait: 4s + random(0, 4s) = 4-8s

**Pros:** Guaranteed minimum wait, good spread
**Cons:** Slightly less optimal than full jitter

#### Decorrelated Jitter (AWS Advanced)
```python
wait_time = min(cap, random(base, previous_wait * 3))
```
**Pros:** Even better spread, adapts to system behavior
**Cons:** More complex

**Recommendation:** Use **equal jitter** for balance of simplicity and effectiveness.

---

## 3. Python Retry Libraries

### Tenacity (Recommended)

**Repository:** https://github.com/jd/tenacity
**Stars:** ~6.5k
**Maintainance:** Active (2025)

#### Why Tenacity?

1. **Comprehensive** - Supports all retry strategies
2. **Flexible** - Decorator or imperative API
3. **Async-friendly** - Works with asyncio
4. **Well-tested** - Production-proven
5. **Readable** - Clean, declarative syntax

#### Basic Usage
```python
from tenacity import retry, wait_exponential, stop_after_attempt

@retry(
    wait=wait_exponential(multiplier=1, min=1, max=10),
    stop=stop_after_attempt(3)
)
async def fetch_data():
    # Your code here
    pass
```

#### Advanced Usage
```python
from tenacity import (
    retry,
    wait_random_exponential,
    stop_after_attempt,
    retry_if_exception_type,
    before_sleep_log,
)
import logging

logger = logging.getLogger(__name__)

@retry(
    # Retry strategy
    wait=wait_random_exponential(multiplier=1, max=60),

    # Stop condition
    stop=stop_after_attempt(3),

    # Only retry on specific exceptions
    retry=retry_if_exception_type((TimeoutError, ConnectionError)),

    # Logging
    before_sleep=before_sleep_log(logger, logging.WARNING),

    # Reraise final exception
    reraise=True
)
async def api_call():
    pass
```

### Alternative: backoff

**Repository:** https://github.com/litl/backoff
**Stars:** ~2k

**Pros:** Simpler API, decorator-focused
**Cons:** Less flexible than Tenacity

```python
import backoff

@backoff.on_exception(
    backoff.expo,
    (TimeoutError, ConnectionError),
    max_tries=3,
    jitter=backoff.full_jitter
)
async def api_call():
    pass
```

**Recommendation:** Use **Tenacity** for more control and flexibility.

---

## 4. Error Classification

### Errors to Retry (Transient)

| Status Code | Description | Retry? | Wait |
|-------------|-------------|--------|------|
| **408** | Request Timeout | ✅ Yes | Exponential |
| **429** | Rate Limit | ✅ Yes | Respect `Retry-After` header |
| **500** | Internal Server Error | ✅ Yes | Exponential |
| **502** | Bad Gateway | ✅ Yes | Exponential |
| **503** | Service Unavailable | ✅ Yes | Exponential |
| **504** | Gateway Timeout | ✅ Yes | Exponential |

### Errors NOT to Retry (Permanent)

| Status Code | Description | Retry? | Action |
|-------------|-------------|--------|--------|
| **400** | Bad Request | ❌ No | Fix request |
| **401** | Unauthorized | ❌ No | Check API key |
| **403** | Forbidden | ❌ No | Check permissions |
| **404** | Not Found | ❌ No | Check URL |
| **422** | Unprocessable Entity | ❌ No | Fix input data |

### Network Errors

| Error Type | Retry? | Wait |
|------------|--------|------|
| `ConnectionError` | ✅ Yes | Exponential |
| `TimeoutError` | ✅ Yes | Exponential |
| `NetworkError` | ✅ Yes | Exponential |
| `SSLError` | ❌ No | Fix SSL config |
| `DNSError` | ⚠️ Maybe | Check network |

---

## 5. Best Practices

### 1. Always Set Stop Conditions

**❌ Bad:**
```python
@retry(wait=wait_exponential())
def api_call():
    pass  # Retries forever!
```

**✅ Good:**
```python
@retry(
    wait=wait_exponential(max=60),
    stop=stop_after_attempt(3)  # Max 3 attempts
)
def api_call():
    pass
```

### 2. Respect `Retry-After` Header

Many APIs include a `Retry-After` header indicating when to retry:

```python
import httpx
from tenacity import retry, wait_chain, wait_fixed
from datetime import datetime, timedelta

def get_retry_after_wait(response):
    """Extract wait time from Retry-After header."""
    if "Retry-After" in response.headers:
        retry_after = response.headers["Retry-After"]

        # Could be seconds (integer)
        try:
            return int(retry_after)
        except ValueError:
            pass

        # Or HTTP-date
        try:
            retry_date = datetime.strptime(retry_after, "%a, %d %b %Y %H:%M:%S GMT")
            return max(0, (retry_date - datetime.utcnow()).total_seconds())
        except ValueError:
            pass

    return None

@retry(wait=wait_exponential(max=60), stop=stop_after_attempt(3))
async def api_call_with_retry_after():
    response = await httpx.get("https://api.example.com/")

    if response.status_code == 429:
        wait_time = get_retry_after_wait(response)
        if wait_time:
            await asyncio.sleep(wait_time)

    response.raise_for_status()
    return response.json()
```

### 3. Log Retry Attempts

Users want to know what's happening:

```python
import logging
from tenacity import retry, before_sleep_log, after_log

logger = logging.getLogger(__name__)

@retry(
    wait=wait_random_exponential(max=60),
    stop=stop_after_attempt(3),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    after=after_log(logger, logging.INFO)
)
async def api_call():
    pass
```

### 4. Provide User Feedback

For CLI tools, show retry progress:

```python
from rich.console import Console

console = Console()

async def api_call_with_feedback():
    for attempt in range(1, 4):
        try:
            return await api_call()
        except TransientError as e:
            if attempt < 3:
                wait_time = 2 ** attempt
                console.print(f"[yellow]Retry {attempt}/3 - waiting {wait_time}s...[/yellow]")
                await asyncio.sleep(wait_time)
            else:
                console.print(f"[red]Failed after 3 attempts[/red]")
                raise
```

### 5. Use Token Bucket for Rate Limiting

Prevent overwhelming your own rate limits:

```python
import asyncio
from collections import deque
from time import time

class TokenBucket:
    """Rate limiter using token bucket algorithm."""

    def __init__(self, rate: float, capacity: int):
        self.rate = rate  # tokens per second
        self.capacity = capacity
        self.tokens = capacity
        self.last_update = time()

    async def acquire(self):
        """Wait until a token is available."""
        while True:
            now = time()
            elapsed = now - self.last_update
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
            self.last_update = now

            if self.tokens >= 1:
                self.tokens -= 1
                return

            # Wait until next token
            wait_time = (1 - self.tokens) / self.rate
            await asyncio.sleep(wait_time)

# Usage
bucket = TokenBucket(rate=10, capacity=20)  # 10 req/s, burst of 20

@retry(wait=wait_exponential(max=60), stop=stop_after_attempt(3))
async def api_call():
    await bucket.acquire()
    # Make API call
    pass
```

### 6. Handle Idempotency

**Idempotent operation:** Can be safely retried without side effects.

**Examples:**
- ✅ GET requests (reading data)
- ✅ PUT requests (updating to specific state)
- ❌ POST requests (creating resources)
- ❌ Payments, emails, notifications

**Solution for non-idempotent operations:**
```python
import uuid

def create_resource_with_idempotency(data):
    # Generate idempotency key
    idempotency_key = str(uuid.uuid4())

    response = api.post(
        "/resources",
        json=data,
        headers={"Idempotency-Key": idempotency_key}
    )

    return response

# If retry occurs, server recognizes idempotency key
# and returns the original response instead of creating duplicate
```

### 7. Circuit Breaker Pattern

For repeated failures, stop retrying temporarily:

```python
from datetime import datetime, timedelta

class CircuitBreaker:
    """Prevents repeated calls to failing service."""

    def __init__(self, failure_threshold: int = 5, timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout = timedelta(seconds=timeout)
        self.failures = 0
        self.last_failure_time = None
        self.state = "closed"  # closed, open, half-open

    def call(self, func, *args, **kwargs):
        if self.state == "open":
            # Check if timeout has passed
            if datetime.now() - self.last_failure_time > self.timeout:
                self.state = "half-open"
            else:
                raise Exception("Circuit breaker is OPEN")

        try:
            result = func(*args, **kwargs)
            self.on_success()
            return result
        except Exception as e:
            self.on_failure()
            raise

    def on_success(self):
        """Reset on successful call."""
        self.failures = 0
        self.state = "closed"

    def on_failure(self):
        """Increment failures and open if threshold reached."""
        self.failures += 1
        self.last_failure_time = datetime.now()

        if self.failures >= self.failure_threshold:
            self.state = "open"

# Usage
breaker = CircuitBreaker(failure_threshold=5, timeout=60)

def protected_api_call():
    return breaker.call(api_call)
```

---

## 6. Error Messages Best Practices

### Helpful Error Messages

**❌ Bad:**
```python
raise Exception("API call failed")
```

**✅ Good:**
```python
raise APIError(
    message="Transcription API call failed",
    details={
        "status_code": 500,
        "url": "https://api.gemini.com/transcribe",
        "attempt": 3,
        "max_attempts": 3,
    },
    suggestion="The API may be experiencing issues. Try again in a few minutes or check status at https://status.google.com"
)
```

### Error Message Components

1. **What happened** - Clear description
2. **Why it happened** - Context (status code, network error)
3. **What to do** - Actionable suggestion
4. **Where to learn more** - Documentation link

### Example Error Classes

```python
from typing import Optional, Dict, Any

class InkwellError(Exception):
    """Base exception for Inkwell errors."""

    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        suggestion: Optional[str] = None
    ):
        self.message = message
        self.details = details or {}
        self.suggestion = suggestion
        super().__init__(self.message)

    def __str__(self):
        parts = [self.message]

        if self.details:
            parts.append(f"Details: {self.details}")

        if self.suggestion:
            parts.append(f"Suggestion: {self.suggestion}")

        return "\n".join(parts)

class TranscriptionError(InkwellError):
    """Transcription-related errors."""
    pass

class ExtractionError(InkwellError):
    """Extraction-related errors."""
    pass

class APIKeyError(InkwellError):
    """API key configuration errors."""

    def __init__(self, provider: str):
        super().__init__(
            message=f"Missing or invalid API key for {provider}",
            suggestion=f"Set your {provider} API key with: inkwell config set {provider.lower()}_api_key YOUR_KEY"
        )

class RateLimitError(InkwellError):
    """Rate limiting errors."""

    def __init__(self, provider: str, retry_after: Optional[int] = None):
        message = f"{provider} API rate limit exceeded"

        if retry_after:
            suggestion = f"Wait {retry_after} seconds before retrying"
        else:
            suggestion = "Wait a few minutes before retrying"

        super().__init__(message=message, suggestion=suggestion)
```

---

## 7. Async Considerations

### Async Context Managers

```python
from contextlib import asynccontextmanager
from tenacity import AsyncRetrying, wait_random_exponential, stop_after_attempt

@asynccontextmanager
async def retry_context():
    """Context manager for retries with cleanup."""
    async for attempt in AsyncRetrying(
        wait=wait_random_exponential(max=60),
        stop=stop_after_attempt(3)
    ):
        with attempt:
            yield attempt

# Usage
async with retry_context() as attempt:
    response = await api_call()
```

### Concurrent Retries

When making multiple API calls concurrently, each should have independent retry logic:

```python
async def fetch_all(urls):
    tasks = [fetch_with_retry(url) for url in urls]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Separate successes from failures
    successes = [r for r in results if not isinstance(r, Exception)]
    failures = [r for r in results if isinstance(r, Exception)]

    return successes, failures

@retry(wait=wait_random_exponential(max=60), stop=stop_after_attempt(3))
async def fetch_with_retry(url):
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.json()
```

---

## 8. Testing Retry Logic

### Mock Transient Failures

```python
import pytest
from unittest.mock import AsyncMock

@pytest.mark.asyncio
async def test_retry_on_transient_failure():
    """Test that function retries on transient errors."""
    mock_api = AsyncMock()

    # Fail twice, then succeed
    mock_api.side_effect = [
        ConnectionError("Network error"),
        ConnectionError("Network error"),
        {"result": "success"}
    ]

    @retry(wait=wait_fixed(0.1), stop=stop_after_attempt(3))
    async def api_call():
        return await mock_api()

    result = await api_call()

    assert result == {"result": "success"}
    assert mock_api.call_count == 3

@pytest.mark.asyncio
async def test_no_retry_on_permanent_failure():
    """Test that function doesn't retry on permanent errors."""
    mock_api = AsyncMock()
    mock_api.side_effect = ValueError("Bad input")

    @retry(
        wait=wait_fixed(0.1),
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type(ConnectionError)  # Only retry ConnectionError
    )
    async def api_call():
        return await mock_api()

    with pytest.raises(ValueError):
        await api_call()

    # Should fail immediately, not retry
    assert mock_api.call_count == 1
```

---

## 9. Key Findings & Recommendations

### Findings

1. **Exponential backoff with jitter is industry standard**
   - Prevents thundering herd problem
   - AWS, Google, Microsoft all recommend it
   - Equal jitter provides good balance

2. **Tenacity is the best Python library**
   - Most flexible and well-maintained
   - Works seamlessly with asyncio
   - Comprehensive retry strategies

3. **Error classification is critical**
   - Retry transient errors (408, 429, 500, 502, 503, 504)
   - Don't retry permanent errors (400, 401, 403, 404)
   - Always set max retry limits

4. **User feedback improves experience**
   - Show retry attempts in terminal
   - Log retry events
   - Provide clear error messages with suggestions

5. **Respect API conventions**
   - Honor `Retry-After` headers
   - Use idempotency keys for non-idempotent operations
   - Implement local rate limiting

### Recommendations for Inkwell

#### Retry Strategy
- ✅ Use Tenacity library
- ✅ Equal jitter exponential backoff
- ✅ Max 3 retry attempts (configurable)
- ✅ Max 60 second wait between retries
- ✅ Respect `Retry-After` headers

#### Error Handling
- ✅ Create custom error classes (APIKeyError, RateLimitError, etc.)
- ✅ Provide helpful error messages with suggestions
- ✅ Log all retry attempts
- ✅ Show retry progress in terminal

#### Implementation
- ✅ Apply to: TranscriptionManager, ExtractionEngine, InterviewAgent
- ✅ Retry on: network errors, 408, 429, 500, 502, 503, 504
- ✅ Don't retry on: 400, 401, 403, 404, 422
- ✅ Use async context managers for cleanup

---

## 10. References

- [AWS Builders Library - Timeouts, Retries, and Backoff with Jitter](https://aws.amazon.com/builders-library/timeouts-retries-and-backoff-with-jitter/)
- [Tenacity Documentation](https://tenacity.readthedocs.io/)
- [Google Cloud - Exponential Backoff](https://cloud.google.com/iot/docs/how-tos/exponential-backoff)
- [Marc Brooker - Exponential Backoff And Jitter](https://aws.amazon.com/blogs/architecture/exponential-backoff-and-jitter/)
- [Medium - Building Resilient HTTP Clients](https://medium.com/@ansh.chaturmohta/building-resilient-http-clients-a-deep-dive-into-retry-logic-with-pythons-tenacity-513bc927042b)

---

## Next Steps

1. Design retry and error handling architecture (see ADR-027)
2. Implement retry utility module (Phase 5 Unit 6)
3. Apply retry logic to all API calls
4. Test error scenarios thoroughly

---

**Document Version:** 1.0
**Last Updated:** 2025-11-09
**Status:** Complete
