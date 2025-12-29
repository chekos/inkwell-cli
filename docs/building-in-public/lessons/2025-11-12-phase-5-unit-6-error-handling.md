# Lessons Learned: Phase 5 Unit 6 - Error Handling & Retry Logic

**Date**: 2025-11-12
**Context**: Implementing robust retry logic with exponential backoff
**Related**: [Devlog](../devlog/2025-11-12-phase-5-unit-6-error-handling.md), [Experiment](../experiments/2025-11-12-retry-timing-analysis.md)

## Technical Insights

### 1. Jitter is Not Optional for Production

**The Problem**:
When multiple clients hit a rate limit simultaneously, they all retry at the same time, causing a "thundering herd" that triggers the rate limit again.

**The Solution**:
Jitter randomizes retry timing, spreading clients across time:
```python
wait_time = min(max_wait, 2^attempt + random(0, max_wait))
```

**Impact**:
- **Without jitter**: 45-80% success rate with concurrent clients
- **With jitter**: 95-100% success rate with concurrent clients

**Lesson**: Always enable jitter in production, even if it adds ~15% overhead for single clients. The improvement for concurrent access is dramatic (2-10x better success rates).

### 2. Test Performance Matters

**The Problem**:
Initial tests took 96 seconds for just 2 tests because they used actual retry logic with 1-60 second waits.

**The Solution**:
Create separate test configuration with minimal delays:
```python
TEST_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    max_wait_seconds=0.1,   # 100ms instead of 60s
    min_wait_seconds=0.01,  # 10ms instead of 1s
    jitter=False,
)
```

**Implementation**:
Use pytest fixture to monkeypatch the default config:
```python
@pytest.fixture(autouse=True)
def fast_retry_config(monkeypatch):
    monkeypatch.setattr("inkwell.utils.retry.DEFAULT_RETRY_CONFIG", TEST_RETRY_CONFIG)
```

**Impact**:
- **Before**: 180+ seconds for 33 tests
- **After**: 0.59 seconds for 33 tests
- **Speedup**: 305x faster

**Lesson**: Test configuration should be separate from production configuration. Unit tests should run in <1 second, not minutes.

### 3. Exception Hierarchy Beats Flags

**Alternative Considered**:
```python
class APIError(Exception):
    def __init__(self, message, is_retryable=False):
        self.is_retryable = is_retryable
```

**Why Rejected**:
- Less explicit (have to check attribute)
- Error-prone (easy to forget to set flag)
- Harder to understand at a glance

**Better Approach**:
```python
class RetryableError(Exception):
    pass

class NonRetryableError(Exception):
    pass

class RateLimitError(RetryableError):
    pass

class AuthenticationError(NonRetryableError):
    pass
```

**Benefits**:
- ✅ Type-safe (can use `isinstance()`)
- ✅ Self-documenting (class name explains behavior)
- ✅ Easy to extend (just inherit from base class)
- ✅ Works with `retry_if_exception_type()`

**Lesson**: Use exception hierarchy instead of flags for categorization. It's more Pythonic and easier to understand.

### 4. Decorator Inheritance Patterns

**The Problem**:
Specialized decorators created their own `RetryConfig` instances, so monkeypatching `DEFAULT_RETRY_CONFIG` in tests didn't affect them:

```python
def with_api_retry(max_attempts=3):
    config = RetryConfig(max_attempts=max_attempts)  # ❌ Doesn't inherit timing
    return with_retry(config=config, retry_on=(...))
```

**The Solution**:
Make decorators inherit timing from DEFAULT_RETRY_CONFIG:
```python
def with_api_retry(max_attempts=3, config=None):
    if config is None:
        config = RetryConfig(
            max_attempts=max_attempts,
            max_wait_seconds=DEFAULT_RETRY_CONFIG.max_wait_seconds,  # ✅ Inherit
            min_wait_seconds=DEFAULT_RETRY_CONFIG.min_wait_seconds,  # ✅ Inherit
            jitter=DEFAULT_RETRY_CONFIG.jitter,  # ✅ Inherit
        )
    return with_retry(config=config, retry_on=(...))
```

**Benefit**: Tests can monkeypatch DEFAULT_RETRY_CONFIG once and affect all decorators.

**Lesson**: When creating specialized decorators, make them inherit from a global default config rather than hardcoding values. This enables easier testing and user customization.

### 5. Mock `time.sleep` for Timing Tests

**The Problem**:
Need to test exponential backoff timing without actually waiting.

**The Solution**:
Use `@patch('time.sleep')` to mock sleep calls:
```python
@patch('time.sleep')
def test_backoff_timing(mock_sleep):
    config = RetryConfig(max_attempts=4, jitter=False)

    @with_retry(config=config)
    def failing_call():
        # Fails 3 times, succeeds on 4th
        pass

    failing_call()

    # Verify sleep was called 3 times (between attempts)
    assert mock_sleep.call_count == 3

    # Verify exponential progression
    wait_times = [call[0][0] for call in mock_sleep.call_args_list]
    assert wait_times == [1, 2, 4]  # 2^0, 2^1, 2^2
```

**Benefits**:
- ✅ Tests run instantly (no actual sleeping)
- ✅ Can verify exact wait times
- ✅ More reliable (no timing-dependent flakiness)

**Lesson**: Use mocking for time-dependent tests. Don't actually wait during unit tests.

### 6. Keyword-Based Error Classification

**The Problem**:
Different APIs return different error messages for the same error type:
- Gemini: "Resource exhausted: Quota exceeded"
- Claude: "Rate limit exceeded. Retry in 30s"
- OpenAI: "429: Too many requests"

**The Solution**:
Classify errors based on keywords in the message:
```python
def classify_api_error(error_message: str) -> Exception:
    msg_lower = error_message.lower()

    if any(kw in msg_lower for kw in ["rate limit", "too many requests", "retry after"]):
        return RateLimitError(error_message)

    if any(kw in msg_lower for kw in ["timeout", "timed out", "deadline exceeded"]):
        return TimeoutError(error_message)

    # ... more patterns
```

**Benefits**:
- ✅ Works across different APIs
- ✅ Handles unexpected error message formats
- ✅ Easy to extend (just add more keywords)

**Trade-off**: Keyword matching is heuristic (not 100% reliable), but good enough in practice.

**Lesson**: When integrating with multiple APIs, use flexible error classification based on keywords rather than exact string matching.

### 7. Context Manager for Non-Decorator Cases

**The Problem**:
Decorators don't work for all scenarios:
- Need retry logic inside a function (not for the whole function)
- Complex control flow with multiple retry points
- Want to log attempt numbers

**The Solution**:
Provide a context manager for manual retry control:
```python
with RetryContext(max_attempts=3) as retry:
    for attempt in retry:
        try:
            result = api_call()
            break  # Success!
        except Exception as e:
            if not retry.should_retry(e):
                raise  # Non-retryable
            logger.warning(f"Attempt {attempt}/{retry.max_attempts} failed: {e}")
            # Will automatically wait and retry
```

**Benefits**:
- ✅ More control (can log attempt numbers, customize behavior per attempt)
- ✅ Works for partial retry (only retry specific operation, not whole function)
- ✅ Explicit (clear which code is being retried)

**Lesson**: Provide both decorator and context manager patterns. Decorators for simple cases, context managers for complex control flow.

### 8. Tenacity Over Manual Implementation

**Decision**: Use Tenacity library instead of implementing retry logic manually

**Rationale**:
- ✅ Battle-tested (100k+ weekly downloads)
- ✅ Handles edge cases we'd miss (thread safety, async support)
- ✅ Flexible configuration
- ✅ Built-in exponential backoff with jitter
- ✅ Well-documented
- ✅ Actively maintained

**Trade-off**: External dependency, but the benefits far outweigh the cost.

**Alternatives Considered**:
- **backoff library**: Less flexible configuration
- **Manual implementation**: Too much work, error-prone
- **retry library**: Less popular, fewer features

**Lesson**: Don't reinvent the wheel for cross-cutting concerns like retry logic. Use a well-established library and focus on your domain logic.

### 9. Separate Retry Logic from Business Logic

**Anti-pattern**:
```python
def gemini_extract(transcript: str) -> dict:
    for attempt in range(3):
        try:
            response = model.generate_content(transcript)
            return parse_response(response)
        except Exception as e:
            if "rate limit" in str(e):
                time.sleep(2 ** attempt)
            else:
                raise
```

**Problems**:
- ❌ Retry logic mixed with business logic
- ❌ Hard to test in isolation
- ❌ Can't reuse retry logic
- ❌ Violates Single Responsibility Principle

**Better Approach**:
```python
@with_api_retry(max_attempts=3)
def gemini_extract(transcript: str) -> dict:
    response = model.generate_content(transcript)
    return parse_response(response)
```

**Benefits**:
- ✅ Clean separation of concerns
- ✅ Reusable retry logic
- ✅ Easy to test
- ✅ Easy to configure

**Lesson**: Use decorators to separate retry logic from business logic. This improves readability, testability, and reusability.

### 10. 3 Attempts is the Sweet Spot

**Analysis**:
```
1 attempt: No retry (50% of transient failures result in error)
2 attempts: 1 retry (catches ~80% of transient failures)
3 attempts: 2 retries (catches ~95% of transient failures)
4 attempts: 3 retries (catches ~98% of transient failures)
5 attempts: 4 retries (catches ~99% of transient failures)
```

**Decision**: Default to 3 attempts (2 retries)

**Rationale**:
- Most transient failures resolve within 1-2 retries
- Diminishing returns after 3 attempts
- 3 attempts = ~8 seconds total wait (1s + 2s + 4s)
- 5 attempts = ~32 seconds total wait (too long for most cases)

**Exception**: Rate limit heavy endpoints use 5 attempts (rate limits can be persistent)

**Lesson**: 3 attempts is a good default for most retry scenarios. It balances reliability with performance. Use more attempts only for specific use cases like rate limits.

## Architecture Patterns

### 1. Configuration Over Hard-Coding

**Pattern**: Centralized configuration object that's easy to override
```python
DEFAULT_RETRY_CONFIG = RetryConfig(...)
TEST_RETRY_CONFIG = RetryConfig(...)

def with_retry(config=None):
    config = config or DEFAULT_RETRY_CONFIG
    # ...
```

**Benefits**:
- Easy to customize per environment (dev, test, prod)
- Easy to override for specific use cases
- Single source of truth

**Lesson**: Make retry behavior configurable, not hardcoded.

### 2. Fail Fast for Non-Retryable Errors

**Pattern**: Distinguish between retryable and non-retryable errors
```python
if isinstance(error, NonRetryableError):
    raise  # Don't waste time retrying
```

**Benefits**:
- ✅ Faster feedback for user errors (auth, invalid requests)
- ✅ Don't waste API quota on retries that won't work
- ✅ Clearer error messages (not buried under retry logs)

**Lesson**: Not all errors should be retried. Fail fast for errors that require user action.

### 3. Logging for Observability

**Pattern**: Log retry attempts for debugging
```python
def log_retry_attempt(retry_state):
    if retry_state.outcome.failed:
        exception = retry_state.outcome.exception()
        logger.warning(
            f"Retry attempt {retry_state.attempt_number} failed: {exception}. "
            f"Waiting {retry_state.next_action.sleep} seconds before next attempt."
        )
```

**Benefits**:
- ✅ Visibility into retry behavior
- ✅ Helps debug rate limit issues
- ✅ Can track retry success rates

**Lesson**: Log retry attempts at WARNING level. This helps diagnose issues in production without cluttering logs (since most requests succeed).

## Testing Strategies

### 1. Fast Test Configuration Pattern

**Pattern**: Separate test config that's orders of magnitude faster
```python
# Production
DEFAULT_RETRY_CONFIG = RetryConfig(max_wait_seconds=60, min_wait_seconds=1)

# Testing
TEST_RETRY_CONFIG = RetryConfig(max_wait_seconds=0.1, min_wait_seconds=0.01)
```

**Application**: Use pytest fixture to monkeypatch globally
```python
@pytest.fixture(autouse=True)
def fast_retry_config(monkeypatch):
    monkeypatch.setattr("module.DEFAULT_RETRY_CONFIG", TEST_RETRY_CONFIG)
```

**Lesson**: Make tests 100-1000x faster by using minimal delays in test configuration.

### 2. Mock Time for Timing Tests

**Pattern**: Use `@patch('time.sleep')` to test timing logic without waiting
```python
@patch('time.sleep')
def test_exponential_backoff(mock_sleep):
    # Test retry logic...
    # Verify sleep calls without actually sleeping
    assert mock_sleep.call_count == 3
```

**Lesson**: Never use actual `time.sleep()` in unit tests. Mock it instead.

### 3. Test Both Success and Failure Paths

**Pattern**: Test both eventual success (after retries) and eventual failure (after max attempts)
```python
def test_retry_until_success():
    # Succeeds on 3rd attempt
    assert call_count == 3

def test_max_attempts_reached():
    # Fails all 3 attempts
    with pytest.raises(RateLimitError):
        always_fails()
    assert call_count == 3  # Verify it tried max_attempts times
```

**Lesson**: Test both the happy path (retries succeed) and the failure path (retries exhausted).

## Common Pitfalls

### 1. ❌ Retrying Non-Retryable Errors

**Mistake**: Retrying authentication errors, invalid requests, etc.
```python
# Bad: Retries all exceptions
@with_retry()
def api_call():
    raise AuthenticationError("Invalid API key")
```

**Fix**: Only retry retryable errors
```python
@with_retry(retry_on=(RateLimitError, TimeoutError, ConnectionError, ServerError))
def api_call():
    raise AuthenticationError("Invalid API key")  # Won't retry, fails immediately
```

**Lesson**: Be explicit about which errors are retryable. Don't blanket retry all exceptions.

### 2. ❌ Forgetting Jitter in Production

**Mistake**: Disabling jitter for "predictable" timing
```python
config = RetryConfig(jitter=False)  # ❌ Bad in production
```

**Impact**: Thundering herd, poor success rates with concurrent clients

**Fix**: Always enable jitter in production
```python
config = RetryConfig(jitter=True)  # ✅ Good
```

**Lesson**: Jitter is critical for production environments. Only disable it in single-threaded tests.

### 3. ❌ Too Many Retry Attempts

**Mistake**: Using 10+ retries "to be safe"
```python
config = RetryConfig(max_attempts=10)  # ❌ Overkill
```

**Impact**:
- Wastes API quota
- Slow failure (can take minutes)
- User frustration (long waits)

**Fix**: Use 3-5 attempts max
```python
config = RetryConfig(max_attempts=3)  # ✅ Good balance
```

**Lesson**: More retries ≠ better. After 3-5 attempts, the error is likely persistent, not transient.

### 4. ❌ Not Testing Retry Logic

**Mistake**: Only testing the happy path (no failures)

**Impact**: Retry logic breaks in production and nobody notices until rate limits hit

**Fix**: Test both success after retries and failure after max attempts
```python
def test_retry_on_rate_limit():
    # Simulates rate limit on first 2 attempts, success on 3rd
    pass

def test_max_attempts_exhausted():
    # Simulates failure on all 3 attempts
    pass
```

**Lesson**: Explicitly test retry behavior. Don't assume decorators work without testing them.

### 5. ❌ Mixing Retry Logic with Business Logic

**Mistake**: Implementing retry logic inline
```python
def api_call():
    for attempt in range(3):
        try:
            return do_stuff()
        except Exception:
            time.sleep(2 ** attempt)
```

**Problems**:
- Hard to test
- Hard to configure
- Violates DRY (copy-paste across functions)

**Fix**: Use decorators
```python
@with_api_retry()
def api_call():
    return do_stuff()
```

**Lesson**: Keep retry logic separate from business logic. Use decorators or context managers.

## Key Takeaways

1. **Jitter is mandatory** for production environments with concurrent clients
2. **Separate test config** enables fast tests (305x speedup in our case)
3. **Exception hierarchy > flags** for categorizing errors
4. **3 attempts** is the sweet spot for most retry scenarios
5. **Use Tenacity** instead of rolling your own retry logic
6. **Mock `time.sleep`** for timing tests
7. **Fail fast** for non-retryable errors (auth, invalid requests)
8. **Log retry attempts** at WARNING level for observability
9. **Test both success and failure paths** for retry logic
10. **Separate retry logic from business logic** using decorators

## Impact

**Reliability**: Handles transient failures gracefully (95-100% success rate)
**Performance**: Fast tests (<1 second vs 3+ minutes)
**Maintainability**: Reusable retry logic across all API calls
**Observability**: Retry attempts logged for debugging

## Future Improvements

1. **Adaptive Retry**: Learn from past failures to optimize retry strategy
2. **Circuit Breaker**: Stop retrying when service is consistently down
3. **Retry Budget**: Limit total retries per time period
4. **Metrics**: Track retry success rates, average wait times
5. **User Configuration**: Allow users to customize retry behavior per API

## References

- [Exponential Backoff and Jitter - AWS](https://aws.amazon.com/blogs/architecture/exponential-backoff-and-jitter/)
- [Tenacity Documentation](https://tenacity.readthedocs.io/)
- [Google Cloud Retry Guidance](https://cloud.google.com/apis/design/errors#error_retries)
- [Devlog](../devlog/2025-11-12-phase-5-unit-6-error-handling.md)
- [Experiment Log](../experiments/2025-11-12-retry-timing-analysis.md)
