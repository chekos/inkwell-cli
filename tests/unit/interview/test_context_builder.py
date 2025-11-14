"""Tests for interview context builder."""

from datetime import datetime
from pathlib import Path

import pytest

from inkwell.interview.context_builder import InterviewContextBuilder
from inkwell.interview.models import InterviewGuidelines
from inkwell.output.models import EpisodeMetadata, EpisodeOutput, OutputFile


@pytest.fixture
def sample_metadata():
    """Create sample episode metadata."""
    return EpisodeMetadata(
        podcast_name="The Changelog",
        episode_title="Building Better Software",
        episode_url="https://example.com/ep123",
        published_date=datetime(2025, 11, 1),
        duration_seconds=3600.0,  # 1 hour
        transcription_source="youtube",
    )


@pytest.fixture
def sample_summary_file():
    """Create sample summary file."""
    content = """# Summary

This is a fascinating episode about building better software.
The host interviews a guest about their experience with distributed systems.

They discuss best practices and common pitfalls.

## Key Takeaways

The episode emphasizes the importance of testing."""

    return OutputFile(
        filename="summary.md",
        template_name="summary",
        content=content,
    )


@pytest.fixture
def sample_quotes_file():
    """Create sample quotes file with various formats."""
    content = '''> "The best code is code that never has to be written."
> — Guest Name [12:34]

> "Testing is not optional, it's essential."
> — Host [23:45]

> "Distributed systems are hard but rewarding."
> — Guest Name

Some other text here.

> "Always start with the simplest solution."
> — Guest Name [45:00]
'''

    return OutputFile(
        filename="quotes.md",
        template_name="quotes",
        content=content,
    )


@pytest.fixture
def sample_concepts_file():
    """Create sample concepts file with bullets and numbers."""
    content = """# Key Concepts

- Distributed systems architecture
- Eventual consistency
- CAP theorem
* Microservices patterns
- API design principles

## Additional Notes

1. Service mesh
2. Container orchestration
3. Event-driven architecture
"""

    return OutputFile(
        filename="key-concepts.md",
        template_name="key-concepts",
        content=content,
    )


@pytest.fixture
def sample_tools_file():
    """Create sample tools-mentioned file."""
    content = """# Tools Mentioned

- Kubernetes
- Docker
- Terraform
* Prometheus
- Grafana
"""

    return OutputFile(
        filename="tools-mentioned.md",
        template_name="tools-mentioned",
        content=content,
    )


@pytest.fixture
def sample_episode_output(
    sample_metadata,
    sample_summary_file,
    sample_quotes_file,
    sample_concepts_file,
    sample_tools_file,
):
    """Create sample episode output with all files."""
    output = EpisodeOutput(
        metadata=sample_metadata,
        output_dir=Path("/tmp/test-output"),
    )
    output.add_file(sample_summary_file)
    output.add_file(sample_quotes_file)
    output.add_file(sample_concepts_file)
    output.add_file(sample_tools_file)
    return output


@pytest.fixture
def context_builder():
    """Create context builder instance."""
    return InterviewContextBuilder()


# Basic Context Building Tests


def test_build_context_basic(context_builder, sample_episode_output):
    """Test basic context building from episode output."""
    context = context_builder.build_context(
        episode_output=sample_episode_output,
        max_questions=5,
    )

    # Check episode metadata
    assert context.podcast_name == "The Changelog"
    assert context.episode_title == "Building Better Software"
    assert context.episode_url == "https://example.com/ep123"
    assert context.duration_minutes == 60.0  # 3600 seconds / 60

    # Check context settings
    assert context.max_questions == 5
    assert context.questions_asked == 0
    assert context.depth_level == 0
    assert context.guidelines is None


def test_build_context_with_guidelines(context_builder, sample_episode_output):
    """Test context building with user guidelines."""
    guidelines = InterviewGuidelines(
        content="Focus on practical applications and real-world examples.",
        focus_areas=["work-applications", "team-practices"],
        question_style="specific",
        depth_preference="deep",
    )

    context = context_builder.build_context(
        episode_output=sample_episode_output,
        guidelines=guidelines,
        max_questions=7,
    )

    assert context.guidelines == guidelines
    assert context.max_questions == 7


# Summary Extraction Tests


def test_extract_summary(context_builder, sample_episode_output):
    """Test summary extraction removes headers."""
    context = context_builder.build_context(sample_episode_output)

    # Should contain main content but not headers
    assert "fascinating episode" in context.summary
    assert "distributed systems" in context.summary
    assert "importance of testing" in context.summary

    # Should not contain markdown headers
    assert "# Summary" not in context.summary
    assert "## Key Takeaways" not in context.summary


def test_extract_summary_missing_file(context_builder, sample_metadata):
    """Test summary extraction when file is missing."""
    output = EpisodeOutput(
        metadata=sample_metadata,
        output_dir=Path("/tmp/test"),
    )

    context = context_builder.build_context(output)
    assert context.summary == ""


# Quote Extraction Tests


def test_extract_quotes(context_builder, sample_episode_output):
    """Test quote extraction from various formats."""
    context = context_builder.build_context(sample_episode_output)

    # Should extract all 4 quotes
    assert len(context.key_quotes) == 4

    # Check first quote (with timestamp)
    quote1 = context.key_quotes[0]
    assert quote1["text"] == "The best code is code that never has to be written."
    assert quote1["speaker"] == "Guest Name"
    assert quote1["timestamp"] == "12:34"

    # Check second quote
    quote2 = context.key_quotes[1]
    assert quote2["text"] == "Testing is not optional, it's essential."
    assert quote2["speaker"] == "Host"
    assert quote2["timestamp"] == "23:45"

    # Check third quote (no timestamp)
    quote3 = context.key_quotes[2]
    assert quote3["text"] == "Distributed systems are hard but rewarding."
    assert quote3["speaker"] == "Guest Name"
    assert quote3["timestamp"] == ""

    # Check fourth quote
    quote4 = context.key_quotes[3]
    assert quote4["text"] == "Always start with the simplest solution."
    assert quote4["speaker"] == "Guest Name"
    assert quote4["timestamp"] == "45:00"


def test_extract_quotes_missing_file(context_builder, sample_metadata):
    """Test quote extraction when file is missing."""
    output = EpisodeOutput(
        metadata=sample_metadata,
        output_dir=Path("/tmp/test"),
    )

    context = context_builder.build_context(output)
    assert context.key_quotes == []


# Concept Extraction Tests


def test_extract_concepts(context_builder, sample_episode_output):
    """Test concept extraction from bullets and numbered lists."""
    context = context_builder.build_context(sample_episode_output)

    # Should extract concepts from both bullet and numbered lists
    assert len(context.key_concepts) == 8

    # Check some specific concepts
    assert "Distributed systems architecture" in context.key_concepts
    assert "Eventual consistency" in context.key_concepts
    assert "CAP theorem" in context.key_concepts
    assert "Microservices patterns" in context.key_concepts
    assert "Service mesh" in context.key_concepts
    assert "Container orchestration" in context.key_concepts


def test_extract_concepts_filters_short(context_builder, sample_metadata):
    """Test that very short concepts are filtered out."""
    concepts_file = OutputFile(
        filename="key-concepts.md",
        template_name="key-concepts",
        content="- AI\n- Machine Learning\n- ML\n- Deep Neural Networks\n",
    )

    output = EpisodeOutput(metadata=sample_metadata, output_dir=Path("/tmp/test"))
    output.add_file(concepts_file)

    context = context_builder.build_context(output)

    # "AI" and "ML" should be filtered (<=3 chars)
    assert "AI" not in context.key_concepts
    assert "ML" not in context.key_concepts
    # Longer ones should be included
    assert "Machine Learning" in context.key_concepts
    assert "Deep Neural Networks" in context.key_concepts


def test_extract_concepts_missing_file(context_builder, sample_metadata):
    """Test concept extraction when file is missing."""
    output = EpisodeOutput(
        metadata=sample_metadata,
        output_dir=Path("/tmp/test"),
    )

    context = context_builder.build_context(output)
    assert context.key_concepts == []


# Additional Content Extraction Tests


def test_extract_additional_content(context_builder, sample_episode_output):
    """Test extraction of additional content templates."""
    context = context_builder.build_context(sample_episode_output)

    # Should have tools-mentioned
    assert "tools-mentioned" in context.additional_extractions
    tools = context.additional_extractions["tools-mentioned"]

    assert len(tools) == 5
    assert "Kubernetes" in tools
    assert "Docker" in tools
    assert "Terraform" in tools
    assert "Prometheus" in tools
    assert "Grafana" in tools


def test_extract_additional_content_books(context_builder, sample_metadata):
    """Test extraction of books-mentioned."""
    books_file = OutputFile(
        filename="books-mentioned.md",
        template_name="books-mentioned",
        content="""# Books Mentioned

1. The Pragmatic Programmer
2. Clean Code
3. Design Patterns
""",
    )

    output = EpisodeOutput(metadata=sample_metadata, output_dir=Path("/tmp/test"))
    output.add_file(books_file)

    context = context_builder.build_context(output)

    assert "books-mentioned" in context.additional_extractions
    books = context.additional_extractions["books-mentioned"]
    assert len(books) == 3
    assert "The Pragmatic Programmer" in books
    assert "Clean Code" in books


def test_extract_additional_content_empty(context_builder, sample_metadata):
    """Test additional content extraction with no additional files."""
    output = EpisodeOutput(
        metadata=sample_metadata,
        output_dir=Path("/tmp/test"),
    )

    context = context_builder.build_context(output)
    assert context.additional_extractions == {}


# Edge Cases


def test_build_context_empty_episode(context_builder, sample_metadata):
    """Test building context from episode with no extracted files."""
    output = EpisodeOutput(
        metadata=sample_metadata,
        output_dir=Path("/tmp/test"),
    )

    context = context_builder.build_context(output)

    # Should still build valid context with defaults
    assert context.podcast_name == "The Changelog"
    assert context.summary == ""
    assert context.key_quotes == []
    assert context.key_concepts == []
    assert context.additional_extractions == {}


def test_build_context_no_duration(context_builder):
    """Test building context when duration is not set."""
    metadata = EpisodeMetadata(
        podcast_name="Test Podcast",
        episode_title="Test Episode",
        episode_url="https://example.com/test",
        transcription_source="youtube",
        duration_seconds=None,
    )

    output = EpisodeOutput(metadata=metadata, output_dir=Path("/tmp/test"))
    context = context_builder.build_context(output)

    assert context.duration_minutes == 0.0


def test_to_prompt_context_formatting(context_builder, sample_episode_output):
    """Test that context converts to well-formatted prompt string."""
    guidelines = InterviewGuidelines(
        content="Focus on practical applications.",
        focus_areas=["work"],
    )

    context = context_builder.build_context(
        episode_output=sample_episode_output,
        guidelines=guidelines,
    )

    prompt_context = context.to_prompt_context()

    # Check structure
    assert "# Episode: Building Better Software" in prompt_context
    assert "Podcast: The Changelog" in prompt_context
    assert "Duration: 60 minutes" in prompt_context
    assert "## Summary" in prompt_context
    assert "## Notable Quotes" in prompt_context
    assert "## Key Concepts" in prompt_context
    assert "## User's Interview Guidelines" in prompt_context
    assert "Focus on practical applications" in prompt_context

    # Check quotes are included
    assert "The best code is code that never has to be written" in prompt_context

    # Check concepts are included
    assert "Distributed systems architecture" in prompt_context


def test_extract_list_items_various_formats(context_builder, sample_metadata):
    """Test list item extraction with various markdown formats."""
    mixed_file = OutputFile(
        filename="test.md",
        template_name="test",
        content="""
- Item with dash
* Item with star
1. Numbered item one
2. Numbered item two
10. Numbered item ten

Not a list item
# Header should be ignored
""",
    )

    output = EpisodeOutput(metadata=sample_metadata, output_dir=Path("/tmp/test"))
    output.add_file(mixed_file)

    items = context_builder._extract_list_items(mixed_file)

    assert len(items) == 5
    assert "Item with dash" in items
    assert "Item with star" in items
    assert "Numbered item one" in items
    assert "Numbered item two" in items
    assert "Numbered item ten" in items
    assert "Not a list item" not in items


# Previous Interviews Tests


def test_load_previous_interviews_empty_dir(context_builder, tmp_path):
    """Test loading previous interviews from empty directory."""
    summaries = context_builder.load_previous_interviews(tmp_path)
    assert summaries == []


def test_load_previous_interviews_nonexistent_dir(context_builder):
    """Test loading previous interviews from nonexistent directory."""
    summaries = context_builder.load_previous_interviews(Path("/tmp/nonexistent-12345"))
    assert summaries == []


def test_load_previous_interviews_with_files(context_builder, tmp_path):
    """Test loading previous interviews when files exist."""
    import json
    import time
    from datetime import datetime, timedelta

    # Create some mock session files with valid JSON
    base_date = datetime(2025, 11, 1, 10, 0, 0)
    for i in range(1, 4):
        session_date = base_date + timedelta(days=i)
        session_data = {
            "session_id": f"session-{i}",
            "episode_url": "https://example.com/test",
            "status": "completed",
            "completed_at": session_date.isoformat() + "+00:00",
            "exchanges": [
                {
                    "question": {"text": f"Question {i}?", "question_number": 1},
                    "response": {"text": f"Response {i}.", "word_count": 2}
                }
            ]
        }
        with open(tmp_path / f"session-00{i}.json", "w") as f:
            json.dump(session_data, f)
        # Small delay to ensure different mtimes
        time.sleep(0.01)

    summaries = context_builder.load_previous_interviews(tmp_path, limit=2)

    # Should return most recent 2 (by modification time)
    assert len(summaries) == 2
    # Since files are created in order 1, 2, 3, the most recent by mtime are 2 and 3
    assert "Question 3?" in summaries[1]  # Most recent
    assert "Question 2?" in summaries[0]


# New _load_previous_interviews Tests (Episode-Specific)


def test_load_previous_interviews_no_sessions_dir(context_builder, sample_metadata):
    """Test loading previous interviews when .sessions directory doesn't exist."""
    output = EpisodeOutput(
        metadata=sample_metadata,
        output_dir=Path("/tmp/test-episode"),
    )

    summaries = context_builder._load_previous_interviews(output)
    assert summaries == []


def test_load_previous_interviews_empty_sessions_dir(context_builder, sample_metadata, tmp_path):
    """Test loading previous interviews from empty .sessions directory."""
    output_dir = tmp_path / "episode-output"
    output_dir.mkdir()
    sessions_dir = output_dir / ".sessions"
    sessions_dir.mkdir()

    output = EpisodeOutput(
        metadata=sample_metadata,
        output_dir=output_dir,
    )

    summaries = context_builder._load_previous_interviews(output)
    assert summaries == []


def test_load_previous_interviews_with_completed_session(
    context_builder, sample_metadata, tmp_path
):
    """Test loading completed interview sessions for an episode."""
    import json

    output_dir = tmp_path / "episode-output"
    output_dir.mkdir()
    sessions_dir = output_dir / ".sessions"
    sessions_dir.mkdir()

    # Create a completed session with exchanges
    session_data = {
        "session_id": "test-session-1",
        "episode_url": "https://example.com/ep123",
        "episode_title": "Building Better Software",
        "podcast_name": "The Changelog",
        "status": "completed",
        "completed_at": "2025-11-10T10:30:00+00:00",
        "exchanges": [
            {
                "question": {
                    "text": "What was the most surprising insight?",
                    "question_number": 1,
                },
                "response": {
                    "text": (
                        "The discussion about compound learning effects was "
                        "eye-opening and really changed my perspective on "
                        "how I approach daily work."
                    ),
                    "word_count": 20,
                },
            },
            {
                "question": {
                    "text": "How does this relate to your experience?",
                    "question_number": 2,
                },
                "response": {
                    "text": (
                        "I've noticed similar patterns in my own work with "
                        "distributed systems where small improvements "
                        "compound over time."
                    ),
                    "word_count": 18,
                },
            }
        ]
    }

    session_file = sessions_dir / "session-test-1.json"
    with open(session_file, "w") as f:
        json.dump(session_data, f)

    output = EpisodeOutput(
        metadata=sample_metadata,
        output_dir=output_dir,
    )

    summaries = context_builder._load_previous_interviews(output)

    assert len(summaries) == 1
    assert "Session on 2025-11-10:" in summaries[0]
    assert "What was the most surprising insight?" in summaries[0]
    assert "compound learning effects" in summaries[0]
    assert "How does this relate to your experience?" in summaries[0]


def test_load_previous_interviews_filters_by_episode_url(
    context_builder, sample_metadata, tmp_path
):
    """Test that only sessions matching episode URL are loaded."""
    import json

    output_dir = tmp_path / "episode-output"
    output_dir.mkdir()
    sessions_dir = output_dir / ".sessions"
    sessions_dir.mkdir()

    # Create session for different episode
    other_session_data = {
        "session_id": "other-session",
        "episode_url": "https://example.com/different-episode",
        "status": "completed",
        "completed_at": "2025-11-10T10:30:00+00:00",
        "exchanges": []
    }

    # Create session for this episode
    this_session_data = {
        "session_id": "this-session",
        "episode_url": "https://example.com/ep123",  # Matches sample_metadata
        "status": "completed",
        "completed_at": "2025-11-11T10:30:00+00:00",
        "exchanges": [
            {
                "question": {"text": "Test question?", "question_number": 1},
                "response": {"text": "Test response here.", "word_count": 3}
            }
        ]
    }

    with open(sessions_dir / "session-other.json", "w") as f:
        json.dump(other_session_data, f)

    with open(sessions_dir / "session-this.json", "w") as f:
        json.dump(this_session_data, f)

    output = EpisodeOutput(
        metadata=sample_metadata,
        output_dir=output_dir,
    )

    summaries = context_builder._load_previous_interviews(output)

    # Should only load the session matching this episode
    assert len(summaries) == 1
    assert "Session on 2025-11-11:" in summaries[0]
    assert "Test question?" in summaries[0]


def test_load_previous_interviews_filters_non_completed(context_builder, sample_metadata, tmp_path):
    """Test that only completed sessions are loaded."""
    import json

    output_dir = tmp_path / "episode-output"
    output_dir.mkdir()
    sessions_dir = output_dir / ".sessions"
    sessions_dir.mkdir()

    # Create active (non-completed) session
    active_session = {
        "session_id": "active-session",
        "episode_url": "https://example.com/ep123",
        "status": "active",
        "exchanges": []
    }

    # Create completed session
    completed_session = {
        "session_id": "completed-session",
        "episode_url": "https://example.com/ep123",
        "status": "completed",
        "completed_at": "2025-11-11T10:30:00+00:00",
        "exchanges": [
            {
                "question": {"text": "Completed question?", "question_number": 1},
                "response": {"text": "Completed response.", "word_count": 2}
            }
        ]
    }

    with open(sessions_dir / "session-active.json", "w") as f:
        json.dump(active_session, f)

    with open(sessions_dir / "session-completed.json", "w") as f:
        json.dump(completed_session, f)

    output = EpisodeOutput(
        metadata=sample_metadata,
        output_dir=output_dir,
    )

    summaries = context_builder._load_previous_interviews(output)

    # Should only load completed session
    assert len(summaries) == 1
    assert "Completed question?" in summaries[0]


def test_load_previous_interviews_limits_to_recent(context_builder, sample_metadata, tmp_path):
    """Test that only most recent N sessions are loaded."""
    import json
    from datetime import datetime, timedelta

    output_dir = tmp_path / "episode-output"
    output_dir.mkdir()
    sessions_dir = output_dir / ".sessions"
    sessions_dir.mkdir()

    # Create 5 completed sessions with different dates
    base_date = datetime(2025, 11, 1, 10, 0, 0)
    for i in range(5):
        session_date = base_date + timedelta(days=i)
        session_data = {
            "session_id": f"session-{i}",
            "episode_url": "https://example.com/ep123",
            "status": "completed",
            "completed_at": session_date.isoformat() + "+00:00",
            "exchanges": [
                {
                    "question": {"text": f"Question {i}?", "question_number": 1},
                    "response": {"text": f"Response {i}.", "word_count": 2}
                }
            ]
        }

        with open(sessions_dir / f"session-{i}.json", "w") as f:
            json.dump(session_data, f)

    output = EpisodeOutput(
        metadata=sample_metadata,
        output_dir=output_dir,
    )

    # Request limit of 3 sessions
    summaries = context_builder._load_previous_interviews(output, limit=3)

    # Should only get 3 most recent (sessions 2, 3, 4)
    assert len(summaries) == 3
    assert "Question 4?" in summaries[0]  # Newest first
    assert "Question 3?" in summaries[1]
    assert "Question 2?" in summaries[2]


def test_load_previous_interviews_truncates_long_responses(
    context_builder, sample_metadata, tmp_path
):
    """Test that long responses are truncated in summaries."""
    import json

    output_dir = tmp_path / "episode-output"
    output_dir.mkdir()
    sessions_dir = output_dir / ".sessions"
    sessions_dir.mkdir()

    long_response = "A" * 150  # 150 characters, should be truncated to 100

    session_data = {
        "session_id": "test-session",
        "episode_url": "https://example.com/ep123",
        "status": "completed",
        "completed_at": "2025-11-10T10:30:00+00:00",
        "exchanges": [
            {
                "question": {"text": "Test question?", "question_number": 1},
                "response": {"text": long_response, "word_count": 1}
            }
        ]
    }

    with open(sessions_dir / "session-test.json", "w") as f:
        json.dump(session_data, f)

    output = EpisodeOutput(
        metadata=sample_metadata,
        output_dir=output_dir,
    )

    summaries = context_builder._load_previous_interviews(output)

    assert len(summaries) == 1
    # Response should be truncated to 100 chars + "..."
    assert "A" * 100 + "..." in summaries[0]
    assert len("A" * 150) > 100  # Verify our test data is actually long


def test_load_previous_interviews_handles_invalid_json(context_builder, sample_metadata, tmp_path):
    """Test that invalid session files are skipped gracefully."""
    output_dir = tmp_path / "episode-output"
    output_dir.mkdir()
    sessions_dir = output_dir / ".sessions"
    sessions_dir.mkdir()

    # Create invalid JSON file
    invalid_file = sessions_dir / "session-invalid.json"
    with open(invalid_file, "w") as f:
        f.write("{ invalid json }")

    # Create valid session file
    valid_session = {
        "session_id": "valid-session",
        "episode_url": "https://example.com/ep123",
        "status": "completed",
        "completed_at": "2025-11-10T10:30:00+00:00",
        "exchanges": [
            {
                "question": {"text": "Valid question?", "question_number": 1},
                "response": {"text": "Valid response.", "word_count": 2}
            }
        ]
    }

    with open(sessions_dir / "session-valid.json", "w") as f:
        import json
        json.dump(valid_session, f)

    output = EpisodeOutput(
        metadata=sample_metadata,
        output_dir=output_dir,
    )

    summaries = context_builder._load_previous_interviews(output)

    # Should skip invalid file and load only valid one
    assert len(summaries) == 1
    assert "Valid question?" in summaries[0]


def test_build_context_includes_previous_interviews(context_builder, sample_metadata, tmp_path):
    """Test that build_context includes previous interview sessions."""
    import json

    output_dir = tmp_path / "episode-output"
    output_dir.mkdir()
    sessions_dir = output_dir / ".sessions"
    sessions_dir.mkdir()

    # Create a completed session
    session_data = {
        "session_id": "test-session",
        "episode_url": "https://example.com/ep123",
        "status": "completed",
        "completed_at": "2025-11-10T10:30:00+00:00",
        "exchanges": [
            {
                "question": {"text": "Previous question?", "question_number": 1},
                "response": {"text": "Previous response here.", "word_count": 3}
            }
        ]
    }

    with open(sessions_dir / "session-test.json", "w") as f:
        json.dump(session_data, f)

    output = EpisodeOutput(
        metadata=sample_metadata,
        output_dir=output_dir,
    )

    context = context_builder.build_context(output)

    # Should have previous interviews populated
    assert len(context.previous_interviews) == 1
    assert "Session on 2025-11-10:" in context.previous_interviews[0]
    assert "Previous question?" in context.previous_interviews[0]


def test_to_prompt_context_includes_previous_interviews():
    """Test that previous interviews appear in prompt context."""
    from inkwell.interview.models import InterviewContext

    context = InterviewContext(
        podcast_name="Test Podcast",
        episode_title="Test Episode",
        episode_url="https://example.com/test",
        duration_minutes=60.0,
        summary="Test summary",
        previous_interviews=[
            (
                "Session on 2025-11-10:\n  Q: What was surprising?\n  "
                "A: The insight about...\n  (2/2 substantive responses)"
            )
        ],
    )

    prompt_text = context.to_prompt_context()

    # Should include previous interviews section
    assert "## Previous Interview Sessions" in prompt_text
    assert "Session on 2025-11-10:" in prompt_text
    assert "What was surprising?" in prompt_text
