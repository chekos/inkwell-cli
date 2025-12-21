"""Tests for simplified interview implementation."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from anthropic.types import Message, TextBlock, Usage

from inkwell.interview.simple_interviewer import (
    SimpleInterviewer,
    SimpleInterviewResult,
    conduct_interview_from_output,
)


@pytest.fixture
def mock_anthropic_response():
    """Create a mock Anthropic API response."""

    def create_response(text: str) -> Message:
        return Message(
            id="msg_123",
            type="message",
            role="assistant",
            content=[TextBlock(type="text", text=text)],
            model="claude-sonnet-4-5",
            stop_reason="end_turn",
            usage=Usage(input_tokens=100, output_tokens=50),
        )

    return create_response


@pytest.mark.asyncio
class TestSimpleInterviewer:
    """Tests for SimpleInterviewer class."""

    async def test_init(self):
        """Test interviewer initialization."""
        interviewer = SimpleInterviewer(api_key="test-key")
        assert interviewer.model == "claude-sonnet-4-5"
        assert interviewer.total_tokens == 0
        assert interviewer.total_cost == 0.0

    async def test_build_context(self):
        """Test context building from episode data."""
        interviewer = SimpleInterviewer(api_key="test-key")

        context = interviewer._build_context(
            episode_title="Test Episode",
            podcast_name="Test Podcast",
            summary="This is a summary",
            key_quotes=["Quote 1", "Quote 2"],
            key_concepts=["Concept 1", "Concept 2"],
        )

        assert "Test Podcast" in context
        assert "Test Episode" in context
        assert "This is a summary" in context
        assert "Quote 1" in context
        assert "Concept 1" in context

    async def test_build_context_with_empty_lists(self):
        """Test context building with no quotes or concepts."""
        interviewer = SimpleInterviewer(api_key="test-key")

        context = interviewer._build_context(
            episode_title="Test Episode",
            podcast_name="Test Podcast",
            summary="This is a summary",
            key_quotes=[],
            key_concepts=[],
        )

        assert "Test Podcast" in context
        assert "This is a summary" in context
        assert "Key Quotes:" not in context
        assert "Key Concepts:" not in context

    async def test_format_markdown(self):
        """Test markdown formatting."""
        interviewer = SimpleInterviewer(api_key="test-key")

        exchanges = [
            {"question": "What did you learn?", "response": "I learned a lot"},
            {"question": "How will you apply this?", "response": "In my work"},
        ]

        markdown = interviewer._format_markdown(
            episode_title="Test Episode",
            podcast_name="Test Podcast",
            exchanges=exchanges,
        )

        assert "# My Notes: Test Episode" in markdown
        assert "**Podcast:** Test Podcast" in markdown
        assert "### Q1: What did you learn?" in markdown
        assert "I learned a lot" in markdown
        assert "### Q2: How will you apply this?" in markdown
        assert "In my work" in markdown

    @patch("inkwell.interview.simple_interviewer.AsyncAnthropic")
    @patch("inkwell.interview.simple_interviewer.Prompt.ask")
    async def test_conduct_interview_basic(
        self, mock_prompt, mock_anthropic_class, mock_anthropic_response
    ):
        """Test basic interview flow."""
        # Setup mocks
        mock_client = AsyncMock()
        mock_anthropic_class.return_value = mock_client

        # Mock Claude responses
        mock_client.messages.create.side_effect = [
            mock_anthropic_response("What interested you most?"),
            mock_anthropic_response("How will you use this?"),
        ]

        # Mock user responses
        mock_prompt.side_effect = [
            "The discussion about AI",
            "quit",  # End early
        ]

        # Conduct interview
        interviewer = SimpleInterviewer(api_key="test-key")
        result = await interviewer.conduct_interview(
            episode_title="Test Episode",
            podcast_name="Test Podcast",
            summary="Summary text",
            key_quotes=["Quote 1"],
            key_concepts=["Concept 1"],
            max_questions=5,
        )

        # Verify result
        assert isinstance(result, SimpleInterviewResult)
        assert len(result.exchanges) == 1  # Only one exchange before quit
        assert result.exchanges[0]["question"] == "What interested you most?"
        assert result.exchanges[0]["response"] == "The discussion about AI"
        assert result.total_cost > 0
        assert result.total_tokens > 0
        assert "Test Episode" in result.transcript

    @patch("inkwell.interview.simple_interviewer.AsyncAnthropic")
    @patch("inkwell.interview.simple_interviewer.Prompt.ask")
    async def test_conduct_interview_with_cost_tracker(
        self, mock_prompt, mock_anthropic_class, mock_anthropic_response
    ):
        """Test interview with cost tracker."""
        # Setup mocks
        mock_client = AsyncMock()
        mock_anthropic_class.return_value = mock_client
        mock_cost_tracker = MagicMock()

        mock_client.messages.create.return_value = mock_anthropic_response("What did you think?")
        mock_prompt.return_value = "quit"

        # Conduct interview with cost tracker
        interviewer = SimpleInterviewer(api_key="test-key", cost_tracker=mock_cost_tracker)
        result = await interviewer.conduct_interview(
            episode_title="Test Episode",
            podcast_name="Test Podcast",
            summary="Summary",
            max_questions=1,
        )

        # Verify cost tracker was called
        assert mock_cost_tracker.add_cost.called

    @patch("inkwell.interview.simple_interviewer.AsyncAnthropic")
    @patch("inkwell.interview.simple_interviewer.Prompt.ask")
    async def test_conduct_interview_skip_empty_response(
        self, mock_prompt, mock_anthropic_class, mock_anthropic_response
    ):
        """Test that empty responses are skipped."""
        # Setup mocks
        mock_client = AsyncMock()
        mock_anthropic_class.return_value = mock_client

        mock_client.messages.create.side_effect = [
            mock_anthropic_response("Question 1"),
            mock_anthropic_response("Question 2"),
            mock_anthropic_response("Question 3"),
        ]
        mock_prompt.side_effect = ["", "Valid response", "quit"]

        # Conduct interview
        interviewer = SimpleInterviewer(api_key="test-key")
        result = await interviewer.conduct_interview(
            episode_title="Test", podcast_name="Test", summary="Test", max_questions=3
        )

        # Should have only 1 exchange (empty was skipped)
        assert len(result.exchanges) == 1
        assert result.exchanges[0]["response"] == "Valid response"


@pytest.mark.asyncio
class TestConductInterviewFromOutput:
    """Tests for conduct_interview_from_output convenience function."""

    @patch("inkwell.interview.simple_interviewer.SimpleInterviewer.conduct_interview")
    async def test_conduct_interview_from_output(self, mock_conduct, tmp_path: Path):
        """Test loading content from output directory."""
        # Create mock output files
        output_dir = tmp_path / "episode-output"
        output_dir.mkdir()

        (output_dir / "summary.md").write_text("This is the episode summary")
        (output_dir / "quotes.md").write_text("## Quotes\n\n> Quote 1\n> Quote 2\n")
        (output_dir / "key-concepts.md").write_text(
            "# Key Concepts\n\n## Concept 1\n## Concept 2\n"
        )

        # Mock the conduct_interview method
        mock_result = SimpleInterviewResult(
            transcript="Interview transcript",
            exchanges=[],
            total_cost=0.01,
            total_tokens=100,
        )
        mock_conduct.return_value = mock_result

        # Call function
        result = await conduct_interview_from_output(
            output_dir=output_dir,
            episode_title="Test Episode",
            podcast_name="Test Podcast",
            api_key="test-key",
            max_questions=5,
        )

        # Verify conduct_interview was called with extracted content
        assert mock_conduct.called
        call_kwargs = mock_conduct.call_args.kwargs
        assert call_kwargs["episode_title"] == "Test Episode"
        assert call_kwargs["podcast_name"] == "Test Podcast"
        assert call_kwargs["summary"] == "This is the episode summary"
        assert "Quote 1" in call_kwargs["key_quotes"]
        assert "Quote 2" in call_kwargs["key_quotes"]
        assert "Concept 1" in call_kwargs["key_concepts"]
        assert "Concept 2" in call_kwargs["key_concepts"]

    @patch("inkwell.interview.simple_interviewer.SimpleInterviewer.conduct_interview")
    async def test_conduct_interview_from_output_missing_files(self, mock_conduct, tmp_path: Path):
        """Test handling missing output files gracefully."""
        # Create directory without files
        output_dir = tmp_path / "episode-output"
        output_dir.mkdir()

        # Mock the conduct_interview method
        mock_result = SimpleInterviewResult(
            transcript="Interview", exchanges=[], total_cost=0.01, total_tokens=100
        )
        mock_conduct.return_value = mock_result

        # Call function
        result = await conduct_interview_from_output(
            output_dir=output_dir,
            episode_title="Test",
            podcast_name="Test",
            api_key="test-key",
        )

        # Should still work with empty content
        assert mock_conduct.called
        call_kwargs = mock_conduct.call_args.kwargs
        assert call_kwargs["summary"] == ""
        assert call_kwargs["key_quotes"] == []
        assert call_kwargs["key_concepts"] == []
