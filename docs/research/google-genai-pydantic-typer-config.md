# Google Generative AI, Pydantic Settings, and Typer Configuration Research

**Research Date:** 2025-11-18
**Research Context:** Fixing configuration bugs where hardcoded model names don't exist, config not passing from CLI to services, and inconsistent environment variable naming.

## Executive Summary

This research covers three critical areas for fixing configuration issues in Inkwell:

1. **Google Generative AI SDK**: Currently using deprecated SDK (`google-generativeai==0.8.5`), model naming conventions, and environment variable handling
2. **Pydantic Settings**: Best practices for dependency injection, environment variable management, and field validation
3. **Typer CLI Framework**: Context passing and shared configuration patterns across command groups

## 1. Google Generative AI Python SDK

### Current Installation

```bash
# From uv pip list
google-generativeai          0.8.5
```

**Status:** Using the **deprecated SDK**. Google recommends migrating to the new `google-genai` SDK.

### Available Models (2025)

The current Gemini model lineup:

| Model | Purpose | Status |
|-------|---------|--------|
| `gemini-3-pro` | Best for multimodal understanding with advanced reasoning | Latest |
| `gemini-2.5-pro` | State-of-the-art thinking model | Current |
| `gemini-2.5-flash` | Best price-performance for large-scale processing | **Recommended** |
| `gemini-2.5-flash-lite` | Fastest, optimized for cost-efficiency | Current |
| `gemini-2.0-flash` | Previous generation | Available |
| `gemini-2.0-flash-lite` | Previous generation | Available |

### Model Naming Conventions

Models follow these version patterns:

- **Stable**: `gemini-2.5-flash` - Points to specific stable models
- **Preview**: `gemini-2.5-flash-preview-09-2025` - May be used for production with billing
- **Latest**: `gemini-2.5-flash-latest` - Auto-updates with 2-week notice (risky for production)
- **Experimental**: Not suitable for production, restrictive rate limits

**IMPORTANT:** `gemini-1.5-flash` is still available but **replaced by `gemini-2.5-flash`** as the recommended fast, cost-effective model.

### Environment Variable Configuration

The SDK supports **TWO** environment variable names:

1. `GOOGLE_API_KEY` (primary, takes precedence)
2. `GEMINI_API_KEY` (secondary fallback)

**Best Practice:** Use `GOOGLE_API_KEY` for consistency across Google services.

### Configuration Examples (Current Deprecated SDK)

```python
# Method 1: Environment variable (automatic)
import google.generativeai as genai
import os

genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
model = genai.GenerativeModel('gemini-2.5-flash')
```

```python
# Method 2: Explicit API key
import google.generativeai as genai

genai.configure(api_key="your-api-key-here")
model = genai.GenerativeModel('gemini-2.5-flash')
```

```python
# Method 3: Auto-detection (GOOGLE_API_KEY env var)
import google.generativeai as genai

# If GOOGLE_API_KEY is set, no explicit configure needed
genai.configure()  # Auto-picks from environment
model = genai.GenerativeModel('gemini-2.5-flash')
```

### Migration to New SDK (Future Consideration)

The new `google-genai` SDK uses a different pattern:

```python
# New SDK pattern (NOT currently used by Inkwell)
from google import genai

client = genai.Client()  # Auto-uses GOOGLE_API_KEY or GEMINI_API_KEY
response = client.models.generate_content(
    model='gemini-2.5-flash',
    contents=...
)
```

**Migration Note:** Don't migrate during bug fix. Address in separate refactoring effort.

### Documentation Links

- **Official Models Documentation**: https://ai.google.dev/gemini-api/docs/models
- **API Key Setup**: https://ai.google.dev/gemini-api/docs/api-key
- **Migration Guide**: https://ai.google.dev/gemini-api/docs/migrate
- **New SDK GitHub**: https://github.com/googleapis/python-genai

## 2. Pydantic Settings for Configuration Management

### Installation

```toml
# From pyproject.toml
pydantic>=2.0.0
pydantic-settings>=2.0.0
```

### Core Pattern: BaseSettings

```python
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

class AppSettings(BaseSettings):
    """Application configuration from environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="INKWELL_",  # All env vars start with INKWELL_
        case_sensitive=False,    # Windows compatibility
        env_file=".env",         # Load from .env file
        env_file_encoding="utf-8",
        extra="ignore"           # Ignore unknown env vars
    )

    # API Keys
    google_api_key: str  # Reads INKWELL_GOOGLE_API_KEY
    anthropic_api_key: str  # Reads INKWELL_ANTHROPIC_API_KEY

    # Model Configuration
    transcription_model: str = "gemini-2.5-flash"
    interview_model: str = "claude-sonnet-4-5"

    # Paths
    output_dir: Path = Path("~/inkwell-notes")

    # Feature Flags
    youtube_check: bool = True
    log_level: str = "INFO"
```

### Field Validation and Defaults

**Key Insight:** Settings validates default values by default (unlike BaseModel).

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        validate_default=False  # Disable default validation
    )

    # This would fail validation if validate_default=True
    foo: int = 'test'
```

**Best Practice:** Keep `validate_default=True` (default) for type safety, even with defaults.

### Environment Variable Management

#### Using env_prefix

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="APP_")

    database_url: str  # Reads APP_DATABASE_URL
    api_key: str       # Reads APP_API_KEY
```

**IMPORTANT:** `env_prefix` does NOT apply to fields with explicit `alias`:

```python
from pydantic import Field

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="APP_")

    # Uses CUSTOM_KEY, NOT APP_CUSTOM_KEY
    key: str = Field(alias="CUSTOM_KEY")
```

#### Nested Configuration with Delimiter

```python
class DatabaseConfig(BaseModel):
    host: str
    port: int = 5432

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_nested_delimiter="__")

    db: DatabaseConfig  # Reads DB__HOST, DB__PORT
```

### Dependency Injection Pattern

**FastAPI-style (recommended for services):**

```python
from functools import lru_cache
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    api_key: str
    model_name: str = "gemini-2.5-flash"

@lru_cache
def get_settings() -> Settings:
    """Cached settings instance."""
    return Settings()

# Service injection
class TranscriptionService:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.model_name = self.settings.model_name
```

**Constructor Injection (for Inkwell pattern):**

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    google_api_key: str
    transcription_model: str = "gemini-2.5-flash"

class GeminiTranscriber:
    def __init__(self, settings: Settings):
        """Inject settings at construction."""
        self.api_key = settings.google_api_key
        self.model_name = settings.transcription_model

        import google.generativeai as genai
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel(self.model_name)
```

### Settings Priority (Highest to Lowest)

1. CLI arguments (explicit overrides)
2. Environment variables
3. `.env` files
4. Secrets files
5. Init kwargs (constructor defaults)

Customize via `settings_customise_sources` classmethod.

### Complex Type Parsing

**Lists and Dicts:**

```python
class Settings(BaseSettings):
    # JSON parsing (default)
    tags: list[str]  # Set as: TAGS='["tag1", "tag2"]'

    # Or use delimiter for simple lists
    model_config = SettingsConfigDict(env_delimiter=",")
    tags: list[str]  # Set as: TAGS=tag1,tag2,tag3
```

### Documentation Links

- **Official Settings Documentation**: https://docs.pydantic.dev/latest/concepts/pydantic_settings/
- **FastAPI Settings Integration**: https://pythonic.blog/2025/02/14/pydantic-series-settings-in-a-fastapi-app/

## 3. Typer CLI Framework Context and Configuration

### Installation

```toml
# From pyproject.toml
typer[all]>=0.12.0
```

### Context Passing Pattern

Typer's `Context` object accesses Click's execution context:

```python
import typer

app = typer.Typer()

@app.callback()
def main(ctx: typer.Context):
    """Main callback with context."""
    print(f"About to execute: {ctx.invoked_subcommand}")
    print(f"Extra args: {ctx.args}")
```

**What Context Provides:**

- `ctx.invoked_subcommand`: Name of the command being executed
- `ctx.args`: Extra CLI arguments (when `allow_extra_args=True`)
- `ctx.obj`: Custom object for storing shared data

**Limitation:** Context is primarily for **inspecting execution flow**, not designed for rich dependency injection.

### Callback Pattern for Shared Configuration

The **recommended pattern** for sharing configuration across commands:

```python
import typer
from typing import Optional

app = typer.Typer()

# Shared state (could be Settings object)
class State:
    def __init__(self):
        self.verbose: bool = False
        self.config: Optional[AppSettings] = None

state = State()

@app.callback()
def main(
    ctx: typer.Context,
    verbose: bool = typer.Option(False, "--verbose", "-v"),
    config_file: Optional[Path] = typer.Option(None, "--config"),
):
    """
    Main callback - runs before any command.

    Sets up shared configuration for all subcommands.
    """
    # Store in module-level state
    state.verbose = verbose

    # Load configuration
    if config_file:
        state.config = load_config(config_file)
    else:
        state.config = AppSettings()  # Load from env vars

    # Or store in Context.obj
    ctx.obj = state

@app.command()
def transcribe(
    ctx: typer.Context,
    url: str,
):
    """Transcribe command using shared config."""
    # Access shared state
    config = ctx.obj.config  # or use module-level state

    # Create service with config
    transcriber = GeminiTranscriber(settings=config)
    result = transcriber.transcribe(url)
```

### Pattern 1: Module-Level State (Simple)

```python
# globals.py
from pydantic_settings import BaseSettings

class AppState:
    settings: BaseSettings | None = None
    verbose: bool = False

state = AppState()

# cli.py
import typer
from .globals import state
from .config import Settings

app = typer.Typer()

@app.callback()
def main(verbose: bool = False):
    state.verbose = verbose
    state.settings = Settings()

@app.command()
def transcribe(url: str):
    # Access shared state
    settings = state.settings
    transcriber = create_transcriber(settings)
```

**Pros:** Simple, easy to test, explicit
**Cons:** Global state (but acceptable for CLI tools)

### Pattern 2: Context Object (Recommended)

```python
import typer
from typing import Any

app = typer.Typer()

class AppContext:
    def __init__(self, settings: Settings, verbose: bool = False):
        self.settings = settings
        self.verbose = verbose

@app.callback()
def main(
    ctx: typer.Context,
    verbose: bool = False,
):
    # Create and store context
    settings = Settings()
    ctx.obj = AppContext(settings=settings, verbose=verbose)

@app.command()
def transcribe(
    ctx: typer.Context,
    url: str,
):
    # Access context
    app_ctx: AppContext = ctx.obj
    transcriber = GeminiTranscriber(settings=app_ctx.settings)
```

**Pros:** Typer-native, testable, explicit passing
**Cons:** Need to access `ctx.obj` in every command

### Pattern 3: Dependency Injection via typer-builder (Advanced)

For complex CLIs, use `typer-builder` package:

```bash
uv add typer-builder
```

```python
from typer_builder import Dependencies

deps = Dependencies()

# Register dependencies
deps.register(Settings, factory=lambda: Settings())

@deps.bind()
def transcribe(url: str, settings: Settings):
    """Settings auto-injected by type hint."""
    transcriber = GeminiTranscriber(settings=settings)
```

**Pros:** True dependency injection, clean commands
**Cons:** Additional dependency, more complex setup

### Recommendation for Inkwell

Use **Pattern 2 (Context Object)** because:

1. Native Typer pattern
2. Explicit, testable
3. No additional dependencies
4. Follows Typer documentation conventions

### Implementation Example

```python
# src/inkwell/cli.py
import typer
from pathlib import Path
from .config.schema import GlobalConfig
from .config.manager import ConfigManager

app = typer.Typer()

class InkwellContext:
    """Shared context for all commands."""
    def __init__(self, config: GlobalConfig, verbose: bool = False):
        self.config = config
        self.verbose = verbose

@app.callback()
def main(
    ctx: typer.Context,
    verbose: bool = typer.Option(False, "--verbose", "-v"),
    config_file: Path | None = typer.Option(None, "--config"),
):
    """Initialize Inkwell CLI with shared configuration."""
    # Load configuration
    manager = ConfigManager()
    config = manager.load_config()

    # Override with CLI options
    if verbose:
        config.log_level = "DEBUG"

    # Store in context
    ctx.obj = InkwellContext(config=config, verbose=verbose)

@app.command()
def transcribe(
    ctx: typer.Context,
    url: str,
):
    """Transcribe using shared config."""
    app_ctx: InkwellContext = ctx.obj

    # Create manager with config
    from .transcription import TranscriptionManager
    manager = TranscriptionManager(
        model_name=app_ctx.config.transcription_model,
        api_key=os.getenv("GOOGLE_API_KEY"),  # Or from settings
    )

    result = manager.transcribe(url)
```

### Documentation Links

- **Typer Official Documentation**: https://typer.tiangolo.com/
- **Using Context Tutorial**: https://typer.tiangolo.com/tutorial/commands/context/
- **Callback Pattern**: https://typer.tiangolo.com/tutorial/commands/callback/
- **typer-builder (Advanced DI)**: https://github.com/NiklasRosenstein/python-typer-builder

## Recommendations for Fixing Inkwell Bugs

### Issue 1: Hardcoded `gemini-1.5-flash` Model Name

**Current Code:**
```python
# src/inkwell/transcription/gemini.py
model_name: str = "gemini-1.5-flash"

# src/inkwell/extraction/extractors/gemini.py
MODEL = "gemini-1.5-flash-latest"
```

**Fix:**
1. Update to `gemini-2.5-flash` (stable) or `gemini-2.0-flash-exp` (experimental)
2. Make model name configurable via `GlobalConfig.transcription_model`
3. Pass from config instead of hardcoding

**Implementation:**
```python
# src/inkwell/config/schema.py
class GlobalConfig(BaseModel):
    transcription_model: str = "gemini-2.5-flash"  # Updated default
    extraction_model: str = "gemini-2.5-flash"     # For extraction

# src/inkwell/transcription/gemini.py
class GeminiTranscriber:
    def __init__(
        self,
        api_key: str | None = None,
        model_name: str | None = None,  # Accept from config
    ):
        self.model_name = model_name or "gemini-2.5-flash"
        # ... rest of init
```

### Issue 2: Config Not Passed from CLI to Services

**Problem:** Services create their own instances instead of receiving config.

**Fix:** Use Constructor Injection pattern:

```python
# Before (BAD)
class TranscriptionManager:
    def __init__(self):
        self.api_key = os.getenv("GOOGLE_API_KEY")
        self.model_name = "gemini-1.5-flash"  # Hardcoded!

# After (GOOD)
class TranscriptionManager:
    def __init__(
        self,
        api_key: str | None = None,
        model_name: str | None = None,
        settings: GlobalConfig | None = None,
    ):
        if settings:
            self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
            self.model_name = model_name or settings.transcription_model
        else:
            self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
            self.model_name = model_name or "gemini-2.5-flash"
```

**CLI Integration:**
```python
# src/inkwell/cli.py
@app.command()
def transcribe(
    ctx: typer.Context,
    url: str,
):
    config: GlobalConfig = ctx.obj.config

    manager = TranscriptionManager(
        model_name=config.transcription_model,
        # api_key will be read from env by manager
    )
```

### Issue 3: Inconsistent Environment Variable Names

**Current Issues:**
- Code uses both `GOOGLE_API_KEY` and `GOOGLE_AI_API_KEY`
- Gemini SDK supports `GOOGLE_API_KEY` or `GEMINI_API_KEY`

**Fix:** Standardize on `GOOGLE_API_KEY`:

```python
# src/inkwell/transcription/gemini.py (BEFORE)
self.api_key = api_key or os.getenv("GOOGLE_AI_API_KEY")  # WRONG!

# src/inkwell/transcription/gemini.py (AFTER)
self.api_key = api_key or os.getenv("GOOGLE_API_KEY")  # CORRECT

# src/inkwell/extraction/extractors/gemini.py
# Use get_validated_api_key("GOOGLE_API_KEY", "gemini")
```

**Documentation Update:**
```markdown
# Required Environment Variables

- `GOOGLE_API_KEY`: Google AI/Gemini API key for transcription and extraction
- `ANTHROPIC_API_KEY`: Anthropic Claude API key for interview mode

# Optional: Alternative names
- `GEMINI_API_KEY`: Alternative to GOOGLE_API_KEY (lower priority)
```

### Issue 4: Settings Injection Pattern

**Use Pydantic Settings for Environment Variables:**

```python
# src/inkwell/config/settings.py (NEW FILE)
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

class InkwellSettings(BaseSettings):
    """Environment-based settings for Inkwell."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # API Keys
    google_api_key: str | None = None  # Optional, validated later
    anthropic_api_key: str | None = None

    # Model Names (with defaults from config)
    transcription_model: str = "gemini-2.5-flash"
    extraction_model: str = "gemini-2.5-flash"
    interview_model: str = "claude-sonnet-4-5"
```

**Integration with GlobalConfig:**

```python
# src/inkwell/config/manager.py
from .settings import InkwellSettings
from .schema import GlobalConfig

class ConfigManager:
    def load_config(self) -> GlobalConfig:
        """Load config, merging with environment variables."""
        # Load from YAML
        yaml_config = self._load_yaml()

        # Load from environment
        env_settings = InkwellSettings()

        # Merge: env vars override YAML
        if env_settings.transcription_model:
            yaml_config.transcription_model = env_settings.transcription_model

        return yaml_config
```

## Implementation Checklist

- [ ] Update hardcoded model names to `gemini-2.5-flash`
- [ ] Standardize on `GOOGLE_API_KEY` environment variable
- [ ] Implement Typer Context pattern for config passing
- [ ] Update `GlobalConfig` with correct model defaults
- [ ] Add Settings class for environment variables
- [ ] Inject config into service constructors
- [ ] Update documentation with correct env var names
- [ ] Add validation for API keys at startup
- [ ] Test config override precedence (env > config > defaults)

## Testing Strategy

```python
# tests/test_config.py
import os
import pytest
from inkwell.config.settings import InkwellSettings

def test_google_api_key_from_env(monkeypatch):
    """Test GOOGLE_API_KEY is read from environment."""
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key-123")
    settings = InkwellSettings()
    assert settings.google_api_key == "test-key-123"

def test_model_defaults():
    """Test default model names."""
    settings = InkwellSettings()
    assert settings.transcription_model == "gemini-2.5-flash"
    assert settings.extraction_model == "gemini-2.5-flash"

def test_config_injection():
    """Test config is passed to services."""
    from inkwell.config.schema import GlobalConfig
    config = GlobalConfig(transcription_model="gemini-2.0-flash")

    from inkwell.transcription import TranscriptionManager
    manager = TranscriptionManager(model_name=config.transcription_model)

    assert manager.model_name == "gemini-2.0-flash"
```

## References

### Google Generative AI
- Official Models: https://ai.google.dev/gemini-api/docs/models
- API Keys: https://ai.google.dev/gemini-api/docs/api-key
- Migration Guide: https://ai.google.dev/gemini-api/docs/migrate
- PyPI Package: https://pypi.org/project/google-generativeai/

### Pydantic Settings
- Official Docs: https://docs.pydantic.dev/latest/concepts/pydantic_settings/
- FastAPI Integration: https://pythonic.blog/2025/02/14/pydantic-series-settings-in-a-fastapi-app/

### Typer
- Official Docs: https://typer.tiangolo.com/
- Context Tutorial: https://typer.tiangolo.com/tutorial/commands/context/
- Callbacks: https://typer.tiangolo.com/tutorial/commands/callback/
- Advanced DI: https://github.com/NiklasRosenstein/python-typer-builder

## Next Steps

1. Create ADR for config injection pattern
2. Implement fixes in order: env vars → model names → config passing
3. Add integration tests for config flow
4. Update user documentation
5. Consider migration to new `google-genai` SDK in future (separate effort)
