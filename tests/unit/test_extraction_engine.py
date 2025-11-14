"""Unit tests for extraction engine."""

from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from inkwell.extraction.cache import ExtractionCache
from inkwell.extraction.engine import ExtractionEngine
from inkwell.extraction.errors import ValidationError
from inkwell.extraction.models import ExtractionTemplate


@pytest.fixture
def mock_api_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set mock API keys."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-claude-key")
    monkeypatch.setenv("GOOGLE_API_KEY", "test-gemini-key")


@pytest.fixture
def temp_cache(tmp_path: Path) -> ExtractionCache:
    """Create temporary cache."""
    return ExtractionCache(cache_dir=tmp_path / "cache")


@pytest.fixture
def text_template() -> ExtractionTemplate:
    """Create text extraction template."""
    return ExtractionTemplate(
        name="summary",
        version="1.0",
        description="Test summary",
        system_prompt="Summarize",
        user_prompt_template="{{ transcript }}",
        expected_format="text",
        max_tokens=1000,
        temperature=0.3,
    )


@pytest.fixture
def json_template() -> ExtractionTemplate:
    """Create JSON extraction template."""
    return ExtractionTemplate(
        name="quotes",
        version="1.0",
        description="Extract quotes",
        system_prompt="Extract quotes",
        user_prompt_template="{{ transcript }}",
        expected_format="json",
        output_schema={
            "type": "object",
            "required": ["quotes"],
            "properties": {"quotes": {"type": "array"}},
        },
        max_tokens=1000,
        temperature=0.2,
    )


class TestExtractionEngineInit:
    """Tests for ExtractionEngine initialization."""

    def test_init_default(self, mock_api_keys: None) -> None:
        """Test initialization with default settings."""
        with patch("inkwell.extraction.engine.ClaudeExtractor"), patch(
            "inkwell.extraction.engine.GeminiExtractor"
        ):
            engine = ExtractionEngine()
            assert engine.default_provider == "gemini"
            assert engine.total_cost_usd == 0.0

    def test_init_custom_provider(self, mock_api_keys: None) -> None:
        """Test initialization with custom default provider."""
        with patch("inkwell.extraction.engine.ClaudeExtractor"), patch(
            "inkwell.extraction.engine.GeminiExtractor"
        ):
            engine = ExtractionEngine(default_provider="claude")
            assert engine.default_provider == "claude"

    def test_init_custom_cache(self, mock_api_keys: None, temp_cache: ExtractionCache) -> None:
        """Test initialization with custom cache."""
        with patch("inkwell.extraction.engine.ClaudeExtractor"), patch(
            "inkwell.extraction.engine.GeminiExtractor"
        ):
            engine = ExtractionEngine(cache=temp_cache)
            assert engine.cache == temp_cache


class TestExtractionEngineExtract:
    """Tests for single extraction."""

    @pytest.mark.asyncio
    async def test_extract_text_success(
        self, mock_api_keys: None, text_template: ExtractionTemplate, temp_cache: ExtractionCache
    ) -> None:
        """Test successful text extraction."""
        with patch("inkwell.extraction.engine.ClaudeExtractor"), patch(
            "inkwell.extraction.engine.GeminiExtractor"
        ):
            engine = ExtractionEngine(cache=temp_cache)

            # Mock extractor
            mock_extract = AsyncMock(return_value="Extracted summary")
            engine.gemini_extractor.extract = mock_extract
            engine.gemini_extractor.estimate_cost = Mock(return_value=0.01)

            result = await engine.extract(
                template=text_template,
                transcript="Test transcript",
                metadata={"podcast_name": "Test"},
            )

            assert result.template_name == "summary"
            assert result.extracted_content is not None
            assert result.extracted_content.content == "Extracted summary"
            assert result.provider == "gemini"
            assert result.cost_usd == 0.01

    @pytest.mark.asyncio
    async def test_extract_json_success(
        self, mock_api_keys: None, json_template: ExtractionTemplate, temp_cache: ExtractionCache
    ) -> None:
        """Test successful JSON extraction."""
        with patch("inkwell.extraction.engine.ClaudeExtractor"), patch(
            "inkwell.extraction.engine.GeminiExtractor"
        ):
            engine = ExtractionEngine(cache=temp_cache)

            # Mock both extractors (quotes template uses Claude by default)
            json_output = '{"quotes": ["one", "two"]}'
            engine.claude_extractor.extract = AsyncMock(return_value=json_output)
            engine.claude_extractor.estimate_cost = Mock(return_value=0.10)
            engine.gemini_extractor.extract = AsyncMock(return_value=json_output)
            engine.gemini_extractor.estimate_cost = Mock(return_value=0.01)

            # Fix class name for provider detection
            engine.claude_extractor.__class__.__name__ = "ClaudeExtractor"
            engine.gemini_extractor.__class__.__name__ = "GeminiExtractor"

            result = await engine.extract(
                template=json_template,
                transcript="Test transcript",
                metadata={},
            )

            assert result.extracted_content is not None
            assert result.extracted_content.content == {"quotes": ["one", "two"]}

    @pytest.mark.asyncio
    async def test_extract_uses_cache(
        self, mock_api_keys: None, text_template: ExtractionTemplate, temp_cache: ExtractionCache
    ) -> None:
        """Test that extraction uses cache for repeated requests."""
        with patch("inkwell.extraction.engine.ClaudeExtractor"), patch(
            "inkwell.extraction.engine.GeminiExtractor"
        ):
            engine = ExtractionEngine(cache=temp_cache)

            # Mock extractor
            mock_extract = AsyncMock(return_value="Extracted summary")
            engine.gemini_extractor.extract = mock_extract
            engine.gemini_extractor.estimate_cost = Mock(return_value=0.01)

            # First extraction
            result1 = await engine.extract(
                template=text_template,
                transcript="Test transcript",
                metadata={},
            )
            assert result1.provider == "gemini"
            assert result1.cost_usd == 0.01
            assert mock_extract.call_count == 1

            # Second extraction (should use cache)
            result2 = await engine.extract(
                template=text_template,
                transcript="Test transcript",
                metadata={},
            )
            assert result2.provider == "cache"
            assert result2.cost_usd == 0.0
            assert mock_extract.call_count == 1  # Not called again

    @pytest.mark.asyncio
    async def test_extract_bypass_cache(
        self, mock_api_keys: None, text_template: ExtractionTemplate, temp_cache: ExtractionCache
    ) -> None:
        """Test extraction with cache bypass."""
        with patch("inkwell.extraction.engine.ClaudeExtractor"), patch(
            "inkwell.extraction.engine.GeminiExtractor"
        ):
            engine = ExtractionEngine(cache=temp_cache)

            # Mock extractor
            mock_extract = AsyncMock(return_value="Extracted summary")
            engine.gemini_extractor.extract = mock_extract
            engine.gemini_extractor.estimate_cost = Mock(return_value=0.01)

            # First extraction
            await engine.extract(
                template=text_template,
                transcript="Test transcript",
                metadata={},
                use_cache=True,
            )

            # Second extraction with cache disabled
            await engine.extract(
                template=text_template,
                transcript="Test transcript",
                metadata={},
                use_cache=False,
            )

            # Should have been called twice
            assert mock_extract.call_count == 2

    @pytest.mark.asyncio
    async def test_extract_invalid_json(
        self, mock_api_keys: None, json_template: ExtractionTemplate, temp_cache: ExtractionCache
    ) -> None:
        """Test extraction with invalid JSON returns failed result."""
        with patch("inkwell.extraction.engine.ClaudeExtractor"), patch(
            "inkwell.extraction.engine.GeminiExtractor"
        ):
            engine = ExtractionEngine(cache=temp_cache)

            # Mock both extractors returning invalid JSON (quotes template uses Claude)
            engine.claude_extractor.extract = AsyncMock(return_value="not valid json")
            engine.claude_extractor.estimate_cost = Mock(return_value=0.10)
            engine.gemini_extractor.extract = AsyncMock(return_value="not valid json")
            engine.gemini_extractor.estimate_cost = Mock(return_value=0.01)

            # Fix class name for provider detection
            engine.claude_extractor.__class__.__name__ = "ClaudeExtractor"
            engine.gemini_extractor.__class__.__name__ = "GeminiExtractor"

            result = await engine.extract(
                template=json_template,
                transcript="Test transcript",
                metadata={},
            )

            # Should return failed result, not raise exception
            assert result.success is False
            assert result.extracted_content is None
            assert "invalid json" in result.error.lower()


class TestExtractionEngineProviderSelection:
    """Tests for provider selection logic."""

    @pytest.mark.asyncio
    async def test_explicit_claude_preference(
        self, mock_api_keys: None, text_template: ExtractionTemplate, temp_cache: ExtractionCache
    ) -> None:
        """Test explicit Claude preference in template."""
        with patch("inkwell.extraction.engine.ClaudeExtractor"), patch(
            "inkwell.extraction.engine.GeminiExtractor"
        ):
            engine = ExtractionEngine(cache=temp_cache, default_provider="gemini")

            # Set Claude preference
            text_template.model_preference = "claude"

            # Mock both extractors
            mock_claude = AsyncMock(return_value="Claude result")
            mock_gemini = AsyncMock(return_value="Gemini result")
            engine.claude_extractor.extract = mock_claude
            engine.gemini_extractor.extract = mock_gemini
            engine.claude_extractor.estimate_cost = Mock(return_value=0.10)
            engine.gemini_extractor.estimate_cost = Mock(return_value=0.01)

            # Fix class name for provider detection
            engine.claude_extractor.__class__.__name__ = "ClaudeExtractor"
            engine.gemini_extractor.__class__.__name__ = "GeminiExtractor"

            result = await engine.extract(
                template=text_template,
                transcript="Test",
                metadata={},
            )

            # Should use Claude
            assert result.provider == "claude"
            assert mock_claude.called
            assert not mock_gemini.called

    @pytest.mark.asyncio
    async def test_explicit_gemini_preference(
        self, mock_api_keys: None, text_template: ExtractionTemplate, temp_cache: ExtractionCache
    ) -> None:
        """Test explicit Gemini preference in template."""
        with patch("inkwell.extraction.engine.ClaudeExtractor"), patch(
            "inkwell.extraction.engine.GeminiExtractor"
        ):
            engine = ExtractionEngine(cache=temp_cache, default_provider="claude")

            # Set Gemini preference
            text_template.model_preference = "gemini"

            # Mock both extractors
            mock_claude = AsyncMock(return_value="Claude result")
            mock_gemini = AsyncMock(return_value="Gemini result")
            engine.claude_extractor.extract = mock_claude
            engine.gemini_extractor.extract = mock_gemini
            engine.claude_extractor.estimate_cost = Mock(return_value=0.10)
            engine.gemini_extractor.estimate_cost = Mock(return_value=0.01)

            result = await engine.extract(
                template=text_template,
                transcript="Test",
                metadata={},
            )

            # Should use Gemini
            assert result.provider == "gemini"
            assert mock_gemini.called
            assert not mock_claude.called

    @pytest.mark.asyncio
    async def test_quote_template_uses_claude(
        self, mock_api_keys: None, temp_cache: ExtractionCache
    ) -> None:
        """Test that quote templates automatically use Claude."""
        with patch("inkwell.extraction.engine.ClaudeExtractor"), patch(
            "inkwell.extraction.engine.GeminiExtractor"
        ):
            engine = ExtractionEngine(cache=temp_cache, default_provider="gemini")

            # Template with "quote" in name
            quote_template = ExtractionTemplate(
                name="quotes-extraction",
                version="1.0",
                description="Extract quotes",
                system_prompt="Extract",
                user_prompt_template="{{ transcript }}",
                expected_format="json",
            )

            # Mock both extractors
            mock_claude = AsyncMock(return_value='{"quotes": []}')
            mock_gemini = AsyncMock(return_value='{"quotes": []}')
            engine.claude_extractor.extract = mock_claude
            engine.gemini_extractor.extract = mock_gemini
            engine.claude_extractor.estimate_cost = Mock(return_value=0.10)
            engine.gemini_extractor.estimate_cost = Mock(return_value=0.01)

            # Fix class name for provider detection
            engine.claude_extractor.__class__.__name__ = "ClaudeExtractor"
            engine.gemini_extractor.__class__.__name__ = "GeminiExtractor"

            result = await engine.extract(
                template=quote_template,
                transcript="Test",
                metadata={},
            )

            # Should use Claude (precision critical)
            assert result.provider == "claude"
            assert mock_claude.called

    @pytest.mark.asyncio
    async def test_default_provider_used(
        self, mock_api_keys: None, text_template: ExtractionTemplate, temp_cache: ExtractionCache
    ) -> None:
        """Test that default provider is used when no preference specified."""
        with patch("inkwell.extraction.engine.ClaudeExtractor"), patch(
            "inkwell.extraction.engine.GeminiExtractor"
        ):
            # Default to Claude
            engine = ExtractionEngine(cache=temp_cache, default_provider="claude")

            mock_claude = AsyncMock(return_value="Result")
            engine.claude_extractor.extract = mock_claude
            engine.claude_extractor.estimate_cost = Mock(return_value=0.10)

            # Fix class name for provider detection
            engine.claude_extractor.__class__.__name__ = "ClaudeExtractor"
            engine.gemini_extractor.__class__.__name__ = "GeminiExtractor"

            result = await engine.extract(
                template=text_template,
                transcript="Test",
                metadata={},
            )

            assert result.provider == "claude"


class TestExtractionEngineMultipleExtractions:
    """Tests for extracting multiple templates."""

    @pytest.mark.asyncio
    async def test_extract_all_success(
        self,
        mock_api_keys: None,
        text_template: ExtractionTemplate,
        json_template: ExtractionTemplate,
        temp_cache: ExtractionCache,
    ) -> None:
        """Test extracting multiple templates."""
        with patch("inkwell.extraction.engine.ClaudeExtractor"), patch(
            "inkwell.extraction.engine.GeminiExtractor"
        ):
            engine = ExtractionEngine(cache=temp_cache)

            # Mock both extractors (summary uses Gemini, quotes uses Claude)
            engine.gemini_extractor.extract = AsyncMock(return_value="Summary text")
            engine.gemini_extractor.estimate_cost = Mock(return_value=0.01)
            engine.claude_extractor.extract = AsyncMock(return_value='{"quotes": []}')
            engine.claude_extractor.estimate_cost = Mock(return_value=0.10)

            # Fix class name for provider detection
            engine.claude_extractor.__class__.__name__ = "ClaudeExtractor"
            engine.gemini_extractor.__class__.__name__ = "GeminiExtractor"

            results, summary = await engine.extract_all(
                templates=[text_template, json_template],
                transcript="Test transcript",
                metadata={},
            )

            assert len(results) == 2
            assert results[0].template_name == "summary"
            assert results[1].template_name == "quotes"
            assert summary.total == 2
            assert summary.successful == 2

    @pytest.mark.asyncio
    async def test_extract_all_partial_failure(
        self,
        mock_api_keys: None,
        text_template: ExtractionTemplate,
        json_template: ExtractionTemplate,
        temp_cache: ExtractionCache,
    ) -> None:
        """Test that extract_all continues on partial failures."""
        with patch("inkwell.extraction.engine.ClaudeExtractor"), patch(
            "inkwell.extraction.engine.GeminiExtractor"
        ):
            engine = ExtractionEngine(cache=temp_cache)

            # Mock extractor - one succeeds, one fails
            call_count = {"count": 0}

            async def mock_extract_fn(template, transcript, metadata):
                call_count["count"] += 1
                if call_count["count"] == 1:
                    return "Summary text"
                else:
                    raise Exception("API error")

            engine.gemini_extractor.extract = mock_extract_fn
            engine.gemini_extractor.estimate_cost = Mock(return_value=0.01)

            results, summary = await engine.extract_all(
                templates=[text_template, json_template],
                transcript="Test transcript",
                metadata={},
            )

            # Only successful results returned
            assert len(results) == 1
            assert results[0].template_name == "summary"
            # But summary tracks both attempts
            assert summary.total == 2
            assert summary.successful == 1
            assert summary.failed == 1


class TestExtractionEngineCostTracking:
    """Tests for cost estimation and tracking."""

    @pytest.mark.asyncio
    async def test_cost_tracking(
        self, mock_api_keys: None, text_template: ExtractionTemplate, temp_cache: ExtractionCache
    ) -> None:
        """Test that costs are tracked."""
        with patch("inkwell.extraction.engine.ClaudeExtractor"), patch(
            "inkwell.extraction.engine.GeminiExtractor"
        ):
            engine = ExtractionEngine(cache=temp_cache)

            mock_extract = AsyncMock(return_value="Result")
            engine.gemini_extractor.extract = mock_extract
            engine.gemini_extractor.estimate_cost = Mock(return_value=0.05)

            # Initial cost
            assert engine.get_total_cost() == 0.0

            # After extraction
            await engine.extract(
                template=text_template,
                transcript="Test",
                metadata={},
            )

            assert engine.get_total_cost() == 0.05

            # After another extraction
            await engine.extract(
                template=text_template,
                transcript="Test 2",
                metadata={},
            )

            assert engine.get_total_cost() == 0.10

    @pytest.mark.asyncio
    async def test_reset_cost_tracking(
        self, mock_api_keys: None, text_template: ExtractionTemplate, temp_cache: ExtractionCache
    ) -> None:
        """Test resetting cost tracking."""
        with patch("inkwell.extraction.engine.ClaudeExtractor"), patch(
            "inkwell.extraction.engine.GeminiExtractor"
        ):
            engine = ExtractionEngine(cache=temp_cache)

            mock_extract = AsyncMock(return_value="Result")
            engine.gemini_extractor.extract = mock_extract
            engine.gemini_extractor.estimate_cost = Mock(return_value=0.05)

            await engine.extract(
                template=text_template,
                transcript="Test",
                metadata={},
            )

            assert engine.get_total_cost() == 0.05

            engine.reset_cost_tracking()
            assert engine.get_total_cost() == 0.0

    def test_estimate_total_cost(
        self,
        mock_api_keys: None,
        text_template: ExtractionTemplate,
        json_template: ExtractionTemplate,
    ) -> None:
        """Test estimating total cost for multiple templates."""
        with patch("inkwell.extraction.engine.ClaudeExtractor"), patch(
            "inkwell.extraction.engine.GeminiExtractor"
        ):
            engine = ExtractionEngine()

            engine.gemini_extractor.estimate_cost = Mock(return_value=0.01)
            engine.claude_extractor.estimate_cost = Mock(return_value=0.10)

            total = engine.estimate_total_cost(
                templates=[text_template, json_template],
                transcript="Test transcript",
            )

            # text_template uses Gemini (0.01), json_template ("quotes") uses Claude (0.10)
            assert total == 0.11


class TestExtractionEngineOutputParsing:
    """Tests for output parsing."""

    def test_parse_text_output(self, mock_api_keys: None, text_template: ExtractionTemplate) -> None:
        """Test parsing text output."""
        with patch("inkwell.extraction.engine.ClaudeExtractor"), patch(
            "inkwell.extraction.engine.GeminiExtractor"
        ):
            engine = ExtractionEngine()

            content = engine._parse_output("Plain text result", text_template)

            assert content.template_name == "summary"
            assert content.content == "Plain text result"

    def test_parse_json_output(self, mock_api_keys: None, json_template: ExtractionTemplate) -> None:
        """Test parsing JSON output."""
        with patch("inkwell.extraction.engine.ClaudeExtractor"), patch(
            "inkwell.extraction.engine.GeminiExtractor"
        ):
            engine = ExtractionEngine()

            json_str = '{"quotes": ["one", "two"]}'
            content = engine._parse_output(json_str, json_template)

            assert content.template_name == "quotes"
            assert content.content == {"quotes": ["one", "two"]}

    def test_parse_markdown_output(self, mock_api_keys: None) -> None:
        """Test parsing markdown output."""
        with patch("inkwell.extraction.engine.ClaudeExtractor"), patch(
            "inkwell.extraction.engine.GeminiExtractor"
        ):
            engine = ExtractionEngine()

            md_template = ExtractionTemplate(
                name="summary",
                version="1.0",
                description="Summary",
                system_prompt="Summarize",
                user_prompt_template="{{ transcript }}",
                expected_format="markdown",
            )

            content = engine._parse_output("# Summary\n\nContent here", md_template)

            assert content.template_name == "summary"
            assert content.content == "# Summary\n\nContent here"

    def test_parse_yaml_output(self, mock_api_keys: None) -> None:
        """Test parsing YAML output."""
        with patch("inkwell.extraction.engine.ClaudeExtractor"), patch(
            "inkwell.extraction.engine.GeminiExtractor"
        ):
            engine = ExtractionEngine()

            yaml_template = ExtractionTemplate(
                name="data",
                version="1.0",
                description="Data",
                system_prompt="Extract",
                user_prompt_template="{{ transcript }}",
                expected_format="yaml",
            )

            yaml_str = "quotes:\n  - one\n  - two"
            content = engine._parse_output(yaml_str, yaml_template)

            assert content.template_name == "data"
            assert content.content == {"quotes": ["one", "two"]}
