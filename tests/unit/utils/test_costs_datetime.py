"""Tests for datetime handling in costs module."""

from datetime import datetime, timedelta, timezone

from inkwell.utils.costs import APIUsage


class TestAPIUsageDatetimeHandling:
    """Tests for APIUsage model datetime handling."""

    def test_default_timestamp_is_timezone_aware(self):
        """Test that default timestamp is timezone-aware."""
        usage = APIUsage(
            provider="gemini",
            model="gemini-2.5-flash",
            operation="transcription",
        )

        assert usage.timestamp.tzinfo is not None
        assert usage.timestamp.tzinfo == timezone.utc

    def test_accepts_aware_datetime(self):
        """Test that explicit timezone-aware datetime is accepted."""
        aware_dt = datetime.now(timezone.utc)

        usage = APIUsage(
            provider="gemini",
            model="gemini-2.5-flash",
            operation="transcription",
            timestamp=aware_dt,
        )

        assert usage.timestamp.tzinfo is not None
        assert usage.timestamp == aware_dt

    def test_converts_naive_datetime_to_aware(self):
        """Test that naive datetime is converted to aware (backward compatibility)."""
        naive_dt = datetime.utcnow()

        usage = APIUsage(
            provider="gemini",
            model="gemini-2.5-flash",
            operation="transcription",
            timestamp=naive_dt,
        )

        # Should be converted to aware
        assert usage.timestamp.tzinfo is not None
        assert usage.timestamp.tzinfo == timezone.utc

    def test_validator_preserves_aware_datetime(self):
        """Test that validator doesn't modify already-aware datetimes."""
        aware_dt = datetime.now(timezone.utc)

        usage = APIUsage(
            provider="gemini",
            model="gemini-2.5-flash",
            operation="transcription",
            timestamp=aware_dt,
        )

        # Should be exactly the same
        assert usage.timestamp == aware_dt
        assert usage.timestamp.tzinfo == timezone.utc

    def test_model_post_init_validates_timestamp(self):
        """Test that model_post_init validates timestamp is timezone-aware."""
        # This should work without errors
        usage = APIUsage(
            provider="gemini",
            model="gemini-2.5-flash",
            operation="transcription",
        )

        # Timestamp should be validated
        assert usage.timestamp.tzinfo is not None

    def test_timestamp_comparison_works(self):
        """Test that timestamps can be compared without TypeError."""
        usage1 = APIUsage(
            provider="gemini",
            model="gemini-2.5-flash",
            operation="transcription",
        )

        usage2 = APIUsage(
            provider="gemini",
            model="gemini-2.5-flash",
            operation="transcription",
        )

        # Should not raise TypeError
        assert usage2.timestamp >= usage1.timestamp

        # Can calculate age
        age = usage2.timestamp - usage1.timestamp
        assert isinstance(age, timedelta)

    def test_serialization_includes_timezone(self):
        """Test that serialized timestamp includes timezone info."""
        usage = APIUsage(
            provider="gemini",
            model="gemini-2.5-flash",
            operation="transcription",
        )

        # Serialize to JSON
        data = usage.model_dump(mode="json")

        # Timestamp should be a string with timezone
        timestamp_str = data["timestamp"]
        assert isinstance(timestamp_str, str)
        # Should have timezone info (either +00:00 or Z)
        assert "+00:00" in timestamp_str or timestamp_str.endswith("Z")

    def test_deserialization_maintains_timezone(self):
        """Test that deserializing from JSON maintains timezone info."""
        usage1 = APIUsage(
            provider="gemini",
            model="gemini-2.5-flash",
            operation="transcription",
        )

        # Serialize and deserialize
        data = usage1.model_dump(mode="json")
        usage2 = APIUsage.model_validate(data)

        # Should maintain timezone awareness
        assert usage2.timestamp.tzinfo is not None
        assert usage2.timestamp.tzinfo == timezone.utc

    def test_cost_tracker_filter_by_date(self):
        """Test that CostTracker filtering by date works correctly."""
        import tempfile
        from pathlib import Path

        from inkwell.utils.costs import CostTracker

        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = CostTracker(costs_file=Path(tmpdir) / "costs.json")

            # Add some usage records
            usage1 = APIUsage(
                provider="gemini",
                model="gemini-2.5-flash",
                operation="transcription",
                cost_usd=0.10,
            )

            usage2 = APIUsage(
                provider="gemini",
                model="gemini-2.5-flash",
                operation="extraction",
                cost_usd=0.20,
            )

            tracker.track(usage1)
            tracker.track(usage2)

            # Filter by date (should work without TypeError)
            since = datetime.now(timezone.utc) - timedelta(hours=1)
            summary = tracker.get_summary(since=since)

            assert summary.total_operations == 2
            assert abs(summary.total_cost_usd - 0.30) < 0.001  # Floating point comparison
