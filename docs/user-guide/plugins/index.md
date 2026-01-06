# Plugin Development Guide

Extend Inkwell with custom plugins for extraction, transcription, and output formats.

---

## Overview

Inkwell's plugin architecture allows third-party developers to add:

- **Extraction plugins**: New LLM providers for content extraction (OpenAI, Ollama, etc.)
- **Transcription plugins**: New audio-to-text backends (Whisper, AssemblyAI, etc.)
- **Output plugins**: New output formats (HTML, Notion, Obsidian Canvas, etc.)

Plugins are discovered automatically via Python entry points, configured through YAML, and managed via the `inkwell plugins` CLI commands.

---

## Quick Start

Create a minimal transcription plugin in 5 minutes:

```python
# my_whisper_plugin.py
from inkwell.plugins.types.transcription import TranscriptionPlugin, TranscriptionRequest

class WhisperTranscriber(TranscriptionPlugin):
    NAME = "whisper"
    VERSION = "1.0.0"
    DESCRIPTION = "Local Whisper transcription"

    CAPABILITIES = {
        "supports_file": True,
        "supports_url": False,
        "requires_internet": False,
    }

    async def transcribe(self, request: TranscriptionRequest):
        # Your implementation here
        import whisper
        model = whisper.load_model("base")
        result = model.transcribe(str(request.file_path))

        from inkwell.transcription.models import Transcript
        return Transcript(text=result["text"])
```

Register it in your `pyproject.toml`:

```toml
[project.entry-points."inkwell.plugins.transcription"]
whisper = "my_whisper_plugin:WhisperTranscriber"
```

Install and use:

```bash
pip install -e .
inkwell plugins list  # Should show whisper plugin
inkwell fetch URL --transcriber whisper
```

---

## Guide Contents

### [Creating Your First Plugin](creating-plugins.md)
Step-by-step tutorial for building each plugin type.

### [Plugin Lifecycle](lifecycle.md)
Understand configure(), validate(), and cleanup() hooks.

### [Configuration](configuration.md)
Schema validation, config files, and environment variables.

### [Testing Plugins](testing.md)
Test utilities, mocks, and best practices.

### [Publishing to PyPI](publishing.md)
Package structure, metadata, and distribution.

---

## Plugin Types at a Glance

| Type | Base Class | Entry Point Group | Key Method |
|------|-----------|-------------------|------------|
| Extraction | `ExtractionPlugin` | `inkwell.plugins.extraction` | `extract()` |
| Transcription | `TranscriptionPlugin` | `inkwell.plugins.transcription` | `transcribe()` |
| Output | `OutputPlugin` | `inkwell.plugins.output` | `render()` |

---

## CLI Commands

```bash
# List all plugins
inkwell plugins list

# List by type
inkwell plugins list --type extraction

# Validate plugin configuration
inkwell plugins validate whisper

# Enable/disable plugins (session only)
inkwell plugins enable whisper
inkwell plugins disable youtube

# Override plugin selection
inkwell fetch URL --extractor claude --transcriber whisper

# Environment variable overrides
INKWELL_EXTRACTOR=gemini inkwell fetch URL
```

---

## API Version Compatibility

Plugins declare an `API_VERSION` that must be compatible with Inkwell's plugin API:

```python
class MyPlugin(InkwellPlugin):
    API_VERSION = "1.0"  # Major version must match Inkwell's
```

**Compatibility rules:**
- Major version must match exactly (1.x works with 1.y)
- Minor versions are backward compatible
- Breaking changes increment major version

Current API version: **1.0**

---

## Built-in Plugins

Inkwell ships with these built-in plugins:

### Extraction
- **claude**: Claude (Anthropic) API - best for precision extraction
- **gemini**: Google Gemini API - cost-effective option

### Transcription
- **youtube**: YouTube transcript API - free, fast for YouTube content
- **gemini**: Gemini audio transcription - fallback for non-YouTube content

### Output
- **markdown**: Markdown file generation with YAML frontmatter

---

## Next Steps

1. Read [Creating Your First Plugin](creating-plugins.md) for a complete tutorial
2. Review [Plugin Lifecycle](lifecycle.md) to understand hooks
3. Check [Testing Plugins](testing.md) for test utilities
