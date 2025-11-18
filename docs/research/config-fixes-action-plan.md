# Configuration Fixes - Action Plan

**Date:** 2025-01-18
**Related Research:** [Configuration Management Best Practices](./configuration-management-best-practices.md)

## Quick Summary

This is the actionable implementation guide based on the comprehensive research. Use this for quick reference when fixing configuration bugs.

---

## The Three Core Problems

### Problem 1: Inconsistent Environment Variable Names
**Current State:**
- `GOOGLE_API_KEY` used in some places
- `GEMINI_API_KEY` used in others
- Users confused about which to use

**Solution:** Use Pydantic `AliasChoices`

```python
from pydantic import Field, AliasChoices

gemini_api_key: SecretStr = Field(
    validation_alias=AliasChoices(
        'GEMINI_API_KEY',    # NEW (preferred)
        'GOOGLE_API_KEY',     # OLD (support for migration)
    )
)
```

### Problem 2: Hardcoded Defaults Override User Config
**Current State:**
```python
def __init__(self, output_dir: Path | None = None):
    if output_dir is None:
        output_dir = Path("~/default")  # BAD: Can't tell if user set None
```

**Solution:** Sentinel values (httpx pattern)

```python
class UnsetType:
    pass

UNSET = UnsetType()

def __init__(self, output_dir: Path | None | UnsetType = UNSET):
    if output_dir is UNSET:
        output_dir = Path("~/default")  # User didn't provide
    elif output_dir is None:
        # User explicitly set None - honor it
        pass
    else:
        # User provided path - use it
        pass
```

### Problem 3: Config Not Passed Through Service Layers
**Current State:**
- Services create their own config
- Can't override for testing
- Config scattered throughout codebase

**Solution:** Constructor injection

```python
# Service receives config, doesn't create it
class TranscriptionService:
    def __init__(self, config: TranscriptionConfig):
        self.config = config
        self.api_key = config.get_gemini_key()

# In CLI or orchestrator
config = TranscriptionConfig()
service = TranscriptionService(config=config)
```

---

## Implementation Priority

### P0: Critical Fixes (Do First)

1. **Fix Environment Variable Names**
   - Files: `src/inkwell/config/schema.py`, `src/inkwell/utils/api_keys.py`
   - Add `AliasChoices` for API keys
   - Add deprecation warnings

2. **Add Sentinel Values**
   - Files: `src/inkwell/config/defaults.py` (create if needed)
   - Create `UnsetType` and `UNSET`
   - Update service constructors

3. **Fix Config Passing**
   - Files: All service files (`transcription/manager.py`, `extraction/engine.py`, etc.)
   - Add config parameter to `__init__`
   - Remove internal config creation

### P1: Important Improvements

4. **Add Config Tests**
   - Files: `tests/unit/test_config_*.py`
   - Test env var loading
   - Test precedence
   - Test validation

5. **Improve API Key Validation**
   - Files: `src/inkwell/utils/api_keys.py`
   - Move validation to Pydantic validators
   - Use `SecretStr` type

### P2: Nice to Have

6. **Add Dependency Injection**
   - Consider if app grows larger
   - Use `python-dependency-injector`

---

## Code Templates

### 1. Pydantic Settings with Environment Variables

```python
from pydantic import Field, SecretStr, AliasChoices
from pydantic_settings import BaseSettings, SettingsConfigDict

class APIConfig(BaseSettings):
    """API configuration with proper env var support."""

    model_config = SettingsConfigDict(
        env_prefix='INKWELL_',
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False,
        extra='ignore',
    )

    # Support both old and new env var names
    gemini_api_key: SecretStr = Field(
        validation_alias=AliasChoices('GEMINI_API_KEY', 'GOOGLE_API_KEY'),
        description="Gemini API key (GOOGLE_API_KEY deprecated)"
    )

    claude_api_key: SecretStr = Field(
        validation_alias=AliasChoices('CLAUDE_API_KEY', 'ANTHROPIC_API_KEY'),
        description="Claude API key"
    )

    @field_validator('gemini_api_key', mode='after')
    @classmethod
    def warn_old_gemini_key(cls, v: SecretStr) -> SecretStr:
        """Warn if using deprecated GOOGLE_API_KEY."""
        import os
        import warnings

        if 'GOOGLE_API_KEY' in os.environ and 'GEMINI_API_KEY' not in os.environ:
            warnings.warn(
                "GOOGLE_API_KEY is deprecated. Use GEMINI_API_KEY instead. "
                "Support will be removed in v2.0.",
                DeprecationWarning,
                stacklevel=2
            )
        return v

    def get_gemini_key(self) -> str:
        """Get Gemini API key as string."""
        return self.gemini_api_key.get_secret_value()

    def get_claude_key(self) -> str:
        """Get Claude API key as string."""
        return self.claude_api_key.get_secret_value()
```

### 2. Sentinel Values for Optional Config

```python
# config/sentinel.py
from typing import TypeVar

class UnsetType:
    """Sentinel type for unset optional values."""

    def __repr__(self) -> str:
        return "UNSET"

UNSET = UnsetType()

T = TypeVar('T')
Unset = UnsetType | T  # Type alias: Unset[str] means str | UnsetType

# Usage in service
from config.sentinel import UNSET, Unset

class TranscriptionService:
    def __init__(
        self,
        config: TranscriptionConfig,
        model_name: Unset[str] = UNSET,
        cache_dir: Unset[Path | None] = UNSET,
    ):
        self.config = config

        # Handle sentinel vs None vs value
        if model_name is UNSET:
            self.model_name = config.default_model
        else:
            self.model_name = model_name

        if cache_dir is UNSET:
            self.cache_dir = config.default_cache_dir
        elif cache_dir is None:
            self.cache_dir = None  # User explicitly disabled caching
        else:
            self.cache_dir = cache_dir
```

### 3. Service Constructor Injection

```python
# Before (BAD)
class TranscriptionService:
    def __init__(self):
        # Creates own config - can't override for testing!
        self.api_key = os.environ.get("GOOGLE_API_KEY")
        self.model = "gemini-2.0-flash-exp"

# After (GOOD)
class TranscriptionService:
    def __init__(self, config: TranscriptionConfig):
        # Receives config via constructor
        self.config = config
        self.api_key = config.get_gemini_key()
        self.model = config.model_name

# Usage in CLI
@app.command()
def process(url: str):
    config = TranscriptionConfig()  # Loads from env vars
    service = TranscriptionService(config=config)
    service.transcribe(url)

# Testing
def test_transcription(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-12345678901234567890")
    config = TranscriptionConfig()

    # Can inject test config
    service = TranscriptionService(config=config)
    assert service.api_key == "test-key-12345678901234567890"
```

### 4. Testing with Monkeypatch

```python
# conftest.py
import pytest
from pathlib import Path

@pytest.fixture
def mock_api_keys(monkeypatch):
    """Set mock API keys for testing."""
    monkeypatch.setenv("GEMINI_API_KEY", "AIza-test-key-12345678901234567890")
    monkeypatch.setenv("CLAUDE_API_KEY", "sk-ant-test-key-12345678901234567890")

@pytest.fixture
def test_config(tmp_path: Path, mock_api_keys) -> TranscriptionConfig:
    """Provide test configuration."""
    return TranscriptionConfig(
        cache_dir=tmp_path / "cache",
        output_dir=tmp_path / "output",
    )

# test_transcription.py
def test_service_creation(test_config):
    """Test service with test configuration."""
    service = TranscriptionService(config=test_config)
    assert service.config.cache_dir.exists()

def test_env_var_precedence(monkeypatch):
    """Test that env vars override defaults."""
    monkeypatch.setenv("INKWELL_TRANSCRIPTION_MODEL", "gemini-1.5-pro")

    config = TranscriptionConfig()
    assert config.model_name == "gemini-1.5-pro"
```

---

## File-by-File Changes

### `src/inkwell/config/schema.py`

**Changes:**
1. Add Pydantic Settings config
2. Add `AliasChoices` for API keys
3. Add deprecation validators
4. Add getter methods for SecretStr fields

**Example:**
```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class GlobalConfig(BaseSettings):
    """Global Inkwell configuration."""

    model_config = SettingsConfigDict(
        env_prefix='INKWELL_',
        env_file='.env',
        case_sensitive=False,
    )

    # ... rest of fields
```

### `src/inkwell/utils/api_keys.py`

**Changes:**
1. Move validation to Pydantic validators (in schema.py)
2. Keep this for backward compatibility or remove
3. Add migration guide in docstring

### `src/inkwell/transcription/manager.py`

**Changes:**
1. Add `config: TranscriptionConfig` parameter to `__init__`
2. Remove `os.environ.get()` calls
3. Use `config.get_gemini_key()` instead

**Before:**
```python
def __init__(self):
    self.api_key = os.environ.get("GOOGLE_API_KEY")
```

**After:**
```python
def __init__(self, config: TranscriptionConfig):
    self.config = config
    self.api_key = config.get_gemini_key()
```

### `src/inkwell/extraction/extractors/gemini.py`

**Changes:**
Same as transcription/manager.py - inject config

### `src/inkwell/cli.py`

**Changes:**
1. Create config once at top level
2. Pass to all services
3. Handle config loading errors gracefully

**Pattern:**
```python
@app.command()
def process(url: str):
    try:
        config = GlobalConfig()
    except ValidationError as e:
        console.print(f"[red]Configuration error:[/red] {e}")
        raise typer.Exit(1)

    # Pass config to services
    transcription_service = TranscriptionService(config=config.transcription)
    extraction_service = ExtractionService(config=config.extraction)
```

---

## Testing Checklist

After making changes, verify:

- [ ] Tests pass with `GEMINI_API_KEY`
- [ ] Tests pass with `GOOGLE_API_KEY` (backward compat)
- [ ] Deprecation warning shows for old env var names
- [ ] Missing API key shows clear error message
- [ ] Invalid API key format caught early
- [ ] User config overrides defaults (not vice versa)
- [ ] Services can be tested with mock config
- [ ] No hardcoded API keys in code
- [ ] `.env.example` file updated

---

## Migration Guide for Users

Create this in your README or docs:

```markdown
## Environment Variable Changes (v1.x → v2.0)

We've standardized environment variable names for clarity.

### What Changed

| Old Name (v1.x)        | New Name (v2.0+)       | Status      |
|------------------------|------------------------|-------------|
| `GOOGLE_API_KEY`       | `GEMINI_API_KEY`       | Deprecated  |
| `ANTHROPIC_API_KEY`    | `CLAUDE_API_KEY`       | Deprecated  |

### Migration Steps

1. Update your `.env` file:
   ```bash
   # Old
   GOOGLE_API_KEY=your-key-here
   ANTHROPIC_API_KEY=your-key-here

   # New
   GEMINI_API_KEY=your-key-here
   CLAUDE_API_KEY=your-key-here
   ```

2. Both names work in v1.x (with deprecation warnings)
3. Old names will be removed in v2.0

### Timeline

- **v1.5+**: Deprecation warnings added
- **v1.9**: Loud warnings (error-like)
- **v2.0**: Old names no longer supported
```

---

## Quick Wins (Do These First)

1. **Add `.env.example` file** to repo:
   ```bash
   # Inkwell Configuration
   # Copy to .env and fill in your values

   # Required: Gemini API key for transcription
   GEMINI_API_KEY=your-gemini-api-key-here

   # Required: Claude API key for interviews
   CLAUDE_API_KEY=your-claude-api-key-here

   # Optional: Output directory
   INKWELL_OUTPUT_DIR=~/podcasts

   # Optional: Model selection
   INKWELL_TRANSCRIPTION_MODEL=gemini-2.0-flash-exp
   INKWELL_INTERVIEW_MODEL=claude-sonnet-4-5
   ```

2. **Update .gitignore** to ensure `.env` never committed:
   ```
   # Environment variables
   .env
   .env.local
   .env.*.local
   ```

3. **Add validation tests** to catch regression:
   ```python
   def test_config_loads_from_env(monkeypatch):
       """Ensure config loads from environment variables."""
       monkeypatch.setenv("GEMINI_API_KEY", "AIza-test-key-12345678901234567890")
       config = GlobalConfig()
       assert config.gemini_api_key is not None
   ```

---

## Next Steps

1. Review comprehensive research: [Configuration Management Best Practices](./configuration-management-best-practices.md)
2. Start with P0 fixes above
3. Create tests for each fix
4. Update documentation
5. Create ADR documenting the changes

## Questions?

Refer to:
- Full research document for detailed explanations
- Pydantic Settings docs: https://docs.pydantic.dev/latest/concepts/pydantic_settings/
- pytest monkeypatch: https://docs.pytest.org/en/stable/how-to/monkeypatch.html
