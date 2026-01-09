"""Unit tests for template selector."""

from unittest.mock import Mock

import pytest

from inkwell.extraction.models import ExtractionTemplate
from inkwell.extraction.template_selector import TemplateSelector
from inkwell.feeds.models import Episode


@pytest.fixture
def mock_loader() -> Mock:
    """Create mock template loader."""
    loader = Mock()
    loader.list_templates = Mock(return_value=[])
    loader.load_template = Mock()
    return loader


@pytest.fixture
def sample_episode() -> Episode:
    """Create sample episode."""
    from datetime import datetime

    return Episode(
        title="Test Episode",
        url="https://example.com/ep1",
        published=datetime(2024, 1, 1),
        description="Test description",
        podcast_name="Test Podcast",
    )


def create_template(
    name: str,
    priority: int = 0,
    category: str | None = None,
    applies_to: list[str] | None = None,
) -> ExtractionTemplate:
    """Helper to create test template."""
    return ExtractionTemplate(
        name=name,
        version="1.0",
        description=f"Test {name}",
        system_prompt="Test",
        user_prompt_template="Test",
        expected_format="json",
        priority=priority,
        category=category,
        applies_to=applies_to or ["all"],
    )


class TestTemplateSelector:
    """Tests for TemplateSelector class."""

    def test_create_selector(self, mock_loader: Mock) -> None:
        """Test creating template selector."""
        selector = TemplateSelector(template_loader=mock_loader)
        assert selector.loader == mock_loader

    def test_select_default_templates(self, mock_loader: Mock, sample_episode: Episode) -> None:
        """Test selecting default templates."""
        # Setup mock to return default templates
        summary = create_template("summary", priority=0)
        quotes = create_template("quotes", priority=5)
        concepts = create_template("key-concepts", priority=10)

        def mock_load(name: str) -> ExtractionTemplate:
            templates = {
                "summary": summary,
                "quotes": quotes,
                "key-concepts": concepts,
            }
            return templates[name]

        mock_loader.load_template = Mock(side_effect=mock_load)

        selector = TemplateSelector(template_loader=mock_loader)
        templates = selector.select_templates(
            episode=sample_episode,
            category=None,
            custom_templates=None,
            transcript="Test transcript",
        )

        # Should include 3 default templates
        assert len(templates) == 3
        template_names = [t.name for t in templates]
        assert "summary" in template_names
        assert "quotes" in template_names
        assert "key-concepts" in template_names

    def test_templates_sorted_by_priority(self, mock_loader: Mock, sample_episode: Episode) -> None:
        """Test that templates are sorted by priority."""
        summary = create_template("summary", priority=0)
        quotes = create_template("quotes", priority=10)
        concepts = create_template("key-concepts", priority=5)

        def mock_load(name: str) -> ExtractionTemplate:
            templates = {
                "summary": summary,
                "quotes": quotes,
                "key-concepts": concepts,
            }
            return templates[name]

        mock_loader.load_template = Mock(side_effect=mock_load)

        selector = TemplateSelector(template_loader=mock_loader)
        templates = selector.select_templates(
            episode=sample_episode,
            category=None,
            custom_templates=None,
            transcript="Test",
        )

        # Should be sorted: summary(0), key-concepts(5), quotes(10)
        assert templates[0].name == "summary"
        assert templates[1].name == "key-concepts"
        assert templates[2].name == "quotes"

    def test_select_with_explicit_category(
        self, mock_loader: Mock, sample_episode: Episode
    ) -> None:
        """Test selecting templates with explicit category."""
        summary = create_template("summary")
        quotes = create_template("quotes")
        concepts = create_template("key-concepts")
        tools = create_template("tools-mentioned", category="tech", applies_to=["tech"])

        def mock_load(name: str) -> ExtractionTemplate:
            templates = {
                "summary": summary,
                "quotes": quotes,
                "key-concepts": concepts,
                "tools-mentioned": tools,
            }
            return templates[name]

        mock_loader.load_template = Mock(side_effect=mock_load)
        mock_loader.list_templates = Mock(
            side_effect=lambda category=None: (["tools-mentioned"] if category == "tech" else [])
        )

        selector = TemplateSelector(template_loader=mock_loader)
        templates = selector.select_templates(
            episode=sample_episode,
            category="tech",
            custom_templates=None,
            transcript="Test",
        )

        # Should include default + tech category templates
        template_names = [t.name for t in templates]
        assert "summary" in template_names
        assert "quotes" in template_names
        assert "key-concepts" in template_names
        assert "tools-mentioned" in template_names

    def test_select_with_custom_templates(self, mock_loader: Mock, sample_episode: Episode) -> None:
        """Test selecting with custom template names."""
        summary = create_template("summary")
        custom = create_template("custom-analysis")

        def mock_load(name: str) -> ExtractionTemplate:
            templates = {
                "summary": summary,
                "quotes": create_template("quotes"),
                "key-concepts": create_template("key-concepts"),
                "custom-analysis": custom,
            }
            return templates[name]

        mock_loader.load_template = Mock(side_effect=mock_load)

        selector = TemplateSelector(template_loader=mock_loader)
        templates = selector.select_templates(
            episode=sample_episode,
            category=None,
            custom_templates=["custom-analysis"],
            transcript="Test",
        )

        template_names = [t.name for t in templates]
        assert "custom-analysis" in template_names

    def test_detect_category_tech(self, mock_loader: Mock) -> None:
        """Test detecting 'tech' category from transcript."""
        selector = TemplateSelector(template_loader=mock_loader)

        tech_transcript = """
        In this episode, we discuss Python programming and Django framework.
        We also cover React, TypeScript, and Docker containers.
        The API was built using FastAPI and PostgreSQL database.
        """

        category = selector.detect_category(tech_transcript)
        assert category == "tech"

    def test_detect_category_interview(self, mock_loader: Mock) -> None:
        """Test detecting 'interview' category from transcript."""
        selector = TemplateSelector(template_loader=mock_loader)

        interview_transcript = """
        Today on the show, we have an amazing guest joining us.
        Welcome to the podcast! Tell us about your background.
        In your book, you mention several key insights.
        Let's hear from our guest about their experience.
        """

        category = selector.detect_category(interview_transcript)
        assert category == "interview"

    def test_detect_category_none(self, mock_loader: Mock) -> None:
        """Test that unrecognized content returns None."""
        selector = TemplateSelector(template_loader=mock_loader)

        generic_transcript = """
        This is some generic content that doesn't match
        any particular category patterns. Just regular text
        about various topics without specific keywords.
        """

        category = selector.detect_category(generic_transcript)
        assert category is None

    def test_detect_category_tech_threshold(self, mock_loader: Mock) -> None:
        """Test tech detection requires minimum keyword density."""
        selector = TemplateSelector(template_loader=mock_loader)

        # Only 1 tech keyword in lots of text
        sparse_transcript = "We briefly mentioned Python. " + "Other stuff. " * 100

        category = selector.detect_category(sparse_transcript)
        # Should not detect as tech (below threshold)
        assert category != "tech" or category is None

    def test_auto_detect_category_when_not_specified(
        self, mock_loader: Mock, sample_episode: Episode
    ) -> None:
        """Test that category is auto-detected when not specified."""
        summary = create_template("summary")
        quotes = create_template("quotes")
        concepts = create_template("key-concepts")
        tools = create_template("tools-mentioned", category="tech")

        def mock_load(name: str) -> ExtractionTemplate:
            templates = {
                "summary": summary,
                "quotes": quotes,
                "key-concepts": concepts,
                "tools-mentioned": tools,
            }
            return templates[name]

        mock_loader.load_template = Mock(side_effect=mock_load)
        mock_loader.list_templates = Mock(
            side_effect=lambda category=None: (["tools-mentioned"] if category == "tech" else [])
        )

        selector = TemplateSelector(template_loader=mock_loader)

        tech_transcript = (
            "We discuss Python programming, API development, and software framework extensively."
        )

        templates = selector.select_templates(
            episode=sample_episode,
            category=None,  # Not specified
            custom_templates=None,
            transcript=tech_transcript,
        )

        template_names = [t.name for t in templates]
        # Should auto-detect tech and include tools-mentioned
        assert "tools-mentioned" in template_names

    def test_no_duplicate_templates(self, mock_loader: Mock, sample_episode: Episode) -> None:
        """Test that same template is not included twice."""
        summary = create_template("summary")

        def mock_load(name: str) -> ExtractionTemplate:
            if name == "summary":
                return summary
            return create_template(name)

        mock_loader.load_template = Mock(side_effect=mock_load)

        selector = TemplateSelector(template_loader=mock_loader)

        # Try to add summary as custom template (already in defaults)
        templates = selector.select_templates(
            episode=sample_episode,
            category=None,
            custom_templates=["summary"],
            transcript="Test",
        )

        template_names = [t.name for t in templates]
        # Should only appear once
        assert template_names.count("summary") == 1

    def test_custom_template_override_default(
        self, mock_loader: Mock, sample_episode: Episode
    ) -> None:
        """Test that explicitly adding a default template doesn't duplicate."""
        summary_v1 = create_template("summary", priority=0)
        summary_v2 = create_template("summary", priority=99)

        load_count = {"summary": 0}

        def mock_load(name: str) -> ExtractionTemplate:
            if name == "summary":
                load_count["summary"] += 1
                # Return different version on second load
                return summary_v1 if load_count["summary"] == 1 else summary_v2
            return create_template(name)

        mock_loader.load_template = Mock(side_effect=mock_load)

        selector = TemplateSelector(template_loader=mock_loader)

        templates = selector.select_templates(
            episode=sample_episode,
            category=None,
            custom_templates=["summary"],
            transcript="Test",
        )

        # Should only have one summary template
        summary_templates = [t for t in templates if t.name == "summary"]
        assert len(summary_templates) == 1

    def test_empty_transcript_no_category_detection(
        self, mock_loader: Mock, sample_episode: Episode
    ) -> None:
        """Test that empty transcript doesn't crash category detection."""

        def mock_load(name: str) -> ExtractionTemplate:
            return create_template(name)

        mock_loader.load_template = Mock(side_effect=mock_load)

        selector = TemplateSelector(template_loader=mock_loader)

        # Should not crash with empty transcript
        templates = selector.select_templates(
            episode=sample_episode,
            category=None,
            custom_templates=None,
            transcript="",
        )

        # Should still return default templates
        assert len(templates) >= 3

    def test_case_insensitive_category_detection(self, mock_loader: Mock) -> None:
        """Test that category detection is case-insensitive."""
        selector = TemplateSelector(template_loader=mock_loader)

        transcript = "We discuss PYTHON programming and SOFTWARE development with API framework."
        category = selector.detect_category(transcript)
        assert category == "tech"

    def test_applies_to_filtering(self, mock_loader: Mock, sample_episode: Episode) -> None:
        """Test that templates with applies_to are properly filtered."""
        summary = create_template("summary", applies_to=["all"])
        tools = create_template(
            "tools-mentioned",
            category="tech",
            applies_to=["tech", "programming"],
        )
        books = create_template("books-mentioned", category="interview", applies_to=["interview"])

        def mock_load(name: str) -> ExtractionTemplate:
            templates = {
                "summary": summary,
                "quotes": create_template("quotes"),
                "key-concepts": create_template("key-concepts"),
                "tools-mentioned": tools,
                "books-mentioned": books,
            }
            return templates[name]

        mock_loader.load_template = Mock(side_effect=mock_load)
        mock_loader.list_templates = Mock(
            side_effect=lambda category=None: {
                "tech": ["tools-mentioned"],
                "interview": ["books-mentioned"],
                None: [],
            }.get(category, [])
        )

        selector = TemplateSelector(template_loader=mock_loader)

        # Select with tech category
        templates = selector.select_templates(
            episode=sample_episode,
            category="tech",
            custom_templates=None,
            transcript="Test",
        )

        template_names = [t.name for t in templates]
        assert "tools-mentioned" in template_names
        assert "books-mentioned" not in template_names

    def test_default_templates_always_included(
        self, mock_loader: Mock, sample_episode: Episode
    ) -> None:
        """Test that default templates are always included."""
        summary = create_template("summary")
        quotes = create_template("quotes")
        concepts = create_template("key-concepts")

        def mock_load(name: str) -> ExtractionTemplate:
            templates = {
                "summary": summary,
                "quotes": quotes,
                "key-concepts": concepts,
            }
            return templates[name]

        mock_loader.load_template = Mock(side_effect=mock_load)
        selector = TemplateSelector(template_loader=mock_loader)

        templates = selector.select_templates(
            episode=sample_episode,
            category=None,
            custom_templates=None,
            transcript="",
        )

        template_names = [t.name for t in templates]
        assert "summary" in template_names
        assert "quotes" in template_names
        assert "key-concepts" in template_names

    def test_mixed_priority_sorting(self, mock_loader: Mock, sample_episode: Episode) -> None:
        """Test sorting with negative and positive priorities."""
        high = create_template("high-priority", priority=-10)
        normal = create_template("normal", priority=0)
        low = create_template("low-priority", priority=100)

        def mock_load(name: str) -> ExtractionTemplate:
            templates = {
                "summary": normal,
                "quotes": create_template("quotes", priority=5),
                "key-concepts": create_template("key-concepts", priority=10),
                "high-priority": high,
                "low-priority": low,
            }
            return templates[name]

        mock_loader.load_template = Mock(side_effect=mock_load)

        selector = TemplateSelector(template_loader=mock_loader)

        templates = selector.select_templates(
            episode=sample_episode,
            category=None,
            custom_templates=["high-priority", "low-priority"],
            transcript="Test",
        )

        # Should be sorted by priority (lowest first)
        assert templates[0].name == "high-priority"  # -10
        # ... others in between
        assert templates[-1].name == "low-priority"  # 100
