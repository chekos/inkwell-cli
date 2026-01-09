"""Error handling and retry utilities for API calls.

Implements exponential backoff with jitter for transient failures.
Based on ADR-027: Retry and Error Handling Strategy.
"""

import logging
from collections.abc import Callable
from functools import wraps
from typing import Any

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
        max_wait_seconds: int | float = 10,
        min_wait_seconds: int | float = 1,
        jitter: bool = True,
    ):
        """Initialize retry configuration.

        Args:
            max_attempts: Maximum number of attempts (including initial)
            max_wait_seconds: Maximum wait time between retries (default: 10s)
            min_wait_seconds: Minimum wait time between retries (default: 1s)
            jitter: Whether to add ±25% jitter to wait times
        """
        self.max_attempts = max_attempts
        self.max_wait_seconds = max_wait_seconds
        self.min_wait_seconds = min_wait_seconds
        self.jitter = jitter


# Default retry configuration
DEFAULT_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    max_wait_seconds=10,  # Reduced from 60 to 10 seconds for better UX
    min_wait_seconds=1,
    jitter=True,
)

# Fast configuration for testing (minimal delays)
# Maintains same ratio as production config (10:1) but much faster
TEST_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    max_wait_seconds=0.1,  # 100ms max (vs 10s in production)
    min_wait_seconds=0.01,  # 10ms min (vs 1s in production)
    jitter=False,  # Disabled for deterministic test timing
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
        # Note: wait_exponential_jitter adds jitter as a random value between 0 and jitter parameter
        # To get ±25% jitter, we pass 25% of max wait time
        jitter_amount = config.max_wait_seconds * 0.25 if config.jitter else 0
        retry_decorator = retry(
            stop=stop_after_attempt(config.max_attempts),
            wait=wait_exponential_jitter(
                initial=config.min_wait_seconds,
                max=config.max_wait_seconds,
                jitter=jitter_amount,
            ),
            retry=retry_if_exception_type(retry_on),
            before_sleep=log_retry_attempt,
            reraise=True,
        )

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
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
