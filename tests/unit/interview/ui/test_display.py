"""Tests for interview UI display components."""

from pathlib import Path
from unittest.mock import patch

import pytest

from inkwell.interview.models import Exchange, InterviewSession, Question, Response
from inkwell.interview.ui.display import (
    ProcessingIndicator,
    display_completion_summary,
    display_conversation_summary,
    display_error,
    display_info,
    display_pause_message,
    display_question,
    display_response_preview,
    display_session_stats,
    display_streaming_question,
    display_thinking,
    display_welcome,
)


# Helper for async iteration
class AsyncTextIterator:
    """Mock async iterator for streaming text."""

    def __init__(self, chunks: list[str]):
        self.chunks = chunks
        self.index = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.index >= len(self.chunks):
            raise StopAsyncIteration
        chunk = self.chunks[self.index]
        self.index += 1
        return chunk


@pytest.fixture
def mock_console():
    """Mock Rich console for testing."""
    with patch("inkwell.interview.ui.display.console") as mock:
        yield mock


@pytest.fixture
def sample_session():
    """Create sample interview session."""
    session = InterviewSession(
        episode_url="https://example.com/ep1",
        episode_title="Test Episode",
        podcast_name="Test Podcast",
        template_name="reflective",
        max_questions=5,
    )

    # Add some exchanges
    q1 = Question(text="What did you think?", question_number=1)
    r1 = Response(question_id=q1.id, text="I thought it was great", thinking_time_seconds=10.0)
    session.add_exchange(q1, r1)

    q2 = Question(text="Tell me more?", question_number=2)
    r2 = Response(
        question_id=q2.id,
        text="Well, the ideas were fascinating",
        thinking_time_seconds=15.0,
    )
    session.add_exchange(q2, r2)

    return session


@pytest.fixture
def sample_exchanges(sample_session):
    """Get exchanges from sample session."""
    return sample_session.exchanges


# Welcome Display Tests


def test_display_welcome(mock_console):
    """Test welcome screen display."""
    display_welcome(
        episode_title="The Future of AI",
        podcast_name="Tech Talks",
        template_name="reflective",
        max_questions=5,
    )

    # Should print panel and newline
    assert mock_console.print.call_count == 2

    # First call should be Panel with welcome text
    first_call = mock_console.print.call_args_list[0]
    assert "Panel" in str(type(first_call[0][0]))


def test_display_welcome_contains_episode_info(mock_console):
    """Test welcome screen contains episode information."""
    display_welcome(
        episode_title="AI Safety",
        podcast_name="My Podcast",
        template_name="analytical",
        max_questions=7,
    )

    # Check panel contains expected text (via Markdown)
    first_call = mock_console.print.call_args_list[0]
    panel = first_call[0][0]
    # Markdown object is in panel.renderable
    markdown_text = str(panel.renderable.markup)

    assert "AI Safety" in markdown_text
    assert "My Podcast" in markdown_text
    assert "analytical" in markdown_text


# Question Display Tests


def test_display_question_regular(mock_console):
    """Test regular question display."""
    display_question(
        question_number=1,
        total_questions=5,
        question_text="What did you think about the episode?",
        is_follow_up=False,
    )

    # Should print: newline, header, newline, question, newline
    assert mock_console.print.call_count == 5


def test_display_question_follow_up(mock_console):
    """Test follow-up question display."""
    display_question(
        question_number=2,
        total_questions=5,
        question_text="Can you elaborate?",
        is_follow_up=True,
    )

    assert mock_console.print.call_count == 5


@pytest.mark.asyncio
async def test_display_streaming_question(mock_console):
    """Test streaming question display."""
    chunks = ["What ", "did ", "you ", "think?"]
    stream = AsyncTextIterator(chunks)

    result = await display_streaming_question(
        question_number=1, total_questions=5, text_stream=stream, is_follow_up=False
    )

    assert result == "What did you think?"
    # Should print newline, header, newline, icon (with end='')
    # Plus Live context manager for streaming
    assert mock_console.print.call_count >= 3


@pytest.mark.asyncio
async def test_display_streaming_follow_up(mock_console):
    """Test streaming follow-up question."""
    chunks = ["Can ", "you ", "say ", "more?"]
    stream = AsyncTextIterator(chunks)

    result = await display_streaming_question(
        question_number=2, total_questions=5, text_stream=stream, is_follow_up=True
    )

    assert result == "Can you say more?"


# Response Preview Tests


def test_display_response_preview_short(mock_console):
    """Test response preview with short text."""
    display_response_preview("This is a short response")

    assert mock_console.print.call_count == 2
    # Should show full text
    first_call_args = str(mock_console.print.call_args_list[0])
    assert "This is a short response" in first_call_args


def test_display_response_preview_long(mock_console):
    """Test response preview with long text."""
    long_text = "x" * 150

    display_response_preview(long_text, max_length=100)

    # Should truncate and add "..."
    first_call_args = str(mock_console.print.call_args_list[0])
    assert "..." in first_call_args


# Thinking Display Test


def test_display_thinking(mock_console):
    """Test thinking indicator display."""
    display_thinking("Processing your response...")

    assert mock_console.print.call_count == 1
    call_args = str(mock_console.print.call_args)
    assert "Processing your response..." in call_args


# Conversation Summary Tests


def test_display_conversation_summary(mock_console, sample_exchanges):
    """Test conversation summary table."""
    display_conversation_summary(sample_exchanges)

    # Should print: newline, table, newline
    assert mock_console.print.call_count == 3


def test_display_conversation_summary_empty(mock_console):
    """Test conversation summary with no exchanges."""
    display_conversation_summary([])

    # Should not print anything
    assert mock_console.print.call_count == 0


def test_display_conversation_summary_truncates_long_text(mock_console):
    """Test that long questions/responses are truncated."""
    long_question_text = "x" * 100
    long_response_text = "y" * 100

    q = Question(text=long_question_text, question_number=1)
    r = Response(question_id=q.id, text=long_response_text)
    exchanges = [Exchange(question=q, response=r)]

    display_conversation_summary(exchanges)

    # Just verify it doesn't crash with long text
    assert mock_console.print.call_count == 3


# Completion Summary Tests


def test_display_completion_summary(mock_console, sample_session):
    """Test completion summary display."""
    output_file = Path("/tmp/test/my-notes.md")

    display_completion_summary(sample_session, output_file)

    # Should print panel and newline
    assert mock_console.print.call_count == 2


def test_display_completion_summary_no_file(mock_console, sample_session):
    """Test completion summary without output file."""
    display_completion_summary(sample_session, None)

    # Should still print panel
    assert mock_console.print.call_count == 2


# Pause Message Tests


def test_display_pause_message(mock_console, sample_session):
    """Test pause message display."""
    sample_session.status = "paused"

    display_pause_message(sample_session)

    # Should print panel and newline
    assert mock_console.print.call_count == 2


# Error/Info Display Tests


def test_display_error(mock_console):
    """Test error message display."""
    display_error("Something went wrong", title="Error")

    assert mock_console.print.call_count == 2


def test_display_info(mock_console):
    """Test info message display."""
    display_info("Here is some information", title="Info")

    assert mock_console.print.call_count == 2


# Session Stats Tests


def test_display_session_stats(mock_console, sample_session):
    """Test session stats display."""
    display_session_stats(sample_session)

    # Should print panel and newline
    assert mock_console.print.call_count == 2


def test_display_session_stats_shows_progress(mock_console):
    """Test session stats shows completion percentage."""
    session = InterviewSession(
        episode_url="https://example.com/ep1",
        episode_title="Test",
        podcast_name="Test",
        max_questions=10,
    )

    # Add 5 exchanges (50%)
    for i in range(5):
        q = Question(text=f"Question {i}", question_number=i + 1)
        r = Response(question_id=q.id, text="Response")
        session.add_exchange(q, r)

    display_session_stats(session)

    # Verify it was called (hard to check exact content due to Text object)
    assert mock_console.print.call_count == 2


# ProcessingIndicator Tests


def test_processing_indicator_context_manager(mock_console):
    """Test ProcessingIndicator as context manager."""
    with ProcessingIndicator("Processing..."):
        pass

    # Should start and stop progress
    # Exact call count depends on Progress implementation


def test_processing_indicator_update(mock_console):
    """Test updating ProcessingIndicator message."""
    with ProcessingIndicator("Initial message") as indicator:
        indicator.update("Updated message")


def test_processing_indicator_non_transient(mock_console):
    """Test ProcessingIndicator with transient=False."""
    with ProcessingIndicator("Persistent message", transient=False):
        pass


# Integration Tests


def test_full_welcome_to_question_flow(mock_console):
    """Test displaying welcome then question."""
    # Welcome
    display_welcome("Episode Title", "Podcast Name", "reflective", 5)

    # Question
    display_question(1, 5, "What did you think?", is_follow_up=False)

    # Should have multiple print calls
    assert mock_console.print.call_count > 5


def test_question_response_preview_flow(mock_console):
    """Test question then response preview."""
    display_question(1, 5, "What are your thoughts?")
    display_response_preview("I thought it was great!")

    assert mock_console.print.call_count > 5
