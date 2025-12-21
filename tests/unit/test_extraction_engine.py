"""Unit tests for extraction engine."""

import warnings
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from inkwell.config.schema import ExtractionConfig
from inkwell.extraction.cache import ExtractionCache
from inkwell.extraction.engine import ExtractionEngine
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
        with (
            patch("inkwell.extraction.engine.ClaudeExtractor"),
            patch("inkwell.extraction.engine.GeminiExtractor"),
        ):
            engine = ExtractionEngine(
                gemini_api_key="AIzaSyD" + "X" * 32,
                claude_api_key="sk-ant-api03-" + "X" * 32,
            )
            assert engine.default_provider == "gemini"
            assert engine.cost_tracker is None  # No cost tracker by default

    def test_init_custom_provider(self, mock_api_keys: None) -> None:
        """Test initialization with custom default provider."""
        with (
            patch("inkwell.extraction.engine.ClaudeExtractor"),
            patch("inkwell.extraction.engine.GeminiExtractor"),
        ):
            engine = ExtractionEngine(default_provider="claude")
            assert engine.default_provider == "claude"

    def test_init_custom_cache(self, mock_api_keys: None, temp_cache: ExtractionCache) -> None:
        """Test initialization with custom cache."""
        with (
            patch("inkwell.extraction.engine.ClaudeExtractor"),
            patch("inkwell.extraction.engine.GeminiExtractor"),
        ):
            engine = ExtractionEngine(
                cache=temp_cache,
                gemini_api_key="AIzaSyD" + "X" * 32,
            )
            assert engine.cache == temp_cache


class TestExtractionEngineConfigInjection:
    """Test configuration dependency injection patterns.

    These tests validate the parameter precedence logic for backward-compatible
    dependency injection, ensuring config objects take precedence over individual params.
    """

    def test_config_object_only(self, mock_api_keys: None) -> None:
        """Using only config object works correctly."""
        config = ExtractionConfig(
            default_provider="claude",
            claude_api_key="test-claude-key-123456789012345678901234567890123456789012345678901234567890",
            gemini_api_key="test-gemini-key-123456789012345678901234567890123456789012345678901234567890",
        )

        with (
            patch("inkwell.extraction.engine.ClaudeExtractor") as mock_claude,
            patch("inkwell.extraction.engine.GeminiExtractor") as mock_gemini,
        ):
            engine = ExtractionEngine(config=config)

            assert engine.default_provider == "claude"
            # Verify config values are stored (extractors are lazy-initialized)
            assert engine._claude_api_key == config.claude_api_key
            assert engine._gemini_api_key == config.gemini_api_key
            # Access extractors to trigger lazy initialization
            _ = engine.claude_extractor
            _ = engine.gemini_extractor
            mock_claude.assert_called_once()
            mock_gemini.assert_called_once()

    def test_individual_params_only(self, mock_api_keys: None) -> None:
        """Using only individual params works (backward compatibility)."""
        with (
            patch("inkwell.extraction.engine.ClaudeExtractor"),
            patch("inkwell.extraction.engine.GeminiExtractor"),
        ):
            engine = ExtractionEngine(
                claude_api_key="test-claude-1234567890123456789012345678901234567890123456789012345678901234567890",
                gemini_api_key="test-gemini-1234567890123456789012345678901234567890123456789012345678901234567890",
                default_provider="gemini",
            )

            assert engine.default_provider == "gemini"

    def test_config_overrides_individual_params(self, mock_api_keys: None) -> None:
        """Config object takes precedence over individual params.

        This is the critical test that catches bug #046 - when both config
        and individual params are provided, config should win.
        """
        config = ExtractionConfig(
            default_provider="claude",
            claude_api_key="config-claude-key-12345678901234567890123456789012345678901234567890123456789012345678901234567890",
        )

        with (
            patch("inkwell.extraction.engine.ClaudeExtractor"),
            patch("inkwell.extraction.engine.GeminiExtractor"),
        ):
            engine = ExtractionEngine(
                config=config,
                claude_api_key="deprecated-key-1234567890123456789012345678901234567890123456789012345678901234567890",
                default_provider="gemini",  # Should be ignored
            )

            # Config values should win
            assert engine.default_provider == "claude"
            # NOT "gemini"

    def test_config_none_values_fall_back_to_params(self, mock_api_keys: None) -> None:
        """When config has None values, falls back to individual params."""
        config = ExtractionConfig(
            claude_api_key=None,  # Explicit None
            default_provider="claude",
        )

        with (
            patch("inkwell.extraction.engine.ClaudeExtractor"),
            patch("inkwell.extraction.engine.GeminiExtractor"),
        ):
            engine = ExtractionEngine(
                config=config,
                claude_api_key="fallback-key-123456789012345678901234567890123456789012345678901234567890",
            )

            # Should use config default_provider
            assert engine.default_provider == "claude"

    def test_empty_config_uses_defaults(self, mock_api_keys: None) -> None:
        """Empty config object uses default values."""
        config = ExtractionConfig()  # All defaults

        with (
            patch("inkwell.extraction.engine.ClaudeExtractor"),
            patch("inkwell.extraction.engine.GeminiExtractor"),
        ):
            engine = ExtractionEngine(config=config)

            # Should use defaults from ExtractionConfig
            assert engine.default_provider == "gemini"

    def test_cost_tracker_injection_with_config(self, mock_api_keys: None, tmp_path: Path) -> None:
        """Cost tracker can be injected with config object."""
        from inkwell.utils.costs import CostTracker

        tracker = CostTracker(costs_file=tmp_path / "costs.json")
        config = ExtractionConfig()

        with (
            patch("inkwell.extraction.engine.ClaudeExtractor"),
            patch("inkwell.extraction.engine.GeminiExtractor"),
        ):
            engine = ExtractionEngine(config=config, cost_tracker=tracker)

            assert engine.cost_tracker is tracker

    def test_cost_tracker_injection_without_config(
        self, mock_api_keys: None, tmp_path: Path
    ) -> None:
        """Cost tracker works with individual params (backward compat)."""
        from inkwell.utils.costs import CostTracker

        tracker = CostTracker(costs_file=tmp_path / "costs.json")

        with (
            patch("inkwell.extraction.engine.ClaudeExtractor"),
            patch("inkwell.extraction.engine.GeminiExtractor"),
        ):
            engine = ExtractionEngine(
                claude_api_key="test-key-1234567890123456789012345678901234567890123456789012345678901234567890",
                cost_tracker=tracker,
            )

            assert engine.cost_tracker is tracker

    def test_config_with_all_values_set(self, mock_api_keys: None) -> None:
        """Config with all values explicitly set works correctly."""
        config = ExtractionConfig(
            default_provider="claude",
            claude_api_key="claude-key-12345678901234567890123456789012345678901234567890123456789012345678901234567890",
            gemini_api_key="gemini-key-12345678901234567890123456789012345678901234567890123456789012345678901234567890",
        )

        with (
            patch("inkwell.extraction.engine.ClaudeExtractor"),
            patch("inkwell.extraction.engine.GeminiExtractor"),
        ):
            engine = ExtractionEngine(config=config)

            assert engine.default_provider == "claude"

    def test_multiple_initialization_paths(self, mock_api_keys: None) -> None:
        """Verify multiple initialization paths don't interfere."""
        with (
            patch("inkwell.extraction.engine.ClaudeExtractor"),
            patch("inkwell.extraction.engine.GeminiExtractor"),
        ):
            # Path 1: Config only
            config1 = ExtractionConfig(default_provider="claude")
            engine1 = ExtractionEngine(config=config1)
            assert engine1.default_provider == "claude"

            # Path 2: Params only
            engine2 = ExtractionEngine(default_provider="gemini")
            assert engine2.default_provider == "gemini"

            # Path 3: Both (config wins)
            config3 = ExtractionConfig(default_provider="claude")
            engine3 = ExtractionEngine(config=config3, default_provider="gemini")
            assert engine3.default_provider == "claude"

            # Verify engines are independent
            assert engine1.default_provider == "claude"
            assert engine2.default_provider == "gemini"
            assert engine3.default_provider == "claude"


class TestExtractionEngineExtract:
    """Tests for single extraction."""

    @pytest.mark.asyncio
    async def test_extract_text_success(
        self, mock_api_keys: None, text_template: ExtractionTemplate, temp_cache: ExtractionCache
    ) -> None:
        """Test successful text extraction."""
        with (
            patch("inkwell.extraction.engine.ClaudeExtractor"),
            patch("inkwell.extraction.engine.GeminiExtractor"),
        ):
            engine = ExtractionEngine(
                cache=temp_cache,
                gemini_api_key="AIzaSyD" + "X" * 32,
            )

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
        with (
            patch("inkwell.extraction.engine.ClaudeExtractor"),
            patch("inkwell.extraction.engine.GeminiExtractor"),
        ):
            engine = ExtractionEngine(
                cache=temp_cache,
                gemini_api_key="AIzaSyD" + "X" * 32,
            )

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
        with (
            patch("inkwell.extraction.engine.ClaudeExtractor"),
            patch("inkwell.extraction.engine.GeminiExtractor"),
        ):
            engine = ExtractionEngine(
                cache=temp_cache,
                gemini_api_key="AIzaSyD" + "X" * 32,
            )

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
        with (
            patch("inkwell.extraction.engine.ClaudeExtractor"),
            patch("inkwell.extraction.engine.GeminiExtractor"),
        ):
            engine = ExtractionEngine(
                cache=temp_cache,
                gemini_api_key="AIzaSyD" + "X" * 32,
            )

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
        with (
            patch("inkwell.extraction.engine.ClaudeExtractor"),
            patch("inkwell.extraction.engine.GeminiExtractor"),
        ):
            engine = ExtractionEngine(
                cache=temp_cache,
                gemini_api_key="AIzaSyD" + "X" * 32,
            )

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
        with (
            patch("inkwell.extraction.engine.ClaudeExtractor"),
            patch("inkwell.extraction.engine.GeminiExtractor"),
        ):
            engine = ExtractionEngine(
                cache=temp_cache,
                default_provider="gemini",
                gemini_api_key="AIzaSyD" + "X" * 32,
                claude_api_key="sk-ant-api03-" + "X" * 32,
            )

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
        with (
            patch("inkwell.extraction.engine.ClaudeExtractor"),
            patch("inkwell.extraction.engine.GeminiExtractor"),
        ):
            engine = ExtractionEngine(
                cache=temp_cache,
                default_provider="claude",
                gemini_api_key="AIzaSyD" + "X" * 32,
                claude_api_key="sk-ant-api03-" + "X" * 32,
            )

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
        with (
            patch("inkwell.extraction.engine.ClaudeExtractor"),
            patch("inkwell.extraction.engine.GeminiExtractor"),
        ):
            engine = ExtractionEngine(
                cache=temp_cache,
                default_provider="gemini",
                gemini_api_key="AIzaSyD" + "X" * 32,
                claude_api_key="sk-ant-api03-" + "X" * 32,
            )

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
        with (
            patch("inkwell.extraction.engine.ClaudeExtractor"),
            patch("inkwell.extraction.engine.GeminiExtractor"),
        ):
            # Default to Claude
            engine = ExtractionEngine(
                cache=temp_cache,
                default_provider="claude",
                gemini_api_key="AIzaSyD" + "X" * 32,
                claude_api_key="sk-ant-api03-" + "X" * 32,
            )

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
        with (
            patch("inkwell.extraction.engine.ClaudeExtractor"),
            patch("inkwell.extraction.engine.GeminiExtractor"),
        ):
            engine = ExtractionEngine(
                cache=temp_cache,
                gemini_api_key="AIzaSyD" + "X" * 32,
                claude_api_key="sk-ant-api03-" + "X" * 32,
            )

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
        with (
            patch("inkwell.extraction.engine.ClaudeExtractor"),
            patch("inkwell.extraction.engine.GeminiExtractor"),
        ):
            engine = ExtractionEngine(
                cache=temp_cache,
                gemini_api_key="AIzaSyD" + "X" * 32,
            )

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
        self,
        mock_api_keys: None,
        text_template: ExtractionTemplate,
        temp_cache: ExtractionCache,
        tmp_path: Path,
    ) -> None:
        """Test that costs are tracked with injected CostTracker."""
        from inkwell.utils.costs import CostTracker

        with (
            patch("inkwell.extraction.engine.ClaudeExtractor"),
            patch("inkwell.extraction.engine.GeminiExtractor"),
        ):
            # Create cost tracker with temp file
            cost_tracker = CostTracker(costs_file=tmp_path / "costs.json")
            engine = ExtractionEngine(
                cache=temp_cache,
                cost_tracker=cost_tracker,
                gemini_api_key="AIzaSyD" + "X" * 32,
            )

            mock_extract = AsyncMock(return_value="Result")
            engine.gemini_extractor.extract = mock_extract
            engine.gemini_extractor.estimate_cost = Mock(return_value=0.05)
            engine.gemini_extractor.model = "gemini-2.5-flash-latest"

            # Initial cost
            assert engine.get_total_cost() == 0.0

            # After extraction
            await engine.extract(
                template=text_template,
                transcript="Test",
                metadata={},
            )

            # Cost should be tracked
            assert engine.get_total_cost() > 0.0

            # After another extraction
            initial_cost = engine.get_total_cost()
            await engine.extract(
                template=text_template,
                transcript="Test 2",
                metadata={},
            )

            # Cost should increase
            assert engine.get_total_cost() > initial_cost

    @pytest.mark.asyncio
    async def test_reset_cost_tracking(
        self,
        mock_api_keys: None,
        text_template: ExtractionTemplate,
        temp_cache: ExtractionCache,
        tmp_path: Path,
    ) -> None:
        """Test resetting cost tracking."""
        from inkwell.utils.costs import CostTracker

        with (
            patch("inkwell.extraction.engine.ClaudeExtractor"),
            patch("inkwell.extraction.engine.GeminiExtractor"),
        ):
            cost_tracker = CostTracker(costs_file=tmp_path / "costs.json")
            engine = ExtractionEngine(
                cache=temp_cache,
                cost_tracker=cost_tracker,
                gemini_api_key="AIzaSyD" + "X" * 32,
            )

            mock_extract = AsyncMock(return_value="Result")
            engine.gemini_extractor.extract = mock_extract
            engine.gemini_extractor.estimate_cost = Mock(return_value=0.05)
            engine.gemini_extractor.model = "gemini-2.5-flash-latest"

            await engine.extract(
                template=text_template,
                transcript="Test",
                metadata={},
            )

            # Cost should be tracked
            initial_cost = engine.get_total_cost()
            assert initial_cost > 0.0

            # Reset should zero out the session cost
            engine.reset_cost_tracking()
            assert engine.get_total_cost() == 0.0

    def test_estimate_total_cost(
        self,
        mock_api_keys: None,
        text_template: ExtractionTemplate,
        json_template: ExtractionTemplate,
    ) -> None:
        """Test estimating total cost for multiple templates."""
        with (
            patch("inkwell.extraction.engine.ClaudeExtractor"),
            patch("inkwell.extraction.engine.GeminiExtractor"),
        ):
            engine = ExtractionEngine(
                gemini_api_key="AIzaSyD" + "X" * 32,
                claude_api_key="sk-ant-api03-" + "X" * 32,
            )

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

    def test_parse_text_output(
        self, mock_api_keys: None, text_template: ExtractionTemplate
    ) -> None:
        """Test parsing text output."""
        with (
            patch("inkwell.extraction.engine.ClaudeExtractor"),
            patch("inkwell.extraction.engine.GeminiExtractor"),
        ):
            engine = ExtractionEngine(
                gemini_api_key="AIzaSyD" + "X" * 32,
                claude_api_key="sk-ant-api03-" + "X" * 32,
            )

            content = engine._parse_output("Plain text result", text_template)

            assert content.template_name == "summary"
            assert content.content == "Plain text result"

    def test_parse_json_output(
        self, mock_api_keys: None, json_template: ExtractionTemplate
    ) -> None:
        """Test parsing JSON output."""
        with (
            patch("inkwell.extraction.engine.ClaudeExtractor"),
            patch("inkwell.extraction.engine.GeminiExtractor"),
        ):
            engine = ExtractionEngine(
                gemini_api_key="AIzaSyD" + "X" * 32,
                claude_api_key="sk-ant-api03-" + "X" * 32,
            )

            json_str = '{"quotes": ["one", "two"]}'
            content = engine._parse_output(json_str, json_template)

            assert content.template_name == "quotes"
            assert content.content == {"quotes": ["one", "two"]}

    def test_parse_markdown_output(self, mock_api_keys: None) -> None:
        """Test parsing markdown output."""
        with (
            patch("inkwell.extraction.engine.ClaudeExtractor"),
            patch("inkwell.extraction.engine.GeminiExtractor"),
        ):
            engine = ExtractionEngine(
                gemini_api_key="AIzaSyD" + "X" * 32,
                claude_api_key="sk-ant-api03-" + "X" * 32,
            )

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
        with (
            patch("inkwell.extraction.engine.ClaudeExtractor"),
            patch("inkwell.extraction.engine.GeminiExtractor"),
        ):
            engine = ExtractionEngine(
                gemini_api_key="AIzaSyD" + "X" * 32,
                claude_api_key="sk-ant-api03-" + "X" * 32,
            )

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


class TestExtractionEngineDeprecationWarnings:
    """Test deprecation warnings for individual parameters."""

    def test_deprecated_api_keys_trigger_warning(self, mock_api_keys: None) -> None:
        """Using deprecated individual API keys should trigger DeprecationWarning."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            with (
                patch("inkwell.extraction.engine.ClaudeExtractor"),
                patch("inkwell.extraction.engine.GeminiExtractor"),
            ):
                engine = ExtractionEngine(
                    claude_api_key="test-claude-key-1234567890123456789012345678901234567890",
                    gemini_api_key="test-gemini-key-1234567890123456789012345678901234567890",
                )

            # Should have triggered exactly one warning
            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert "deprecated" in str(w[0].message).lower()
            assert "ExtractionConfig" in str(w[0].message)
            assert "v2.0" in str(w[0].message)
            # Should mention both API keys
            assert "claude_api_key" in str(w[0].message)
            assert "gemini_api_key" in str(w[0].message)

    def test_deprecated_default_provider_trigger_warning(self, mock_api_keys: None) -> None:
        """Using deprecated default_provider should trigger DeprecationWarning."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            with (
                patch("inkwell.extraction.engine.ClaudeExtractor"),
                patch("inkwell.extraction.engine.GeminiExtractor"),
            ):
                engine = ExtractionEngine(
                    default_provider="claude"  # Non-default value
                )

            # Should have triggered warning
            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert "default_provider" in str(w[0].message)

    def test_default_provider_gemini_no_warning(self, mock_api_keys: None) -> None:
        """Using default value for default_provider should NOT trigger warning."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            with (
                patch("inkwell.extraction.engine.ClaudeExtractor"),
                patch("inkwell.extraction.engine.GeminiExtractor"),
            ):
                engine = ExtractionEngine(
                    default_provider="gemini"  # Default value
                )

            # Should have no warnings (default value)
            assert len(w) == 0

    def test_config_object_no_warning(self, mock_api_keys: None) -> None:
        """Using config object should NOT trigger warning."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            config = ExtractionConfig(
                claude_api_key="test-key-1234567890123456789012345678901234567890"
            )

            with (
                patch("inkwell.extraction.engine.ClaudeExtractor"),
                patch("inkwell.extraction.engine.GeminiExtractor"),
            ):
                engine = ExtractionEngine(config=config)

            # Should have no warnings
            assert len(w) == 0

    def test_only_claude_api_key_warns(self, mock_api_keys: None) -> None:
        """Using only claude_api_key should trigger warning."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            with (
                patch("inkwell.extraction.engine.ClaudeExtractor"),
                patch("inkwell.extraction.engine.GeminiExtractor"),
            ):
                engine = ExtractionEngine(
                    claude_api_key="test-key-1234567890123456789012345678901234567890"
                )

            # Should have triggered warning
            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert "claude_api_key" in str(w[0].message)

    def test_only_gemini_api_key_warns(self, mock_api_keys: None) -> None:
        """Using only gemini_api_key should trigger warning."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            with (
                patch("inkwell.extraction.engine.ClaudeExtractor"),
                patch("inkwell.extraction.engine.GeminiExtractor"),
            ):
                engine = ExtractionEngine(
                    gemini_api_key="test-key-1234567890123456789012345678901234567890"
                )

            # Should have triggered warning
            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert "gemini_api_key" in str(w[0].message)

    def test_config_with_individual_params_no_warning(self, mock_api_keys: None) -> None:
        """When config is provided, no warning even if deprecated params present.

        This is by design - if user provides config, they're using the new pattern.
        Individual params might be there for legacy reasons but config takes precedence.
        """
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            config = ExtractionConfig(
                claude_api_key="config-key-1234567890123456789012345678901234567890"
            )

            with (
                patch("inkwell.extraction.engine.ClaudeExtractor"),
                patch("inkwell.extraction.engine.GeminiExtractor"),
            ):
                engine = ExtractionEngine(
                    config=config,
                    claude_api_key="param-key-1234567890123456789012345678901234567890",
                )

            # Should have no warnings (config is provided)
            assert len(w) == 0

    def test_no_params_no_warning(self, mock_api_keys: None) -> None:
        """Using ExtractionConfig should not trigger deprecation warning."""
        from inkwell.config.schema import ExtractionConfig

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            with (
                patch("inkwell.extraction.engine.ClaudeExtractor"),
                patch("inkwell.extraction.engine.GeminiExtractor"),
            ):
                # Using ExtractionConfig avoids deprecation warning
                config = ExtractionConfig(
                    gemini_api_key="AIzaSyD" + "X" * 32,
                    claude_api_key="sk-ant-api03-" + "X" * 32,
                )
                engine = ExtractionEngine(config=config)

            # Should have no deprecation warnings when using config
            assert len(w) == 0

    def test_warning_message_includes_migration_info(self, mock_api_keys: None) -> None:
        """Warning message should include what to use instead."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            with (
                patch("inkwell.extraction.engine.ClaudeExtractor"),
                patch("inkwell.extraction.engine.GeminiExtractor"),
            ):
                engine = ExtractionEngine(
                    gemini_api_key="test-key-1234567890123456789012345678901234567890"
                )

            # Verify warning message is helpful
            warning_msg = str(w[0].message)
            assert "ExtractionConfig" in warning_msg
            assert "v2.0" in warning_msg
            assert "deprecated" in warning_msg.lower()

    def test_multiple_deprecated_params_listed(self, mock_api_keys: None) -> None:
        """Warning should list all deprecated params being used."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            with (
                patch("inkwell.extraction.engine.ClaudeExtractor"),
                patch("inkwell.extraction.engine.GeminiExtractor"),
            ):
                engine = ExtractionEngine(
                    claude_api_key="test-claude-1234567890123456789012345678901234567890",
                    gemini_api_key="test-gemini-1234567890123456789012345678901234567890",
                    default_provider="claude",
                )

            # Should list all three deprecated params
            warning_msg = str(w[0].message)
            assert "claude_api_key" in warning_msg
            assert "gemini_api_key" in warning_msg
            assert "default_provider" in warning_msg
