"""Tests for interview agent."""

from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from inkwell.interview.agent import InterviewAgent
from inkwell.interview.models import (
    InterviewContext,
    InterviewSession,
    Question,
)


@pytest.fixture
def mock_anthropic():
    """Create mock Anthropic client."""
    with patch("inkwell.interview.agent.AsyncAnthropic") as mock:
        yield mock


@pytest.fixture
def sample_context():
    """Create sample interview context."""
    return InterviewContext(
        podcast_name="Test Podcast",
        episode_title="Test Episode",
        episode_url="https://example.com/test",
        duration_minutes=60.0,
        summary="This is a test episode about testing.",
        key_quotes=[
            {"text": "Testing is important", "speaker": "Guest", "timestamp": "12:34"}
        ],
        key_concepts=["Testing", "Quality", "Best practices"],
        max_questions=5,
    )


@pytest.fixture
def sample_session():
    """Create sample interview session."""
    return InterviewSession(
        episode_url="https://example.com/test",
        episode_title="Test Episode",
        podcast_name="Test Podcast",
        template_name="reflective",
        max_questions=5,
    )


@pytest.fixture
def agent(mock_anthropic):
    """Create interview agent with mocked client."""
    agent = InterviewAgent(api_key="test-key")
    return agent


# Agent Initialization Tests


def test_create_agent(mock_anthropic):
    """Test agent creation with default parameters."""
    agent = InterviewAgent(api_key="test-api-key")

    assert agent.model == "claude-sonnet-4-5"
    assert agent.temperature == 0.7
    assert agent.system_prompt == ""
    mock_anthropic.assert_called_once_with(api_key="test-api-key")


def test_create_agent_custom_params(mock_anthropic):
    """Test agent creation with custom parameters."""
    agent = InterviewAgent(
        api_key="test-key", model="claude-opus-4", temperature=0.5
    )

    assert agent.model == "claude-opus-4"
    assert agent.temperature == 0.5


def test_set_system_prompt(agent):
    """Test setting system prompt."""
    prompt = "You are a helpful interview assistant."
    agent.set_system_prompt(prompt)

    assert agent.system_prompt == prompt


# Question Generation Tests


@pytest.mark.asyncio
async def test_generate_question(agent, sample_context, sample_session):
    """Test generating a question."""
    # Mock API response
    mock_usage = Mock()
    mock_usage.input_tokens = 100
    mock_usage.output_tokens = 50

    mock_content = Mock()
    mock_content.text = "What did you find most interesting about this episode?"

    mock_response = Mock()
    mock_response.content = [mock_content]
    mock_response.usage = mock_usage

    agent.client.messages.create = AsyncMock(return_value=mock_response)

    # Generate question
    question = await agent.generate_question(
        context=sample_context,
        session=sample_session,
        template_prompt="Generate a reflective question.",
    )

    # Verify question
    assert isinstance(question, Question)
    assert question.text == "What did you find most interesting about this episode?"
    assert question.question_number == 1
    assert question.depth_level == 0
    assert "has_summary" in question.context_used
    assert question.context_used["has_summary"] is True
    assert question.context_used["quote_count"] == 1
    assert question.context_used["concept_count"] == 3

    # Verify session updated
    assert sample_session.total_tokens_used == 150
    assert sample_session.total_cost_usd > 0


@pytest.mark.asyncio
async def test_generate_question_with_system_prompt(
    agent, sample_context, sample_session
):
    """Test question generation with system prompt set."""
    agent.set_system_prompt("You are a reflective interviewer.")

    mock_usage = Mock()
    mock_usage.input_tokens = 100
    mock_usage.output_tokens = 50

    mock_content = Mock()
    mock_content.text = "Test question?"

    mock_response = Mock()
    mock_response.content = [mock_content]
    mock_response.usage = mock_usage

    agent.client.messages.create = AsyncMock(return_value=mock_response)

    await agent.generate_question(
        context=sample_context,
        session=sample_session,
        template_prompt="Generate question.",
    )

    # Verify API called with system prompt
    call_kwargs = agent.client.messages.create.call_args[1]
    assert call_kwargs["system"] == "You are a reflective interviewer."


@pytest.mark.asyncio
async def test_generate_question_includes_context(
    agent, sample_context, sample_session
):
    """Test that generated question includes episode context."""
    mock_usage = Mock()
    mock_usage.input_tokens = 100
    mock_usage.output_tokens = 50

    mock_content = Mock()
    mock_content.text = "Question text"

    mock_response = Mock()
    mock_response.content = [mock_content]
    mock_response.usage = mock_usage

    agent.client.messages.create = AsyncMock(return_value=mock_response)

    await agent.generate_question(
        context=sample_context,
        session=sample_session,
        template_prompt="Generate.",
    )

    # Verify prompt includes context
    call_kwargs = agent.client.messages.create.call_args[1]
    user_prompt = call_kwargs["messages"][0]["content"]

    assert "Test Podcast" in user_prompt
    assert "Test Episode" in user_prompt
    assert "This is a test episode" in user_prompt


# Follow-up Generation Tests


@pytest.mark.asyncio
async def test_generate_follow_up(agent, sample_context):
    """Test generating a follow-up question."""
    original_question = Question(
        text="What resonated with you?",
        question_number=1,
        depth_level=0,
    )

    response_text = (
        "I found the discussion about testing very interesting "
        "and it reminded me of my own work."
    )

    mock_usage = Mock()
    mock_usage.input_tokens = 100
    mock_usage.output_tokens = 50

    mock_content = Mock()
    mock_content.text = "Can you tell me more about how this relates to your work?"

    mock_response = Mock()
    mock_response.content = [mock_content]
    mock_response.usage = mock_usage

    agent.client.messages.create = AsyncMock(return_value=mock_response)

    # Generate follow-up
    follow_up = await agent.generate_follow_up(
        question=original_question,
        response_text=response_text,
        context=sample_context,
        template_prompt="Generate deeper question.",
    )

    # Verify follow-up
    assert follow_up is not None
    assert isinstance(follow_up, Question)
    assert follow_up.text == "Can you tell me more about how this relates to your work?"
    assert follow_up.question_number == 1  # Same number
    assert follow_up.depth_level == 1  # One deeper
    assert follow_up.parent_question_id == original_question.id


@pytest.mark.asyncio
async def test_generate_follow_up_max_depth_reached(agent, sample_context):
    """Test that follow-up returns None when max depth reached."""
    original_question = Question(
        text="Deep question",
        question_number=1,
        depth_level=2,  # At max depth
    )

    response_text = "Long response with more than ten words here."

    # Should return None without calling API
    follow_up = await agent.generate_follow_up(
        question=original_question,
        response_text=response_text,
        context=sample_context,
        template_prompt="Generate.",
        max_depth=2,
    )

    assert follow_up is None


@pytest.mark.asyncio
async def test_generate_follow_up_response_too_brief(agent, sample_context):
    """Test that follow-up returns None for brief responses."""
    original_question = Question(
        text="Question",
        question_number=1,
        depth_level=0,
    )

    response_text = "Yes."  # Only 1 word

    # Should return None without calling API
    follow_up = await agent.generate_follow_up(
        question=original_question,
        response_text=response_text,
        context=sample_context,
        template_prompt="Generate.",
    )

    assert follow_up is None


# Streaming Tests


@pytest.mark.asyncio
async def test_stream_question(agent, sample_context, sample_session):
    """Test streaming question generation."""

    # Create async iterator for text stream
    class AsyncTextIterator:
        def __init__(self, items):
            self.items = items
            self.index = 0

        def __aiter__(self):
            return self

        async def __anext__(self):
            if self.index >= len(self.items):
                raise StopAsyncIteration
            item = self.items[self.index]
            self.index += 1
            return item

    # Mock streaming response
    mock_stream = AsyncMock()
    mock_stream.text_stream = AsyncTextIterator(["What ", "did ", "you ", "think?"])

    mock_stream_context = MagicMock()
    mock_stream_context.__aenter__ = AsyncMock(return_value=mock_stream)
    mock_stream_context.__aexit__ = AsyncMock(return_value=None)

    agent.client.messages.stream = Mock(return_value=mock_stream_context)

    # Collect streamed chunks
    chunks = []
    async for chunk in agent.stream_question(
        context=sample_context,
        session=sample_session,
        template_prompt="Generate.",
    ):
        chunks.append(chunk)

    # Verify chunks
    assert chunks == ["What ", "did ", "you ", "think?"]


# Prompt Building Tests


def test_build_question_prompt_basic(agent, sample_context, sample_session):
    """Test building basic question prompt."""
    prompt = agent._build_question_prompt(
        context=sample_context,
        session=sample_session,
        template_prompt="Generate a reflective question.",
    )

    # Verify context included
    assert "Test Podcast" in prompt
    assert "Test Episode" in prompt
    assert "This is a test episode" in prompt

    # Verify template prompt included
    assert "Generate a reflective question." in prompt

    # Verify progress included
    assert "question 1 of approximately 5" in prompt.lower()


def test_build_question_prompt_with_previous_questions(
    agent, sample_context, sample_session
):
    """Test prompt includes previous questions to avoid repetition."""
    from inkwell.interview.models import Response

    # Add some exchanges
    q1 = Question(text="First question?", question_number=1)
    r1 = Response(question_id=q1.id, text="First answer")
    sample_session.add_exchange(q1, r1)

    q2 = Question(text="Second question?", question_number=2)
    r2 = Response(question_id=q2.id, text="Second answer")
    sample_session.add_exchange(q2, r2)

    prompt = agent._build_question_prompt(
        context=sample_context,
        session=sample_session,
        template_prompt="Generate.",
    )

    # Verify previous questions included
    assert "Previous Questions Asked" in prompt
    assert "First question?" in prompt
    assert "Second question?" in prompt


def test_build_question_prompt_limits_previous_questions(
    agent, sample_context, sample_session
):
    """Test that only last 3 questions are included."""
    from inkwell.interview.models import Response

    # Add 5 exchanges
    for i in range(5):
        q = Question(text=f"Question {i+1}?", question_number=i + 1)
        r = Response(question_id=q.id, text=f"Answer {i+1}")
        sample_session.add_exchange(q, r)

    prompt = agent._build_question_prompt(
        context=sample_context,
        session=sample_session,
        template_prompt="Generate.",
    )

    # Should only include questions 3, 4, 5
    assert "Question 3?" in prompt
    assert "Question 4?" in prompt
    assert "Question 5?" in prompt
    assert "Question 1?" not in prompt
    assert "Question 2?" not in prompt


# Cost Calculation Tests


def test_calculate_cost():
    """Test cost calculation with known values."""
    agent = InterviewAgent(api_key="test-key")

    mock_usage = Mock()
    mock_usage.input_tokens = 1_000_000  # 1M input tokens
    mock_usage.output_tokens = 1_000_000  # 1M output tokens

    cost = agent._calculate_cost(mock_usage)

    # 1M input @ $3/M = $3
    # 1M output @ $15/M = $15
    # Total = $18
    assert cost == 18.0


def test_calculate_cost_small_amounts():
    """Test cost calculation for small token counts."""
    agent = InterviewAgent(api_key="test-key")

    mock_usage = Mock()
    mock_usage.input_tokens = 100
    mock_usage.output_tokens = 50

    cost = agent._calculate_cost(mock_usage)

    # Should be small but non-zero
    assert 0 < cost < 0.01
    # 100 input @ $3/M = $0.0003
    # 50 output @ $15/M = $0.00075
    # Total = $0.00105
    assert abs(cost - 0.00105) < 0.00001


# Edge Cases


@pytest.mark.asyncio
async def test_generate_question_strips_whitespace(
    agent, sample_context, sample_session
):
    """Test that generated question text is stripped."""
    mock_usage = Mock()
    mock_usage.input_tokens = 100
    mock_usage.output_tokens = 50

    mock_content = Mock()
    mock_content.text = "  \n  Question with whitespace?  \n  "

    mock_response = Mock()
    mock_response.content = [mock_content]
    mock_response.usage = mock_usage

    agent.client.messages.create = AsyncMock(return_value=mock_response)

    question = await agent.generate_question(
        context=sample_context,
        session=sample_session,
        template_prompt="Generate.",
    )

    assert question.text == "Question with whitespace?"


@pytest.mark.asyncio
async def test_generate_question_increments_question_number(
    agent, sample_context, sample_session
):
    """Test that question number increments correctly."""
    from inkwell.interview.models import Response

    # Add one exchange
    q1 = Question(text="First?", question_number=1)
    r1 = Response(question_id=q1.id, text="Answer")
    sample_session.add_exchange(q1, r1)

    mock_usage = Mock()
    mock_usage.input_tokens = 100
    mock_usage.output_tokens = 50

    mock_content = Mock()
    mock_content.text = "Second question?"

    mock_response = Mock()
    mock_response.content = [mock_content]
    mock_response.usage = mock_usage

    agent.client.messages.create = AsyncMock(return_value=mock_response)

    question = await agent.generate_question(
        context=sample_context,
        session=sample_session,
        template_prompt="Generate.",
    )

    assert question.question_number == 2


@pytest.mark.asyncio
async def test_generate_question_tracks_tokens_cumulative(
    agent, sample_context, sample_session
):
    """Test that tokens accumulate across multiple questions."""
    sample_session.total_tokens_used = 100

    mock_usage = Mock()
    mock_usage.input_tokens = 50
    mock_usage.output_tokens = 25

    mock_content = Mock()
    mock_content.text = "Question?"

    mock_response = Mock()
    mock_response.content = [mock_content]
    mock_response.usage = mock_usage

    agent.client.messages.create = AsyncMock(return_value=mock_response)

    await agent.generate_question(
        context=sample_context,
        session=sample_session,
        template_prompt="Generate.",
    )

    # Should add 75 to existing 100
    assert sample_session.total_tokens_used == 175
