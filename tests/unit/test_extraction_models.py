"""Unit tests for extraction models."""

from datetime import datetime

import pytest
from pydantic import ValidationError

from inkwell.extraction.models import (
    ExtractedContent,
    ExtractionResult,
    ExtractionTemplate,
    TemplateVariable,
)
from inkwell.utils.datetime import now_utc


class TestTemplateVariable:
    """Tests for TemplateVariable model."""

    def test_create_variable(self) -> None:
        """Test creating a template variable."""
        var = TemplateVariable(
            name="podcast_name",
            description="Name of the podcast",
            required=True,
        )

        assert var.name == "podcast_name"
        assert var.description == "Name of the podcast"
        assert var.required is True
        assert var.default is None

    def test_variable_with_default(self) -> None:
        """Test variable with default value."""
        var = TemplateVariable(
            name="language",
            description="Podcast language",
            default="en",
            required=False,
        )

        assert var.default == "en"
        assert var.required is False

    def test_invalid_variable_name(self) -> None:
        """Test that invalid variable names are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            TemplateVariable(
                name="invalid-name",  # Hyphens not allowed in identifiers
                description="Test",
            )

        assert "must be valid identifier" in str(exc_info.value)

    def test_variable_name_with_spaces_fails(self) -> None:
        """Test that variable names with spaces fail."""
        with pytest.raises(ValidationError):
            TemplateVariable(
                name="podcast name",  # Spaces not allowed
                description="Test",
            )


class TestExtractionTemplate:
    """Tests for ExtractionTemplate model."""

    def test_create_minimal_template(self) -> None:
        """Test creating template with minimum required fields."""
        template = ExtractionTemplate(
            name="summary",
            version="1.0",
            description="Generate episode summary",
            system_prompt="You are an expert podcast analyst.",
            user_prompt_template="Summarize: {{ transcript }}",
            expected_format="markdown",
        )

        assert template.name == "summary"
        assert template.version == "1.0"
        assert template.expected_format == "markdown"
        assert template.max_tokens == 2000  # Default
        assert template.temperature == 0.3  # Default
        assert template.priority == 0  # Default

    def test_template_with_all_fields(self) -> None:
        """Test creating template with all optional fields."""
        template = ExtractionTemplate(
            name="quotes",
            version="2.1.0",
            description="Extract notable quotes",
            system_prompt="Extract quotes accurately.",
            user_prompt_template="Find quotes in: {{ transcript }}",
            expected_format="json",
            output_schema={"type": "object", "properties": {}},
            category="general",
            applies_to=["tech", "interview"],
            priority=5,
            model_preference="claude",
            max_tokens=3000,
            temperature=0.2,
            variables=[],
            few_shot_examples=[{"input": "test", "output": {"quotes": []}}],
        )

        assert template.category == "general"
        assert template.applies_to == ["tech", "interview"]
        assert template.priority == 5
        assert template.model_preference == "claude"
        assert template.max_tokens == 3000
        assert template.temperature == 0.2
        assert len(template.few_shot_examples) == 1

    def test_template_name_validation(self) -> None:
        """Test that template names are validated."""
        # Valid names
        ExtractionTemplate(
            name="summary",
            version="1.0",
            description="Test",
            system_prompt="Test",
            user_prompt_template="Test",
            expected_format="text",
        )

        ExtractionTemplate(
            name="tools-mentioned",
            version="1.0",
            description="Test",
            system_prompt="Test",
            user_prompt_template="Test",
            expected_format="text",
        )

        ExtractionTemplate(
            name="key_concepts",
            version="1.0",
            description="Test",
            system_prompt="Test",
            user_prompt_template="Test",
            expected_format="text",
        )

        # Invalid name (special characters)
        with pytest.raises(ValidationError) as exc_info:
            ExtractionTemplate(
                name="invalid@name",
                version="1.0",
                description="Test",
                system_prompt="Test",
                user_prompt_template="Test",
                expected_format="text",
            )

        assert "must be alphanumeric" in str(exc_info.value)

    def test_jinja_template_validation(self) -> None:
        """Test that Jinja2 templates are validated."""
        # Valid template
        ExtractionTemplate(
            name="test",
            version="1.0",
            description="Test",
            system_prompt="Test",
            user_prompt_template="Hello {{ transcript }}",
            expected_format="text",
        )

        # Invalid Jinja2 syntax
        with pytest.raises(ValidationError) as exc_info:
            ExtractionTemplate(
                name="test",
                version="1.0",
                description="Test",
                system_prompt="Test",
                user_prompt_template="Hello {{ transcript",  # Unclosed
                expected_format="text",
            )

        assert "Invalid Jinja2 template" in str(exc_info.value)

    def test_temperature_validation(self) -> None:
        """Test temperature must be between 0 and 1."""
        # Valid temperatures
        for temp in [0.0, 0.5, 1.0]:
            ExtractionTemplate(
                name="test",
                version="1.0",
                description="Test",
                system_prompt="Test",
                user_prompt_template="Test",
                expected_format="text",
                temperature=temp,
            )

        # Invalid temperature (too high)
        with pytest.raises(ValidationError):
            ExtractionTemplate(
                name="test",
                version="1.0",
                description="Test",
                system_prompt="Test",
                user_prompt_template="Test",
                expected_format="text",
                temperature=1.5,
            )

        # Invalid temperature (negative)
        with pytest.raises(ValidationError):
            ExtractionTemplate(
                name="test",
                version="1.0",
                description="Test",
                system_prompt="Test",
                user_prompt_template="Test",
                expected_format="text",
                temperature=-0.1,
            )

    def test_cache_key_base(self) -> None:
        """Test cache key generation."""
        template = ExtractionTemplate(
            name="summary",
            version="1.0",
            description="Test",
            system_prompt="Test",
            user_prompt_template="Test",
            expected_format="text",
        )

        assert template.cache_key_base == "summary:1.0"


class TestExtractedContent:
    """Tests for ExtractedContent model."""

    def test_create_content_with_dict(self) -> None:
        """Test creating extracted content with dict."""
        content = ExtractedContent(
            template_name="summary",
            content={"summary": "This is a summary", "takeaways": ["Point 1"]},
            confidence=0.95,
        )

        assert content.template_name == "summary"
        assert isinstance(content.content, dict)
        assert content.confidence == 0.95
        assert content.is_valid is True
        assert content.has_warnings is False

    def test_create_content_with_string(self) -> None:
        """Test creating extracted content with string."""
        content = ExtractedContent(
            template_name="summary",
            content="This is a markdown summary.",
        )

        assert isinstance(content.content, str)
        assert content.confidence is None
        assert content.is_valid is True  # No warnings, confidence None is OK

    def test_content_with_warnings(self) -> None:
        """Test content with validation warnings."""
        content = ExtractedContent(
            template_name="quotes",
            content={"quotes": []},
            warnings=["No quotes found", "Incomplete extraction"],
            confidence=0.4,
        )

        assert content.has_warnings is True
        assert len(content.warnings) == 2
        assert content.is_valid is False  # Has warnings

    def test_low_confidence_invalid(self) -> None:
        """Test that low confidence makes content invalid."""
        content = ExtractedContent(
            template_name="test",
            content="test",
            confidence=0.5,  # Below 0.7 threshold
        )

        assert content.is_valid is False

    def test_high_confidence_valid(self) -> None:
        """Test that high confidence makes content valid."""
        content = ExtractedContent(
            template_name="test",
            content="test",
            confidence=0.8,
        )

        assert content.is_valid is True

    def test_extracted_at_timestamp(self) -> None:
        """Test that extraction timestamp is set."""
        content = ExtractedContent(
            template_name="test",
            content="test",
        )

        assert isinstance(content.extracted_at, datetime)
        assert content.extracted_at <= now_utc()


class TestExtractionResult:
    """Tests for ExtractionResult model."""

    def test_successful_result(self) -> None:
        """Test creating successful extraction result."""
        content = ExtractedContent(
            template_name="summary",
            content="Test summary",
        )

        result = ExtractionResult(
            episode_url="https://example.com/ep123",
            template_name="summary",
            success=True,
            extracted_content=content,
            duration_seconds=4.2,
            tokens_used=1500,
            cost_usd=0.23,
            provider="claude",
        )

        assert result.is_successful is True
        assert result.is_cached is False
        assert result.provider == "claude"
        assert result.cost_usd == 0.23

    def test_failed_result(self) -> None:
        """Test creating failed extraction result."""
        result = ExtractionResult(
            episode_url="https://example.com/ep123",
            template_name="summary",
            success=False,
            error="API timeout",
        )

        assert result.is_successful is False
        assert result.extracted_content is None
        assert result.error == "API timeout"

    def test_cached_result(self) -> None:
        """Test cached result."""
        content = ExtractedContent(
            template_name="summary",
            content="Cached summary",
        )

        result = ExtractionResult(
            episode_url="https://example.com/ep123",
            template_name="summary",
            success=True,
            extracted_content=content,
            from_cache=True,
            cache_key="abc123",
        )

        assert result.is_cached is True
        assert result.cache_key == "abc123"
        assert result.cost_usd == 0.0  # Cached = no cost

    def test_get_summary_success(self) -> None:
        """Test summary string for successful result."""
        content = ExtractedContent(
            template_name="summary",
            content="Test",
        )

        result = ExtractionResult(
            episode_url="https://example.com/ep123",
            template_name="summary",
            success=True,
            extracted_content=content,
            duration_seconds=4.2,
            cost_usd=0.23,
        )

        summary = result.get_summary()
        assert "✓ summary" in summary
        assert "Success" in summary
        assert "4.2s" in summary
        assert "$0.230" in summary

    def test_get_summary_cached(self) -> None:
        """Test summary string for cached result."""
        content = ExtractedContent(
            template_name="summary",
            content="Test",
        )

        result = ExtractionResult(
            episode_url="https://example.com/ep123",
            template_name="summary",
            success=True,
            extracted_content=content,
            from_cache=True,
        )

        summary = result.get_summary()
        assert "(cached)" in summary

    def test_get_summary_failed(self) -> None:
        """Test summary string for failed result."""
        result = ExtractionResult(
            episode_url="https://example.com/ep123",
            template_name="summary",
            success=False,
            error="Network timeout",
        )

        summary = result.get_summary()
        assert "✗ summary" in summary
        assert "Failed" in summary
        assert "Network timeout" in summary

    def test_negative_values_rejected(self) -> None:
        """Test that negative values are rejected."""
        content = ExtractedContent(template_name="test", content="test")

        # Negative duration
        with pytest.raises(ValidationError):
            ExtractionResult(
                episode_url="test",
                template_name="test",
                success=True,
                extracted_content=content,
                duration_seconds=-1.0,
            )

        # Negative tokens
        with pytest.raises(ValidationError):
            ExtractionResult(
                episode_url="test",
                template_name="test",
                success=True,
                extracted_content=content,
                tokens_used=-100,
            )

        # Negative cost
        with pytest.raises(ValidationError):
            ExtractionResult(
                episode_url="test",
                template_name="test",
                success=True,
                extracted_content=content,
                cost_usd=-0.10,
            )
