"""Tests for interview manager."""

from unittest.mock import AsyncMock, patch

import pytest

from inkwell.interview.manager import InterviewManager
from inkwell.interview.models import (
    InterviewContext,
    InterviewGuidelines,
    InterviewSession,
    Question,
    Response,
)


@pytest.fixture
def mock_api_key():
    """Mock API key."""
    return "test-api-key"


@pytest.fixture
def manager(mock_api_key, tmp_path):
    """Create manager with mocked dependencies."""
    return InterviewManager(api_key=mock_api_key, session_dir=tmp_path / "sessions")


@pytest.fixture
def sample_context():
    """Create sample interview context."""
    return InterviewContext(
        podcast_name="Test Podcast",
        episode_title="Test Episode",
        episode_url="https://example.com/ep1",
        duration_minutes=60.0,
        summary="Test summary",
        key_quotes=[],
        key_concepts=[],
        max_questions=5,
    )


@pytest.fixture
def sample_session():
    """Create sample session."""
    return InterviewSession(
        episode_url="https://example.com/ep1",
        episode_title="Test Episode",
        podcast_name="Test Podcast",
        template_name="reflective",
        max_questions=5,
    )


# Initialization Tests


def test_create_manager_with_api_key(mock_api_key, tmp_path):
    """Test creating manager with explicit API key."""
    manager = InterviewManager(api_key=mock_api_key, session_dir=tmp_path)

    assert manager.api_key == mock_api_key
    assert manager.session_manager is not None
    assert manager.context_builder is not None


def test_create_manager_from_env(tmp_path, monkeypatch):
    """Test creating manager from environment variable."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "env-api-key")

    manager = InterviewManager(session_dir=tmp_path)

    assert manager.api_key == "env-api-key"


def test_create_manager_no_api_key_raises():
    """Test that missing API key raises error."""
    with pytest.raises(ValueError, match="Anthropic API key required"):
        InterviewManager(api_key=None)


# Context Building Tests


def test_build_context_from_output(manager, tmp_path):
    """Test building context from output directory."""
    context = manager._build_context_from_output(
        output_dir=tmp_path,
        episode_url="https://example.com/ep1",
        episode_title="Test Episode",
        podcast_name="Test Podcast",
        guidelines=None,
        max_questions=5,
    )

    assert context.episode_url == "https://example.com/ep1"
    assert context.episode_title == "Test Episode"
    assert context.podcast_name == "Test Podcast"
    assert context.max_questions == 5


def test_build_context_with_guidelines(manager, tmp_path):
    """Test building context with guidelines."""
    guidelines = InterviewGuidelines(
        content="Focus on practical applications",
        focus_areas=["work"],
    )

    context = manager._build_context_from_output(
        output_dir=tmp_path,
        episode_url="https://example.com/ep1",
        episode_title="Test Episode",
        podcast_name="Test Podcast",
        guidelines=guidelines,
        max_questions=5,
    )

    assert context.guidelines == guidelines


# Session Management Tests


def test_list_sessions(manager):
    """Test listing sessions."""
    # Create some sessions
    session1 = manager.session_manager.create_session(
        episode_url="https://example.com/ep1",
        episode_title="Episode 1",
        podcast_name="Test Podcast",
    )

    session2 = manager.session_manager.create_session(
        episode_url="https://example.com/ep2",
        episode_title="Episode 2",
        podcast_name="Test Podcast",
    )

    # List all sessions
    sessions = manager.list_sessions()

    assert len(sessions) == 2
    assert any(s.session_id == session1.session_id for s in sessions)
    assert any(s.session_id == session2.session_id for s in sessions)


def test_list_sessions_filtered(manager):
    """Test listing sessions with filter."""
    session1 = manager.session_manager.create_session(
        episode_url="https://example.com/ep1",
        episode_title="Episode 1",
        podcast_name="Podcast A",
    )

    manager.session_manager.create_session(
        episode_url="https://example.com/ep2",
        episode_title="Episode 2",
        podcast_name="Podcast B",
    )

    # Filter by podcast
    sessions = manager.list_sessions(podcast_name="Podcast A")

    assert len(sessions) == 1
    assert sessions[0].session_id == session1.session_id


# Resume Session Tests


def test_resume_session_loads_and_validates(manager, sample_session):
    """Test resuming session loads and validates."""
    # Save session in paused state
    sample_session.pause()
    manager.session_manager.save_session(sample_session)

    # Resume
    resumed = manager._resume_session(sample_session.session_id)

    assert resumed.session_id == sample_session.session_id
    assert resumed.status == "active"  # Should be resumed


def test_resume_session_not_found_raises(manager):
    """Test resuming non-existent session raises error."""
    with pytest.raises(FileNotFoundError):
        manager._resume_session("nonexistent-session-id")


def test_resume_session_completed_raises(manager, sample_session):
    """Test resuming completed session raises error."""
    # Complete session
    sample_session.complete()
    manager.session_manager.save_session(sample_session)

    # Try to resume
    with pytest.raises(ValueError, match="Cannot resume completed session"):
        manager._resume_session(sample_session.session_id)


# Format Transcript Tests


def test_format_transcript(manager, sample_session, tmp_path):
    """Test formatting transcript."""
    # Add some exchanges
    q = Question(text="Test question?", question_number=1)
    r = Response(question_id=q.id, text="Test response")
    sample_session.add_exchange(q, r)
    sample_session.complete()

    # Format
    result = manager._format_transcript(sample_session, tmp_path, "structured")

    assert result.formatted_transcript is not None
    assert "Test question?" in result.formatted_transcript
    assert result.output_file is not None
    assert result.output_file.exists()


def test_format_transcript_all_styles(manager, sample_session, tmp_path):
    """Test all format styles work."""
    q = Question(text="Question?", question_number=1)
    r = Response(question_id=q.id, text="Response")
    sample_session.add_exchange(q, r)

    for style in ["structured", "narrative", "qa"]:
        result = manager._format_transcript(sample_session, tmp_path / style, style)
        assert result.formatted_transcript is not None


# Partial Result Tests


def test_create_partial_result(manager, sample_session, tmp_path):
    """Test creating partial result for paused interview."""
    q = Question(text="Question?", question_number=1)
    r = Response(question_id=q.id, text="Response")
    sample_session.add_exchange(q, r)

    result = manager._create_partial_result(sample_session, tmp_path, "structured")

    assert result.formatted_transcript is not None
    assert result.output_file is None  # Not saved


# Integration Tests (mocked async operations)


@pytest.mark.asyncio
async def test_conduct_interview_basic_flow(manager, tmp_path):
    """Test basic interview flow (mocked)."""
    # Mock all the async/interactive parts
    with patch.object(manager, "_interview_loop", new_callable=AsyncMock) as mock_loop:
        with patch.object(manager, "_build_context_from_output") as mock_context:
            with patch("inkwell.interview.manager.display_welcome") as mock_welcome:
                with patch("inkwell.interview.manager.display_completion_summary") as mock_summary:
                    mock_context.return_value = InterviewContext(
                        podcast_name="Test",
                        episode_title="Test",
                        episode_url="https://example.com/ep1",
                        duration_minutes=60.0,
                        summary="Test",
                        max_questions=5,
                    )

                    result = await manager.conduct_interview(
                        episode_url="https://example.com/ep1",
                        episode_title="Test Episode",
                        podcast_name="Test Podcast",
                        output_dir=tmp_path,
                        template_name="reflective",
                        max_questions=5,
                    )

                    # Verify flow
                    mock_welcome.assert_called_once()
                    mock_loop.assert_called_once()
                    mock_summary.assert_called_once()
                    assert result is not None


@pytest.mark.asyncio
async def test_conduct_interview_creates_session(manager, tmp_path):
    """Test that conduct_interview creates a session."""
    with patch.object(manager, "_interview_loop", new_callable=AsyncMock):
        with patch.object(manager, "_build_context_from_output") as mock_context:
            with patch("inkwell.interview.manager.display_welcome"):
                with patch("inkwell.interview.manager.display_completion_summary"):
                    mock_context.return_value = InterviewContext(
                        podcast_name="Test",
                        episode_title="Test",
                        episode_url="https://example.com/ep1",
                        duration_minutes=60.0,
                        summary="Test",
                        max_questions=5,
                    )

                    await manager.conduct_interview(
                        episode_url="https://example.com/ep1",
                        episode_title="Test Episode",
                        podcast_name="Test Podcast",
                        output_dir=tmp_path,
                    )

                    # Check session was created
                    sessions = manager.list_sessions(episode_url="https://example.com/ep1")
                    assert len(sessions) == 1
                    assert sessions[0].status == "completed"


@pytest.mark.asyncio
async def test_resume_interview_flow(manager, tmp_path, sample_session):
    """Test resume interview flow (mocked)."""
    # Save paused session
    sample_session.pause()
    manager.session_manager.save_session(sample_session)

    with patch.object(manager, "_interview_loop", new_callable=AsyncMock):
        with patch.object(manager, "_build_context_from_output") as mock_context:
            with patch("inkwell.interview.manager.display_info"):
                with patch("inkwell.interview.manager.display_completion_summary"):
                    mock_context.return_value = InterviewContext(
                        podcast_name="Test",
                        episode_title="Test",
                        episode_url="https://example.com/ep1",
                        duration_minutes=60.0,
                        summary="Test",
                        max_questions=5,
                    )

                    result = await manager.resume_interview(
                        session_id=sample_session.session_id,
                        output_dir=tmp_path,
                    )

                    assert result is not None

                    # Check session is now completed
                    resumed = manager.session_manager.load_session(sample_session.session_id)
                    assert resumed.status == "completed"


@pytest.mark.asyncio
async def test_resume_interview_not_resumable_raises(manager, sample_session):
    """Test resuming non-resumable session raises error."""
    # Complete session
    sample_session.complete()
    manager.session_manager.save_session(sample_session)

    with pytest.raises(ValueError, match="Cannot resume completed session"):
        await manager.resume_interview(
            session_id=sample_session.session_id,
        )


# Edge Cases


def test_manager_without_anthropic_env_var(tmp_path):
    """Test manager without ANTHROPIC_API_KEY env var."""
    import os

    # Clear env var if present
    old_key = os.environ.pop("ANTHROPIC_API_KEY", None)

    try:
        with pytest.raises(ValueError, match="Anthropic API key required"):
            InterviewManager(session_dir=tmp_path)
    finally:
        # Restore env var if it was set
        if old_key:
            os.environ["ANTHROPIC_API_KEY"] = old_key


def test_format_transcript_creates_directory(manager, sample_session, tmp_path):
    """Test that format_transcript creates output directory."""
    q = Question(text="Q?", question_number=1)
    r = Response(question_id=q.id, text="R")
    sample_session.add_exchange(q, r)

    nested_dir = tmp_path / "nested" / "dir"
    result = manager._format_transcript(sample_session, nested_dir, "structured")

    assert nested_dir.exists()
    assert result.output_file is not None
    assert result.output_file.parent == nested_dir
