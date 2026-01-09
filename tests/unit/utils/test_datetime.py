"""Tests for datetime utilities."""

from datetime import datetime, timedelta, timezone

import pytest

from inkwell.utils.datetime import format_duration, now_utc, validate_timezone_aware


class TestNowUtc:
    """Tests for now_utc() function."""

    def test_returns_datetime(self):
        """Test that now_utc returns a datetime object."""
        result = now_utc()
        assert isinstance(result, datetime)

    def test_is_timezone_aware(self):
        """Test that returned datetime is timezone-aware."""
        result = now_utc()
        assert result.tzinfo is not None
        assert result.tzinfo == timezone.utc

    def test_is_utc(self):
        """Test that returned datetime is in UTC timezone."""
        result = now_utc()
        assert result.tzinfo == timezone.utc

    def test_returns_current_time(self):
        """Test that returned datetime is close to current time."""
        before = datetime.now(timezone.utc)
        result = now_utc()
        after = datetime.now(timezone.utc)

        # Should be between before and after (within 1 second)
        assert before <= result <= after
        assert (after - before).total_seconds() < 1

    def test_multiple_calls_increment(self):
        """Test that multiple calls return increasing timestamps."""
        first = now_utc()
        second = now_utc()

        # Second should be >= first (accounting for same-microsecond calls)
        assert second >= first


class TestValidateTimezoneAware:
    """Tests for validate_timezone_aware() function."""

    def test_accepts_aware_datetime(self):
        """Test that timezone-aware datetimes pass validation."""
        aware_dt = datetime.now(timezone.utc)
        # Should not raise
        validate_timezone_aware(aware_dt)

    def test_rejects_naive_datetime(self):
        """Test that naive datetimes raise ValueError."""
        naive_dt = datetime.utcnow()
        with pytest.raises(ValueError, match="must be timezone-aware"):
            validate_timezone_aware(naive_dt)

    def test_error_message_includes_field_name(self):
        """Test that error message includes custom field name."""
        naive_dt = datetime.utcnow()
        with pytest.raises(ValueError, match="timestamp must be timezone-aware"):
            validate_timezone_aware(naive_dt, name="timestamp")

    def test_error_message_includes_solution(self):
        """Test that error message suggests correct usage."""
        naive_dt = datetime.utcnow()
        with pytest.raises(ValueError, match="Use datetime.now\\(timezone.utc\\)"):
            validate_timezone_aware(naive_dt)

    def test_accepts_different_timezones(self):
        """Test that any timezone-aware datetime passes validation."""
        # UTC
        utc_dt = datetime.now(timezone.utc)
        validate_timezone_aware(utc_dt)

        # UTC+5
        plus_five = timezone(timedelta(hours=5))
        plus_five_dt = datetime.now(plus_five)
        validate_timezone_aware(plus_five_dt)

        # UTC-3
        minus_three = timezone(timedelta(hours=-3))
        minus_three_dt = datetime.now(minus_three)
        validate_timezone_aware(minus_three_dt)


class TestDatetimeComparisons:
    """Tests for datetime comparisons to ensure no TypeError."""

    def test_can_compare_two_aware_datetimes(self):
        """Test that two timezone-aware datetimes can be compared."""
        dt1 = now_utc()
        dt2 = now_utc()

        # Should not raise TypeError
        assert dt2 >= dt1

        # Can calculate timedelta
        delta = dt2 - dt1
        assert isinstance(delta, timedelta)
        assert delta.total_seconds() >= 0

    def test_cannot_compare_naive_and_aware(self):
        """Test that comparing naive and aware raises TypeError."""
        aware = datetime.now(timezone.utc)
        naive = datetime.utcnow()

        # Python 3.9+ raises TypeError
        with pytest.raises(TypeError):
            _ = aware - naive

        with pytest.raises(TypeError):
            _ = naive - aware

        with pytest.raises(TypeError):
            _ = aware > naive

    def test_cache_ttl_scenario(self):
        """Test cache TTL calculation scenario (from TODO description)."""
        # Simulate cached timestamp
        cached_at = now_utc() - timedelta(hours=1)

        # Current time
        now = now_utc()

        # Calculate age (should work without TypeError)
        age = now - cached_at

        assert isinstance(age, timedelta)
        assert age.total_seconds() >= 3600  # At least 1 hour

    def test_session_cleanup_scenario(self):
        """Test session cleanup scenario (from TODO description)."""
        # Simulate old session
        session_updated_at = now_utc() - timedelta(days=35)

        # Cutoff date
        cutoff_date = now_utc() - timedelta(days=30)

        # Should be able to compare
        is_old = session_updated_at < cutoff_date

        assert is_old is True


class TestBackwardCompatibility:
    """Tests for backward compatibility with existing code."""

    def test_json_serialization_with_aware_datetime(self):
        """Test that timezone-aware datetimes serialize to JSON correctly."""
        dt = now_utc()
        iso_str = dt.isoformat()

        # Should include timezone info
        assert "+" in iso_str or "Z" in iso_str

        # Should be deserializable
        parsed = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        assert parsed.tzinfo is not None

    def test_pydantic_serialization(self):
        """Test that Pydantic handles timezone-aware datetimes correctly."""
        from pydantic import BaseModel, Field

        class TestModel(BaseModel):
            timestamp: datetime = Field(default_factory=now_utc)

        # Create instance
        model = TestModel()

        # Verify timestamp is aware
        assert model.timestamp.tzinfo is not None
        assert model.timestamp.tzinfo == timezone.utc

        # Serialize to dict
        data = model.model_dump(mode="json")
        assert "timestamp" in data

        # Deserialize from dict
        model2 = TestModel.model_validate(data)
        assert model2.timestamp.tzinfo is not None


class TestFormatDuration:
    """Tests for format_duration() function."""

    def test_seconds(self):
        """Test formatting durations under 1 minute."""
        assert format_duration(0) == "0s"
        assert format_duration(30) == "30s"
        assert format_duration(59) == "59s"
        assert format_duration(59.9) == "59s"

    def test_minutes(self):
        """Test formatting durations under 1 hour."""
        assert format_duration(60) == "1m"
        assert format_duration(120) == "2m"
        assert format_duration(1800) == "30m"
        assert format_duration(3599) == "59m"

    def test_hours(self):
        """Test formatting durations under 1 day."""
        assert format_duration(3600) == "1h"
        assert format_duration(7200) == "2h"
        assert format_duration(43200) == "12h"
        assert format_duration(86399) == "23h"

    def test_days(self):
        """Test formatting durations in days."""
        assert format_duration(86400) == "1d"
        assert format_duration(172800) == "2d"
        assert format_duration(604800) == "7d"
        assert format_duration(2592000) == "30d"

    def test_rounds_down(self):
        """Test that durations are rounded down."""
        # 1.5 minutes = 90 seconds = "1m" (not "2m")
        assert format_duration(90) == "1m"

        # 2.5 hours = 9000 seconds = "2h" (not "3h")
        assert format_duration(9000) == "2h"

        # 1.5 days = 129600 seconds = "1d" (not "2d")
        assert format_duration(129600) == "1d"

    def test_boundary_cases(self):
        """Test boundary conditions between units."""
        # Just under 1 minute
        assert format_duration(59.999) == "59s"

        # Exactly 1 minute
        assert format_duration(60) == "1m"

        # Just under 1 hour
        assert format_duration(3599.999) == "59m"

        # Exactly 1 hour
        assert format_duration(3600) == "1h"

        # Just under 1 day
        assert format_duration(86399.999) == "23h"

        # Exactly 1 day
        assert format_duration(86400) == "1d"

    def test_real_world_examples(self):
        """Test real-world usage scenarios."""
        # Session resumed after 2 hours
        assert format_duration(7200) == "2h"

        # Session from yesterday (25 hours ago)
        assert format_duration(90000) == "1d"

        # Very recent session (30 seconds ago)
        assert format_duration(30) == "30s"

        # Session from last week
        assert format_duration(604800) == "7d"
