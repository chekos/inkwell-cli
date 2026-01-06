"""Unit tests for ExtractionPlugin base class and integration."""

from unittest.mock import AsyncMock, patch

import pytest

from inkwell.plugins import ExtractionPlugin, PluginRegistry
from inkwell.plugins.base import PLUGIN_API_VERSION


class TestExtractionPluginBase:
    """Tests for ExtractionPlugin base class."""

    def test_plugin_requires_abstract_methods(self) -> None:
        """Test that plugins must implement abstract methods."""
        # This should raise TypeError for abstract class
        with pytest.raises(TypeError, match="abstract"):

            class BadPlugin(ExtractionPlugin):
                NAME = "bad-plugin"
                VERSION = "1.0.0"
                DESCRIPTION = "Incomplete plugin"

            BadPlugin()  # Should fail because abstract methods not implemented

    def test_plugin_inherits_from_inkwell_plugin(self) -> None:
        """Test that ExtractionPlugin inherits from InkwellPlugin."""
        from inkwell.plugins.base import InkwellPlugin

        assert issubclass(ExtractionPlugin, InkwellPlugin)

    def test_plugin_api_version(self) -> None:
        """Test that ExtractionPlugin has correct API version."""
        assert ExtractionPlugin.API_VERSION == PLUGIN_API_VERSION


class TestClaudePluginIntegration:
    """Tests for ClaudeExtractor as a plugin."""

    def test_claude_extractor_is_extraction_plugin(self) -> None:
        """Test that ClaudeExtractor is an ExtractionPlugin."""
        from inkwell.extraction.extractors.claude import ClaudeExtractor

        assert issubclass(ClaudeExtractor, ExtractionPlugin)

    def test_claude_extractor_has_required_metadata(self) -> None:
        """Test that ClaudeExtractor has required plugin metadata."""
        from inkwell.extraction.extractors.claude import ClaudeExtractor

        assert ClaudeExtractor.NAME == "claude"
        assert ClaudeExtractor.VERSION == "1.0.0"
        assert ClaudeExtractor.DESCRIPTION is not None
        assert len(ClaudeExtractor.DESCRIPTION) > 0

    def test_claude_extractor_has_model_and_pricing(self) -> None:
        """Test that ClaudeExtractor has model and pricing info."""
        from inkwell.extraction.extractors.claude import ClaudeExtractor

        assert ClaudeExtractor.MODEL is not None
        assert ClaudeExtractor.INPUT_PRICE_PER_M > 0
        assert ClaudeExtractor.OUTPUT_PRICE_PER_M > 0


class TestGeminiPluginIntegration:
    """Tests for GeminiExtractor as a plugin."""

    def test_gemini_extractor_is_extraction_plugin(self) -> None:
        """Test that GeminiExtractor is an ExtractionPlugin."""
        from inkwell.extraction.extractors.gemini import GeminiExtractor

        assert issubclass(GeminiExtractor, ExtractionPlugin)

    def test_gemini_extractor_has_required_metadata(self) -> None:
        """Test that GeminiExtractor has required plugin metadata."""
        from inkwell.extraction.extractors.gemini import GeminiExtractor

        assert GeminiExtractor.NAME == "gemini"
        assert GeminiExtractor.VERSION == "1.0.0"
        assert GeminiExtractor.DESCRIPTION is not None
        assert len(GeminiExtractor.DESCRIPTION) > 0

    def test_gemini_extractor_has_model_and_pricing(self) -> None:
        """Test that GeminiExtractor has model and pricing info."""
        from inkwell.extraction.extractors.gemini import GeminiExtractor

        assert GeminiExtractor.MODEL is not None
        assert GeminiExtractor.INPUT_PRICE_PER_M > 0
        assert GeminiExtractor.OUTPUT_PRICE_PER_M > 0


class TestExtractionPluginRegistry:
    """Tests for ExtractionPlugin registry integration."""

    def test_registry_can_hold_extraction_plugins(self) -> None:
        """Test that PluginRegistry can be parameterized with ExtractionPlugin."""
        registry: PluginRegistry[ExtractionPlugin] = PluginRegistry(ExtractionPlugin)
        assert len(registry) == 0

    def test_register_extraction_plugin(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test registering an extraction plugin."""
        from inkwell.extraction.extractors.claude import ClaudeExtractor

        # Set up API key
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-api03-" + "X" * 32)

        registry: PluginRegistry[ExtractionPlugin] = PluginRegistry(ExtractionPlugin)

        extractor = ClaudeExtractor()
        registry.register(
            name="claude",
            plugin=extractor,
            priority=100,
            source="test:claude",
        )

        assert len(registry) == 1
        assert "claude" in registry
        retrieved = registry.get("claude")
        assert retrieved is extractor


class TestExtractionEngineRegistry:
    """Tests for ExtractionEngine plugin registry integration."""

    @pytest.fixture
    def mock_api_keys(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Set mock API keys."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-api03-" + "X" * 32)
        monkeypatch.setenv("GOOGLE_API_KEY", "AIzaSyD" + "X" * 32)

    def test_engine_has_extraction_registry(self, mock_api_keys: None) -> None:
        """Test that ExtractionEngine exposes extraction_registry."""
        from inkwell.extraction.engine import ExtractionEngine

        # Create engine without plugin registry to avoid entry point discovery
        engine = ExtractionEngine(use_plugin_registry=False)
        assert hasattr(engine, "extraction_registry")
        assert isinstance(engine.extraction_registry, PluginRegistry)

    @pytest.mark.skip(reason="Entry point discovery requires package to be installed")
    def test_engine_discovers_plugins(self, mock_api_keys: None) -> None:
        """Test that ExtractionEngine discovers plugins from entry points."""
        from inkwell.extraction.engine import ExtractionEngine

        # This would require the package to be installed with entry points
        engine = ExtractionEngine(use_plugin_registry=True)
        registry = engine.extraction_registry

        # Should have discovered at least claude and gemini
        assert "claude" in registry or "gemini" in registry

    def test_engine_uses_legacy_extractors_when_registry_disabled(
        self, mock_api_keys: None
    ) -> None:
        """Test that engine uses legacy extractors when plugin registry disabled."""
        from inkwell.extraction.engine import ExtractionEngine
        from inkwell.extraction.extractors.claude import ClaudeExtractor
        from inkwell.extraction.extractors.gemini import GeminiExtractor

        engine = ExtractionEngine(use_plugin_registry=False)

        # Should use legacy extractors
        assert isinstance(engine.claude_extractor, ClaudeExtractor)
        assert isinstance(engine.gemini_extractor, GeminiExtractor)


class TestExtractionPluginConfigure:
    """Tests for ExtractionPlugin configuration."""

    def test_plugin_configure_sets_cost_tracker(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that configure() sets cost tracker."""
        from inkwell.extraction.extractors.claude import ClaudeExtractor
        from inkwell.utils.costs import CostTracker

        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-api03-" + "X" * 32)

        extractor = ClaudeExtractor()
        cost_tracker = CostTracker()

        extractor.configure({}, cost_tracker)

        assert extractor.cost_tracker is cost_tracker
        assert extractor.is_initialized is True

    def test_plugin_configure_with_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that configure() can provide API key."""
        from inkwell.extraction.extractors.claude import ClaudeExtractor

        # Don't set env var
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        # Create with lazy init (like plugin discovery does)
        extractor = ClaudeExtractor(lazy_init=True)

        # Configure should set up the API key
        api_key = "sk-ant-api03-" + "Y" * 32
        extractor.configure({"api_key": api_key})

        assert extractor.api_key == api_key
        assert extractor._client is not None


class TestExtractionPluginBuildPrompt:
    """Tests for ExtractionPlugin build_prompt method."""

    def test_build_prompt_renders_template(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that build_prompt renders Jinja2 template."""
        from inkwell.extraction.extractors.claude import ClaudeExtractor
        from inkwell.extraction.models import ExtractionTemplate

        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-api03-" + "X" * 32)

        extractor = ClaudeExtractor()
        template = ExtractionTemplate(
            name="test",
            version="1.0",
            description="Test template",
            system_prompt="System prompt",
            user_prompt_template="Extract from: {{ transcript }}. Podcast: {{ metadata.podcast_name }}",
            expected_format="text",
        )

        prompt = extractor.build_prompt(
            template=template,
            transcript="Test transcript content",
            metadata={"podcast_name": "My Podcast"},
        )

        assert "Test transcript content" in prompt
        assert "My Podcast" in prompt
