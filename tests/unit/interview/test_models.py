"""Tests for interview data models."""

from datetime import datetime, timedelta

import pytest
from pydantic import ValidationError

from inkwell.interview.models import (
    Exchange,
    InterviewContext,
    InterviewGuidelines,
    InterviewResult,
    InterviewSession,
    InterviewTemplate,
    Question,
    Response,
)


class TestQuestion:
    """Tests for Question model."""

    def test_create_question(self) -> None:
        """Test creating a question."""
        question = Question(text="What surprised you?", question_number=1)

        assert question.text == "What surprised you?"
        assert question.question_number == 1
        assert question.depth_level == 0
        assert question.parent_question_id is None
        assert question.id  # Auto-generated UUID
        assert isinstance(question.generated_at, datetime)

    def test_question_with_depth(self) -> None:
        """Test question with depth level."""
        parent_id = "parent-123"
        question = Question(
            text="Can you elaborate?",
            question_number=1,
            depth_level=1,
            parent_question_id=parent_id,
        )

        assert question.depth_level == 1
        assert question.parent_question_id == parent_id

    def test_empty_text_raises_error(self) -> None:
        """Test that empty question text raises error."""
        with pytest.raises(ValidationError):
            Question(text="", question_number=1)

        with pytest.raises(ValidationError):
            Question(text="   ", question_number=1)

    def test_whitespace_stripped(self) -> None:
        """Test that whitespace is stripped from question text."""
        question = Question(text="  What do you think?  ", question_number=1)
        assert question.text == "What do you think?"

    def test_negative_question_number_raises_error(self) -> None:
        """Test that negative question number raises error."""
        with pytest.raises(ValidationError):
            Question(text="Test", question_number=0)

        with pytest.raises(ValidationError):
            Question(text="Test", question_number=-1)

    def test_negative_depth_raises_error(self) -> None:
        """Test that negative depth level raises error."""
        with pytest.raises(ValidationError):
            Question(text="Test", question_number=1, depth_level=-1)


class TestResponse:
    """Tests for Response model."""

    def test_create_response(self) -> None:
        """Test creating a response."""
        response = Response(question_id="q1", text="I thought it was interesting.")

        assert response.question_id == "q1"
        assert response.text == "I thought it was interesting."
        assert response.word_count == 5  # "I thought it was interesting." = 5 words
        assert isinstance(response.responded_at, datetime)

    def test_word_count_calculated(self) -> None:
        """Test that word count is automatically calculated."""
        response = Response(question_id="q1", text="One two three four five")
        assert response.word_count == 5

    def test_word_count_override(self) -> None:
        """Test that provided word count is preserved."""
        response = Response(question_id="q1", text="Test", word_count=10)
        assert response.word_count == 10

    def test_is_substantive(self) -> None:
        """Test substantive response detection."""
        # Substantive responses (>= 5 words, not skip command)
        substantive = Response(question_id="q1", text="This is a thoughtful response here")
        assert substantive.is_substantive

        # Not substantive - too short
        short = Response(question_id="q1", text="Yes")
        assert not short.is_substantive

        # Not substantive - skip command
        skip = Response(question_id="q1", text="skip")
        assert not skip.is_substantive

    def test_is_skip(self) -> None:
        """Test skip command detection."""
        assert Response(question_id="q1", text="skip").is_skip
        assert Response(question_id="q1", text="SKIP").is_skip
        assert Response(question_id="q1", text="  skip  ").is_skip
        assert Response(question_id="q1", text="pass").is_skip
        assert Response(question_id="q1", text="next").is_skip

        assert not Response(question_id="q1", text="I'll skip this part").is_skip
        assert not Response(question_id="q1", text="done").is_skip

    def test_is_exit(self) -> None:
        """Test exit command detection."""
        assert Response(question_id="q1", text="done").is_exit
        assert Response(question_id="q1", text="QUIT").is_exit
        assert Response(question_id="q1", text="  exit  ").is_exit
        assert Response(question_id="q1", text="finish").is_exit

        assert not Response(question_id="q1", text="skip").is_exit
        assert not Response(question_id="q1", text="I'm done thinking").is_exit

    def test_thinking_time(self) -> None:
        """Test thinking time tracking."""
        response = Response(
            question_id="q1", text="Response", thinking_time_seconds=45.5
        )
        assert response.thinking_time_seconds == 45.5


class TestExchange:
    """Tests for Exchange model."""

    def test_create_exchange(self) -> None:
        """Test creating a question-response exchange."""
        question = Question(text="What surprised you?", question_number=1)
        response = Response(question_id=question.id, text="The scale of the problem.")

        exchange = Exchange(question=question, response=response)

        assert exchange.question == question
        assert exchange.response == response
        assert exchange.depth_level == 0

    def test_depth_level_from_question(self) -> None:
        """Test that depth level comes from question."""
        question = Question(text="Test", question_number=1, depth_level=2)
        response = Response(question_id=question.id, text="Answer")
        exchange = Exchange(question=question, response=response)

        assert exchange.depth_level == 2

    def test_is_substantive(self) -> None:
        """Test substantive exchange detection."""
        question = Question(text="Test", question_number=1)

        # Substantive exchange
        substantive_response = Response(
            question_id=question.id, text="This is a detailed thoughtful answer"
        )
        substantive_exchange = Exchange(question=question, response=substantive_response)
        assert substantive_exchange.is_substantive

        # Non-substantive exchange
        skip_response = Response(question_id=question.id, text="skip")
        skip_exchange = Exchange(question=question, response=skip_response)
        assert not skip_exchange.is_substantive


class TestInterviewSession:
    """Tests for InterviewSession model."""

    def test_create_session(self) -> None:
        """Test creating an interview session."""
        session = InterviewSession(
            episode_url="https://example.com/episode",
            episode_title="Episode Title",
            podcast_name="My Podcast",
        )

        assert session.episode_url == "https://example.com/episode"
        assert session.episode_title == "Episode Title"
        assert session.podcast_name == "My Podcast"
        assert session.session_id  # Auto-generated UUID
        assert session.status == "active"
        assert session.question_count == 0
        assert len(session.exchanges) == 0

    def test_add_exchange(self) -> None:
        """Test adding exchange to session."""
        session = InterviewSession(
            episode_url="https://example.com/episode",
            episode_title="Test",
            podcast_name="Test",
        )

        question = Question(text="What surprised you?", question_number=1)
        response = Response(question_id=question.id, text="The scale.")

        session.add_exchange(question, response)

        assert session.question_count == 1
        assert len(session.exchanges) == 1
        assert session.current_question_number == 1

    def test_substantive_response_count(self) -> None:
        """Test counting substantive responses."""
        session = InterviewSession(
            episode_url="https://example.com/episode",
            episode_title="Test",
            podcast_name="Test",
        )

        # Add substantive response
        q1 = Question(text="Q1", question_number=1)
        r1 = Response(question_id=q1.id, text="This is a substantive response here")
        session.add_exchange(q1, r1)

        # Add skip response
        q2 = Question(text="Q2", question_number=2)
        r2 = Response(question_id=q2.id, text="skip")
        session.add_exchange(q2, r2)

        assert session.question_count == 2
        assert session.substantive_response_count == 1

    def test_average_response_length(self) -> None:
        """Test average response length calculation."""
        session = InterviewSession(
            episode_url="https://example.com/episode",
            episode_title="Test",
            podcast_name="Test",
        )

        # Add responses of different lengths
        q1 = Question(text="Q1", question_number=1)
        r1 = Response(question_id=q1.id, text="Short")  # 1 word
        session.add_exchange(q1, r1)

        q2 = Question(text="Q2", question_number=2)
        r2 = Response(question_id=q2.id, text="Much longer response here")  # 4 words
        session.add_exchange(q2, r2)

        assert session.average_response_length == 2.5  # (1 + 4) / 2

    def test_average_response_length_empty(self) -> None:
        """Test average response length when no exchanges."""
        session = InterviewSession(
            episode_url="https://example.com/episode",
            episode_title="Test",
            podcast_name="Test",
        )

        assert session.average_response_length == 0.0

    def test_total_thinking_time(self) -> None:
        """Test total thinking time calculation."""
        session = InterviewSession(
            episode_url="https://example.com/episode",
            episode_title="Test",
            podcast_name="Test",
        )

        q1 = Question(text="Q1", question_number=1)
        r1 = Response(question_id=q1.id, text="Answer", thinking_time_seconds=30.0)
        session.add_exchange(q1, r1)

        q2 = Question(text="Q2", question_number=2)
        r2 = Response(question_id=q2.id, text="Answer", thinking_time_seconds=45.5)
        session.add_exchange(q2, r2)

        assert session.total_thinking_time == 75.5

    def test_session_lifecycle(self) -> None:
        """Test session status lifecycle."""
        session = InterviewSession(
            episode_url="https://example.com/episode",
            episode_title="Test",
            podcast_name="Test",
        )

        # Start active
        assert session.status == "active"
        assert not session.is_complete

        # Pause
        session.pause()
        assert session.status == "paused"

        # Resume
        session.resume()
        assert session.status == "active"

        # Complete
        session.complete()
        assert session.status == "completed"
        assert session.is_complete
        assert session.completed_at is not None

        # Abandon
        session2 = InterviewSession(
            episode_url="https://example.com/episode",
            episode_title="Test",
            podcast_name="Test",
        )
        session2.abandon()
        assert session2.status == "abandoned"

    def test_duration(self) -> None:
        """Test session duration calculation."""
        session = InterviewSession(
            episode_url="https://example.com/episode",
            episode_title="Test",
            podcast_name="Test",
        )

        # Active session - duration is current time - start
        duration1 = session.duration
        assert isinstance(duration1, timedelta)
        assert duration1.total_seconds() >= 0

        # Completed session - duration is completed_at - started_at
        session.complete()
        duration2 = session.duration
        assert isinstance(duration2, timedelta)

    def test_mark_updated(self) -> None:
        """Test updating timestamp."""
        session = InterviewSession(
            episode_url="https://example.com/episode",
            episode_title="Test",
            podcast_name="Test",
        )

        original_updated_at = session.updated_at
        session.mark_updated()

        assert session.updated_at > original_updated_at


class TestInterviewGuidelines:
    """Tests for InterviewGuidelines model."""

    def test_create_guidelines(self) -> None:
        """Test creating interview guidelines."""
        guidelines = InterviewGuidelines(
            content="Focus on practical applications.",
            focus_areas=["work", "software"],
            question_style="open-ended",
            depth_preference="deep",
        )

        assert guidelines.content == "Focus on practical applications."
        assert guidelines.focus_areas == ["work", "software"]
        assert guidelines.question_style == "open-ended"
        assert guidelines.depth_preference == "deep"

    def test_defaults(self) -> None:
        """Test default values."""
        guidelines = InterviewGuidelines(content="Test")

        assert guidelines.focus_areas == []
        assert guidelines.question_style == "open-ended"
        assert guidelines.depth_preference == "moderate"


class TestInterviewTemplate:
    """Tests for InterviewTemplate model."""

    def test_create_template(self) -> None:
        """Test creating an interview template."""
        template = InterviewTemplate(
            name="reflective",
            description="Deep reflection",
            system_prompt="You are a reflective interviewer...",
            initial_question_prompt="Ask about resonance...",
            follow_up_prompt="Go deeper...",
            conclusion_prompt="Ask about action...",
        )

        assert template.name == "reflective"
        assert template.description == "Deep reflection"
        assert template.target_questions == 5  # Default
        assert template.max_depth == 3  # Default
        assert template.temperature == 0.7  # Default

    def test_template_name_validation(self) -> None:
        """Test template name validation."""
        # Valid names
        InterviewTemplate(
            name="reflective",
            description="Test",
            system_prompt="Test",
            initial_question_prompt="Test",
            follow_up_prompt="Test",
            conclusion_prompt="Test",
        )

        InterviewTemplate(
            name="my-template",
            description="Test",
            system_prompt="Test",
            initial_question_prompt="Test",
            follow_up_prompt="Test",
            conclusion_prompt="Test",
        )

        # Invalid name (special characters)
        with pytest.raises(ValidationError):
            InterviewTemplate(
                name="my template!",  # Space and exclamation
                description="Test",
                system_prompt="Test",
                initial_question_prompt="Test",
                follow_up_prompt="Test",
                conclusion_prompt="Test",
            )

    def test_custom_parameters(self) -> None:
        """Test custom template parameters."""
        template = InterviewTemplate(
            name="analytical",
            description="Critical analysis",
            system_prompt="Test",
            initial_question_prompt="Test",
            follow_up_prompt="Test",
            conclusion_prompt="Test",
            target_questions=7,
            max_depth=2,
            temperature=0.5,
        )

        assert template.target_questions == 7
        assert template.max_depth == 2
        assert template.temperature == 0.5


class TestInterviewContext:
    """Tests for InterviewContext model."""

    def test_create_context(self) -> None:
        """Test creating interview context."""
        context = InterviewContext(
            podcast_name="My Podcast",
            episode_title="Episode 1",
            episode_url="https://example.com/episode",
            duration_minutes=60.0,
            summary="Episode summary...",
        )

        assert context.podcast_name == "My Podcast"
        assert context.episode_title == "Episode 1"
        assert context.duration_minutes == 60.0
        assert context.summary == "Episode summary..."

    def test_context_with_quotes(self) -> None:
        """Test context with quotes."""
        context = InterviewContext(
            podcast_name="Test",
            episode_title="Test",
            episode_url="https://example.com",
            duration_minutes=30.0,
            summary="Test",
            key_quotes=[
                {"text": "Quote 1", "speaker": "Speaker 1"},
                {"text": "Quote 2", "speaker": "Speaker 2"},
            ],
        )

        assert len(context.key_quotes) == 2

    def test_to_prompt_context(self) -> None:
        """Test conversion to prompt context string."""
        context = InterviewContext(
            podcast_name="My Podcast",
            episode_title="AI Safety",
            episode_url="https://example.com",
            duration_minutes=45.0,
            summary="Discussion about AI alignment.",
            key_quotes=[{"text": "Alignment is critical", "speaker": "Expert"}],
            key_concepts=["Alignment", "Safety", "Scaling"],
        )

        prompt = context.to_prompt_context()

        assert "# Episode: AI Safety" in prompt
        assert "Podcast: My Podcast" in prompt
        assert "Duration: 45 minutes" in prompt
        assert "## Summary" in prompt
        assert "Discussion about AI alignment" in prompt
        assert "## Notable Quotes" in prompt
        assert '"Alignment is critical"' in prompt
        assert "## Key Concepts" in prompt
        assert "- Alignment" in prompt

    def test_to_prompt_context_with_guidelines(self) -> None:
        """Test prompt context with user guidelines."""
        guidelines = InterviewGuidelines(
            content="Focus on practical applications in software engineering."
        )

        context = InterviewContext(
            podcast_name="Test",
            episode_title="Test",
            episode_url="https://example.com",
            duration_minutes=30.0,
            summary="Test",
            guidelines=guidelines,
        )

        prompt = context.to_prompt_context()

        assert "## User's Interview Guidelines" in prompt
        assert "practical applications" in prompt


class TestInterviewResult:
    """Tests for InterviewResult model."""

    def test_create_result(self) -> None:
        """Test creating interview result."""
        session = InterviewSession(
            episode_url="https://example.com",
            episode_title="Test",
            podcast_name="Test",
        )
        session.complete()

        result = InterviewResult(
            session=session,
            formatted_transcript="# Interview\n\nQ: Test\nA: Answer",
            key_insights=["Insight 1", "Insight 2"],
            action_items=["Action 1"],
        )

        assert result.session == session
        assert result.formatted_transcript.startswith("# Interview")
        assert len(result.key_insights) == 2
        assert len(result.action_items) == 1

    def test_word_count(self) -> None:
        """Test word count calculation."""
        session = InterviewSession(
            episode_url="https://example.com",
            episode_title="Test",
            podcast_name="Test",
        )

        q1 = Question(text="Q1", question_number=1)
        r1 = Response(question_id=q1.id, text="One two three")  # 3 words
        session.add_exchange(q1, r1)

        q2 = Question(text="Q2", question_number=2)
        r2 = Response(question_id=q2.id, text="Four five")  # 2 words
        session.add_exchange(q2, r2)

        result = InterviewResult(session=session, formatted_transcript="Test")

        assert result.word_count == 5  # 3 + 2

    def test_duration_minutes(self) -> None:
        """Test duration calculation in minutes."""
        session = InterviewSession(
            episode_url="https://example.com",
            episode_title="Test",
            podcast_name="Test",
        )
        session.complete()

        result = InterviewResult(session=session, formatted_transcript="Test")

        # Duration should be > 0 (session just created and completed)
        assert result.duration_minutes >= 0

    def test_quality_metrics(self) -> None:
        """Test quality metrics."""
        session = InterviewSession(
            episode_url="https://example.com",
            episode_title="Test",
            podcast_name="Test",
        )

        result = InterviewResult(
            session=session,
            formatted_transcript="Test",
            quality_score=0.85,
            quality_notes=["Good depth", "Clear insights"],
        )

        assert result.quality_score == 0.85
        assert len(result.quality_notes) == 2
