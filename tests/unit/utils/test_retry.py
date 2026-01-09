"""Tests for retry and error handling utilities."""

from unittest.mock import patch

import pytest

from inkwell.utils.retry import (
    TEST_RETRY_CONFIG,
    AuthenticationError,
    ConnectionError,
    InvalidRequestError,
    QuotaExceededError,
    RateLimitError,
    RetryConfig,
    ServerError,
    TimeoutError,
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


class TestRetryConfig:
    """Test retry configuration."""

    def test_default_config(self):
        """Test default retry configuration."""
        config = RetryConfig()
        assert config.max_attempts == 3
        assert config.max_wait_seconds == 10  # Updated from 60 to 10 seconds
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


class TestExponentialBackoff:
    """Test exponential backoff timing."""

    @patch("time.sleep")
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

    @patch("time.sleep")
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
