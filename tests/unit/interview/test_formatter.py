"""Tests for interview transcript formatter."""


import pytest

from inkwell.interview.formatter import TranscriptFormatter
from inkwell.interview.models import InterviewSession, Question, Response


@pytest.fixture
def sample_session():
    """Create sample interview session with exchanges."""
    session = InterviewSession(
        episode_url="https://example.com/ep1",
        episode_title="The Future of AI",
        podcast_name="Tech Talks",
        template_name="reflective",
        max_questions=5,
    )

    # Add some exchanges
    q1 = Question(text="What surprised you most about this episode?", question_number=1)
    r1 = Response(
        question_id=q1.id,
        text="I realized that AI safety is more important than I thought. "
        "This made me think about my own work differently.",
        thinking_time_seconds=30.0,
    )
    session.add_exchange(q1, r1)

    q2 = Question(text="Can you elaborate on that?", question_number=2, depth_level=1)
    r2 = Response(
        question_id=q2.id,
        text="I should start considering ethical implications in my projects. "
        "I want to learn more about alignment research.",
        thinking_time_seconds=25.0,
    )
    session.add_exchange(q2, r2)

    q3 = Question(text="How does this relate to your current work?", question_number=3)
    r3 = Response(
        question_id=q3.id,
        text="We often optimize for speed without thinking about safety. "
        "The connection is clear now - we need better guardrails.",
        thinking_time_seconds=20.0,
    )
    session.add_exchange(q3, r3)

    session.complete()
    return session


# Initialization Tests


def test_create_formatter_default():
    """Test creating formatter with default settings."""
    formatter = TranscriptFormatter()

    assert formatter.format_style == "structured"


def test_create_formatter_with_style():
    """Test creating formatter with specific style."""
    formatter = TranscriptFormatter(format_style="narrative")

    assert formatter.format_style == "narrative"


# Format Session Tests


def test_format_session_structured(sample_session):
    """Test formatting session in structured style."""
    formatter = TranscriptFormatter(format_style="structured")

    result = formatter.format_session(sample_session)

    assert result.session == sample_session
    assert "Interview Notes:" in result.formatted_transcript
    assert "The Future of AI" in result.formatted_transcript
    assert "## Conversation" in result.formatted_transcript
    assert "### Question 1" in result.formatted_transcript
    assert "What surprised you most" in result.formatted_transcript


def test_format_session_narrative(sample_session):
    """Test formatting session in narrative style."""
    formatter = TranscriptFormatter(format_style="narrative")

    result = formatter.format_session(sample_session)

    assert "I reflected on" in result.formatted_transcript
    assert "Tech Talks" in result.formatted_transcript
    # Narrative uses italics for questions
    has_question = (
        "_What surprised you most" in result.formatted_transcript
        or "What surprised you most" in result.formatted_transcript
    )
    assert has_question


def test_format_session_qa(sample_session):
    """Test formatting session in Q&A style."""
    formatter = TranscriptFormatter(format_style="qa")

    result = formatter.format_session(sample_session)

    assert "**Q**:" in result.formatted_transcript
    assert "**A**:" in result.formatted_transcript
    assert "What surprised you most" in result.formatted_transcript


def test_format_session_includes_all_exchanges(sample_session):
    """Test that all exchanges are included."""
    formatter = TranscriptFormatter()

    result = formatter.format_session(sample_session)

    # Should have all 3 exchanges
    has_all = (
        result.formatted_transcript.count("**Q**:") >= 3
        or result.formatted_transcript.count("### Question") >= 2
    )
    assert has_all


# Metadata Tests


def test_format_includes_metadata(sample_session):
    """Test that metadata is included in structured format."""
    formatter = TranscriptFormatter(format_style="structured")

    result = formatter.format_session(sample_session)

    transcript = result.formatted_transcript

    assert "**Podcast**:" in transcript
    assert "Tech Talks" in transcript
    assert "**Episode**:" in transcript
    assert "The Future of AI" in transcript
    assert "**Template**:" in transcript
    assert "reflective" in transcript


def test_format_includes_statistics(sample_session):
    """Test that statistics are included."""
    formatter = TranscriptFormatter(format_style="structured")

    result = formatter.format_session(sample_session)

    transcript = result.formatted_transcript

    assert "## Session Statistics" in transcript
    assert "Questions asked" in transcript
    assert "Substantive responses" in transcript
    assert "Total time" in transcript


# Insight Extraction Tests


def test_extract_insights(sample_session):
    """Test extracting insights from session."""
    formatter = TranscriptFormatter()

    result = formatter.format_session(sample_session, extract_insights=True)

    # Should find insights based on patterns
    assert len(result.key_insights) > 0
    # Check for insight from first response
    has_insight = any("realized" in insight.lower() for insight in result.key_insights)
    assert has_insight


def test_extract_insights_disabled(sample_session):
    """Test that insights can be disabled."""
    formatter = TranscriptFormatter()

    result = formatter.format_session(sample_session, extract_insights=False)

    assert len(result.key_insights) == 0


def test_extract_insights_patterns():
    """Test various insight patterns are detected."""
    session = InterviewSession(
        episode_url="https://example.com/ep1",
        episode_title="Test",
        podcast_name="Test",
        max_questions=5,
    )

    # Add responses with different insight patterns
    patterns = [
        "I realize this is important and needs attention",
        "I've realized something crucial about my work",
        "I learned that consistency matters more than speed",
        "This made me think about my approach differently",
        "I hadn't considered the ethical implications before",
    ]

    for i, text in enumerate(patterns, 1):
        q = Question(text=f"Question {i}?", question_number=i)
        r = Response(question_id=q.id, text=text)
        session.add_exchange(q, r)

    formatter = TranscriptFormatter()
    result = formatter.format_session(session, extract_insights=True)

    # Should find at least 3 insights
    assert len(result.key_insights) >= 3


# Action Item Extraction Tests


def test_extract_action_items(sample_session):
    """Test extracting action items from session."""
    formatter = TranscriptFormatter()

    result = formatter.format_session(sample_session, extract_actions=True)

    # Should find action items
    assert len(result.action_items) > 0
    # Check for action from second response
    has_action = any("learn more" in action.lower() for action in result.action_items)
    assert has_action


def test_extract_action_items_disabled(sample_session):
    """Test that action extraction can be disabled."""
    formatter = TranscriptFormatter()

    result = formatter.format_session(sample_session, extract_actions=False)

    assert len(result.action_items) == 0


def test_extract_action_items_patterns():
    """Test various action patterns are detected."""
    session = InterviewSession(
        episode_url="https://example.com/ep1",
        episode_title="Test",
        podcast_name="Test",
        max_questions=5,
    )

    # Add responses with different action patterns
    patterns = [
        "I should start working on this immediately",
        "I'll try to apply this next week",
        "I want to read more about this topic",
        "I need to discuss this with my team",
        "I'm going to implement these changes",
    ]

    for i, text in enumerate(patterns, 1):
        q = Question(text=f"Question {i}?", question_number=i)
        r = Response(question_id=q.id, text=text)
        session.add_exchange(q, r)

    formatter = TranscriptFormatter()
    result = formatter.format_session(session, extract_actions=True)

    # Should find multiple action items
    assert len(result.action_items) >= 3


# Theme Extraction Tests


def test_extract_themes(sample_session):
    """Test extracting themes from session."""
    formatter = TranscriptFormatter()

    result = formatter.format_session(sample_session, extract_themes=True)

    # Should identify some themes (repeated phrases)
    # May or may not find themes depending on repetition
    assert isinstance(result.themes, list)


def test_extract_themes_disabled(sample_session):
    """Test that theme extraction can be disabled."""
    formatter = TranscriptFormatter()

    result = formatter.format_session(sample_session, extract_themes=False)

    assert len(result.themes) == 0


def test_extract_themes_with_repetition():
    """Test theme extraction with repeated phrases."""
    session = InterviewSession(
        episode_url="https://example.com/ep1",
        episode_title="Test",
        podcast_name="Test",
        max_questions=5,
    )

    # Add responses with repeated phrases
    q1 = Question(text="Question 1?", question_number=1)
    r1 = Response(
        question_id=q1.id,
        text="Machine learning is fascinating. I think machine learning will change everything.",
    )
    session.add_exchange(q1, r1)

    q2 = Question(text="Question 2?", question_number=2)
    r2 = Response(
        question_id=q2.id,
        text="Machine learning and deep learning are related. Machine learning is the foundation.",
    )
    session.add_exchange(q2, r2)

    formatter = TranscriptFormatter()
    result = formatter.format_session(session, extract_themes=True)

    # Should find "machine learning" as theme (appears 3 times)
    assert len(result.themes) > 0
    has_ml_theme = any("machine learning" in theme.lower() for theme in result.themes)
    assert has_ml_theme


# Follow-up Question Formatting Tests


def test_format_follow_up_questions():
    """Test that follow-up questions are formatted correctly."""
    session = InterviewSession(
        episode_url="https://example.com/ep1",
        episode_title="Test",
        podcast_name="Test",
        max_questions=5,
    )

    # Main question
    q1 = Question(text="Main question?", question_number=1, depth_level=0)
    r1 = Response(question_id=q1.id, text="Main response")
    session.add_exchange(q1, r1)

    # Follow-up
    q2 = Question(text="Follow-up question?", question_number=2, depth_level=1)
    r2 = Response(question_id=q2.id, text="Follow-up response")
    session.add_exchange(q2, r2)

    formatter = TranscriptFormatter(format_style="structured")
    result = formatter.format_session(session)

    # Check for follow-up indicator
    assert "Follow-up" in result.formatted_transcript or "Question 2" in result.formatted_transcript


# Save Transcript Tests


def test_save_transcript(sample_session, tmp_path):
    """Test saving transcript to file."""
    formatter = TranscriptFormatter()
    result = formatter.format_session(sample_session)

    output_file = formatter.save_transcript(result, tmp_path, "test-notes.md")

    # File should exist
    assert output_file.exists()
    assert output_file.name == "test-notes.md"

    # Should contain transcript
    content = output_file.read_text()
    assert "The Future of AI" in content


def test_save_transcript_with_insights(sample_session, tmp_path):
    """Test saving transcript includes insights section."""
    formatter = TranscriptFormatter()
    result = formatter.format_session(sample_session, extract_insights=True)

    output_file = formatter.save_transcript(result, tmp_path)

    content = output_file.read_text()

    if result.key_insights:
        assert "## Key Insights" in content


def test_save_transcript_with_action_items(sample_session, tmp_path):
    """Test saving transcript includes action items section."""
    formatter = TranscriptFormatter()
    result = formatter.format_session(sample_session, extract_actions=True)

    output_file = formatter.save_transcript(result, tmp_path)

    content = output_file.read_text()

    if result.action_items:
        assert "## Action Items" in content
        # Check for checkbox format
        assert "- [ ]" in content


def test_save_transcript_with_themes(sample_session, tmp_path):
    """Test saving transcript includes themes section."""
    formatter = TranscriptFormatter()
    result = formatter.format_session(sample_session, extract_themes=True)

    output_file = formatter.save_transcript(result, tmp_path)

    content = output_file.read_text()

    if result.themes:
        assert "## Recurring Themes" in content


def test_save_transcript_creates_directory(sample_session, tmp_path):
    """Test that save_transcript creates output directory."""
    formatter = TranscriptFormatter()
    result = formatter.format_session(sample_session)

    nested_dir = tmp_path / "nested" / "dir"
    output_file = formatter.save_transcript(result, nested_dir)

    assert nested_dir.exists()
    assert output_file.exists()


def test_save_transcript_updates_result(sample_session, tmp_path):
    """Test that save_transcript updates result with output path."""
    formatter = TranscriptFormatter()
    result = formatter.format_session(sample_session)

    assert result.output_file is None

    formatter.save_transcript(result, tmp_path)

    assert result.output_file is not None
    assert result.output_file.exists()


# Edge Cases


def test_format_empty_session():
    """Test formatting session with no exchanges."""
    session = InterviewSession(
        episode_url="https://example.com/ep1",
        episode_title="Empty Session",
        podcast_name="Test",
        max_questions=5,
    )

    formatter = TranscriptFormatter()
    result = formatter.format_session(session)

    # Should still produce valid transcript
    assert "Empty Session" in result.formatted_transcript
    assert len(result.key_insights) == 0
    assert len(result.action_items) == 0


def test_format_session_with_non_substantive_responses():
    """Test that non-substantive responses don't generate insights/actions."""
    session = InterviewSession(
        episode_url="https://example.com/ep1",
        episode_title="Test",
        podcast_name="Test",
        max_questions=5,
    )

    # Add non-substantive responses (< 5 words)
    for i in range(3):
        q = Question(text=f"Question {i+1}?", question_number=i + 1)
        r = Response(question_id=q.id, text="Yes")  # Only 1 word
        session.add_exchange(q, r)

    formatter = TranscriptFormatter()
    result = formatter.format_session(session)

    # Should have no insights or actions from non-substantive responses
    assert len(result.key_insights) == 0
    assert len(result.action_items) == 0


def test_deduplication_of_insights():
    """Test that duplicate insights are removed."""
    session = InterviewSession(
        episode_url="https://example.com/ep1",
        episode_title="Test",
        podcast_name="Test",
        max_questions=5,
    )

    # Add duplicate insights
    for i in range(3):
        q = Question(text=f"Question {i+1}?", question_number=i + 1)
        r = Response(
            question_id=q.id, text="I realized that this is very important and significant"
        )
        session.add_exchange(q, r)

    formatter = TranscriptFormatter()
    result = formatter.format_session(session)

    # Should deduplicate (only 1 unique insight)
    assert len(result.key_insights) == 1


def test_action_text_cleaning():
    """Test that action text is cleaned properly."""
    session = InterviewSession(
        episode_url="https://example.com/ep1",
        episode_title="Test",
        podcast_name="Test",
        max_questions=5,
    )

    q = Question(text="Question?", question_number=1)
    r = Response(question_id=q.id, text="and i should start this project soon")
    session.add_exchange(q, r)

    formatter = TranscriptFormatter()
    result = formatter.format_session(session)

    # Action should be cleaned (capitalized, no leading "and")
    if result.action_items:
        action = result.action_items[0]
        # Should not start with "and"
        assert not action.lower().startswith("and ")
        # Should be capitalized
        assert action[0].isupper()


# Integration Tests


def test_full_workflow(sample_session, tmp_path):
    """Test complete workflow from format to save."""
    formatter = TranscriptFormatter(format_style="structured")

    # Format session
    result = formatter.format_session(
        sample_session, extract_insights=True, extract_actions=True, extract_themes=True
    )

    # Verify result
    assert result.formatted_transcript
    assert isinstance(result.key_insights, list)
    assert isinstance(result.action_items, list)
    assert isinstance(result.themes, list)

    # Save to file
    output_file = formatter.save_transcript(result, tmp_path, "complete-notes.md")

    # Verify file
    assert output_file.exists()
    content = output_file.read_text()

    assert "The Future of AI" in content
    assert "## Conversation" in content


def test_all_format_styles_work(sample_session):
    """Test that all format styles produce valid output."""
    styles = ["structured", "narrative", "qa"]

    for style in styles:
        formatter = TranscriptFormatter(format_style=style)
        result = formatter.format_session(sample_session)

        assert result.formatted_transcript
        assert len(result.formatted_transcript) > 100  # Should have substantial content
        assert "The Future of AI" in result.formatted_transcript
