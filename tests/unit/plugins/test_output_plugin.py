"""Unit tests for OutputPlugin base class and MarkdownOutput integration."""

import warnings

import pytest

from inkwell.extraction.models import ExtractedContent, ExtractionResult
from inkwell.plugins import OutputPlugin, PluginRegistry
from inkwell.plugins.base import PLUGIN_API_VERSION


class TestOutputPluginBase:
    """Tests for OutputPlugin base class."""

    def test_plugin_requires_abstract_methods(self) -> None:
        """Test that plugins must implement abstract methods."""
        # This should raise TypeError for abstract class
        with pytest.raises(TypeError, match="abstract"):

            class BadPlugin(OutputPlugin):
                NAME = "bad-plugin"
                VERSION = "1.0.0"
                DESCRIPTION = "Incomplete plugin"

            BadPlugin()  # Should fail because abstract methods not implemented

    def test_plugin_inherits_from_inkwell_plugin(self) -> None:
        """Test that OutputPlugin inherits from InkwellPlugin."""
        from inkwell.plugins.base import InkwellPlugin

        assert issubclass(OutputPlugin, InkwellPlugin)

    def test_plugin_api_version(self) -> None:
        """Test that OutputPlugin has correct API version."""
        assert OutputPlugin.API_VERSION == PLUGIN_API_VERSION

    def test_plugin_has_output_format_defaults(self) -> None:
        """Test that OutputPlugin has default output format attributes."""
        assert OutputPlugin.OUTPUT_FORMAT == "Unknown"
        assert OutputPlugin.FILE_EXTENSION == ".txt"


class TestMarkdownOutputPlugin:
    """Tests for MarkdownOutput as a plugin."""

    def test_markdown_output_is_output_plugin(self) -> None:
        """Test that MarkdownOutput is an OutputPlugin."""
        from inkwell.output.markdown import MarkdownOutput

        assert issubclass(MarkdownOutput, OutputPlugin)

    def test_markdown_output_has_required_metadata(self) -> None:
        """Test that MarkdownOutput has required plugin metadata."""
        from inkwell.output.markdown import MarkdownOutput

        assert MarkdownOutput.NAME == "markdown"
        assert MarkdownOutput.VERSION == "1.0.0"
        assert MarkdownOutput.DESCRIPTION is not None
        assert len(MarkdownOutput.DESCRIPTION) > 0

    def test_markdown_output_has_format_metadata(self) -> None:
        """Test that MarkdownOutput has output format metadata."""
        from inkwell.output.markdown import MarkdownOutput

        assert MarkdownOutput.OUTPUT_FORMAT == "Markdown"
        assert MarkdownOutput.FILE_EXTENSION == ".md"

    def test_markdown_output_properties(self) -> None:
        """Test that MarkdownOutput properties work correctly."""
        from inkwell.output.markdown import MarkdownOutput

        output = MarkdownOutput()
        assert output.output_format == "Markdown"
        assert output.file_extension == ".md"
        assert output.NAME == "markdown"

    def test_markdown_output_lazy_init(self) -> None:
        """Test that MarkdownOutput supports lazy initialization."""
        from inkwell.output.markdown import MarkdownOutput

        output = MarkdownOutput(lazy_init=True)
        assert output._lazy_init is True
        assert output.is_initialized is False

        output.configure({})
        assert output.is_initialized is True

    def test_get_filename(self) -> None:
        """Test that get_filename returns correct filename."""
        from inkwell.output.markdown import MarkdownOutput

        output = MarkdownOutput()
        assert output.get_filename("summary") == "summary.md"
        assert output.get_filename("quotes") == "quotes.md"


class TestMarkdownOutputRender:
    """Tests for MarkdownOutput.render() method."""

    @pytest.fixture
    def markdown_output(self) -> "MarkdownOutput":
        """Create configured MarkdownOutput instance."""
        from inkwell.output.markdown import MarkdownOutput

        output = MarkdownOutput()
        output.configure({})
        return output

    @pytest.fixture
    def sample_result(self) -> ExtractionResult:
        """Create sample extraction result."""
        return ExtractionResult(
            episode_url="https://example.com/ep1",
            template_name="summary",
            success=True,
            extracted_content=ExtractedContent(
                template_name="summary",
                content="This is a test summary.",
            ),
            cost_usd=0.01,
            provider="gemini",
        )

    @pytest.fixture
    def sample_metadata(self) -> dict:
        """Create sample episode metadata."""
        return {
            "podcast_name": "Test Podcast",
            "episode_title": "Episode 1: Testing",
            "episode_url": "https://example.com/ep1",
        }

    @pytest.mark.asyncio
    async def test_render_basic(
        self, markdown_output, sample_result: ExtractionResult, sample_metadata: dict
    ) -> None:
        """Test basic render functionality."""
        content = await markdown_output.render(sample_result, sample_metadata)

        # Check frontmatter is present
        assert content.startswith("---")
        assert "template: summary" in content
        assert "podcast: Test Podcast" in content
        # YAML may quote strings with colons, so check for the title content
        assert "Episode 1: Testing" in content

        # Check content is present
        assert "This is a test summary." in content

    @pytest.mark.asyncio
    async def test_render_without_frontmatter(
        self, markdown_output, sample_result: ExtractionResult, sample_metadata: dict
    ) -> None:
        """Test render without frontmatter."""
        content = await markdown_output.render(
            sample_result, sample_metadata, include_frontmatter=False
        )

        # Check frontmatter is NOT present
        assert not content.startswith("---")
        # Content should still be there
        assert "This is a test summary." in content

    @pytest.mark.asyncio
    async def test_render_json_content(self, markdown_output, sample_metadata: dict) -> None:
        """Test render with JSON/dict content."""
        result = ExtractionResult(
            episode_url="https://example.com/ep1",
            template_name="quotes",
            success=True,
            extracted_content=ExtractedContent(
                template_name="quotes",
                content={"quotes": [{"text": "Test quote", "speaker": "John", "timestamp": "5:30"}]},
            ),
            cost_usd=0.02,
            provider="claude",
        )

        content = await markdown_output.render(result, sample_metadata)

        # Check structured content is formatted
        assert "# Quotes" in content
        assert "Test quote" in content
        assert "John" in content
        assert "5:30" in content


class TestMarkdownOutputBackwardCompatibility:
    """Tests for backward compatibility with MarkdownGenerator."""

    def test_markdown_generator_alias_exists(self) -> None:
        """Test that MarkdownGenerator alias exists."""
        from inkwell.output.markdown import MarkdownGenerator, MarkdownOutput

        assert MarkdownGenerator is MarkdownOutput

    def test_generate_method_emits_deprecation_warning(self) -> None:
        """Test that generate() method emits deprecation warning."""
        from inkwell.output.markdown import MarkdownOutput

        output = MarkdownOutput()

        result = ExtractionResult(
            episode_url="https://example.com/ep1",
            template_name="summary",
            success=True,
            extracted_content=ExtractedContent(
                template_name="summary",
                content="Test content",
            ),
            cost_usd=0.01,
            provider="gemini",
        )

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            content = output.generate(result, {"podcast_name": "Test", "episode_title": "Ep1"})

            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert "deprecated" in str(w[0].message).lower()
            assert "render" in str(w[0].message).lower()

        # But it should still work
        assert "---" in content
        assert "Test content" in content


class TestOutputPluginRegistry:
    """Tests for OutputPlugin registry integration."""

    def test_registry_can_hold_output_plugins(self) -> None:
        """Test that PluginRegistry can be parameterized with OutputPlugin."""
        registry: PluginRegistry[OutputPlugin] = PluginRegistry(OutputPlugin)
        assert len(registry) == 0

    def test_register_output_plugin(self) -> None:
        """Test registering an output plugin."""
        from inkwell.output.markdown import MarkdownOutput

        registry: PluginRegistry[OutputPlugin] = PluginRegistry(OutputPlugin)
        plugin = MarkdownOutput(lazy_init=True)

        registry.register(
            name="markdown",
            plugin=plugin,
            priority=100,
            source="inkwell.plugins.output:markdown",
        )

        assert len(registry) == 1
        assert registry.get("markdown") is plugin

    def test_get_enabled_returns_priority_order(self) -> None:
        """Test that get_enabled returns plugins in priority order."""
        from inkwell.output.markdown import MarkdownOutput

        registry: PluginRegistry[OutputPlugin] = PluginRegistry(OutputPlugin)

        # Create and register plugins with different priorities
        md1 = MarkdownOutput(lazy_init=True)
        md2 = MarkdownOutput(lazy_init=True)

        registry.register(name="markdown-low", plugin=md1, priority=50)
        registry.register(name="markdown-high", plugin=md2, priority=100)

        enabled = registry.get_enabled()
        assert len(enabled) == 2
        assert enabled[0][0] == "markdown-high"  # Higher priority first
        assert enabled[1][0] == "markdown-low"


class TestOutputPluginDiscovery:
    """Tests for OutputPlugin discovery via entry points."""

    def test_discover_output_plugins(self) -> None:
        """Test that output plugins can be discovered."""
        from inkwell.plugins.discovery import discover_plugins

        results = list(discover_plugins("inkwell.plugins.output"))

        # Should find at least the built-in markdown plugin
        assert len(results) >= 1

        # Find the markdown plugin
        markdown_result = next((r for r in results if r.name == "markdown"), None)
        assert markdown_result is not None
        assert markdown_result.success is True
        assert markdown_result.plugin is not None

    def test_discovered_plugin_is_output_plugin(self) -> None:
        """Test that discovered plugin is an OutputPlugin."""
        from inkwell.plugins.discovery import discover_plugins

        results = list(discover_plugins("inkwell.plugins.output"))
        markdown_result = next((r for r in results if r.name == "markdown"), None)

        assert markdown_result is not None
        assert isinstance(markdown_result.plugin, OutputPlugin)


class TestOutputManagerPluginIntegration:
    """Tests for OutputManager integration with OutputPlugin."""

    def test_output_manager_accepts_renderer(self, tmp_path) -> None:
        """Test that OutputManager accepts renderer parameter."""
        from inkwell.output.manager import OutputManager
        from inkwell.output.markdown import MarkdownOutput

        output_dir = tmp_path / "output"
        renderer = MarkdownOutput()

        manager = OutputManager(output_dir=output_dir, renderer=renderer)

        assert manager.renderer is renderer

    def test_output_manager_defaults_to_markdown_output(self, tmp_path) -> None:
        """Test that OutputManager defaults to MarkdownOutput."""
        from inkwell.output.manager import OutputManager
        from inkwell.output.markdown import MarkdownOutput

        output_dir = tmp_path / "output"
        manager = OutputManager(output_dir=output_dir)

        assert isinstance(manager.renderer, MarkdownOutput)

    def test_output_manager_markdown_generator_deprecation(self, tmp_path) -> None:
        """Test that markdown_generator parameter emits deprecation warning."""
        from inkwell.output.manager import OutputManager
        from inkwell.output.markdown import MarkdownOutput

        output_dir = tmp_path / "output"
        renderer = MarkdownOutput()

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            manager = OutputManager(output_dir=output_dir, markdown_generator=renderer)

            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert "markdown_generator" in str(w[0].message)
            assert "renderer" in str(w[0].message)

        # But it should still work
        assert manager._renderer is renderer

    def test_output_manager_markdown_generator_property_deprecation(self, tmp_path) -> None:
        """Test that markdown_generator property emits deprecation warning."""
        from inkwell.output.manager import OutputManager

        output_dir = tmp_path / "output"
        manager = OutputManager(output_dir=output_dir)

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            _ = manager.markdown_generator

            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
