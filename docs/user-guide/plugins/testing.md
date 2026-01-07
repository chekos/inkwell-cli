# Testing Plugins

Test utilities, mocks, and best practices for testing Inkwell plugins.

---

## Testing Utilities

Inkwell provides testing utilities in `inkwell.plugins.testing`:

```python
from inkwell.plugins.testing import (
    MockCostTracker,
    MockPlugin,
    create_test_plugin,
    assert_plugin_valid,
    assert_plugin_configured,
    create_mock_entry_point,
)
```

---

## MockCostTracker

A mock cost tracker for testing plugins that track API usage:

```python
from inkwell.plugins.testing import MockCostTracker

def test_extraction_tracks_cost():
    # Create mock tracker
    tracker = MockCostTracker()

    # Configure plugin with mock tracker
    plugin = MyExtractor()
    plugin.configure({}, cost_tracker=tracker)

    # Run extraction
    result = await plugin.extract(template, transcript, metadata)

    # Verify cost was tracked
    assert tracker.call_count == 1
    assert tracker.total_cost > 0
    assert len(tracker.usage_history) == 1

    # Check specific usage record
    usage = tracker.usage_history[0]
    assert usage.provider == "my-extractor"
    assert usage.input_tokens > 0
```

### MockCostTracker Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `add_cost(provider, model, ...)` | `float` | Track API usage |
| `get_total_cost()` | `float` | Total cost across all usage |
| `get_session_cost()` | `float` | Cost for current session |
| `reset_session_cost()` | `None` | Reset session tracking |

### MockCostTracker Properties

| Property | Type | Description |
|----------|------|-------------|
| `total_cost` | `float` | Alias for `get_total_cost()` |
| `call_count` | `int` | Number of `add_cost` calls |
| `usage_history` | `list[MockAPIUsage]` | All recorded usage |

---

## MockPlugin

A simple mock plugin for testing infrastructure:

```python
from inkwell.plugins.testing import MockPlugin

def test_plugin_lifecycle():
    plugin = MockPlugin()

    # Configure plugin
    plugin.configure({"should_fail": False}, cost_tracker=None)
    assert plugin.configure_called

    # Validate plugin
    plugin.validate()
    assert plugin.validate_called

    # Cleanup plugin
    plugin.cleanup()
    assert plugin.cleanup_called


def test_validation_failure():
    plugin = MockPlugin()

    # Configure to fail validation
    plugin.configure({"should_fail": True, "validation_errors": ["Test error"]})

    # Verify validation raises
    with pytest.raises(PluginValidationError) as exc_info:
        plugin.validate()

    assert "Test error" in str(exc_info.value)
```

---

## Test Factories

### create_test_plugin()

Create test plugins with custom attributes:

```python
from inkwell.plugins.testing import create_test_plugin

def test_plugin_with_custom_metadata():
    plugin = create_test_plugin(
        name="custom-plugin",
        version="2.0.0",
        description="Custom test plugin",
        api_version="1.0",
        depends_on=["other-plugin"],
    )

    assert plugin.NAME == "custom-plugin"
    assert plugin.VERSION == "2.0.0"
    assert plugin.DEPENDS_ON == ["other-plugin"]


def test_plugin_validation_failure():
    plugin = create_test_plugin(
        name="failing-plugin",
        should_fail_validation=True,
    )

    plugin.configure({})

    with pytest.raises(PluginValidationError):
        plugin.validate()
```

### create_mock_entry_point()

Create mock entry points for testing discovery:

```python
from inkwell.plugins.testing import create_mock_entry_point
from unittest.mock import patch

def test_plugin_discovery():
    # Create mock entry point
    mock_ep = create_mock_entry_point(
        name="test-plugin",
        plugin_class=MyPlugin,
        group="inkwell.plugins.extraction",
    )

    # Patch entry point discovery
    with patch("importlib.metadata.entry_points") as mock_eps:
        mock_eps.return_value.select.return_value = [mock_ep]

        # Test discovery
        from inkwell.plugins.discovery import discover_plugins
        plugins = discover_plugins("inkwell.plugins.extraction")

        assert "test-plugin" in [p[0] for p in plugins]
```

---

## Assertion Helpers

### assert_plugin_valid()

Assert that a plugin passes validation:

```python
from inkwell.plugins.testing import assert_plugin_valid

def test_plugin_validates():
    plugin = MyPlugin()
    plugin.configure({"api_key": "test-key"})

    # This will raise AssertionError with details if validation fails
    assert_plugin_valid(plugin)
```

### assert_plugin_configured()

Assert that a plugin is properly configured:

```python
from inkwell.plugins.testing import assert_plugin_configured

def test_plugin_configuration():
    plugin = MyPlugin()
    plugin.configure({"model": "base", "language": "en"})

    # Check basic initialization
    assert_plugin_configured(plugin)

    # Check specific config values
    assert_plugin_configured(plugin, expected_config={"model": "base"})
```

---

## Testing Patterns

### Testing Extraction Plugins

```python
import pytest
from unittest.mock import AsyncMock, MagicMock

from inkwell.plugins.testing import MockCostTracker
from inkwell.extraction.models import ExtractionTemplate

@pytest.fixture
def mock_template():
    return ExtractionTemplate(
        name="test-template",
        system_prompt="You are a helpful assistant.",
        user_prompt_template="Extract info from: {{ transcript }}",
        max_tokens=1000,
        temperature=0.1,
    )

@pytest.fixture
def mock_metadata():
    return {
        "podcast_name": "Test Podcast",
        "episode_title": "Test Episode",
    }

class TestMyExtractor:
    @pytest.fixture
    def extractor(self):
        extractor = MyExtractor(lazy_init=True)
        extractor.configure({}, cost_tracker=MockCostTracker())
        return extractor

    @pytest.mark.asyncio
    async def test_extract_returns_string(self, extractor, mock_template, mock_metadata):
        # Mock the API client
        extractor._client = AsyncMock()
        extractor._client.messages.create.return_value = MagicMock(
            content=[MagicMock(text="Extracted content")]
        )

        result = await extractor.extract(
            mock_template,
            "This is a test transcript.",
            mock_metadata,
        )

        assert isinstance(result, str)
        assert len(result) > 0

    def test_estimate_cost(self, extractor, mock_template):
        cost = extractor.estimate_cost(mock_template, transcript_length=10000)
        assert cost > 0
        assert isinstance(cost, float)

    def test_supports_structured_output(self, extractor):
        assert isinstance(extractor.supports_structured_output(), bool)
```

### Testing Transcription Plugins

```python
import pytest
from pathlib import Path
from unittest.mock import patch

from inkwell.plugins.testing import MockCostTracker
from inkwell.plugins.types.transcription import TranscriptionRequest
from inkwell.transcription.models import Transcript

class TestWhisperTranscriber:
    @pytest.fixture
    def transcriber(self):
        transcriber = WhisperTranscriber(lazy_init=True)
        transcriber.configure({"model": "base"}, cost_tracker=MockCostTracker())
        return transcriber

    def test_can_handle_file(self, transcriber):
        request = TranscriptionRequest(file_path=Path("/tmp/audio.mp3"))
        assert transcriber.can_handle(request)

    def test_cannot_handle_url(self, transcriber):
        request = TranscriptionRequest(url="https://youtube.com/watch?v=abc")
        assert not transcriber.can_handle(request)

    @pytest.mark.asyncio
    async def test_transcribe_file(self, transcriber, tmp_path):
        # Create test audio file
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio data")

        # Mock whisper
        with patch("whisper.load_model") as mock_load:
            mock_model = MagicMock()
            mock_model.transcribe.return_value = {"text": "Hello world"}
            mock_load.return_value = mock_model

            request = TranscriptionRequest(file_path=audio_file)
            result = await transcriber.transcribe(request)

            assert isinstance(result, Transcript)
            assert result.text == "Hello world"

    def test_validate_missing_whisper(self, transcriber):
        with patch.dict("sys.modules", {"whisper": None}):
            with pytest.raises(PluginValidationError) as exc_info:
                transcriber.validate()
            assert "openai-whisper not installed" in str(exc_info.value)
```

### Testing Output Plugins

```python
import pytest
from inkwell.plugins.testing import MockCostTracker
from inkwell.extraction.models import ExtractionResult

class TestHTMLOutput:
    @pytest.fixture
    def output_plugin(self):
        plugin = HTMLOutput()
        plugin.configure({})
        return plugin

    @pytest.fixture
    def mock_result(self):
        return ExtractionResult(
            template_name="summary",
            content="# Summary\n\nThis is a test summary.",
            cost=0.001,
            provider="test",
        )

    @pytest.fixture
    def mock_metadata(self):
        return {
            "podcast_name": "Test Podcast",
            "episode_title": "Test Episode",
        }

    @pytest.mark.asyncio
    async def test_render_html(self, output_plugin, mock_result, mock_metadata):
        html = await output_plugin.render(mock_result, mock_metadata)

        assert "<!DOCTYPE html>" in html
        assert "<title>Test Episode</title>" in html
        assert "Test Podcast" in html

    def test_file_extension(self, output_plugin):
        assert output_plugin.file_extension == ".html"

    def test_output_format(self, output_plugin):
        assert output_plugin.output_format == "HTML"

    def test_get_filename(self, output_plugin):
        filename = output_plugin.get_filename("summary")
        assert filename == "summary.html"
```

---

## Testing Validation

```python
import pytest
from inkwell.plugins.base import PluginValidationError
from inkwell.plugins.testing import assert_plugin_valid

class TestPluginValidation:
    def test_missing_api_key(self):
        plugin = MyExtractor(lazy_init=True)
        plugin.configure({})  # No API key

        with pytest.raises(PluginValidationError) as exc_info:
            plugin.validate()

        assert "API_KEY" in str(exc_info.value)
        assert plugin.NAME in exc_info.value.plugin_name

    def test_valid_configuration(self, monkeypatch):
        monkeypatch.setenv("MY_API_KEY", "test-key")

        plugin = MyExtractor(lazy_init=True)
        plugin.configure({})

        # Should not raise
        assert_plugin_valid(plugin)

    def test_multiple_validation_errors(self):
        plugin = MyPlugin()
        plugin.configure({"invalid_model": True, "invalid_device": True})

        with pytest.raises(PluginValidationError) as exc_info:
            plugin.validate()

        # Check all errors are reported
        assert len(exc_info.value.errors) >= 2
```

---

## pytest Configuration

Add to your `pyproject.toml`:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "pytest-mock>=3.12.0",
]
```

---

## Best Practices

### 1. Use Fixtures

```python
@pytest.fixture
def configured_plugin():
    """Pre-configured plugin for tests."""
    plugin = MyPlugin(lazy_init=True)
    plugin.configure({"model": "test"}, cost_tracker=MockCostTracker())
    return plugin
```

### 2. Mock External APIs

```python
@pytest.fixture
def mock_api_response():
    with patch("openai.AsyncOpenAI") as mock:
        mock.return_value.chat.completions.create = AsyncMock(
            return_value=MagicMock(
                choices=[MagicMock(message=MagicMock(content="response"))]
            )
        )
        yield mock
```

### 3. Test Error Cases

```python
def test_handles_api_error(configured_plugin):
    with patch.object(configured_plugin._client, "create", side_effect=APIError("Rate limited")):
        with pytest.raises(APIError):
            await configured_plugin.extract(...)
```

### 4. Use Markers for Slow Tests

```python
@pytest.mark.slow
def test_large_file_transcription():
    # This test takes a while
    ...
```

---

## Next Steps

- [Publishing to PyPI](publishing.md) - Package and distribute your plugin
