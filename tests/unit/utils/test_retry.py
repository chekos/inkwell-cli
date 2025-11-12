"""Tests for retry and error handling utilities."""

import time
from unittest.mock import Mock, patch

import pytest

from inkwell.utils.retry import (
    AuthenticationError,
    ConnectionError,
    InvalidRequestError,
    NonRetryableError,
    QuotaExceededError,
    RateLimitError,
    RetryConfig,
    RetryContext,
    ServerError,
    TEST_RETRY_CONFIG,
    TimeoutError,
    classify_api_error,
    classify_http_error,
    with_api_retry,
    with_network_retry,
    with_rate_limit_retry,
    with_retry,
)


# Pytest fixture to use fast retry config in tests
@pytest.fixture(autouse=True)
def fast_retry_config(monkeypatch):
    """Use fast retry configuration for all tests to avoid long delays."""
    monkeypatch.setattr("inkwell.utils.retry.DEFAULT_RETRY_CONFIG", TEST_RETRY_CONFIG)


class TestErrorClassification:
    """Test error classification."""

    def test_retryable_errors(self):
        """Test retryable error types."""
        assert issubclass(RateLimitError, Exception)
        assert issubclass(TimeoutError, Exception)
        assert issubclass(ConnectionError, Exception)
        assert issubclass(ServerError, Exception)

    def test_non_retryable_errors(self):
        """Test non-retryable error types."""
        assert issubclass(AuthenticationError, Exception)
        assert issubclass(InvalidRequestError, Exception)
        assert issubclass(QuotaExceededError, Exception)


class TestClassifyHttpError:
    """Test HTTP error classification."""

    def test_rate_limit_429(self):
        """Test 429 classified as rate limit."""
        error = classify_http_error(429, "Too many requests")
        assert isinstance(error, RateLimitError)
        assert "Rate limit exceeded" in str(error)

    def test_server_errors_5xx(self):
        """Test 5xx classified as server errors."""
        for status_code in [500, 502, 503, 504]:
            error = classify_http_error(status_code, "Server error")
            assert isinstance(error, ServerError)

    def test_timeout_408(self):
        """Test 408 classified as timeout."""
        error = classify_http_error(408, "Request timeout")
        assert isinstance(error, TimeoutError)

    def test_auth_errors_401_403(self):
        """Test 401/403 classified as authentication errors."""
        for status_code in [401, 403]:
            error = classify_http_error(status_code, "Unauthorized")
            assert isinstance(error, AuthenticationError)

    def test_client_errors_4xx(self):
        """Test other 4xx classified as invalid request."""
        for status_code in [400, 404, 422]:
            error = classify_http_error(status_code, "Bad request")
            assert isinstance(error, InvalidRequestError)

    def test_unknown_error(self):
        """Test unknown status codes classified as non-retryable."""
        error = classify_http_error(999, "Unknown error")
        assert isinstance(error, NonRetryableError)


class TestClassifyApiError:
    """Test API error classification."""

    def test_rate_limit_keywords(self):
        """Test rate limit keyword detection."""
        error = classify_api_error(Exception("rate limit exceeded"))
        assert isinstance(error, RateLimitError)

        error = classify_api_error(Exception("too many requests"))
        assert isinstance(error, RateLimitError)

    def test_timeout_keywords(self):
        """Test timeout keyword detection."""
        error = classify_api_error(Exception("request timeout"))
        assert isinstance(error, TimeoutError)

        error = classify_api_error(Exception("operation timed out"))
        assert isinstance(error, TimeoutError)

    def test_connection_keywords(self):
        """Test connection keyword detection."""
        error = classify_api_error(Exception("connection refused"))
        assert isinstance(error, ConnectionError)

        error = classify_api_error(Exception("network error"))
        assert isinstance(error, ConnectionError)

    def test_auth_keywords(self):
        """Test authentication keyword detection."""
        error = classify_api_error(Exception("authentication failed"))
        assert isinstance(error, AuthenticationError)

        error = classify_api_error(Exception("invalid api key"))
        assert isinstance(error, AuthenticationError)

    def test_quota_keywords(self):
        """Test quota keyword detection."""
        error = classify_api_error(Exception("quota exceeded"))
        assert isinstance(error, QuotaExceededError)

    def test_unknown_error(self):
        """Test unknown errors classified as non-retryable."""
        error = classify_api_error(Exception("something went wrong"))
        assert isinstance(error, NonRetryableError)


class TestRetryConfig:
    """Test retry configuration."""

    def test_default_config(self):
        """Test default retry configuration."""
        config = RetryConfig()
        assert config.max_attempts == 3
        assert config.max_wait_seconds == 60
        assert config.min_wait_seconds == 1
        assert config.jitter is True

    def test_custom_config(self):
        """Test custom retry configuration."""
        config = RetryConfig(
            max_attempts=5,
            max_wait_seconds=120,
            min_wait_seconds=2,
            jitter=False,
        )
        assert config.max_attempts == 5
        assert config.max_wait_seconds == 120
        assert config.min_wait_seconds == 2
        assert config.jitter is False


class TestWithRetryDecorator:
    """Test with_retry decorator."""

    def test_success_no_retry(self):
        """Test successful call doesn't retry."""
        call_count = 0

        @with_retry()
        def successful_call():
            nonlocal call_count
            call_count += 1
            return "success"

        result = successful_call()
        assert result == "success"
        assert call_count == 1

    def test_retry_on_retryable_error(self):
        """Test retries on retryable errors."""
        call_count = 0

        # Use fast config for testing
        test_config = RetryConfig(
            max_attempts=3,
            max_wait_seconds=TEST_RETRY_CONFIG.max_wait_seconds,
            min_wait_seconds=TEST_RETRY_CONFIG.min_wait_seconds,
            jitter=False,
        )

        @with_retry(config=test_config)
        def failing_call():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RateLimitError("Rate limit")
            return "success"

        result = failing_call()
        assert result == "success"
        assert call_count == 3

    def test_no_retry_on_non_retryable_error(self):
        """Test doesn't retry on non-retryable errors."""
        call_count = 0

        @with_retry()
        def auth_error_call():
            nonlocal call_count
            call_count += 1
            raise AuthenticationError("Invalid API key")

        with pytest.raises(AuthenticationError):
            auth_error_call()

        assert call_count == 1  # No retries

    def test_max_attempts_reached(self):
        """Test raises error after max attempts."""
        call_count = 0

        # Use fast config for testing
        test_config = RetryConfig(
            max_attempts=3,
            max_wait_seconds=TEST_RETRY_CONFIG.max_wait_seconds,
            min_wait_seconds=TEST_RETRY_CONFIG.min_wait_seconds,
            jitter=False,
        )

        @with_retry(config=test_config)
        def always_fails():
            nonlocal call_count
            call_count += 1
            raise RateLimitError("Rate limit")

        with pytest.raises(RateLimitError):
            always_fails()

        assert call_count == 3

    def test_custom_retry_on(self):
        """Test custom exception types for retry."""
        call_count = 0

        @with_retry(retry_on=(TimeoutError,))
        def timeout_only():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise TimeoutError("Timeout")
            return "success"

        result = timeout_only()
        assert result == "success"
        assert call_count == 2

        # RateLimitError should not retry
        call_count = 0

        @with_retry(retry_on=(TimeoutError,))
        def rate_limit_not_retried():
            nonlocal call_count
            call_count += 1
            raise RateLimitError("Rate limit")

        with pytest.raises(RateLimitError):
            rate_limit_not_retried()

        assert call_count == 1


class TestSpecializedRetryDecorators:
    """Test specialized retry decorators."""

    def test_with_api_retry(self):
        """Test API retry decorator."""
        call_count = 0

        @with_api_retry(max_attempts=3)
        def api_call():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise RateLimitError("Rate limit")
            return "success"

        result = api_call()
        assert result == "success"
        assert call_count == 2

    def test_with_network_retry(self):
        """Test network retry decorator."""
        call_count = 0

        @with_network_retry(max_attempts=3)
        def network_call():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("Connection failed")
            return "success"

        result = network_call()
        assert result == "success"
        assert call_count == 2

    def test_with_rate_limit_retry(self):
        """Test rate limit retry decorator (5 attempts by default)."""
        call_count = 0

        @with_rate_limit_retry()
        def rate_limited_call():
            nonlocal call_count
            call_count += 1
            if call_count < 4:
                raise RateLimitError("Rate limit")
            return "success"

        result = rate_limited_call()
        assert result == "success"
        assert call_count == 4


class TestRetryContext:
    """Test retry context manager."""

    def test_successful_first_attempt(self):
        """Test success on first attempt."""
        attempt_count = 0

        with RetryContext(max_attempts=3) as retry:
            for attempt in retry:
                attempt_count = attempt
                # Success on first attempt
                break

        assert attempt_count == 1

    def test_retry_on_retryable_error(self):
        """Test retries on retryable errors."""
        attempts = []

        with RetryContext(max_attempts=3) as retry:
            for attempt in retry:
                attempts.append(attempt)
                try:
                    if attempt < 3:
                        raise RateLimitError("Rate limit")
                    # Success on third attempt
                    break
                except RateLimitError as e:
                    if not retry.should_retry(e):
                        raise
                    # Continue to next attempt

        assert attempts == [1, 2, 3]

    def test_no_retry_on_non_retryable(self):
        """Test stops immediately on non-retryable errors."""
        attempts = []

        with pytest.raises(AuthenticationError):
            with RetryContext(max_attempts=3) as retry:
                for attempt in retry:
                    attempts.append(attempt)
                    raise AuthenticationError("Invalid API key")

        assert attempts == [1]

    def test_should_retry_method(self):
        """Test should_retry classification."""
        retry = RetryContext()

        # Retryable
        assert retry.should_retry(RateLimitError("Rate limit"))
        assert retry.should_retry(TimeoutError("Timeout"))
        assert retry.should_retry(ConnectionError("Connection"))
        assert retry.should_retry(ServerError("Server error"))

        # Non-retryable
        assert not retry.should_retry(AuthenticationError("Auth failed"))
        assert not retry.should_retry(InvalidRequestError("Bad request"))
        assert not retry.should_retry(QuotaExceededError("Quota exceeded"))


class TestExponentialBackoff:
    """Test exponential backoff timing."""

    @patch('time.sleep')
    def test_backoff_timing_without_jitter(self, mock_sleep):
        """Test backoff timing without jitter."""
        config = RetryConfig(max_attempts=4, jitter=False)
        call_count = 0

        @with_retry(config=config)
        def failing_call():
            nonlocal call_count
            call_count += 1
            if call_count < 4:
                raise RateLimitError("Rate limit")
            return "success"

        result = failing_call()
        assert result == "success"

        # Should have 3 sleep calls (after attempts 1, 2, 3)
        assert mock_sleep.call_count == 3

    @patch('time.sleep')
    def test_backoff_max_wait_time(self, mock_sleep):
        """Test backoff respects max wait time."""
        config = RetryConfig(max_attempts=10, max_wait_seconds=10, jitter=False)
        call_count = 0

        @with_retry(config=config)
        def failing_call():
            nonlocal call_count
            call_count += 1
            if call_count < 5:
                raise RateLimitError("Rate limit")
            return "success"

        result = failing_call()
        assert result == "success"

        # All sleep calls should be <= max_wait_seconds
        for call in mock_sleep.call_args_list:
            wait_time = call[0][0]
            assert wait_time <= 10


class TestRetryDecoratorsIntegration:
    """Test retry decorators with realistic scenarios."""

    def test_gemini_api_simulation(self):
        """Simulate Gemini API with rate limits."""
        call_count = 0
        rate_limit_until = 2  # Fail first 2 attempts

        @with_api_retry(max_attempts=3)
        def gemini_call():
            nonlocal call_count
            call_count += 1

            if call_count <= rate_limit_until:
                raise RateLimitError("Gemini rate limit exceeded")

            return {"result": "success"}

        result = gemini_call()
        assert result["result"] == "success"
        assert call_count == 3

    def test_network_timeout_simulation(self):
        """Simulate network timeout with eventual success."""
        call_count = 0

        @with_network_retry(max_attempts=3)
        def download_audio():
            nonlocal call_count
            call_count += 1

            if call_count < 2:
                raise TimeoutError("Download timeout")

            return b"audio data"

        result = download_audio()
        assert result == b"audio data"
        assert call_count == 2

    def test_authentication_failure_no_retry(self):
        """Simulate authentication failure (should not retry)."""
        call_count = 0

        @with_api_retry(max_attempts=3)
        def invalid_api_key():
            nonlocal call_count
            call_count += 1
            raise AuthenticationError("Invalid API key")

        with pytest.raises(AuthenticationError):
            invalid_api_key()

        # Should only try once (no retries for auth errors)
        assert call_count == 1
