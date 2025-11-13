"""Tests for datetime handling in interview models."""

import pytest
from datetime import datetime, timezone, timedelta

from inkwell.interview.models import InterviewSession, Question, Response


class TestInterviewSessionDatetimeHandling:
    """Tests for InterviewSession model datetime handling."""

    def test_default_timestamps_are_timezone_aware(self):
        """Test that default timestamps are timezone-aware."""
        session = InterviewSession(
            episode_url="https://example.com/ep1",
            episode_title="Test Episode",
            podcast_name="Test Podcast",
        )

        assert session.started_at.tzinfo is not None
        assert session.started_at.tzinfo == timezone.utc
        assert session.updated_at.tzinfo is not None
        assert session.updated_at.tzinfo == timezone.utc

    def test_completed_at_none_by_default(self):
        """Test that completed_at is None by default."""
        session = InterviewSession(
            episode_url="https://example.com/ep1",
            episode_title="Test Episode",
            podcast_name="Test Podcast",
        )

        assert session.completed_at is None

    def test_completed_at_is_aware_when_set(self):
        """Test that completed_at is timezone-aware when session completes."""
        session = InterviewSession(
            episode_url="https://example.com/ep1",
            episode_title="Test Episode",
            podcast_name="Test Podcast",
        )

        session.complete()

        assert session.completed_at is not None
        assert session.completed_at.tzinfo is not None
        assert session.completed_at.tzinfo == timezone.utc

    def test_mark_updated_sets_aware_timestamp(self):
        """Test that mark_updated() sets timezone-aware timestamp."""
        session = InterviewSession(
            episode_url="https://example.com/ep1",
            episode_title="Test Episode",
            podcast_name="Test Podcast",
        )

        original_updated = session.updated_at
        session.mark_updated()

        assert session.updated_at > original_updated
        assert session.updated_at.tzinfo is not None
        assert session.updated_at.tzinfo == timezone.utc

    def test_duration_calculation_works(self):
        """Test that duration calculation works without TypeError."""
        session = InterviewSession(
            episode_url="https://example.com/ep1",
            episode_title="Test Episode",
            podcast_name="Test Podcast",
        )

        # Duration should be calculated without error
        duration = session.duration
        assert isinstance(duration, timedelta)
        assert duration.total_seconds() >= 0

    def test_duration_with_completed_session(self):
        """Test duration calculation for completed session."""
        session = InterviewSession(
            episode_url="https://example.com/ep1",
            episode_title="Test Episode",
            podcast_name="Test Podcast",
        )

        session.complete()

        # Duration should use completed_at
        duration = session.duration
        assert isinstance(duration, timedelta)
        assert duration.total_seconds() >= 0

    def test_validator_converts_naive_to_aware(self):
        """Test that validator converts naive datetimes to aware (backward compatibility)."""
        naive_dt = datetime.utcnow()

        session = InterviewSession(
            episode_url="https://example.com/ep1",
            episode_title="Test Episode",
            podcast_name="Test Podcast",
            started_at=naive_dt,
        )

        # Should be converted to aware
        assert session.started_at.tzinfo is not None
        assert session.started_at.tzinfo == timezone.utc

    def test_serialization_includes_timezone(self):
        """Test that serialized timestamps include timezone info."""
        session = InterviewSession(
            episode_url="https://example.com/ep1",
            episode_title="Test Episode",
            podcast_name="Test Podcast",
        )

        data = session.model_dump(mode="json")

        # Check timestamps have timezone info
        started_str = data["started_at"]
        assert "+00:00" in started_str or started_str.endswith("Z")

    def test_deserialization_maintains_timezone(self):
        """Test that deserializing maintains timezone awareness."""
        session1 = InterviewSession(
            episode_url="https://example.com/ep1",
            episode_title="Test Episode",
            podcast_name="Test Podcast",
        )

        data = session1.model_dump(mode="json")
        session2 = InterviewSession.model_validate(data)

        assert session2.started_at.tzinfo is not None
        assert session2.started_at.tzinfo == timezone.utc
        assert session2.updated_at.tzinfo is not None
        assert session2.updated_at.tzinfo == timezone.utc


class TestSessionManagerDatetimeHandling:
    """Tests for SessionManager datetime handling."""

    def test_cleanup_old_sessions_date_comparison(self):
        """Test that cleanup_old_sessions uses timezone-aware comparison."""
        from inkwell.interview.session_manager import SessionManager
        from pathlib import Path
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SessionManager(session_dir=Path(tmpdir))

            # Create a session
            session = manager.create_session(
                episode_url="https://example.com/ep1",
                episode_title="Test Episode",
                podcast_name="Test Podcast",
            )

            # Mark as completed
            session.complete()
            manager.save_session(session)

            # Cleanup (should work without TypeError)
            deleted = manager.cleanup_old_sessions(days=30)

            # Should not delete recent session
            assert deleted == 0

    def test_detect_timeout_date_comparison(self):
        """Test that detect_timeout uses timezone-aware comparison."""
        from inkwell.interview.session_manager import SessionManager
        from pathlib import Path
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SessionManager(session_dir=Path(tmpdir))

            session = manager.create_session(
                episode_url="https://example.com/ep1",
                episode_title="Test Episode",
                podcast_name="Test Podcast",
            )

            # Should not timeout (recent session)
            is_timeout = manager.detect_timeout(session, timeout_minutes=60)
            assert is_timeout is False


class TestQuestionDatetimeHandling:
    """Tests for Question model datetime handling."""

    def test_default_generated_at_is_aware(self):
        """Test that default generated_at is timezone-aware."""
        question = Question(
            text="What did you think about this?",
            question_number=1,
        )

        assert question.generated_at.tzinfo is not None
        assert question.generated_at.tzinfo == timezone.utc


class TestResponseDatetimeHandling:
    """Tests for Response model datetime handling."""

    def test_default_responded_at_is_aware(self):
        """Test that default responded_at is timezone-aware."""
        response = Response(
            question_id="q1",
            text="I thought it was interesting because...",
        )

        assert response.responded_at.tzinfo is not None
        assert response.responded_at.tzinfo == timezone.utc
