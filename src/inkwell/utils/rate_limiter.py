"""Rate limiting for API calls using token bucket algorithm."""

import time
import threading
from functools import wraps
from typing import Callable, Literal, ParamSpec, TypeVar

P = ParamSpec("P")
T = TypeVar("T")


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
        self.tokens = float(max_calls)  # Start with full bucket
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
            self.tokens = float(self.max_calls)
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
        "gemini": {"max_calls": 60, "period": 60},  # 60/minute
        "claude": {"max_calls": 50, "period": 60},  # 50/minute
        "youtube": {"max_calls": 100, "period": 60},  # 100/minute (generous)
    }

    if provider not in _rate_limiters:
        config = defaults.get(provider, {"max_calls": 30, "period": 60})
        _rate_limiters[provider] = RateLimiter(
            max_calls=max_calls or config["max_calls"],
            period_seconds=period_seconds or config["period"],
        )

    return _rate_limiters[provider]


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


def reset_all_rate_limiters() -> None:
    """Reset all rate limiters (for testing/debugging)."""
    global _rate_limiters
    _rate_limiters = {}
