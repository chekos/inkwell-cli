# Plugin Lifecycle

Understanding the plugin lifecycle hooks: configure, validate, and cleanup.

---

## Lifecycle Overview

```
┌───────────────┐    ┌────────────┐    ┌─────────┐    ┌─────────┐
│  configure()  │───▶│ validate() │───▶│  use()  │───▶│cleanup()│
└───────────────┘    └────────────┘    └─────────┘    └─────────┘
       │                   │               │              │
  Receive config      Check state      Plugin is      Release
  and services        is valid         active         resources
```

All plugins inherit these lifecycle methods from `InkwellPlugin`:

| Method | When Called | Purpose |
|--------|-------------|---------|
| `__init__()` | Plugin instantiation | Basic setup only |
| `configure()` | After discovery | Receive config and services |
| `validate()` | Before first use | Verify plugin is ready |
| `cleanup()` | Shutdown | Release resources |

---

## configure()

Called immediately after plugin instantiation with configuration and services.

### Signature

```python
def configure(
    self,
    config: dict[str, Any],
    cost_tracker: CostTracker | None = None,
) -> None:
```

### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `config` | `dict[str, Any]` | Plugin-specific configuration from `~/.config/inkwell/config.yaml` |
| `cost_tracker` | `CostTracker \| None` | Optional cost tracking service (direct dependency injection) |

### What Happens

1. If `CONFIG_SCHEMA` is defined, config is validated against it
2. Validated config stored in `self._config`
3. Cost tracker stored in `self._cost_tracker`
4. `self._initialized` set to `True`

### Example

```python
from pydantic import BaseModel

class WhisperConfig(BaseModel):
    model: str = "base"
    device: str = "cpu"
    language: str = "auto"

class WhisperTranscriber(TranscriptionPlugin):
    NAME = "whisper"
    VERSION = "1.0.0"
    DESCRIPTION = "Local Whisper transcription"

    # Define config schema for automatic validation
    CONFIG_SCHEMA = WhisperConfig

    def configure(self, config: dict[str, Any], cost_tracker=None):
        """Configure with Whisper-specific settings."""
        # Call parent to validate and store config
        super().configure(config, cost_tracker)

        # Now self.config is a validated WhisperConfig instance
        print(f"Using model: {self.config.model}")
        print(f"Device: {self.config.device}")

        # Initialize Whisper model with configured settings
        import whisper
        self._model = whisper.load_model(
            self.config.model,
            device=self.config.device,
        )
```

### Best Practices

- **Always call `super().configure()`** first
- Use `CONFIG_SCHEMA` for automatic Pydantic validation
- Initialize API clients and heavy resources here (not in `__init__`)
- Store the cost tracker for later use in tracking API calls

---

## validate()

Called after `configure()` but before the plugin is used. Raise `PluginValidationError` if the plugin cannot operate.

### Signature

```python
def validate(self) -> None:
    """Raise PluginValidationError if plugin state is invalid."""
```

### When to Raise Errors

- Required API keys not set
- Required binaries not found (ffmpeg, whisper, etc.)
- External service unreachable
- Configuration values out of bounds

### Example

```python
from inkwell.plugins.base import PluginValidationError
import os
import shutil

class WhisperTranscriber(TranscriptionPlugin):
    # ...

    def validate(self) -> None:
        """Verify Whisper is ready to use."""
        errors = []

        # Check whisper is installed
        try:
            import whisper  # noqa: F401
        except ImportError:
            errors.append(
                "openai-whisper not installed. Run: pip install openai-whisper"
            )

        # Check ffmpeg is available (required for audio processing)
        if not shutil.which("ffmpeg"):
            errors.append(
                "ffmpeg not found in PATH. Install via: brew install ffmpeg"
            )

        # Check CUDA if GPU mode requested
        if hasattr(self, '_config') and self.config.device == "cuda":
            try:
                import torch
                if not torch.cuda.is_available():
                    errors.append("CUDA requested but not available")
            except ImportError:
                errors.append("PyTorch not installed for CUDA support")

        # Raise all errors at once
        if errors:
            raise PluginValidationError(self.NAME, errors)
```

### PluginValidationError

```python
class PluginValidationError(Exception):
    """Raised when plugin configuration is invalid."""

    def __init__(self, plugin_name: str, errors: list[str]) -> None:
        self.plugin_name = plugin_name
        self.errors = errors
```

When validation fails, the plugin becomes a "BrokenPlugin" with error details and recovery hints shown in `inkwell plugins list`.

### Best Practices

- Collect all errors before raising (don't fail on first error)
- Provide actionable recovery hints in error messages
- Check both configuration AND runtime requirements
- Keep validation fast (avoid network calls if possible)

---

## cleanup()

Called when the plugin is no longer needed. Release resources like network connections, file handles, and background tasks.

### Signature

```python
def cleanup(self) -> None:
    """Release resources when plugin is no longer needed."""
```

### Example

```python
class OpenAIExtractor(ExtractionPlugin):
    # ...

    def __init__(self):
        super().__init__()
        self._client = None
        self._temp_files = []

    def configure(self, config, cost_tracker=None):
        super().configure(config, cost_tracker)
        from openai import AsyncOpenAI
        self._client = AsyncOpenAI()

    def cleanup(self) -> None:
        """Clean up OpenAI client and temp files."""
        # Close HTTP client
        if self._client:
            # AsyncOpenAI handles cleanup automatically
            self._client = None

        # Remove temporary files
        import os
        for path in self._temp_files:
            if os.path.exists(path):
                os.remove(path)
        self._temp_files.clear()
```

### When cleanup() is Called

- Application shutdown
- Plugin disabled via `inkwell plugins disable`
- Plugin replaced by another plugin
- Explicit cleanup request

### Best Practices

- Clean up ALL resources (connections, files, threads)
- Handle cleanup gracefully even if partially initialized
- Don't raise exceptions (log warnings instead)
- Reset state so plugin could theoretically be re-configured

---

## Accessing Configuration and Services

After `configure()`, access config and services via properties:

```python
class MyPlugin(InkwellPlugin):
    def some_method(self):
        # Access validated configuration
        api_key = self.config.get("api_key")

        # Or if using CONFIG_SCHEMA (Pydantic model)
        model_name = self.config.model

        # Access cost tracker for API usage tracking
        if self.cost_tracker:
            self.cost_tracker.add_cost(
                provider=self.NAME,
                model="my-model",
                operation="extraction",
                input_tokens=1000,
                output_tokens=500,
            )

        # Check if plugin is ready
        if not self.is_initialized:
            raise RuntimeError("Plugin not configured")
```

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `config` | `dict \| BaseModel` | Validated configuration |
| `cost_tracker` | `CostTracker \| None` | Cost tracking service |
| `is_initialized` | `bool` | Whether configure() was called |

---

## Lazy Initialization Pattern

For expensive resources, use lazy initialization to speed up plugin discovery:

```python
class HeavyPlugin(ExtractionPlugin):
    NAME = "heavy"

    def __init__(self, *, lazy_init: bool = False):
        super().__init__()
        self._model = None

        # Plugin discovery sets lazy_init=True
        if not lazy_init:
            self._init_model()

    def _init_model(self):
        """Initialize expensive model."""
        import torch
        self._model = torch.load("large_model.pt")

    def configure(self, config, cost_tracker=None):
        super().configure(config, cost_tracker)
        # Initialize model if not already done
        if self._model is None:
            self._init_model()

    @property
    def model(self):
        """Lazy-load model on first access."""
        if self._model is None:
            self._init_model()
        return self._model
```

This pattern allows:
- Fast plugin discovery (no model loading)
- Model loads only when plugin is actually used
- Backward compatibility with direct instantiation

---

## Async Considerations

All plugin methods (`extract()`, `transcribe()`, `render()`) are async. For sync operations, use `asyncio.to_thread()`:

```python
import asyncio

class WhisperTranscriber(TranscriptionPlugin):
    async def transcribe(self, request: TranscriptionRequest) -> Transcript:
        # Run CPU-intensive work in thread pool
        result = await asyncio.to_thread(
            self._transcribe_sync,
            request.file_path,
        )
        return Transcript(text=result["text"])

    def _transcribe_sync(self, file_path):
        """Sync transcription (runs in thread pool)."""
        import whisper
        model = whisper.load_model("base")
        return model.transcribe(str(file_path))
```

---

## Next Steps

- [Configuration](configuration.md) - Schema validation and config files
- [Testing Plugins](testing.md) - Mock services and test utilities
