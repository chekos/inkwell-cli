# Plugin Configuration

Configure plugins via YAML config files, environment variables, and Pydantic schemas.

---

## Configuration Sources

Plugins receive configuration from multiple sources (in priority order):

1. **Environment variables** (highest priority)
2. **CLI flags** (`--extractor`, `--transcriber`)
3. **Config file** (`~/.config/inkwell/config.yaml`)
4. **Plugin defaults** (lowest priority)

---

## Config File Structure

Add plugin configuration under the `plugins:` key in `~/.config/inkwell/config.yaml`:

```yaml
# ~/.config/inkwell/config.yaml

# Global settings
log_level: INFO
default_output_dir: ~/inkwell-notes

# Plugin configuration
plugins:
  # Per-plugin settings
  whisper:
    enabled: true
    priority: 50  # Third-party default
    config:
      model: base
      device: cuda
      language: auto

  # Override built-in plugin settings
  claude:
    enabled: true
    priority: 100  # Built-in default
    config:
      # API key via environment variable (recommended)
      # api_key: sk-...  # Or hardcode (not recommended)

  # Disable a built-in plugin
  youtube:
    enabled: false
```

### Plugin Config Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | `bool` | `true` | Whether plugin is active |
| `priority` | `int` | `100` | Selection priority (higher = preferred) |
| `config` | `dict` | `{}` | Plugin-specific settings |

### Priority Ranges

| Range | Use Case | Example |
|-------|----------|---------|
| 150 | User override (always use this) | Custom preferred plugin |
| 100 | Built-in plugins | claude, gemini, youtube |
| 50 | Third-party production | inkwell-whisper-plugin |
| 0 | Experimental | Community plugins |

---

## Environment Variable Overrides

Override plugin selection via environment variables:

```bash
# Force specific extractor
export INKWELL_EXTRACTOR=claude

# Force specific transcriber
export INKWELL_TRANSCRIBER=whisper

# Use with any command
inkwell fetch URL  # Uses overrides automatically
```

This is useful for:
- CI/CD pipelines
- Temporary testing
- Scripts that need consistent behavior

---

## Schema Validation with Pydantic

Define a `CONFIG_SCHEMA` for automatic validation:

```python
from pydantic import BaseModel, Field
from typing import Literal

class WhisperConfig(BaseModel):
    """Configuration schema for Whisper plugin."""

    model: Literal["tiny", "base", "small", "medium", "large"] = "base"
    device: Literal["cpu", "cuda"] = "cpu"
    language: str = "auto"
    compute_type: str = Field(
        default="float16",
        description="Computation type for GPU inference"
    )


class WhisperTranscriber(TranscriptionPlugin):
    NAME = "whisper"
    VERSION = "1.0.0"
    DESCRIPTION = "Local Whisper transcription"

    # Pydantic model for config validation
    CONFIG_SCHEMA = WhisperConfig

    def configure(self, config: dict, cost_tracker=None):
        super().configure(config, cost_tracker)

        # self.config is now a validated WhisperConfig instance
        print(f"Model: {self.config.model}")  # Type-safe access
```

### Benefits

- Automatic type validation
- Default values
- Clear documentation via type hints
- IDE autocomplete support
- Error messages with field names

### Validation Errors

If config validation fails, users see clear error messages:

```
$ inkwell plugins validate whisper

Plugin 'whisper' validation failed:
  - model: Input should be 'tiny', 'base', 'small', 'medium' or 'large', got 'invalid'
  - device: Input should be 'cpu' or 'cuda', got 'tpu'
```

---

## API Key Handling

### Recommended: Environment Variables

```python
class MyExtractor(ExtractionPlugin):
    def validate(self) -> None:
        import os
        if not os.environ.get("MY_API_KEY"):
            raise PluginValidationError(
                self.NAME,
                ["MY_API_KEY environment variable not set"]
            )
```

Users set the key:

```bash
export MY_API_KEY=sk-...
```

### Alternative: Config File

```yaml
# ~/.config/inkwell/config.yaml
plugins:
  my-extractor:
    config:
      api_key: sk-...  # Less secure, but convenient
```

### Using Inkwell's API Key Utilities

```python
from inkwell.utils.api_keys import get_validated_api_key, validate_api_key

class MyExtractor(ExtractionPlugin):
    def configure(self, config, cost_tracker=None):
        super().configure(config, cost_tracker)

        # Get API key from config or environment
        api_key = config.get("api_key")
        if api_key:
            self.api_key = validate_api_key(api_key, "my-provider", "MY_API_KEY")
        else:
            self.api_key = get_validated_api_key("MY_API_KEY", "my-provider")
```

---

## Accessing Configuration

### In Plugin Methods

```python
class MyPlugin(InkwellPlugin):
    CONFIG_SCHEMA = MyConfig  # Optional

    async def extract(self, template, transcript, metadata, **kwargs):
        # Access validated config
        model = self.config.model  # If CONFIG_SCHEMA defined
        # or
        model = self.config.get("model", "default")  # If dict

        # Check if initialized
        if not self.is_initialized:
            raise RuntimeError("Plugin not configured")
```

### Configuration Properties

| Property | Type | Description |
|----------|------|-------------|
| `self.config` | `BaseModel \| dict` | Validated configuration |
| `self.is_initialized` | `bool` | Whether configure() was called |
| `self.cost_tracker` | `CostTracker \| None` | Cost tracking service |

---

## Dynamic Configuration

Some plugins need configuration that changes at runtime:

```python
class DynamicPlugin(ExtractionPlugin):
    def __init__(self):
        super().__init__()
        self._runtime_model = None

    def configure(self, config, cost_tracker=None):
        super().configure(config, cost_tracker)
        # Set initial model from config
        self._runtime_model = config.get("model", "default")

    def set_model(self, model_name: str):
        """Allow runtime model switching."""
        self._runtime_model = model_name

    async def extract(self, template, transcript, metadata, **kwargs):
        # Use runtime model (not just config)
        model = self._runtime_model
        # ...
```

---

## Configuration Examples

### Extraction Plugin Config

```yaml
plugins:
  claude:
    priority: 100
    config:
      # Model override (optional)
      model: claude-3-5-sonnet-20241022
      # Temperature override (optional)
      temperature: 0.1

  openai:
    enabled: true
    priority: 50
    config:
      model: gpt-4-turbo
      organization: org-xxx  # Optional org ID
```

### Transcription Plugin Config

```yaml
plugins:
  whisper:
    enabled: true
    priority: 150  # Prefer over built-ins
    config:
      model: medium
      device: cuda
      language: en
      compute_type: float16

  assemblyai:
    enabled: true
    priority: 50
    config:
      # API key via environment recommended
      speaker_labels: true
      punctuate: true
```

### Output Plugin Config

```yaml
plugins:
  markdown:
    priority: 100
    config:
      include_frontmatter: true
      frontmatter_format: yaml

  notion:
    enabled: true
    priority: 50
    config:
      database_id: abc123
      # API key via NOTION_API_KEY env var
```

---

## Troubleshooting

### Config Not Applied

1. Check file location: `~/.config/inkwell/config.yaml`
2. Validate YAML syntax: `python -c "import yaml; yaml.safe_load(open('config.yaml'))"`
3. Check plugin name matches exactly
4. Verify `enabled: true` is set

### Validation Errors

```bash
# See detailed validation errors
inkwell plugins validate my-plugin
```

### Priority Not Working

```bash
# List plugins with priorities
inkwell plugins list

# Force specific plugin (ignores priority)
inkwell fetch URL --extractor claude
```

---

## Next Steps

- [Testing Plugins](testing.md) - Test utilities and mocks
- [Publishing to PyPI](publishing.md) - Package and distribute
