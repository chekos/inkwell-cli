# Quick Reference: Configuration Fixes

**For detailed research, see:** [google-genai-pydantic-typer-config.md](./google-genai-pydantic-typer-config.md)

## 1. Model Names - What to Change

### WRONG (Current)
```python
model_name: str = "gemini-1.5-flash"
MODEL = "gemini-1.5-flash-latest"
```

### RIGHT (Fixed)
```python
model_name: str = "gemini-2.5-flash"  # Stable, recommended
# Or
model_name: str = "gemini-2.0-flash-exp"  # If using experimental
```

**Available Models in 2025:**
- `gemini-2.5-flash` ✅ Recommended (replaced 1.5-flash)
- `gemini-2.5-flash-lite` - Fastest, cost-efficient
- `gemini-2.0-flash-exp` - Experimental version

## 2. Environment Variable - Standardize

### WRONG (Inconsistent)
```python
# Some files use this
api_key = os.getenv("GOOGLE_AI_API_KEY")  # ❌

# Others use this
api_key = os.getenv("GOOGLE_API_KEY")     # ✅
```

### RIGHT (Standardized)
```python
# Always use GOOGLE_API_KEY
api_key = os.getenv("GOOGLE_API_KEY")

# Or better, use validation utility
from inkwell.utils.api_keys import get_validated_api_key
api_key = get_validated_api_key("GOOGLE_API_KEY", "gemini")
```

**SDK Support:**
- `GOOGLE_API_KEY` - Primary (use this!)
- `GEMINI_API_KEY` - Fallback (SDK checks both)

## 3. Config Injection - Pass Don't Create

### WRONG (Services create config)
```python
class TranscriptionManager:
    def __init__(self):
        # BAD: Hardcoded, not configurable
        self.model_name = "gemini-1.5-flash"
        self.api_key = os.getenv("GOOGLE_AI_API_KEY")
```

### RIGHT (Inject config)
```python
class TranscriptionManager:
    def __init__(
        self,
        model_name: str | None = None,
        api_key: str | None = None,
    ):
        self.model_name = model_name or "gemini-2.5-flash"
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
```

## 4. Typer Context Pattern

### Implementation
```python
# cli.py
import typer
from inkwell.config.manager import ConfigManager

app = typer.Typer()

class InkwellContext:
    def __init__(self, config: GlobalConfig):
        self.config = config

@app.callback()
def main(ctx: typer.Context):
    """Setup shared config."""
    config = ConfigManager().load_config()
    ctx.obj = InkwellContext(config=config)

@app.command()
def transcribe(ctx: typer.Context, url: str):
    """Use shared config."""
    config = ctx.obj.config

    # Pass config to service
    manager = TranscriptionManager(
        model_name=config.transcription_model
    )
```

## 5. Quick Fixes Summary

| File | Change | From | To |
|------|--------|------|-----|
| `transcription/gemini.py` | Model name | `gemini-1.5-flash` | `gemini-2.5-flash` |
| `transcription/gemini.py` | Env var | `GOOGLE_AI_API_KEY` | `GOOGLE_API_KEY` |
| `extraction/extractors/gemini.py` | Model name | `gemini-1.5-flash-latest` | `gemini-2.5-flash` |
| `config/schema.py` | Default model | `gemini-1.5-flash-exp` | `gemini-2.0-flash-exp` |
| `cli.py` | Add context | None | `ctx.obj = InkwellContext(config)` |
| All services | Add params | Hardcoded | Accept config injection |

## 6. Testing Commands

```bash
# Test model is available
uv run python -c "
import google.generativeai as genai
import os
genai.configure(api_key=os.getenv('GOOGLE_API_KEY'))
model = genai.GenerativeModel('gemini-2.5-flash')
print('Model loaded successfully')
"

# Test environment variable
echo $GOOGLE_API_KEY

# Test config loading
uv run inkwell config show
```

## 7. Documentation URLs

**Google Generative AI:**
- Models: https://ai.google.dev/gemini-api/docs/models
- API Keys: https://ai.google.dev/gemini-api/docs/api-key

**Pydantic Settings:**
- Docs: https://docs.pydantic.dev/latest/concepts/pydantic_settings/

**Typer:**
- Context: https://typer.tiangolo.com/tutorial/commands/context/
- Callbacks: https://typer.tiangolo.com/tutorial/commands/callback/

## 8. Code Snippets

### Pydantic Settings Class (Optional Enhancement)
```python
# src/inkwell/config/settings.py
from pydantic_settings import BaseSettings, SettingsConfigDict

class InkwellSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
    )

    google_api_key: str | None = None
    anthropic_api_key: str | None = None
    transcription_model: str = "gemini-2.5-flash"
```

### Service Constructor Pattern
```python
class GeminiTranscriber:
    def __init__(
        self,
        api_key: str | None = None,
        model_name: str | None = None,
    ):
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        self.model_name = model_name or "gemini-2.5-flash"

        if not self.api_key:
            raise ValueError("GOOGLE_API_KEY required")

        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel(self.model_name)
```
