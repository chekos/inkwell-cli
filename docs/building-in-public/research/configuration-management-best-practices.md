# Configuration Management Best Practices for Python CLI Applications

**Research Date:** 2025-01-18
**Context:** Fixing configuration bugs in Inkwell CLI where values aren't passed through properly, hardcoded defaults override user config, and inconsistent environment variable names exist.

## Executive Summary

This research synthesizes best practices from authoritative sources (official docs, well-known projects like httpx, langchain, openai-python) and current industry standards (2024-2025) for configuration management in Python CLI applications using Typer and Pydantic.

**Key Recommendations:**
1. Use `pydantic-settings` for all configuration management
2. Implement sentinel values (UNSET pattern) to distinguish "not provided" from "None"
3. Support multiple environment variable names using `AliasChoices` for migration
4. Use dependency injection patterns for passing config through service layers
5. Test config-dependent code with pytest's `monkeypatch` fixture

---

## 1. Configuration Management Architecture

### 1.1 The Pydantic Settings Pattern (MUST HAVE)

**Source:** Official Pydantic documentation, LangChain, PydanticAI projects

Pydantic Settings (via `pydantic-settings`) is the industry standard for Python configuration management in 2024-2025.

**Why Use It:**
- Type-safe configuration with automatic validation
- Built-in support for environment variables
- Excellent error messages when validation fails
- IDE autocompletion support
- Seamless integration with Typer CLI applications

**Basic Pattern:**

```python
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    """Application configuration with environment variable support."""

    model_config = SettingsConfigDict(
        env_prefix='INKWELL_',  # All env vars prefixed with INKWELL_
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False,  # INKWELL_API_KEY == inkwell_api_key
        extra='ignore',  # Ignore extra fields
    )

    # Basic fields with defaults
    api_key: str = Field(description="API key for external service")
    output_dir: Path = Field(default=Path("~/output"))

    # Optional fields
    debug_mode: bool = Field(default=False)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
```

**Environment Variable Loading:**
- Automatically loads from `.env` file if present
- Environment variables override `.env` values
- Respects prefix (e.g., `INKWELL_API_KEY` maps to `api_key` field)

**Authority Level:** Official recommendation from Pydantic docs (v2.0+)

---

### 1.2 Sentinel Values for Optional Configuration (RECOMMENDED)

**Source:** httpx/_config.py implementation

Use sentinel values to distinguish between "not provided", "None", and actual values. This prevents hardcoded defaults from overriding user configuration.

**The Problem:**
```python
# BAD: Can't distinguish "not set" from "set to None"
def process(output_dir: Path | None = None):
    if output_dir is None:
        output_dir = Path("~/default")  # Overrides user's explicit None!
```

**The Solution (httpx pattern):**

```python
from typing import TypeVar

class UnsetType:
    """Sentinel type for unset optional values."""
    def __repr__(self) -> str:
        return "UNSET"

UNSET = UnsetType()
T = TypeVar('T')

# Type alias for optional with sentinel
Unset = UnsetType | T

# Usage
def process(output_dir: Unset[Path | None] = UNSET):
    if output_dir is UNSET:
        # User didn't provide value, use default
        output_dir = Path("~/default")
    elif output_dir is None:
        # User explicitly set to None
        # Handle accordingly
    else:
        # User provided a path
        # Use it
```

**Real-World Example from httpx:**

```python
# From httpx/_config.py
DEFAULT_TIMEOUT_CONFIG = Timeout(timeout=5.0)
DEFAULT_LIMITS = Limits(max_connections=100, max_keepalive_connections=20)

class Client:
    def __init__(
        self,
        timeout: Unset[Timeout] = UNSET,
        limits: Unset[Limits] = UNSET,
    ):
        self.timeout = DEFAULT_TIMEOUT_CONFIG if timeout is UNSET else timeout
        self.limits = DEFAULT_LIMITS if limits is UNSET else limits
```

**Authority Level:** Established pattern in production libraries (httpx, starlette)

---

### 1.3 Environment Variable Prefix Configuration (RECOMMENDED)

**Source:** Pydantic Settings official docs

Use `env_prefix` to namespace your environment variables and avoid conflicts.

```python
class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix='DB_')

    endpoint: str = Field(default='http://localhost:8080/')
    key: str = ''

# Reads from: DB_ENDPOINT, DB_KEY
```

**Nested Configuration:**

```python
class AppConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix='APP_')

    # Reads from APP_DB__ENDPOINT (note double underscore)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
```

**Important Note:** `env_prefix` does NOT apply to fields with `alias`. If you use Field aliases, the prefix is ignored.

**Authority Level:** Official Pydantic documentation

---

## 2. API Key Management

### 2.1 Environment Variable Best Practices (MUST HAVE)

**Sources:** OpenAI documentation, Anthropic docs, security best practices

**Core Principles:**
1. NEVER hardcode API keys in source code
2. Use environment variables or secret management systems
3. Add `.env` to `.gitignore` immediately
4. Validate keys early (fail fast)
5. Provide clear error messages

**Recommended Pattern:**

```python
from pydantic import Field, SecretStr, validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class APIConfig(BaseSettings):
    """API configuration with key validation."""

    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
    )

    # Use SecretStr to prevent accidental logging
    gemini_api_key: SecretStr = Field(
        description="Google Gemini API key"
    )
    claude_api_key: SecretStr = Field(
        description="Anthropic Claude API key"
    )

    @validator('gemini_api_key', 'claude_api_key')
    def validate_key_format(cls, v: SecretStr) -> SecretStr:
        """Validate API key is not empty and has minimum length."""
        key = v.get_secret_value()

        if not key or len(key) < 20:
            raise ValueError("API key appears invalid (too short or empty)")

        # Check for common mistakes
        if key.strip() != key:
            raise ValueError("API key has leading/trailing whitespace")

        return v

    def get_gemini_key(self) -> str:
        """Get Gemini API key as plain string."""
        return self.gemini_api_key.get_secret_value()
```

**Security Checklist:**
- [ ] Use `SecretStr` type for API keys in Pydantic models
- [ ] Validate key format early (length, pattern)
- [ ] Check for common mistakes (quotes, whitespace, control chars)
- [ ] Never log full API keys (use masking)
- [ ] Store in `.env` file, never commit to git

**Authority Level:** Industry standard (OpenAI, Anthropic, AWS recommendations)

---

### 2.2 Multiple Environment Variable Names (Migration Strategy)

**Source:** Pydantic AliasChoices pattern, LangChain practices

When migrating from old environment variable names to new ones, support both temporarily using `AliasChoices`.

**The Problem:**
```
# Old code used GOOGLE_API_KEY
# New code uses GEMINI_API_KEY
# Users have GOOGLE_API_KEY in their .env
# How to support both during migration?
```

**Solution Using AliasChoices:**

```python
from pydantic import Field, AliasChoices
from pydantic_settings import BaseSettings

class APIConfig(BaseSettings):
    """API configuration with backward compatibility."""

    gemini_api_key: str = Field(
        validation_alias=AliasChoices(
            'GEMINI_API_KEY',      # NEW (preferred)
            'GOOGLE_API_KEY',       # OLD (deprecated)
            'GOOGLE_GENAI_API_KEY', # ALTERNATIVE
        ),
        description="Gemini API key (formerly GOOGLE_API_KEY)"
    )
```

**How It Works:**
1. Pydantic tries each alias in order
2. First one found is used
3. All aliases can populate the same field
4. Order matters: put preferred name first

**Deprecation Warning Pattern:**

```python
import warnings
from pydantic import field_validator

class APIConfig(BaseSettings):
    gemini_api_key: str = Field(
        validation_alias=AliasChoices('GEMINI_API_KEY', 'GOOGLE_API_KEY')
    )

    @field_validator('gemini_api_key', mode='after')
    @classmethod
    def warn_deprecated_env_var(cls, v: str) -> str:
        """Warn if using deprecated environment variable name."""
        import os

        # Check which env var was actually used
        if 'GOOGLE_API_KEY' in os.environ and 'GEMINI_API_KEY' not in os.environ:
            warnings.warn(
                "GOOGLE_API_KEY is deprecated and will be removed in v2.0. "
                "Please use GEMINI_API_KEY instead.",
                DeprecationWarning,
                stacklevel=2
            )

        return v
```

**Migration Timeline:**
- **v1.x:** Support both names, warn on old name
- **v1.y:** Loud deprecation warning, update docs
- **v2.0:** Remove old name support

**Authority Level:** Pydantic official pattern, used in LangChain, FastAPI

---

## 3. Dependency Injection Patterns

### 3.1 CLI Application Dependency Injection (RECOMMENDED)

**Source:** python-dependency-injector tutorial, Typer best practices

For larger CLI applications, use dependency injection to pass configuration through service layers.

**Core Pattern:**

```python
# containers.py
from dependency_injector import containers, providers
from pydantic_settings import BaseSettings

class AppConfig(BaseSettings):
    """Application configuration."""
    api_key: str
    output_dir: Path

class Container(containers.DeclarativeContainer):
    """Application container with all dependencies."""

    # Configuration
    config = providers.Configuration()

    # Load from pydantic settings
    settings = providers.Singleton(
        AppConfig,
    )

    # Services (receive config via constructor)
    transcription_service = providers.Factory(
        TranscriptionService,
        api_key=settings.provided.api_key,
    )

    extraction_service = providers.Factory(
        ExtractionService,
        api_key=settings.provided.api_key,
        output_dir=settings.provided.output_dir,
    )
```

**CLI Integration:**

```python
# cli.py
import typer
from dependency_injector.wiring import inject, Provide

from .containers import Container, AppConfig

app = typer.Typer()
container = Container()

# Load settings
container.settings.override(providers.Singleton(AppConfig))

# Wire the container to this module
container.wire(modules=[__name__])

@app.command()
@inject
def process(
    url: str,
    transcription_service: TranscriptionService = Provide[Container.transcription_service],
    extraction_service: ExtractionService = Provide[Container.extraction_service],
) -> None:
    """Process a podcast episode."""
    # Services already have config injected
    transcript = transcription_service.transcribe(url)
    result = extraction_service.extract(transcript)
```

**Benefits:**
- Configuration flows through explicitly
- Easy to test (override providers)
- Single source of truth
- Type-safe

**Authority Level:** python-dependency-injector official tutorial

---

### 3.2 Simpler Pattern: Settings Singleton (ALTERNATIVE)

**Source:** FastAPI, Typer community practices

For smaller applications, a settings singleton can be sufficient:

```python
# config.py
from functools import lru_cache
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    api_key: str
    output_dir: Path

@lru_cache
def get_settings() -> Settings:
    """Get settings singleton (cached)."""
    return Settings()

# cli.py
def process(url: str) -> None:
    settings = get_settings()  # Same instance every time
    service = TranscriptionService(api_key=settings.api_key)
    service.transcribe(url)
```

**When to Use:**
- **Singleton:** Small to medium CLI apps, simple config
- **DI Container:** Large apps, complex dependencies, multiple services

**Authority Level:** FastAPI official pattern for simpler applications

---

## 4. Model Versioning with External APIs

### 4.1 Configuration-Driven Model Selection (RECOMMENDED)

**Source:** LangChain model providers, API best practices

Allow users to configure which model version to use, with sensible defaults.

```python
class TranscriptionConfig(BaseSettings):
    """Transcription service configuration."""

    # Model selection
    gemini_model: str = Field(
        default="gemini-2.0-flash-exp",
        description="Gemini model version for transcription"
    )

    # Fallback model (if primary fails)
    gemini_fallback_model: str | None = Field(
        default="gemini-1.5-flash",
        description="Fallback model if primary unavailable"
    )

    # Feature flags for model capabilities
    use_latest_features: bool = Field(
        default=True,
        description="Use latest model features (may be unstable)"
    )

class TranscriptionService:
    def __init__(self, config: TranscriptionConfig):
        self.config = config
        self.primary_model = config.gemini_model
        self.fallback_model = config.gemini_fallback_model

    async def transcribe(self, audio_path: Path) -> str:
        """Transcribe audio with automatic fallback."""
        try:
            return await self._transcribe_with_model(
                audio_path,
                self.primary_model
            )
        except ModelUnavailableError:
            if self.fallback_model:
                logger.warning(
                    f"Primary model {self.primary_model} unavailable, "
                    f"falling back to {self.fallback_model}"
                )
                return await self._transcribe_with_model(
                    audio_path,
                    self.fallback_model
                )
            raise
```

**Authority Level:** Common pattern in LangChain, LlamaIndex, similar tools

---

### 4.2 Version Pinning Strategy (RECOMMENDED)

**Sources:** API stability guides, production deployment practices

**Approaches:**

1. **Conservative (Recommended for Production):**
   - Pin to stable versions (e.g., "gemini-1.5-flash")
   - Test new versions before upgrading
   - Use config to allow opt-in to experimental models

2. **Progressive (For Development):**
   - Default to "latest" or experimental versions
   - Provide config option to pin to stable
   - Monitor for breaking changes

**Configuration Example:**

```python
class ModelConfig(BaseSettings):
    """Model versioning configuration."""

    # Stability preference
    model_stability: Literal["stable", "latest", "experimental"] = "stable"

    # Explicit version override
    transcription_model_override: str | None = None

    def get_transcription_model(self) -> str:
        """Get transcription model based on stability preference."""
        if self.transcription_model_override:
            return self.transcription_model_override

        # Model selection based on stability
        models = {
            "stable": "gemini-1.5-flash",
            "latest": "gemini-2.0-flash-exp",
            "experimental": "gemini-2.0-flash-thinking-exp"
        }

        return models[self.model_stability]
```

**Best Practices:**
- Document which models are stable vs experimental
- Provide migration guides when deprecating models
- Log which model version is actually used
- Allow override via env var: `INKWELL_TRANSCRIPTION_MODEL=gemini-1.5-pro`

**Authority Level:** Industry best practices from OpenAI, Anthropic, Google

---

## 5. Testing Configuration-Dependent Code

### 5.1 Pytest Monkeypatch Pattern (MUST HAVE)

**Source:** Official pytest documentation

Use `monkeypatch` fixture to safely override environment variables in tests.

**Basic Pattern:**

```python
def test_api_key_loading(monkeypatch):
    """Test that API key is loaded from environment."""
    # Set environment variable for test
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-12345678901234567890")

    # Create config (will read from env)
    config = APIConfig()

    # Verify
    assert config.gemini_api_key.get_secret_value() == "test-key-12345678901234567890"

def test_missing_api_key(monkeypatch):
    """Test error when API key missing."""
    # Ensure env var is NOT set
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    # Should raise validation error
    with pytest.raises(ValidationError) as exc_info:
        APIConfig()

    assert "gemini_api_key" in str(exc_info.value)
```

**Advanced: Testing Config Precedence:**

```python
def test_env_var_overrides_default(monkeypatch):
    """Test that environment variable overrides default value."""
    # Set environment override
    monkeypatch.setenv("INKWELL_OUTPUT_DIR", "/custom/path")

    config = AppConfig()

    # Should use env var, not default
    assert config.output_dir == Path("/custom/path")

def test_explicit_override_trumps_env(monkeypatch):
    """Test that explicit constructor arg overrides env var."""
    monkeypatch.setenv("INKWELL_OUTPUT_DIR", "/env/path")

    # Explicit override (if your settings class supports it)
    config = AppConfig(output_dir="/explicit/path")

    assert config.output_dir == Path("/explicit/path")
```

**Authority Level:** Official pytest documentation, standard practice

---

### 5.2 Test Fixtures for Configuration (RECOMMENDED)

**Source:** Pytest best practices, FastAPI testing patterns

Create reusable fixtures for common test configurations.

```python
# conftest.py
import pytest
from pathlib import Path
from typing import Generator

@pytest.fixture
def test_config(tmp_path: Path, monkeypatch) -> Generator[AppConfig, None, None]:
    """Provide test configuration with isolated temp directory."""
    # Set test environment variables
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key-1234567890123456")
    monkeypatch.setenv("CLAUDE_API_KEY", "sk-ant-test-key-1234567890123456")
    monkeypatch.setenv("INKWELL_OUTPUT_DIR", str(tmp_path))

    # Create config
    config = AppConfig()

    yield config

    # Cleanup happens automatically with tmp_path

@pytest.fixture
def mock_api_keys(monkeypatch) -> dict[str, str]:
    """Set mock API keys for testing."""
    keys = {
        "GEMINI_API_KEY": "AIza-test-gemini-key-1234567890",
        "CLAUDE_API_KEY": "sk-ant-test-claude-key-1234567890",
    }

    for key, value in keys.items():
        monkeypatch.setenv(key, value)

    return keys

# Usage in tests
def test_service_with_config(test_config):
    """Test service using test configuration."""
    service = TranscriptionService(config=test_config)
    # Service has valid test config
    assert service.config.output_dir.exists()

def test_api_key_validation(mock_api_keys):
    """Test API key validation with mock keys."""
    config = APIConfig()
    assert config.gemini_api_key.get_secret_value().startswith("AIza")
```

**Authority Level:** pytest community best practices

---

### 5.3 Override Testing with Dependency Injection (ADVANCED)

**Source:** python-dependency-injector testing documentation

If using DI, leverage provider overrides for testing.

```python
def test_service_with_mock_config():
    """Test service with mocked configuration."""
    # Create test container
    container = Container()

    # Override config provider with test config
    test_config = AppConfig(
        api_key="test-key-123456789012345678",
        output_dir=Path("/tmp/test")
    )

    with container.settings.override(test_config):
        # Get service (will use test config)
        service = container.transcription_service()

        # Verify service has test config
        assert service.api_key == "test-key-123456789012345678"
```

**Authority Level:** python-dependency-injector official docs

---

## 6. Migration Strategies

### 6.1 Environment Variable Renaming (RECOMMENDED PROCESS)

**Source:** Open source project migrations (SQLAlchemy, Jupyter, Django)

When changing environment variable names, follow this migration path:

**Phase 1: Dual Support (v1.x)**
```python
from pydantic import Field, AliasChoices, field_validator
import warnings

class Config(BaseSettings):
    api_key: str = Field(
        validation_alias=AliasChoices(
            'NEW_API_KEY',  # Preferred
            'OLD_API_KEY',  # Deprecated
        )
    )

    @field_validator('api_key', mode='after')
    @classmethod
    def warn_old_name(cls, v: str) -> str:
        import os
        if 'OLD_API_KEY' in os.environ and 'NEW_API_KEY' not in os.environ:
            warnings.warn(
                "OLD_API_KEY is deprecated. Use NEW_API_KEY instead. "
                "Support for OLD_API_KEY will be removed in v2.0.",
                DeprecationWarning,
                stacklevel=2
            )
        return v
```

**Phase 2: Loud Warning (v1.y, 3-6 months later)**
```python
# Upgrade warning to UserWarning (shows by default)
warnings.warn(
    "OLD_API_KEY will be removed in the next major version! "
    "Please update to NEW_API_KEY immediately.",
    UserWarning,  # More visible
    stacklevel=2
)
```

**Phase 3: Remove Old Name (v2.0)**
```python
class Config(BaseSettings):
    # Only new name supported
    api_key: str = Field(
        alias='NEW_API_KEY'
    )
```

**Documentation Updates:**
- Immediately update docs to show new name
- Add migration guide with examples
- Include in changelog/release notes
- Update example `.env` files

**Authority Level:** Established pattern from major Python projects

---

### 6.2 Configuration Schema Versioning (ADVANCED)

**Source:** API versioning best practices

For complex configuration changes, version your config schema:

```python
from pydantic import Field

class ConfigV1(BaseSettings):
    """Configuration schema version 1."""
    version: Literal["1"] = "1"
    api_key: str

class ConfigV2(BaseSettings):
    """Configuration schema version 2."""
    version: Literal["2"] = "2"
    gemini_api_key: str  # Renamed from api_key
    claude_api_key: str  # New field

def load_config() -> ConfigV2:
    """Load config with automatic migration."""
    # Try loading as v2
    try:
        return ConfigV2()
    except ValidationError:
        pass

    # Try loading as v1 and migrate
    try:
        v1 = ConfigV1()
        logger.warning("Migrating config from v1 to v2...")

        # Migrate
        return ConfigV2(
            version="2",
            gemini_api_key=v1.api_key,
            claude_api_key=os.environ.get("CLAUDE_API_KEY", "")
        )
    except ValidationError as e:
        raise ConfigurationError(f"Invalid configuration: {e}")
```

**Authority Level:** Advanced pattern, use only for complex migrations

---

## 7. Real-World Examples from Well-Known Projects

### 7.1 HTTPX Configuration Pattern

**Source:** `httpx/_config.py`

**Key Techniques:**
- Sentinel values (`UNSET`) for optional parameters
- Module-level default constants
- Environment variable checking with `trust_env` flag
- SSL/TLS configuration from `SSL_CERT_FILE` and `SSL_CERT_DIR`

**Pattern:**
```python
# Module-level defaults
DEFAULT_TIMEOUT_CONFIG = Timeout(timeout=5.0)
DEFAULT_LIMITS = Limits(max_connections=100, max_keepalive_connections=20)

class Client:
    def __init__(
        self,
        timeout: Unset[Timeout] = UNSET,
        limits: Unset[Limits] = UNSET,
        trust_env: bool = True,
    ):
        self.timeout = DEFAULT_TIMEOUT_CONFIG if timeout is UNSET else timeout
        self.limits = DEFAULT_LIMITS if limits is UNSET else limits

        # Environment variables only consulted if trust_env=True
        if trust_env:
            self._apply_env_config()
```

**Authority:** Production code from widely-used library (encode/httpx)

---

### 7.2 LangChain Configuration Pattern

**Source:** LangChain model providers

**Key Techniques:**
- Pydantic models for configuration
- `AliasChoices` for multiple env var names
- ConfigurableField for runtime configuration
- Model fallback chains

**Pattern:**
```python
from langchain_core.runnables import ConfigurableField

model = ChatOpenAI(temperature=0).configurable_fields(
    temperature=ConfigurableField(
        id="llm_temperature",
        name="LLM Temperature",
        description="The temperature of the LLM",
    )
)

# Use with custom config at runtime
response = model.with_config({"temperature": 0.9}).invoke("Hello")
```

**Authority:** Production pattern from LangChain (major AI framework)

---

### 7.3 OpenAI Python SDK Pattern

**Source:** `openai-python` library

**Key Techniques:**
- Multiple environment variable names (`OPENAI_API_KEY` or `OPENAI_KEY`)
- Client initialization with explicit or env-based keys
- Pydantic for request/response models

**Pattern:**
```python
import os
from openai import OpenAI

# Automatic env var loading
client = OpenAI()  # Checks OPENAI_API_KEY automatically

# Or explicit
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
```

**Authority:** Official OpenAI SDK

---

## 8. Recommendations for Inkwell CLI

Based on the research, here are specific recommendations for fixing Inkwell's configuration issues:

### 8.1 Immediate Fixes (High Priority)

1. **Standardize Environment Variable Names**
   - Current issue: Both `GOOGLE_API_KEY` and `GEMINI_API_KEY` used
   - Fix: Use `AliasChoices` to support both, warn on old name

   ```python
   gemini_api_key: SecretStr = Field(
       validation_alias=AliasChoices('GEMINI_API_KEY', 'GOOGLE_API_KEY')
   )
   ```

2. **Implement Sentinel Values**
   - Current issue: Can't distinguish user's `None` from "not provided"
   - Fix: Add `UNSET` sentinel following httpx pattern

   ```python
   class UnsetType:
       pass

   UNSET = UnsetType()

   def __init__(self, output_dir: Path | None | UnsetType = UNSET):
       if output_dir is UNSET:
           # Use default
       elif output_dir is None:
           # User explicitly set None
       else:
           # User provided value
   ```

3. **Fix Configuration Passing**
   - Current issue: Config not passed through service layers
   - Fix: Use constructor injection pattern

   ```python
   class TranscriptionService:
       def __init__(self, config: TranscriptionConfig):
           self.config = config
           self.api_key = config.get_gemini_key()
   ```

### 8.2 Medium-Term Improvements

4. **Add Configuration Tests**
   - Test env var loading
   - Test precedence (env > default)
   - Test validation errors

   ```python
   def test_config_loading(monkeypatch):
       monkeypatch.setenv("INKWELL_GEMINI_API_KEY", "test-key")
       config = AppConfig()
       assert config.gemini_api_key.get_secret_value() == "test-key"
   ```

5. **Improve Error Messages**
   - Validate API keys early
   - Provide actionable error messages
   - Use `APIKeyError` for key-specific issues

6. **Document Migration Path**
   - Create migration guide for users
   - Update all examples in docs
   - Add to changelog

### 8.3 Long-Term Architecture

7. **Consider Dependency Injection**
   - If application grows, add DI container
   - Use `python-dependency-injector`
   - Makes testing easier

8. **Version Configuration Schema**
   - Add `version` field to config
   - Allow migration from old schemas
   - Warn on deprecated fields

---

## 9. References and Further Reading

### Official Documentation
- [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) - Official Pydantic settings docs
- [Typer](https://typer.tiangolo.com/) - Typer CLI framework
- [pytest monkeypatch](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) - Testing with environment variables
- [python-dependency-injector](https://python-dependency-injector.ets-labs.org/) - DI framework docs

### Real-World Examples
- [httpx/_config.py](https://github.com/encode/httpx/blob/master/httpx/_config.py) - Sentinel pattern, defaults
- [LangChain Settings](https://python.langchain.com/docs/how_to/configure/) - ConfigurableField pattern
- [OpenAI Python](https://github.com/openai/openai-python) - API key management

### Articles and Guides
- [Configuration Management in Python like a Boss](https://medium.com/pythonistas/configuration-management-in-python-like-a-boss-pydantic-with-python-dotenv-b4832eb9d930)
- [Best Practices for API Key Safety](https://help.openai.com/en/articles/5112595-best-practices-for-api-key-safety)
- [Improving Python CLIs with Pydantic](https://www.maskset.net/blog/2025/07/01/improving-python-clis-with-pydantic-and-dataclasses/)

### Related Inkwell Docs
- [ADR-008: Use uv for Python Tooling](../adr/008-use-uv-for-python-tooling.md)
- [PRD v0](../PRD_v0.md)

---

## Appendix: Quick Reference

### Environment Variable Checklist

- [ ] Use `pydantic-settings` BaseSettings
- [ ] Add `env_prefix` for namespacing
- [ ] Use `SecretStr` for API keys
- [ ] Support multiple names with `AliasChoices`
- [ ] Validate keys early (length, format)
- [ ] Add `.env` to `.gitignore`
- [ ] Document env vars in README
- [ ] Provide example `.env.example` file

### Testing Checklist

- [ ] Test config loading from env vars
- [ ] Test missing required fields
- [ ] Test invalid values (validation)
- [ ] Test precedence (env > file > default)
- [ ] Use `monkeypatch` for env vars
- [ ] Create fixtures for common configs
- [ ] Test migration/deprecation warnings

### Migration Checklist

- [ ] Support both old and new names
- [ ] Add deprecation warning
- [ ] Update documentation
- [ ] Add to changelog
- [ ] Provide migration guide
- [ ] Set removal timeline
- [ ] Monitor usage of old names
