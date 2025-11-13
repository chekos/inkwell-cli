"""Error handling and retry utilities for API calls.

Implements exponential backoff with jitter for transient failures.
Based on ADR-027: Retry and Error Handling Strategy.
"""

import logging
import random
from collections.abc import Callable
from functools import wraps

from tenacity import (
    RetryCallState,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

logger = logging.getLogger(__name__)


# Error classification: Which errors should trigger retries?

class RetryableError(Exception):
    """Base class for errors that should trigger retries."""

    pass


class RateLimitError(RetryableError):
    """API rate limit exceeded."""

    pass


class TimeoutError(RetryableError):
    """Request timeout."""

    pass


class ConnectionError(RetryableError):
    """Network connection error."""

    pass


class ServerError(RetryableError):
    """Server-side error (5xx)."""

    pass


class NonRetryableError(Exception):
    """Base class for errors that should NOT trigger retries."""

    pass


class AuthenticationError(NonRetryableError):
    """Invalid API key or authentication failed."""

    pass


class InvalidRequestError(NonRetryableError):
    """Invalid request parameters (4xx)."""

    pass


class QuotaExceededError(NonRetryableError):
    """API quota exceeded (different from rate limit)."""

    pass


# Retry configuration

class RetryConfig:
    """Configuration for retry behavior."""

    def __init__(
        self,
        max_attempts: int = 3,
        max_wait_seconds: int = 60,
        min_wait_seconds: int = 1,
        jitter: bool = True,
    ):
        """Initialize retry configuration.

        Args:
            max_attempts: Maximum number of attempts (including initial)
            max_wait_seconds: Maximum wait time between retries
            min_wait_seconds: Minimum wait time between retries
            jitter: Whether to add jitter to wait times
        """
        self.max_attempts = max_attempts
        self.max_wait_seconds = max_wait_seconds
        self.min_wait_seconds = min_wait_seconds
        self.jitter = jitter


# Default retry configuration
DEFAULT_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    max_wait_seconds=60,
    min_wait_seconds=1,
    jitter=True,
)

# Fast configuration for testing (minimal delays)
TEST_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    max_wait_seconds=0.1,
    min_wait_seconds=0.01,
    jitter=False,
)


def log_retry_attempt(retry_state: RetryCallState) -> None:
    """Log retry attempts for debugging.

    Args:
        retry_state: Tenacity retry state
    """
    if retry_state.outcome and retry_state.outcome.failed:
        exception = retry_state.outcome.exception()
        attempt_number = retry_state.attempt_number

        logger.warning(
            f"Retry attempt {attempt_number} failed: {type(exception).__name__}: {exception}"
        )


def with_retry(
    config: RetryConfig | None = None,
    retry_on: tuple[type[Exception], ...] | None = None,
) -> Callable:
    """Decorator for adding retry logic with exponential backoff.

    Usage:
        @with_retry()
        def api_call():
            # Make API call
            pass

        @with_retry(config=RetryConfig(max_attempts=5))
        def important_call():
            # Make important API call with more retries
            pass

        @with_retry(retry_on=(ConnectionError, TimeoutError))
        def network_call():
            # Only retry on network errors
            pass

    Args:
        config: Retry configuration (uses DEFAULT_RETRY_CONFIG if None)
        retry_on: Tuple of exception types to retry on (uses all RetryableError subclasses if None)

    Returns:
        Decorated function with retry logic
    """
    config = config or DEFAULT_RETRY_CONFIG

    # Default: retry on all RetryableError subclasses
    if retry_on is None:
        retry_on = (
            RateLimitError,
            TimeoutError,
            ConnectionError,
            ServerError,
        )

    def decorator(func: Callable) -> Callable:
        # Create retry decorator with exponential backoff + jitter
        retry_decorator = retry(
            stop=stop_after_attempt(config.max_attempts),
            wait=wait_exponential_jitter(
                initial=config.min_wait_seconds,
                max=config.max_wait_seconds,
                jitter=config.max_wait_seconds if config.jitter else 0,
            ),
            retry=retry_if_exception_type(retry_on),
            before_sleep=log_retry_attempt,
            reraise=True,
        )

        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return retry_decorator(func)(*args, **kwargs)
            except Exception as e:
                # Log final failure
                logger.error(
                    f"Function {func.__name__} failed after {config.max_attempts} attempts: "
                    f"{type(e).__name__}: {e}"
                )
                raise

        return wrapper

    return decorator


# Specialized retry decorators for common scenarios

def with_api_retry(max_attempts: int = 3, config: RetryConfig | None = None) -> Callable:
    """Retry decorator for API calls (rate limits, timeouts, server errors).

    Args:
        max_attempts: Maximum number of attempts
        config: Custom retry configuration (uses DEFAULT_RETRY_CONFIG if None)

    Returns:
        Decorated function with API retry logic
    """
    if config is None:
        config = RetryConfig(
            max_attempts=max_attempts,
            max_wait_seconds=DEFAULT_RETRY_CONFIG.max_wait_seconds,
            min_wait_seconds=DEFAULT_RETRY_CONFIG.min_wait_seconds,
            jitter=DEFAULT_RETRY_CONFIG.jitter,
        )
    return with_retry(
        config=config,
        retry_on=(RateLimitError, TimeoutError, ConnectionError, ServerError),
    )


def with_network_retry(max_attempts: int = 3, config: RetryConfig | None = None) -> Callable:
    """Retry decorator for network calls (timeouts, connection errors).

    Args:
        max_attempts: Maximum number of attempts
        config: Custom retry configuration (uses DEFAULT_RETRY_CONFIG if None)

    Returns:
        Decorated function with network retry logic
    """
    if config is None:
        config = RetryConfig(
            max_attempts=max_attempts,
            max_wait_seconds=DEFAULT_RETRY_CONFIG.max_wait_seconds,
            min_wait_seconds=DEFAULT_RETRY_CONFIG.min_wait_seconds,
            jitter=DEFAULT_RETRY_CONFIG.jitter,
        )
    return with_retry(
        config=config,
        retry_on=(TimeoutError, ConnectionError),
    )


def with_rate_limit_retry(max_attempts: int = 5, config: RetryConfig | None = None) -> Callable:
    """Retry decorator specifically for rate limit errors.

    Uses more attempts since rate limits are common with APIs.

    Args:
        max_attempts: Maximum number of attempts (default 5)
        config: Custom retry configuration (uses DEFAULT_RETRY_CONFIG if None)

    Returns:
        Decorated function with rate limit retry logic
    """
    if config is None:
        config = RetryConfig(
            max_attempts=max_attempts,
            max_wait_seconds=DEFAULT_RETRY_CONFIG.max_wait_seconds,
            min_wait_seconds=DEFAULT_RETRY_CONFIG.min_wait_seconds,
            jitter=DEFAULT_RETRY_CONFIG.jitter,
        )
    return with_retry(
        config=config,
        retry_on=(RateLimitError,),
    )


# Error classification helpers

def classify_http_error(status_code: int, error_message: str = "") -> Exception:
    """Classify HTTP error into retryable or non-retryable.

    Args:
        status_code: HTTP status code
        error_message: Error message from API

    Returns:
        Appropriate exception instance

    Example:
        try:
            response = requests.get(url)
            response.raise_for_status()
        except requests.HTTPError as e:
            raise classify_http_error(e.response.status_code, str(e))
    """
    # 429 - Rate limit
    if status_code == 429:
        return RateLimitError(f"Rate limit exceeded: {error_message}")

    # 5xx - Server errors (retryable)
    if 500 <= status_code < 600:
        return ServerError(f"Server error (HTTP {status_code}): {error_message}")

    # 408 - Request timeout
    if status_code == 408:
        return TimeoutError(f"Request timeout: {error_message}")

    # 401, 403 - Authentication errors (non-retryable)
    if status_code in (401, 403):
        return AuthenticationError(f"Authentication failed (HTTP {status_code}): {error_message}")

    # 400, 404, 422 - Client errors (non-retryable)
    if 400 <= status_code < 500:
        return InvalidRequestError(f"Invalid request (HTTP {status_code}): {error_message}")

    # Default: non-retryable
    return NonRetryableError(f"HTTP error {status_code}: {error_message}")


def classify_api_error(exception: Exception) -> Exception:
    """Classify generic API exception into retryable or non-retryable.

    Args:
        exception: Exception from API call

    Returns:
        Classified exception (may be same exception or reclassified)

    Example:
        try:
            api_call()
        except Exception as e:
            raise classify_api_error(e)
    """
    error_str = str(exception).lower()

    # Rate limit indicators
    if "rate limit" in error_str or "too many requests" in error_str:
        return RateLimitError(str(exception))

    # Timeout indicators
    if "timeout" in error_str or "timed out" in error_str:
        return TimeoutError(str(exception))

    # Connection indicators
    if "connection" in error_str or "network" in error_str:
        return ConnectionError(str(exception))

    # Authentication indicators
    if "authentication" in error_str or "unauthorized" in error_str or "api key" in error_str:
        return AuthenticationError(str(exception))

    # Quota indicators
    if "quota" in error_str or "limit exceeded" in error_str:
        return QuotaExceededError(str(exception))

    # If we can't classify, assume non-retryable to be safe
    return NonRetryableError(str(exception))


# Context manager for retry operations

class RetryContext:
    """Context manager for operations that need retry logic.

    Example:
        with RetryContext(max_attempts=3) as retry:
            for attempt in retry:
                try:
                    result = api_call()
                    break  # Success, exit loop
                except Exception as e:
                    if not retry.should_retry(e):
                        raise  # Non-retryable, propagate
                    # Retryable, continue to next attempt
    """

    def __init__(self, max_attempts: int = 3, config: RetryConfig | None = None):
        """Initialize retry context.

        Args:
            max_attempts: Maximum number of attempts
            config: Retry configuration
        """
        self.max_attempts = max_attempts
        self.config = config or DEFAULT_RETRY_CONFIG
        self.attempt = 0

    def __enter__(self):
        """Enter context."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context."""
        return False  # Don't suppress exceptions

    def __iter__(self):
        """Iterate over retry attempts."""
        for i in range(self.max_attempts):
            self.attempt = i + 1
            yield self.attempt

            # Wait before next attempt (except after last attempt)
            if i < self.max_attempts - 1:
                self._wait()

    def should_retry(self, exception: Exception) -> bool:
        """Check if exception is retryable.

        Args:
            exception: Exception to check

        Returns:
            True if should retry, False otherwise
        """
        return isinstance(
            exception,
            (RateLimitError, TimeoutError, ConnectionError, ServerError),
        )

    def _wait(self):
        """Wait before next retry attempt (exponential backoff with jitter)."""
        # Exponential backoff: 2^attempt seconds
        base_wait = min(2 ** self.attempt, self.config.max_wait_seconds)

        # Add jitter: random value between 0 and base_wait
        if self.config.jitter:
            jitter = random.uniform(0, base_wait)
            wait_time = base_wait + jitter
        else:
            wait_time = base_wait

        # Cap at max_wait_seconds
        wait_time = min(wait_time, self.config.max_wait_seconds)

        logger.debug(f"Waiting {wait_time:.2f}s before retry attempt {self.attempt + 1}")

        import time
        time.sleep(wait_time)
