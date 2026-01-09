# Publishing Plugins to PyPI

Package structure, metadata, and distribution for Inkwell plugins.

---

## Package Structure

Recommended structure for an Inkwell plugin package:

```
inkwell-whisper-plugin/
├── pyproject.toml
├── README.md
├── LICENSE
├── src/
│   └── inkwell_whisper/
│       ├── __init__.py
│       └── transcriber.py
└── tests/
    ├── __init__.py
    └── test_transcriber.py
```

---

## pyproject.toml

Complete example for a transcription plugin:

```toml
[project]
name = "inkwell-whisper-plugin"
version = "1.0.0"
description = "Local Whisper transcription plugin for Inkwell"
readme = "README.md"
requires-python = ">=3.10"
license = {text = "MIT"}
authors = [
    {name = "Your Name", email = "your@email.com"}
]
keywords = [
    "inkwell",
    "plugin",
    "transcription",
    "whisper",
    "speech-to-text",
]
classifiers = [
    "Development Status :: 4 - Beta",
    "Environment :: Plugins",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Topic :: Multimedia :: Sound/Audio :: Speech",
]

# Dependencies
dependencies = [
    "inkwell-cli>=0.11.0",  # Minimum Inkwell version
    "openai-whisper>=20231117",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
]

[project.urls]
Homepage = "https://github.com/yourusername/inkwell-whisper-plugin"
Repository = "https://github.com/yourusername/inkwell-whisper-plugin.git"
Issues = "https://github.com/yourusername/inkwell-whisper-plugin/issues"

# Entry point registration - THIS IS REQUIRED
[project.entry-points."inkwell.plugins.transcription"]
whisper = "inkwell_whisper:WhisperTranscriber"

# Optional: Plugin metadata for tooling
[tool.inkwell.plugin]
type = "transcription"
min_api_version = "1.0"
capabilities = ["offline", "gpu-accelerated"]

[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]
```

---

## Entry Points

Entry points are **required** for plugin discovery. The format is:

```toml
[project.entry-points."inkwell.plugins.<type>"]
<plugin-name> = "<module>:<ClassName>"
```

### Entry Point Groups

| Plugin Type | Group |
|-------------|-------|
| Extraction | `inkwell.plugins.extraction` |
| Transcription | `inkwell.plugins.transcription` |
| Output | `inkwell.plugins.output` |

### Examples

```toml
# Extraction plugin
[project.entry-points."inkwell.plugins.extraction"]
openai = "inkwell_openai:OpenAIExtractor"

# Transcription plugin
[project.entry-points."inkwell.plugins.transcription"]
whisper = "inkwell_whisper:WhisperTranscriber"
assemblyai = "inkwell_assemblyai:AssemblyAITranscriber"

# Output plugin
[project.entry-points."inkwell.plugins.output"]
html = "inkwell_html:HTMLOutput"
notion = "inkwell_notion:NotionOutput"
```

---

## Plugin Module

The entry point must point to an importable class:

```python
# src/inkwell_whisper/__init__.py
"""Inkwell Whisper Plugin - Local transcription using OpenAI Whisper."""

from .transcriber import WhisperTranscriber

__all__ = ["WhisperTranscriber"]
__version__ = "1.0.0"
```

```python
# src/inkwell_whisper/transcriber.py
"""Whisper transcription implementation."""

from typing import ClassVar
from inkwell.plugins.types.transcription import TranscriptionPlugin, TranscriptionRequest
from inkwell.transcription.models import Transcript

class WhisperTranscriber(TranscriptionPlugin):
    """Local transcription using OpenAI Whisper."""

    NAME: ClassVar[str] = "whisper"
    VERSION: ClassVar[str] = "1.0.0"
    DESCRIPTION: ClassVar[str] = "Local Whisper transcription (offline, GPU-accelerated)"

    # ... implementation
```

---

## README.md

Include essential information:

```markdown
# inkwell-whisper-plugin

Local Whisper transcription plugin for [Inkwell](https://github.com/chekos/inkwell-cli).

## Installation

```bash
pip install inkwell-whisper-plugin
# or with uv
uv add inkwell-whisper-plugin
```

## Usage

After installation, the plugin is automatically discovered:

```bash
# List plugins to verify installation
inkwell plugins list

# Use whisper for transcription
inkwell fetch URL --transcriber whisper
```

## Configuration

Add to `~/.config/inkwell/config.yaml`:

```yaml
plugins:
  whisper:
    priority: 150  # Prefer over built-in transcribers
    config:
      model: base  # tiny, base, small, medium, large
      device: cuda  # cpu or cuda
      language: auto
```

## Requirements

- Python 3.10+
- Inkwell CLI 0.11.0+
- ffmpeg (for audio processing)
- CUDA (optional, for GPU acceleration)

## License

MIT
```

---

## Versioning

Follow semantic versioning:

- **MAJOR**: Breaking changes to plugin interface
- **MINOR**: New features, backward compatible
- **PATCH**: Bug fixes

```python
# Match your package version
class MyPlugin(InkwellPlugin):
    NAME = "my-plugin"
    VERSION = "1.2.3"  # Keep in sync with pyproject.toml
```

---

## API Version Compatibility

Declare the minimum Inkwell plugin API version:

```python
class MyPlugin(InkwellPlugin):
    API_VERSION = "1.0"  # Must match major version of Inkwell's API
```

Also specify in dependencies:

```toml
dependencies = [
    "inkwell-cli>=0.11.0",  # First version with plugin API 1.0
]
```

---

## Building and Publishing

### Build the Package

```bash
# Install build tools
pip install build twine

# Build
python -m build

# This creates:
# dist/inkwell_whisper_plugin-1.0.0.tar.gz
# dist/inkwell_whisper_plugin-1.0.0-py3-none-any.whl
```

### Test Locally

```bash
# Install in development mode
pip install -e .

# Verify plugin is discovered
inkwell plugins list

# Test functionality
inkwell fetch URL --transcriber whisper
```

### Publish to PyPI

```bash
# Upload to Test PyPI first
twine upload --repository testpypi dist/*

# Test installation from Test PyPI
pip install --index-url https://test.pypi.org/simple/ inkwell-whisper-plugin

# Upload to PyPI
twine upload dist/*
```

### Using GitHub Actions

```yaml
# .github/workflows/publish.yml
name: Publish to PyPI

on:
  release:
    types: [published]

jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install build tools
        run: pip install build twine

      - name: Build package
        run: python -m build

      - name: Publish to PyPI
        env:
          TWINE_USERNAME: __token__
          TWINE_PASSWORD: ${{ secrets.PYPI_API_TOKEN }}
        run: twine upload dist/*
```

---

## Testing Before Release

### Run Plugin Tests

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run with coverage
pytest --cov=inkwell_whisper
```

### Integration Test

```bash
# Install in clean environment
python -m venv test-env
source test-env/bin/activate
pip install inkwell-cli
pip install -e .

# Verify
inkwell plugins list
inkwell plugins validate whisper
```

---

## Naming Conventions

### Package Name

Use the pattern: `inkwell-<name>-plugin`

Examples:
- `inkwell-whisper-plugin`
- `inkwell-openai-plugin`
- `inkwell-notion-plugin`

### Plugin Name (NAME attribute)

Short, lowercase, hyphenated:

```python
NAME = "whisper"        # Good
NAME = "openai"         # Good
NAME = "notion-export"  # Good
NAME = "WhisperPlugin"  # Bad (use lowercase)
```

---

## Best Practices

### 1. Document Dependencies

```toml
dependencies = [
    "inkwell-cli>=0.11.0",
    "openai-whisper>=20231117",
]
```

### 2. Handle Missing Dependencies

```python
def validate(self):
    try:
        import whisper
    except ImportError:
        raise PluginValidationError(
            self.NAME,
            ["openai-whisper not installed. Run: pip install openai-whisper"]
        )
```

### 3. Provide Recovery Hints

```python
errors = []
if not shutil.which("ffmpeg"):
    errors.append("ffmpeg not found. Install via: brew install ffmpeg (macOS) or apt install ffmpeg (Linux)")
```

### 4. Test on Multiple Python Versions

```yaml
# .github/workflows/test.yml
strategy:
  matrix:
    python-version: ["3.10", "3.11", "3.12"]
```

### 5. Include Type Hints

```python
async def transcribe(self, request: TranscriptionRequest) -> Transcript:
    ...
```

---

## Checklist

Before publishing:

- [ ] Package builds successfully (`python -m build`)
- [ ] All tests pass (`pytest`)
- [ ] Entry point is correctly configured
- [ ] README includes installation and usage instructions
- [ ] Version matches in `pyproject.toml` and plugin class
- [ ] API_VERSION is compatible with target Inkwell version
- [ ] Dependencies are properly specified
- [ ] License file is included
- [ ] Plugin validates successfully after clean install

---

## Resources

- [Python Packaging User Guide](https://packaging.python.org/)
- [PyPI Publishing Guide](https://packaging.python.org/tutorials/packaging-projects/)
- [Inkwell Plugin API Reference](index.md)
