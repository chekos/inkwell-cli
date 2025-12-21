"""Unit tests for markdown generator."""

import pytest

from inkwell.extraction.models import ExtractedContent, ExtractionResult
from inkwell.output.markdown import MarkdownGenerator


@pytest.fixture
def generator() -> MarkdownGenerator:
    """Create markdown generator."""
    return MarkdownGenerator()


@pytest.fixture
def episode_metadata() -> dict:
    """Create sample episode metadata."""
    return {
        "podcast_name": "Test Podcast",
        "episode_title": "Episode 1: Testing",
        "episode_url": "https://example.com/ep1",
    }


class TestMarkdownGeneratorFrontmatter:
    """Tests for frontmatter generation."""

    def test_generate_frontmatter_basic(
        self, generator: MarkdownGenerator, episode_metadata: dict
    ) -> None:
        """Test basic frontmatter generation."""
        result = ExtractionResult(
            episode_url="https://example.com/ep1",
            template_name="summary",
            success=True,
            extracted_content=ExtractedContent(template_name="summary", content="Test"),
            cost_usd=0.01,
            provider="gemini",
        )

        frontmatter = generator._generate_frontmatter(result, episode_metadata)

        assert frontmatter.startswith("---\n")
        assert frontmatter.endswith("---")
        assert "template: summary" in frontmatter
        assert "podcast: Test Podcast" in frontmatter
        assert "Episode 1: Testing" in frontmatter  # May be quoted in YAML
        assert "extracted_with: gemini" in frontmatter
        assert "cost_usd: 0.01" in frontmatter

    def test_frontmatter_includes_url(
        self, generator: MarkdownGenerator, episode_metadata: dict
    ) -> None:
        """Test that URL is included in frontmatter."""
        result = ExtractionResult(
            episode_url="https://example.com/ep1",
            template_name="summary",
            success=True,
            extracted_content=ExtractedContent(template_name="summary", content="Test"),
            cost_usd=0.0,
            provider="cache",
        )

        frontmatter = generator._generate_frontmatter(result, episode_metadata)

        assert "url: https://example.com/ep1" in frontmatter

    def test_frontmatter_includes_tags(
        self, generator: MarkdownGenerator, episode_metadata: dict
    ) -> None:
        """Test that appropriate tags are generated."""
        result = ExtractionResult(
            episode_url="https://example.com/ep1",
            template_name="quotes",
            success=True,
            extracted_content=ExtractedContent(template_name="quotes", content={"quotes": []}),
            cost_usd=0.0,
            provider="cache",
        )

        frontmatter = generator._generate_frontmatter(result, episode_metadata)

        assert "tags:" in frontmatter
        assert "- podcast" in frontmatter
        assert "- inkwell" in frontmatter
        assert "- quotes" in frontmatter

    def test_generate_tags_for_different_templates(self, generator: MarkdownGenerator) -> None:
        """Test tag generation for different template types."""
        # Quotes
        assert "quotes" in generator._generate_tags("quotes")
        assert "quotes" in generator._generate_tags("extract-quotes")

        # Summary
        assert "summary" in generator._generate_tags("summary")

        # Concepts
        assert "concepts" in generator._generate_tags("key-concepts")

        # Tools
        assert "tools" in generator._generate_tags("tools-mentioned")

        # Books
        assert "books" in generator._generate_tags("books-mentioned")

    def test_frontmatter_with_missing_metadata(self, generator: MarkdownGenerator) -> None:
        """Test frontmatter generation with missing metadata."""
        result = ExtractionResult(
            episode_url="https://example.com/ep1",
            template_name="summary",
            success=True,
            extracted_content=ExtractedContent(template_name="summary", content="Test"),
            cost_usd=0.0,
            provider="cache",
        )

        # Empty metadata
        frontmatter = generator._generate_frontmatter(result, {})

        assert "podcast: Unknown" in frontmatter
        assert "episode: Unknown" in frontmatter


class TestMarkdownGeneratorQuotes:
    """Tests for quote formatting."""

    def test_format_quotes_basic(self, generator: MarkdownGenerator) -> None:
        """Test basic quote formatting."""
        data = {
            "quotes": [
                {
                    "text": "This is a test quote",
                    "speaker": "John Doe",
                    "timestamp": "12:34",
                }
            ]
        }

        _content = ExtractedContent(template_name="quotes", content=data)
        markdown = generator._format_quotes(data)

        assert "# Quotes" in markdown
        assert "## Quote 1" in markdown
        assert "> This is a test quote" in markdown
        assert "**Speaker:** John Doe" in markdown
        assert "**Timestamp:** 12:34" in markdown

    def test_format_multiple_quotes(self, generator: MarkdownGenerator) -> None:
        """Test formatting multiple quotes."""
        data = {
            "quotes": [
                {"text": "First quote", "speaker": "Alice", "timestamp": "01:00"},
                {"text": "Second quote", "speaker": "Bob", "timestamp": "02:00"},
            ]
        }

        markdown = generator._format_quotes(data)

        assert "## Quote 1" in markdown
        assert "## Quote 2" in markdown
        assert "First quote" in markdown
        assert "Second quote" in markdown

    def test_format_quotes_without_timestamp(self, generator: MarkdownGenerator) -> None:
        """Test formatting quotes without timestamp."""
        data = {"quotes": [{"text": "Quote without timestamp", "speaker": "John"}]}

        markdown = generator._format_quotes(data)

        assert "Quote without timestamp" in markdown
        assert "**Speaker:** John" in markdown
        assert "Timestamp" not in markdown

    def test_format_quotes_empty(self, generator: MarkdownGenerator) -> None:
        """Test formatting with no quotes."""
        data = {"other": "data"}

        markdown = generator._format_quotes(data)

        assert "No quotes found" in markdown


class TestMarkdownGeneratorConcepts:
    """Tests for concept formatting."""

    def test_format_concepts_basic(self, generator: MarkdownGenerator) -> None:
        """Test basic concept formatting."""
        data = {
            "concepts": [
                {
                    "name": "Test Concept",
                    "explanation": "This is what it means",
                    "context": "Discussed in detail",
                }
            ]
        }

        markdown = generator._format_concepts(data)

        assert "# Key Concepts" in markdown
        assert "## Test Concept" in markdown
        assert "This is what it means" in markdown
        assert "**Context:** Discussed in detail" in markdown

    def test_format_concepts_minimal(self, generator: MarkdownGenerator) -> None:
        """Test concept formatting with minimal data."""
        data = {"concepts": [{"name": "Minimal Concept"}]}

        markdown = generator._format_concepts(data)

        assert "## Minimal Concept" in markdown

    def test_format_concepts_empty(self, generator: MarkdownGenerator) -> None:
        """Test formatting with no concepts."""
        data = {}

        markdown = generator._format_concepts(data)

        assert "No concepts found" in markdown


class TestMarkdownGeneratorTools:
    """Tests for tools formatting."""

    def test_format_tools_as_table(self, generator: MarkdownGenerator) -> None:
        """Test tools formatted as markdown table."""
        data = {
            "tools": [
                {"name": "Python", "category": "language", "context": "Used for backend"},
                {"name": "React", "category": "framework", "context": "Used for frontend"},
            ]
        }

        markdown = generator._format_tools(data)

        assert "# Tools & Technologies Mentioned" in markdown
        assert "| Tool | Category | Context |" in markdown
        assert "| Python | language |" in markdown
        assert "| React | framework |" in markdown

    def test_format_tools_truncates_long_context(self, generator: MarkdownGenerator) -> None:
        """Test that long context is truncated."""
        data = {
            "tools": [
                {
                    "name": "Tool",
                    "category": "type",
                    "context": "x" * 100,  # Very long context
                }
            ]
        }

        markdown = generator._format_tools(data)

        # Should be truncated to 50 chars
        assert "x" * 50 in markdown
        assert "x" * 51 not in markdown

    def test_format_tools_empty(self, generator: MarkdownGenerator) -> None:
        """Test formatting with no tools."""
        data = {}

        markdown = generator._format_tools(data)

        assert "No tools found" in markdown


class TestMarkdownGeneratorBooks:
    """Tests for books formatting."""

    def test_format_books_basic(self, generator: MarkdownGenerator) -> None:
        """Test basic book formatting."""
        data = {
            "books": [
                {
                    "title": "Test Book",
                    "author": "Jane Smith",
                    "context": "Recommended reading",
                }
            ]
        }

        markdown = generator._format_books(data)

        assert "# Books & Publications" in markdown
        assert "## Test Book" in markdown
        assert "**Author:** Jane Smith" in markdown
        assert "**Mentioned:** Recommended reading" in markdown

    def test_format_books_without_context(self, generator: MarkdownGenerator) -> None:
        """Test book formatting without context."""
        data = {"books": [{"title": "Book Title", "author": "Author Name"}]}

        markdown = generator._format_books(data)

        assert "## Book Title" in markdown
        assert "**Author:** Author Name" in markdown
        assert "Mentioned" not in markdown

    def test_format_books_empty(self, generator: MarkdownGenerator) -> None:
        """Test formatting with no books."""
        data = {}

        markdown = generator._format_books(data)

        assert "No books found" in markdown


class TestMarkdownGeneratorGeneric:
    """Tests for generic formatting."""

    def test_format_generic_json(self, generator: MarkdownGenerator) -> None:
        """Test generic JSON formatting."""
        data = {"key1": "value1", "key2": [1, 2, 3], "key3": {"nested": "data"}}

        markdown = generator._format_generic_json(data)

        assert "# Extracted Data" in markdown
        assert "```json" in markdown
        assert "```" in markdown
        assert "key1" in markdown
        assert "value1" in markdown

    def test_format_markdown_content(self, generator: MarkdownGenerator) -> None:
        """Test markdown content (pass-through)."""
        content = ExtractedContent(
            template_name="summary",
            content="# Heading\n\nParagraph text",
        )

        markdown = generator._format_markdown_content(content)

        assert markdown == "# Heading\n\nParagraph text"

    def test_format_yaml_content(self, generator: MarkdownGenerator) -> None:
        """Test YAML content formatting."""
        content = ExtractedContent(template_name="test", content={"key": "value"})

        markdown = generator._format_yaml_content(content)

        assert "# Extracted Data" in markdown
        assert "```yaml" in markdown
        assert "key: value" in markdown

    def test_format_text_content(self, generator: MarkdownGenerator) -> None:
        """Test text content formatting."""
        content = ExtractedContent(template_name="summary", content="Plain text content")

        markdown = generator._format_text_content(content)

        assert markdown == "Plain text content"


class TestMarkdownGeneratorFullGeneration:
    """Tests for complete markdown generation."""

    def test_generate_with_frontmatter(
        self, generator: MarkdownGenerator, episode_metadata: dict
    ) -> None:
        """Test full markdown generation with frontmatter."""
        result = ExtractionResult(
            episode_url="https://example.com/ep1",
            template_name="summary",
            success=True,
            extracted_content=ExtractedContent(template_name="summary", content="Episode summary"),
            cost_usd=0.01,
            provider="gemini",
        )

        markdown = generator.generate(result, episode_metadata, include_frontmatter=True)

        # Should have frontmatter
        assert markdown.startswith("---\n")
        assert "podcast: Test Podcast" in markdown

        # Should have content
        assert "Episode summary" in markdown

        # Should be separated properly
        parts = markdown.split("---")
        assert len(parts) >= 3  # Opening, frontmatter, closing, content

    def test_generate_without_frontmatter(
        self, generator: MarkdownGenerator, episode_metadata: dict
    ) -> None:
        """Test markdown generation without frontmatter."""
        result = ExtractionResult(
            episode_url="https://example.com/ep1",
            template_name="summary",
            success=True,
            extracted_content=ExtractedContent(template_name="summary", content="Episode summary"),
            cost_usd=0.0,
            provider="cache",
        )

        markdown = generator.generate(result, episode_metadata, include_frontmatter=False)

        # Should not have frontmatter
        assert not markdown.startswith("---")
        assert "podcast:" not in markdown

        # Should have content
        assert "Episode summary" in markdown

    def test_generate_with_json_quotes(
        self, generator: MarkdownGenerator, episode_metadata: dict
    ) -> None:
        """Test generation with JSON quotes."""
        result = ExtractionResult(
            episode_url="https://example.com/ep1",
            template_name="quotes",
            success=True,
            extracted_content=ExtractedContent(
                template_name="quotes",
                content={
                    "quotes": [{"text": "Test quote", "speaker": "Speaker", "timestamp": "10:00"}]
                },
            ),
            cost_usd=0.01,
            provider="claude",
        )

        markdown = generator.generate(result, episode_metadata)

        assert "---" in markdown  # Has frontmatter
        assert "# Quotes" in markdown
        assert "> Test quote" in markdown
        assert "**Speaker:** Speaker" in markdown

    def test_generate_with_markdown_summary(
        self, generator: MarkdownGenerator, episode_metadata: dict
    ) -> None:
        """Test generation with markdown summary."""
        summary_text = (
            "# Summary\n\nThis episode discusses testing.\n\n## Key Points\n\n- Point 1\n- Point 2"
        )

        result = ExtractionResult(
            episode_url="https://example.com/ep1",
            template_name="summary",
            success=True,
            extracted_content=ExtractedContent(template_name="summary", content=summary_text),
            cost_usd=0.005,
            provider="gemini",
        )

        markdown = generator.generate(result, episode_metadata)

        assert "# Summary" in markdown
        assert "## Key Points" in markdown
        assert "- Point 1" in markdown

    def test_generate_handles_cache_provider(
        self, generator: MarkdownGenerator, episode_metadata: dict
    ) -> None:
        """Test that cached results are properly marked."""
        result = ExtractionResult(
            episode_url="https://example.com/ep1",
            template_name="summary",
            success=True,
            extracted_content=ExtractedContent(template_name="summary", content="Summary"),
            cost_usd=0.0,
            provider="cache",
        )

        markdown = generator.generate(result, episode_metadata)

        assert "extracted_with: cache" in markdown
        assert "cost_usd: 0.0" in markdown


class TestMarkdownGeneratorEdgeCases:
    """Tests for edge cases and error handling."""

    def test_handle_empty_data(self, generator: MarkdownGenerator) -> None:
        """Test handling of empty data structures."""
        data = {}

        # Should handle gracefully
        markdown = generator._format_quotes(data)
        assert "No quotes found" in markdown

    def test_handle_missing_fields(self, generator: MarkdownGenerator) -> None:
        """Test handling of missing fields in data."""
        data = {"quotes": [{"text": "Quote without speaker"}]}

        markdown = generator._format_quotes(data)

        assert "Quote without speaker" in markdown
        assert "**Speaker:** Unknown" in markdown

    def test_handle_special_characters_in_content(self, generator: MarkdownGenerator) -> None:
        """Test handling of special characters."""
        data = {
            "quotes": [
                {
                    "text": "Quote with \"quotes\" and 'apostrophes'",
                    "speaker": "Test",
                }
            ]
        }

        markdown = generator._format_quotes(data)

        assert "Quote with \"quotes\" and 'apostrophes'" in markdown

    def test_handle_unicode_content(self, generator: MarkdownGenerator) -> None:
        """Test handling of unicode characters."""
        data = {"quotes": [{"text": "Quote with émojis 🎉 and symbols ™", "speaker": "Test"}]}

        markdown = generator._format_quotes(data)

        assert "émojis 🎉" in markdown

    def test_handle_very_long_content(self, generator: MarkdownGenerator) -> None:
        """Test handling of very long content."""
        long_text = "x" * 10000

        content = ExtractedContent(template_name="summary", content=long_text)

        markdown = generator._format_text_content(content)

        assert len(markdown) == 10000
        assert markdown == long_text
