"""Tests for session manager."""

import json
from datetime import datetime, timedelta

import pytest

from inkwell.interview.models import InterviewGuidelines, InterviewSession, Question, Response
from inkwell.interview.session_manager import SessionManager


@pytest.fixture
def session_dir(tmp_path):
    """Create temporary session directory."""
    return tmp_path / "sessions"


@pytest.fixture
def manager(session_dir):
    """Create session manager with temp directory."""
    return SessionManager(session_dir=session_dir)


@pytest.fixture
def sample_session():
    """Create sample session."""
    return InterviewSession(
        episode_url="https://example.com/ep1",
        episode_title="Episode 1",
        podcast_name="Test Podcast",
        template_name="reflective",
        max_questions=5,
    )


# Initialization Tests


def test_create_manager(session_dir):
    """Test creating session manager."""
    manager = SessionManager(session_dir=session_dir)

    assert manager.session_dir == session_dir
    assert session_dir.exists()


def test_create_manager_default_dir():
    """Test creating manager with default directory."""
    manager = SessionManager()

    # Should use XDG_DATA_HOME or ~/.local/share
    assert manager.session_dir.exists()
    assert "inkwell" in str(manager.session_dir)
    assert "sessions" in str(manager.session_dir)


# Session Creation Tests


def test_create_session(manager):
    """Test creating a new session."""
    session = manager.create_session(
        episode_url="https://example.com/ep1",
        episode_title="Episode 1",
        podcast_name="Test Podcast",
        template_name="reflective",
        max_questions=5,
    )

    assert session.episode_url == "https://example.com/ep1"
    assert session.episode_title == "Episode 1"
    assert session.podcast_name == "Test Podcast"
    assert session.template_name == "reflective"
    assert session.max_questions == 5
    assert session.status == "active"
    assert session.session_id is not None

    # Should be saved to disk
    session_file = manager._get_session_file(session.session_id)
    assert session_file.exists()


def test_create_session_with_guidelines(manager):
    """Test creating session with guidelines."""
    guidelines = InterviewGuidelines(
        content="Focus on practical applications",
        focus_areas=["work", "projects"],
    )

    session = manager.create_session(
        episode_url="https://example.com/ep1",
        episode_title="Episode 1",
        podcast_name="Test Podcast",
        guidelines=guidelines,
    )

    assert session.guidelines == guidelines


# Save/Load Tests


def test_save_session(manager, sample_session):
    """Test saving a session."""
    session_file = manager.save_session(sample_session)

    assert session_file.exists()
    assert session_file.name == f"session-{sample_session.session_id}.json"

    # Check file contents
    with session_file.open("r") as f:
        data = json.load(f)

    assert data["episode_url"] == sample_session.episode_url
    assert data["session_id"] == sample_session.session_id


def test_save_session_atomic(manager, sample_session):
    """Test that save uses atomic write."""
    session_file = manager._get_session_file(sample_session.session_id)
    temp_file = session_file.with_suffix(".tmp")

    # Save session
    manager.save_session(sample_session)

    # Temp file should not exist after successful save
    assert not temp_file.exists()
    assert session_file.exists()


def test_load_session(manager, sample_session):
    """Test loading a session."""
    # Save first
    manager.save_session(sample_session)

    # Load
    loaded = manager.load_session(sample_session.session_id)

    assert loaded.session_id == sample_session.session_id
    assert loaded.episode_url == sample_session.episode_url
    assert loaded.episode_title == sample_session.episode_title
    assert loaded.podcast_name == sample_session.podcast_name


def test_load_session_not_found(manager):
    """Test loading non-existent session."""
    with pytest.raises(FileNotFoundError):
        manager.load_session("nonexistent-id")


def test_load_session_invalid_json(manager, session_dir):
    """Test loading session with invalid JSON."""
    # Create file with invalid JSON
    session_file = session_dir / "session-test.json"
    session_file.write_text("invalid json {")

    with pytest.raises(ValueError, match="Invalid session data"):
        manager.load_session("test")


def test_save_load_with_exchanges(manager):
    """Test saving and loading session with exchanges."""
    session = manager.create_session(
        episode_url="https://example.com/ep1",
        episode_title="Episode 1",
        podcast_name="Test Podcast",
    )

    # Add some exchanges
    q1 = Question(text="Question 1?", question_number=1)
    r1 = Response(question_id=q1.id, text="Response 1")
    session.add_exchange(q1, r1)

    q2 = Question(text="Question 2?", question_number=2)
    r2 = Response(question_id=q2.id, text="Response 2")
    session.add_exchange(q2, r2)

    # Save
    manager.save_session(session)

    # Load
    loaded = manager.load_session(session.session_id)

    assert len(loaded.exchanges) == 2
    assert loaded.exchanges[0].question.text == "Question 1?"
    assert loaded.exchanges[1].question.text == "Question 2?"


# List Sessions Tests


def test_list_sessions_empty(manager):
    """Test listing sessions when none exist."""
    sessions = manager.list_sessions()
    assert sessions == []


def test_list_sessions(manager):
    """Test listing multiple sessions."""
    # Create 3 sessions
    manager.create_session(
        episode_url="https://example.com/ep1",
        episode_title="Episode 1",
        podcast_name="Podcast A",
    )

    manager.create_session(
        episode_url="https://example.com/ep2",
        episode_title="Episode 2",
        podcast_name="Podcast B",
    )

    manager.create_session(
        episode_url="https://example.com/ep3",
        episode_title="Episode 3",
        podcast_name="Podcast A",
    )

    # List all
    sessions = manager.list_sessions()
    assert len(sessions) == 3


def test_list_sessions_filter_by_episode_url(manager):
    """Test filtering sessions by episode URL."""
    manager.create_session(
        episode_url="https://example.com/ep1",
        episode_title="Episode 1",
        podcast_name="Test",
    )

    manager.create_session(
        episode_url="https://example.com/ep2",
        episode_title="Episode 2",
        podcast_name="Test",
    )

    # Filter
    sessions = manager.list_sessions(episode_url="https://example.com/ep1")

    assert len(sessions) == 1
    assert sessions[0].episode_url == "https://example.com/ep1"


def test_list_sessions_filter_by_podcast(manager):
    """Test filtering sessions by podcast name."""
    manager.create_session(
        episode_url="https://example.com/ep1",
        episode_title="Episode 1",
        podcast_name="Podcast A",
    )

    manager.create_session(
        episode_url="https://example.com/ep2",
        episode_title="Episode 2",
        podcast_name="Podcast B",
    )

    # Filter
    sessions = manager.list_sessions(podcast_name="Podcast A")

    assert len(sessions) == 1
    assert sessions[0].podcast_name == "Podcast A"


def test_list_sessions_filter_by_status(manager):
    """Test filtering sessions by status."""
    s1 = manager.create_session(
        episode_url="https://example.com/ep1",
        episode_title="Episode 1",
        podcast_name="Test",
    )

    s2 = manager.create_session(
        episode_url="https://example.com/ep2",
        episode_title="Episode 2",
        podcast_name="Test",
    )

    # Complete one session
    s2.complete()
    manager.save_session(s2)

    # Filter by active
    active_sessions = manager.list_sessions(status="active")
    assert len(active_sessions) == 1
    assert active_sessions[0].session_id == s1.session_id

    # Filter by completed
    completed_sessions = manager.list_sessions(status="completed")
    assert len(completed_sessions) == 1
    assert completed_sessions[0].session_id == s2.session_id


def test_list_sessions_sorted_by_recent(manager):
    """Test that sessions are sorted by most recent."""
    import time

    s1 = manager.create_session(
        episode_url="https://example.com/ep1",
        episode_title="Episode 1",
        podcast_name="Test",
    )

    time.sleep(0.01)  # Ensure different timestamps

    s2 = manager.create_session(
        episode_url="https://example.com/ep2",
        episode_title="Episode 2",
        podcast_name="Test",
    )

    sessions = manager.list_sessions()

    # Most recent first
    assert sessions[0].session_id == s2.session_id
    assert sessions[1].session_id == s1.session_id


# Find Resumable Session Tests


def test_find_resumable_session_active(manager):
    """Test finding active resumable session."""
    session = manager.create_session(
        episode_url="https://example.com/ep1",
        episode_title="Episode 1",
        podcast_name="Test",
    )

    # Find resumable
    found = manager.find_resumable_session("https://example.com/ep1")

    assert found is not None
    assert found.session_id == session.session_id


def test_find_resumable_session_paused(manager):
    """Test finding paused resumable session."""
    session = manager.create_session(
        episode_url="https://example.com/ep1",
        episode_title="Episode 1",
        podcast_name="Test",
    )

    # Pause session
    session.pause()
    manager.save_session(session)

    # Find resumable
    found = manager.find_resumable_session("https://example.com/ep1")

    assert found is not None
    assert found.session_id == session.session_id
    assert found.status == "paused"


def test_find_resumable_session_completed(manager):
    """Test that completed sessions are not resumable."""
    session = manager.create_session(
        episode_url="https://example.com/ep1",
        episode_title="Episode 1",
        podcast_name="Test",
    )

    # Complete session
    session.complete()
    manager.save_session(session)

    # Should not find
    found = manager.find_resumable_session("https://example.com/ep1")
    assert found is None


def test_find_resumable_session_not_found(manager):
    """Test finding session for non-existent episode."""
    found = manager.find_resumable_session("https://example.com/nonexistent")
    assert found is None


def test_find_resumable_session_prefers_active(manager):
    """Test that active sessions are preferred over paused."""
    # Create paused session
    s1 = manager.create_session(
        episode_url="https://example.com/ep1",
        episode_title="Episode 1",
        podcast_name="Test",
    )
    s1.pause()
    manager.save_session(s1)

    import time

    time.sleep(0.01)

    # Create active session
    s2 = manager.create_session(
        episode_url="https://example.com/ep1",
        episode_title="Episode 1",
        podcast_name="Test",
    )

    # Should find active one
    found = manager.find_resumable_session("https://example.com/ep1")
    assert found.session_id == s2.session_id
    assert found.status == "active"


# Delete Session Tests


def test_delete_session(manager, sample_session):
    """Test deleting a session."""
    manager.save_session(sample_session)

    # Delete
    result = manager.delete_session(sample_session.session_id)

    assert result is True

    # File should not exist
    session_file = manager._get_session_file(sample_session.session_id)
    assert not session_file.exists()


def test_delete_session_not_found(manager):
    """Test deleting non-existent session."""
    result = manager.delete_session("nonexistent")
    assert result is False


# Cleanup Tests


def test_cleanup_old_sessions(manager):
    """Test cleaning up old sessions."""
    # Create old completed session
    s1 = manager.create_session(
        episode_url="https://example.com/ep1",
        episode_title="Episode 1",
        podcast_name="Test",
    )
    s1.complete()

    # Manually set old timestamp and save without updating
    s1.updated_at = datetime.utcnow() - timedelta(days=40)
    manager.save_session(s1, update_timestamp=False)

    # Create recent session
    s2 = manager.create_session(
        episode_url="https://example.com/ep2",
        episode_title="Episode 2",
        podcast_name="Test",
    )
    s2.complete()
    manager.save_session(s2)

    # Cleanup (30 day threshold)
    deleted = manager.cleanup_old_sessions(days=30)

    assert deleted == 1

    # Old session should be gone
    assert not manager._get_session_file(s1.session_id).exists()

    # Recent session should remain
    assert manager._get_session_file(s2.session_id).exists()


def test_cleanup_only_completed_or_abandoned(manager):
    """Test that only completed/abandoned sessions are cleaned up."""
    # Create old active session
    s1 = manager.create_session(
        episode_url="https://example.com/ep1",
        episode_title="Episode 1",
        podcast_name="Test",
    )
    s1.updated_at = datetime.utcnow() - timedelta(days=40)
    manager.save_session(s1)

    # Cleanup
    deleted = manager.cleanup_old_sessions(days=30)

    assert deleted == 0

    # Active session should remain even though old
    assert manager._get_session_file(s1.session_id).exists()


# Timeout Tests


def test_detect_timeout_not_timed_out(manager, sample_session):
    """Test detecting timeout on recent session."""
    timed_out = manager.detect_timeout(sample_session, timeout_minutes=60)
    assert timed_out is False


def test_detect_timeout_timed_out(manager):
    """Test detecting timed out session."""
    session = manager.create_session(
        episode_url="https://example.com/ep1",
        episode_title="Episode 1",
        podcast_name="Test",
    )

    # Manually set old timestamp
    session.updated_at = datetime.utcnow() - timedelta(minutes=90)

    timed_out = manager.detect_timeout(session, timeout_minutes=60)
    assert timed_out is True


def test_detect_timeout_completed_session(manager):
    """Test that completed sessions don't timeout."""
    session = manager.create_session(
        episode_url="https://example.com/ep1",
        episode_title="Episode 1",
        podcast_name="Test",
    )

    session.complete()
    session.updated_at = datetime.utcnow() - timedelta(minutes=90)

    timed_out = manager.detect_timeout(session, timeout_minutes=60)
    assert timed_out is False


def test_auto_abandon_timed_out(manager):
    """Test auto-abandoning timed out sessions."""
    # Create timed out session
    s1 = manager.create_session(
        episode_url="https://example.com/ep1",
        episode_title="Episode 1",
        podcast_name="Test",
    )
    s1.updated_at = datetime.utcnow() - timedelta(minutes=90)
    manager.save_session(s1, update_timestamp=False)

    # Create recent session
    s2 = manager.create_session(
        episode_url="https://example.com/ep2",
        episode_title="Episode 2",
        podcast_name="Test",
    )

    # Auto-abandon
    abandoned = manager.auto_abandon_timed_out(timeout_minutes=60)

    assert abandoned == 1

    # Load and check status
    loaded = manager.load_session(s1.session_id)
    assert loaded.status == "abandoned"

    # Recent session should still be active
    loaded2 = manager.load_session(s2.session_id)
    assert loaded2.status == "active"


# Stats Tests


def test_get_session_stats(manager):
    """Test getting session statistics."""
    session = manager.create_session(
        episode_url="https://example.com/ep1",
        episode_title="Episode 1",
        podcast_name="Test",
        max_questions=5,
    )

    # Add exchanges
    q1 = Question(text="Q1?", question_number=1)
    r1 = Response(
        question_id=q1.id,
        text="Response 1 with many words here",
        thinking_time_seconds=5.0,
    )
    session.add_exchange(q1, r1)

    q2 = Question(text="Q2?", question_number=2)
    r2 = Response(question_id=q2.id, text="Response 2 with enough words", thinking_time_seconds=3.0)
    session.add_exchange(q2, r2)

    # Update costs
    session.total_tokens_used = 1000
    session.total_cost_usd = 0.05

    # Get stats
    stats = manager.get_session_stats(session)

    assert stats["session_id"] == session.session_id
    assert stats["status"] == "active"
    assert stats["question_count"] == 2
    assert stats["substantive_responses"] == 2
    assert stats["total_thinking_time"] == 8.0
    assert stats["tokens_used"] == 1000
    assert stats["cost_usd"] == 0.05
    assert stats["completion_rate"] == 0.4  # 2/5


# Edge Cases


def test_session_file_path(manager):
    """Test session file path generation."""
    session_id = "test-123"
    path = manager._get_session_file(session_id)

    assert path.name == "session-test-123.json"
    assert path.parent == manager.session_dir


def test_list_sessions_skips_invalid_files(manager, session_dir):
    """Test that invalid session files are skipped."""
    # Create valid session
    s1 = manager.create_session(
        episode_url="https://example.com/ep1",
        episode_title="Episode 1",
        podcast_name="Test",
    )

    # Create invalid JSON file
    (session_dir / "session-invalid.json").write_text("invalid json")

    # List should not crash
    sessions = manager.list_sessions()

    assert len(sessions) == 1
    assert sessions[0].session_id == s1.session_id


def test_save_session_updates_timestamp(manager, sample_session):
    """Test that saving updates the updated_at timestamp."""
    old_timestamp = sample_session.updated_at

    import time

    time.sleep(0.01)

    manager.save_session(sample_session)

    # Timestamp should be updated
    assert sample_session.updated_at > old_timestamp
