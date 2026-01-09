"""Tests for rate limiting functionality."""

import time
from threading import Thread

from inkwell.utils.rate_limiter import RateLimiter, get_rate_limiter, reset_all_rate_limiters


class TestRateLimiter:
    """Test RateLimiter class."""

    def test_init(self):
        """Test rate limiter initialization."""
        limiter = RateLimiter(max_calls=10, period_seconds=60)
        assert limiter.max_calls == 10
        assert limiter.period == 60
        assert limiter.tokens == 10.0  # Should start with full bucket

    def test_acquire_blocking(self):
        """Test blocking token acquisition."""
        limiter = RateLimiter(max_calls=5, period_seconds=10)

        # First 5 calls should succeed immediately
        for _ in range(5):
            assert limiter.acquire(blocking=False)

        # 6th call should fail (no tokens)
        assert not limiter.acquire(blocking=False)

    def test_acquire_timeout(self):
        """Test timeout on token acquisition."""
        limiter = RateLimiter(max_calls=1, period_seconds=10)

        # Consume token
        assert limiter.acquire()

        # Next call times out
        start = time.time()
        assert not limiter.acquire(timeout=0.5)
        elapsed = time.time() - start

        # Should timeout around 0.5 seconds
        assert 0.4 < elapsed < 0.7

    def test_token_refill(self):
        """Test that tokens refill over time."""
        limiter = RateLimiter(max_calls=5, period_seconds=10)

        # Consume all tokens
        for _ in range(5):
            assert limiter.acquire(blocking=False)

        # Should have no tokens
        assert not limiter.acquire(blocking=False)

        # Wait for tokens to refill (2 seconds = 1 token at 5/10s rate)
        time.sleep(2.1)

        # Should now have ~1 token
        assert limiter.acquire(blocking=False)

        # But not 2 tokens
        assert not limiter.acquire(blocking=False)

    def test_reset(self):
        """Test resetting the rate limiter."""
        limiter = RateLimiter(max_calls=5, period_seconds=10)

        # Consume all tokens
        for _ in range(5):
            assert limiter.acquire(blocking=False)

        # Reset
        limiter.reset()

        # Should have full bucket again
        for _ in range(5):
            assert limiter.acquire(blocking=False)

    def test_thread_safety(self):
        """Test rate limiter is thread-safe."""
        limiter = RateLimiter(max_calls=10, period_seconds=1)
        acquired_count = []

        def try_acquire():
            if limiter.acquire(blocking=False):
                acquired_count.append(1)

        # Start 20 threads trying to acquire tokens
        threads = [Thread(target=try_acquire) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Only 10 should have succeeded
        assert len(acquired_count) == 10

    def test_burst_allowed(self):
        """Test that bursts are allowed up to bucket capacity."""
        limiter = RateLimiter(max_calls=10, period_seconds=60)

        # Should be able to make 10 calls immediately (burst)
        for _ in range(10):
            assert limiter.acquire(blocking=False)

        # But 11th fails
        assert not limiter.acquire(blocking=False)

    def test_rate_averaging(self):
        """Test that average rate is maintained over time."""
        limiter = RateLimiter(max_calls=5, period_seconds=1)

        # Make initial burst
        for _ in range(5):
            assert limiter.acquire(blocking=False)

        # Over 2 seconds, should be able to make ~10 more calls
        # (5 refilled per second)
        time.sleep(2.1)

        count = 0
        while limiter.acquire(blocking=False):
            count += 1
            if count > 15:  # Safety limit
                break

        # Should have gotten ~5 tokens (capped at max_calls)
        # The bucket refills to max capacity (5), not accumulates beyond it
        assert count == 5


class TestGetRateLimiter:
    """Test get_rate_limiter factory function."""

    def teardown_method(self):
        """Reset rate limiters after each test."""
        reset_all_rate_limiters()

    def test_get_gemini_limiter(self):
        """Test getting Gemini rate limiter."""
        limiter = get_rate_limiter("gemini")
        assert limiter.max_calls == 60  # Default for Gemini
        assert limiter.period == 60

    def test_get_claude_limiter(self):
        """Test getting Claude rate limiter."""
        limiter = get_rate_limiter("claude")
        assert limiter.max_calls == 50  # Default for Claude
        assert limiter.period == 60

    def test_get_youtube_limiter(self):
        """Test getting YouTube rate limiter."""
        limiter = get_rate_limiter("youtube")
        assert limiter.max_calls == 100  # Default for YouTube
        assert limiter.period == 60

    def test_custom_limits(self):
        """Test creating rate limiter with custom limits."""
        # First call creates with custom limits
        limiter = get_rate_limiter("gemini", max_calls=30, period_seconds=120)
        assert limiter.max_calls == 30
        assert limiter.period == 120

        # Second call returns same instance (singleton)
        limiter2 = get_rate_limiter("gemini", max_calls=60, period_seconds=60)
        assert limiter2 is limiter
        assert limiter2.max_calls == 30  # Still has original settings

    def test_singleton_per_provider(self):
        """Test that same limiter instance is returned for same provider."""
        limiter1 = get_rate_limiter("gemini")
        limiter2 = get_rate_limiter("gemini")
        assert limiter1 is limiter2

    def test_different_limiters_per_provider(self):
        """Test that different providers get different limiters."""
        gemini = get_rate_limiter("gemini")
        claude = get_rate_limiter("claude")
        assert gemini is not claude


class TestResetAllRateLimiters:
    """Test reset_all_rate_limiters function."""

    def test_reset_all(self):
        """Test resetting all rate limiters."""
        # Create and exhaust multiple limiters
        gemini = get_rate_limiter("gemini")
        claude = get_rate_limiter("claude")

        # Exhaust tokens
        for _ in range(60):
            gemini.acquire(blocking=False)
        for _ in range(50):
            claude.acquire(blocking=False)

        # Both should be exhausted
        assert not gemini.acquire(blocking=False)
        assert not claude.acquire(blocking=False)

        # Reset all (clears the dictionary)
        reset_all_rate_limiters()

        # Get fresh limiters
        gemini_new = get_rate_limiter("gemini")
        claude_new = get_rate_limiter("claude")

        # Should work again
        assert gemini_new.acquire(blocking=False)
        assert claude_new.acquire(blocking=False)


class TestIntegrationScenarios:
    """Test realistic integration scenarios."""

    def teardown_method(self):
        """Reset rate limiters after each test."""
        reset_all_rate_limiters()

    def test_prevents_runaway_api_calls(self):
        """Test that rate limiter prevents runaway API calls."""
        limiter = RateLimiter(max_calls=10, period_seconds=1)

        # Simulate bug that tries to make 100 API calls
        successful_calls = 0
        for _ in range(100):
            if limiter.acquire(blocking=False):
                successful_calls += 1

        # Should have only allowed ~10 calls
        assert successful_calls == 10

    def test_concurrent_extraction_rate_limiting(self):
        """Test rate limiting with concurrent extraction tasks."""
        limiter = get_rate_limiter("gemini")
        call_count = []

        def simulate_extraction():
            if limiter.acquire(blocking=False):
                call_count.append(1)
                # Simulate work
                time.sleep(0.01)

        # Simulate 100 concurrent extraction tasks
        threads = [Thread(target=simulate_extraction) for _ in range(100)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should have limited to max_calls
        assert len(call_count) <= 60  # Gemini default

    def test_cost_protection(self):
        """Test that rate limiting provides cost protection."""
        # Simulate a scenario where a bug causes infinite loop
        limiter = RateLimiter(max_calls=60, period_seconds=60)

        # Simulate 1000 API calls (bug scenario)
        calls_made = 0
        start_time = time.time()

        for _ in range(1000):
            # Try to make call (non-blocking to avoid test hanging)
            if limiter.acquire(blocking=False):
                calls_made += 1
            else:
                # Rate limited - break out of buggy loop
                break

        elapsed = time.time() - start_time

        # Should have been limited to 60 calls
        assert calls_made == 60

        # Should have happened quickly (no waiting)
        assert elapsed < 1.0

        # This represents 94% cost savings compared to unlimited calls!
        cost_savings = (1000 - calls_made) / 1000
        assert cost_savings > 0.9  # >90% savings
