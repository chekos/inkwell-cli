# Creating Your First Plugin

Step-by-step guides for creating each type of Inkwell plugin.

---

## Extraction Plugins

Extraction plugins use LLMs to extract structured content from transcripts.

### Base Class

```python
from inkwell.plugins.types.extraction import ExtractionPlugin
```

### Required Methods

| Method | Return Type | Description |
|--------|-------------|-------------|
| `extract()` | `str` | Extract content using LLM |
| `estimate_cost()` | `float` | Estimate cost in USD |
| `supports_structured_output()` | `bool` | Whether provider supports JSON mode |

### Example: OpenAI Extractor

```python
"""OpenAI GPT-4 extraction plugin."""
from typing import Any, ClassVar
from openai import AsyncOpenAI

from inkwell.plugins.types.extraction import ExtractionPlugin
from inkwell.extraction.models import ExtractionTemplate


class OpenAIExtractor(ExtractionPlugin):
    """Extractor using OpenAI GPT-4 API."""

    # Required metadata
    NAME: ClassVar[str] = "openai"
    VERSION: ClassVar[str] = "1.0.0"
    DESCRIPTION: ClassVar[str] = "OpenAI GPT-4 extractor"

    # Optional: Model and pricing for cost tracking
    MODEL: ClassVar[str] = "gpt-4-turbo"
    INPUT_PRICE_PER_M: ClassVar[float] = 10.00   # $10/M input tokens
    OUTPUT_PRICE_PER_M: ClassVar[float] = 30.00  # $30/M output tokens

    def __init__(self, api_key: str | None = None, *, lazy_init: bool = False):
        super().__init__()
        self._api_key = api_key
        self._client: AsyncOpenAI | None = None
        if not lazy_init:
            self._init_client()

    def _init_client(self):
        import os
        api_key = self._api_key or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not set")
        self._client = AsyncOpenAI(api_key=api_key)

    def configure(self, config: dict[str, Any], cost_tracker=None):
        """Configure plugin after discovery."""
        super().configure(config, cost_tracker)
        if config.get("api_key"):
            self._api_key = config["api_key"]
        self._init_client()

    async def extract(
        self,
        template: ExtractionTemplate,
        transcript: str,
        metadata: dict[str, Any],
        force_json: bool = False,
        max_tokens_override: int | None = None,
    ) -> str:
        """Extract content using GPT-4."""
        user_prompt = self.build_prompt(template, transcript, metadata)

        response = await self._client.chat.completions.create(
            model=self.MODEL,
            messages=[
                {"role": "system", "content": template.system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=max_tokens_override or template.max_tokens,
            temperature=template.temperature,
        )

        result = response.choices[0].message.content

        # Track cost if cost_tracker is configured
        if self._cost_tracker and response.usage:
            self.track_cost(
                input_tokens=response.usage.prompt_tokens,
                output_tokens=response.usage.completion_tokens,
                template_name=template.name,
            )

        return result

    def estimate_cost(self, template: ExtractionTemplate, transcript_length: int) -> float:
        """Estimate extraction cost."""
        input_tokens = self._count_tokens(template.system_prompt)
        input_tokens += transcript_length // 4  # ~4 chars per token
        output_tokens = template.max_tokens

        input_cost = (input_tokens / 1_000_000) * self.INPUT_PRICE_PER_M
        output_cost = (output_tokens / 1_000_000) * self.OUTPUT_PRICE_PER_M
        return input_cost + output_cost

    def supports_structured_output(self) -> bool:
        """GPT-4 supports JSON mode."""
        return True
```

---

## Transcription Plugins

Transcription plugins convert audio/video to text.

### Base Class

```python
from inkwell.plugins.types.transcription import (
    TranscriptionPlugin,
    TranscriptionRequest,
)
```

### Required Methods

| Method | Return Type | Description |
|--------|-------------|-------------|
| `transcribe()` | `Transcript` | Convert audio to text |

### Optional Methods

| Method | Return Type | Default | Description |
|--------|-------------|---------|-------------|
| `can_handle()` | `bool` | Based on `CAPABILITIES` | Check if plugin can handle request |
| `estimate_cost()` | `float` | `0.0` | Estimate cost for duration |

### Class Attributes

```python
# URL patterns this plugin handles (for auto-selection)
HANDLES_URLS: ClassVar[list[str]] = ["youtube.com", "youtu.be"]

# Capability declarations
CAPABILITIES: ClassVar[dict] = {
    "formats": ["mp3", "wav", "m4a", "mp4"],
    "max_duration_hours": None,  # None = no limit
    "requires_internet": True,
    "supports_file": True,
    "supports_url": False,
    "supports_bytes": False,
}
```

### Example: Whisper Local Transcription

```python
"""Local Whisper transcription plugin."""
import asyncio
from pathlib import Path
from typing import Any, ClassVar

from inkwell.plugins.types.transcription import (
    TranscriptionPlugin,
    TranscriptionRequest,
)
from inkwell.transcription.models import Transcript


class WhisperTranscriber(TranscriptionPlugin):
    """Local transcription using OpenAI Whisper."""

    NAME: ClassVar[str] = "whisper"
    VERSION: ClassVar[str] = "1.0.0"
    DESCRIPTION: ClassVar[str] = "Local Whisper transcription (offline, GPU-accelerated)"

    CAPABILITIES: ClassVar[dict[str, Any]] = {
        "formats": ["mp3", "wav", "m4a", "mp4", "webm"],
        "max_duration_hours": None,
        "requires_internet": False,
        "supports_file": True,
        "supports_url": False,  # Requires downloaded file
        "supports_bytes": False,
    }

    def __init__(self, *, lazy_init: bool = False):
        super().__init__()
        self._model = None
        self._model_name = "base"  # Can be configured

    def configure(self, config: dict[str, Any], cost_tracker=None):
        """Configure with model size."""
        super().configure(config, cost_tracker)
        self._model_name = config.get("model", "base")

    def validate(self):
        """Check whisper is installed."""
        try:
            import whisper  # noqa: F401
        except ImportError:
            from inkwell.plugins.base import PluginValidationError
            raise PluginValidationError(
                self.NAME,
                ["openai-whisper not installed. Run: pip install openai-whisper"]
            )

    async def transcribe(self, request: TranscriptionRequest) -> Transcript:
        """Transcribe audio file using Whisper."""
        if request.source_type != "file":
            raise ValueError("Whisper plugin only supports local files")

        # Run CPU-intensive transcription in thread pool
        result = await asyncio.to_thread(
            self._transcribe_sync, request.file_path
        )

        return Transcript(
            text=result["text"],
            language=result.get("language", "en"),
        )

    def _transcribe_sync(self, file_path: Path) -> dict:
        """Synchronous transcription (runs in thread pool)."""
        import whisper

        if self._model is None:
            self._model = whisper.load_model(self._model_name)

        return self._model.transcribe(str(file_path))

    def estimate_cost(self, duration_seconds: float) -> float:
        """Whisper is free (local)."""
        return 0.0
```

---

## Output Plugins

Output plugins format extraction results for different destinations.

### Base Class

```python
from inkwell.plugins.types.output import OutputPlugin
```

### Required Methods

| Method | Return Type | Description |
|--------|-------------|-------------|
| `render()` | `str` | Convert result to formatted output |

### Class Attributes

```python
OUTPUT_FORMAT: ClassVar[str] = "Markdown"  # Human-readable name
FILE_EXTENSION: ClassVar[str] = ".md"      # Including dot
```

### Example: HTML Output Plugin

```python
"""HTML output plugin."""
from typing import Any, ClassVar

from inkwell.plugins.types.output import OutputPlugin
from inkwell.extraction.models import ExtractionResult


class HTMLOutput(OutputPlugin):
    """Generate HTML output files."""

    NAME: ClassVar[str] = "html"
    VERSION: ClassVar[str] = "1.0.0"
    DESCRIPTION: ClassVar[str] = "HTML file generation"

    OUTPUT_FORMAT: ClassVar[str] = "HTML"
    FILE_EXTENSION: ClassVar[str] = ".html"

    async def render(
        self,
        result: ExtractionResult,
        episode_metadata: dict[str, Any],
        include_frontmatter: bool = True,
    ) -> str:
        """Render extraction result as HTML."""
        title = episode_metadata.get("episode_title", "Episode Notes")
        podcast = episode_metadata.get("podcast_name", "Unknown Podcast")

        # Build HTML
        html_parts = [
            "<!DOCTYPE html>",
            "<html>",
            "<head>",
            f"  <title>{title}</title>",
            '  <meta charset="utf-8">',
            "  <style>",
            "    body { font-family: system-ui; max-width: 800px; margin: 0 auto; padding: 20px; }",
            "    .metadata { color: #666; font-size: 0.9em; }",
            "    blockquote { border-left: 3px solid #ccc; padding-left: 1em; margin-left: 0; }",
            "  </style>",
            "</head>",
            "<body>",
        ]

        if include_frontmatter:
            html_parts.extend([
                f'<p class="metadata">Podcast: {podcast}</p>',
                f'<p class="metadata">Template: {result.template_name}</p>',
            ])

        html_parts.extend([
            f"<h1>{result.template_name.replace('-', ' ').title()}</h1>",
            self._markdown_to_html(result.content),
            "</body>",
            "</html>",
        ])

        return "\n".join(html_parts)

    def _markdown_to_html(self, markdown: str) -> str:
        """Basic markdown to HTML conversion."""
        # In production, use a proper markdown library
        import re

        html = markdown

        # Headers
        html = re.sub(r"^### (.+)$", r"<h3>\1</h3>", html, flags=re.MULTILINE)
        html = re.sub(r"^## (.+)$", r"<h2>\1</h2>", html, flags=re.MULTILINE)
        html = re.sub(r"^# (.+)$", r"<h1>\1</h1>", html, flags=re.MULTILINE)

        # Bold and italic
        html = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html)
        html = re.sub(r"\*(.+?)\*", r"<em>\1</em>", html)

        # Paragraphs
        paragraphs = html.split("\n\n")
        html = "".join(f"<p>{p}</p>" for p in paragraphs if p.strip())

        return html
```

---

## Entry Point Registration

All plugins must be registered via entry points in `pyproject.toml`:

```toml
[project.entry-points."inkwell.plugins.extraction"]
openai = "my_package.extraction:OpenAIExtractor"

[project.entry-points."inkwell.plugins.transcription"]
whisper = "my_package.transcription:WhisperTranscriber"

[project.entry-points."inkwell.plugins.output"]
html = "my_package.output:HTMLOutput"
```

### Entry Point Groups

| Plugin Type | Entry Point Group |
|-------------|-------------------|
| Extraction | `inkwell.plugins.extraction` |
| Transcription | `inkwell.plugins.transcription` |
| Output | `inkwell.plugins.output` |

---

## Testing Your Plugin

After creating your plugin:

```bash
# Install in development mode
pip install -e .

# Verify plugin is discovered
inkwell plugins list

# Validate configuration
inkwell plugins validate whisper

# Test with real content
inkwell fetch URL --transcriber whisper
```

See [Testing Plugins](testing.md) for test utilities and best practices.

---

## Next Steps

1. Read [Plugin Lifecycle](lifecycle.md) for hooks details
2. Add [Configuration](configuration.md) with schema validation
3. Write tests using [Testing Utilities](testing.md)
4. [Publish to PyPI](publishing.md) when ready
