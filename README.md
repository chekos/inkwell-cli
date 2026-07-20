# Inkwell CLI

[![CI](https://github.com/chekos/inkwell-cli/actions/workflows/ci.yml/badge.svg)](https://github.com/chekos/inkwell-cli/actions/workflows/ci.yml)
[![Docs](https://github.com/chekos/inkwell-cli/actions/workflows/docs.yml/badge.svg)](https://github.com/chekos/inkwell-cli/actions/workflows/docs.yml)
[![PyPI](https://img.shields.io/pypi/v/inkwell-cli.svg)](https://pypi.org/project/inkwell-cli/)
[![Python](https://img.shields.io/pypi/pyversions/inkwell-cli.svg)](https://pypi.org/project/inkwell-cli/)
[![License](https://img.shields.io/badge/license-BSD--3--Clause-blue.svg)](LICENSE)

Transform podcast episodes into structured, searchable markdown notes for Obsidian.

**Inkwell** downloads audio from RSS feeds (including private/paid feeds), transcribes content, extracts key information through LLM processing, and optionally conducts an interactive interview to capture personal insights.

> **Vision:** Transform passive podcast listening into active knowledge building by capturing both *what was said* and *what you thought about it*.

## Status

Inkwell is beta software with the core podcast-to-markdown pipeline implemented and released on PyPI. The PyPI badge above reflects the current published release. The project has automated CI, branch protection, PyPI Trusted Publishing, MkDocs documentation, and a large regression suite.

Current health baseline:
- Podcast feed management with RSS and YouTube channel URL support
- Conservative input resolution for feeds, URLs, local files, stdin, direct media, and YouTube
- Multi-tier transcription: cache → YouTube transcripts → Gemini YouTube URL/audio fallback
- Transcript-only extraction for media workflows
- Local audio/video ingestion plus local text/markdown, image/PDF OCR, and stdin extraction
- Template-based LLM extraction with Claude/Gemini APIs plus explicit local
  Codex and Claude CLI backends
- Interactive interview mode
- Obsidian-friendly markdown with frontmatter, wikilinks, and tags
- JSON/plain output modes for scripting `fetch` and `transcribe`
- Plugin architecture for extraction, transcription, OCR, and output providers
- Cost tracking, cache observability, bounded media cache controls, retry logic, and structured errors
- 1,300+ tests with a measured 75%+ coverage gate

## Quick Start

### Installation

```bash
# Install as a CLI tool
uv tool install inkwell-cli
```

For local image or scanned-PDF OCR, install the optional extra and Tesseract:

```bash
uv tool install 'inkwell-cli[ocr]'
brew install tesseract  # macOS; use your OS package manager elsewhere
```

Inkwell is distributed as the `inkwell-cli` package on PyPI. `uv tool install`
is the recommended install path; Docker images and a Homebrew formula are not
currently provided.

### API Keys

```bash
# Set your API keys
export GOOGLE_API_KEY="your-gemini-api-key"
export ANTHROPIC_API_KEY="your-claude-api-key"  # Optional, for interview mode
```

### Process Your First Episode

```bash
# Add a podcast feed
inkwell add "https://feed.syntax.fm/rss" --feed-name syntax

# Process the latest episode
inkwell fetch syntax --latest

# Output:
# Processing: Modern CSS Features (Episode 789)
# Transcription: YouTube API (free) ✓
# Extraction:    Gemini Flash      ✓
# Templates:     4
# Cost:          $0.0055
# Output:        ~/inkwell-notes/syntax/modern-css-features/
# ✓ Complete!
```

That's it! You now have a structured markdown directory ready for Obsidian.

You can also start from one-off media, local files, or stdin:

```bash
# Process a YouTube or direct media URL
inkwell fetch https://youtube.com/watch?v=xyz
inkwell fetch https://example.com/episode.mp3

# Process local audio/video
inkwell fetch ~/Downloads/interview.mp3

# Process local text/markdown or pasted text
inkwell fetch ./notes.md
pbpaste | inkwell fetch -

# Process a local image or scanned PDF with local OCR
inkwell fetch ./whiteboard.png
inkwell fetch ./scanned-paper.pdf

# Get transcript text only
inkwell fetch https://youtube.com/watch?v=xyz --extract
```

## Features

### 🎙️ Smart Transcription

**Multi-tier transcription** that optimizes for cost and quality:
1. **Cache (Free)**: Check local cache first (30-day TTL)
2. **YouTube (Free)**: Extract existing captions/transcripts from YouTube videos, including non-English captions when English is unavailable
3. **Gemini YouTube URL (Preview)**: For public YouTube videos where cloud workers are blocked from captions or downloads, ask Gemini to process bounded clips directly from the public video URL
4. **Gemini Audio (Paid)**: Download audio and transcribe as the final fallback for non-YouTube sources or sources where URL-based video input is not available

**Result**: Most episodes cost $0.005-0.012 (YouTube + extraction)

### 🤖 LLM Content Extraction

**Template-based extraction** pulls structured information from transcripts:
- **Summary**: Episode overview with key topics
- **Quotes**: Memorable quotes with context
- **Key Concepts**: Main ideas and takeaways
- **Context-specific**: Tools mentioned, books referenced, people discussed, etc.

**Obsidian Features**:
- **Wikilinks**: Auto-generated `[[links]]` for entities (books, people, concepts)
- **Tags**: Smart tag generation using LLM (e.g., `#productivity`, `#ai`, `#health`)

### 🔎 Local Document OCR

Images and scanned PDFs can be read locally through the optional Tesseract OCR
plugin. Selectable PDF text is reused automatically; only pages without enough
text fall back to OCR. Source bytes stay on the machine and deterministic
provenance is recorded in `.metadata.yaml`. Normal note extraction can still
send the resulting text to the configured LLM; use `--extract` for local text
extraction without template or interview API calls.
- **Dataview**: Rich frontmatter for Obsidian Dataview queries

### 💬 Interactive Interview Mode

**Capture your thoughts** while the episode is fresh:

```bash
inkwell fetch syntax --latest --interview
```

Claude will ask you questions like:
- "What stood out most to you?"
- "How might you apply these ideas?"
- "What questions do you still have?"

Your responses are saved in `my-notes.md` within the episode directory.

### 💰 Cost Tracking

**Know exactly what you're spending**:

```bash
# View overall spending
inkwell costs

# View recent operations
inkwell costs --recent 10

# Filter by provider
inkwell costs --provider gemini --days 30

# See today's costs
inkwell costs --days 1
```

**Typical Costs**:
- YouTube + Gemini extraction: $0.005-0.012
- Public YouTube URL fallback + Gemini extraction: currently similar to YouTube + extraction while Gemini's YouTube URL input is in preview; pricing and limits may change
- Gemini transcription + extraction: $0.115-0.175
- **Recommendation**: Use YouTube when available (saves 95%)

### 📚 Obsidian Integration

Every episode output includes:

**Frontmatter** (Dataview-compatible):
```yaml
---
podcast: Syntax FM
episode: Modern CSS Features
episode_date: 2025-11-13
duration_minutes: 42
rating: null
topics: [css, web-development, frontend]
people: [Wes Bos, Scott Tolinski]
tools: [CSS Grid, Flexbox, Container Queries]
books: []
tags: [podcast, technical, web-development]
---
```

**Wikilinks**: Automatic `[[Entity]]` links for discoverability

**Tags**: Smart contextual tags (`#css`, `#web-development`, etc.)

**Dataview Support**: See the [Obsidian guide](./docs/user-guide/obsidian.md) for frontmatter, wikilinks, and Dataview usage.

### 🔄 Robust Error Handling

**Automatic retry** with exponential backoff:
- API failures: 3 attempts with backoff
- Rate limits: Intelligent retry timing
- Network errors: Automatic recovery
- Transient failures: Handled gracefully

**Graceful degradation**: If YouTube fails, falls back to Gemini

### 🧪 Comprehensive Testing

- **Unit Tests**: broad coverage across core modules
- **Integration Tests**: CLI and workflow behavior
- **E2E Tests**: 7 tests validating complete pipeline
- **Total**: 1,200+ tests with coverage reporting

**E2E Test Coverage**:
- 5 diverse content types (technical, interview, discussion, educational, storytelling)
- Duration range: 15-90 minutes
- Quality validation: Files, frontmatter, wikilinks, tags
- Cost benchmarking: Expected vs actual costs

## Documentation

### For Users

- **[Documentation Site](https://chekos.github.io/inkwell-cli/)**: Full user documentation
- **[Installation](./docs/getting-started/installation.md)**: Platform setup and dependencies
- **[Quick Start](./docs/getting-started/quickstart.md)**: Process your first episode
- **[CLI Reference](./docs/reference/cli-commands.md)**: Complete command reference
- **[Troubleshooting](./docs/reference/troubleshooting.md)**: Common issues and fixes

### For Developers

- **[Developer Knowledge System](./docs/building-in-public/index.md)**: Engineering notes
- **[Architecture Decision Records](./docs/building-in-public/adr/)**: Design decisions and rationale
- **[Development Logs](./docs/building-in-public/devlog/)**: Implementation journals
- **[Lessons Learned](./docs/building-in-public/lessons/)**: Retrospectives and insights
- **[Research Docs](./docs/building-in-public/research/)**: Technology research notes

## Basic Usage

### Feed Management

```bash
# Add a podcast
inkwell add "https://feed.syntax.fm/rss" --feed-name syntax

# Add with authentication
inkwell add "https://private.com/feed.rss" --feed-name premium --auth

# List your podcasts
inkwell list

# Remove a podcast
inkwell remove syntax
```

### Processing Episodes

```bash
# Process latest episode
inkwell fetch syntax --latest

# Process specific episode number
inkwell fetch syntax --episode 789

# Process multiple episodes
inkwell fetch syntax --episode 1-5

# Process with interview mode
inkwell fetch syntax --latest --interview

# Overwrite existing output
inkwell fetch syntax --latest --overwrite

# Use specific provider
inkwell fetch syntax --latest --provider claude
```

### Cost Management

```bash
# View all costs
inkwell costs

# View last 10 operations
inkwell costs --recent 10

# View by date range
inkwell costs --days 7

# Filter by provider
inkwell costs --provider gemini

# Filter by operation
inkwell costs --operation transcription

# Clear cost history
inkwell costs --clear
```

### Local Files, Stdin, And Transcript-Only Output

```bash
# Local audio/video routes through transcription
inkwell fetch ~/Downloads/interview.mp3

# Local text/markdown routes directly to extraction templates
inkwell fetch ./conference-notes.md --templates summary,key-concepts

# Stdin works the same way for already-clean source text
pbpaste | inkwell fetch -

# Transcript only, no structured extraction or note directory
inkwell fetch https://youtube.com/watch?v=xyz --extract

# Write transcript-only files and print their paths
inkwell fetch syntax --latest --extract --output-dir ~/transcripts --plain
```

Local PDFs and images enter the source-text path; image-based pages use optional
local OCR. Slide/video-frame extraction remains a separate capability.

### Machine-Readable Output

```bash
# JSON envelope to stdout; progress and warnings to stderr
inkwell fetch syntax --latest --json > result.json 2> progress.log
inkwell transcribe https://youtube.com/watch?v=xyz --json > transcript.json

# Terse stdout for shell scripts
inkwell fetch https://youtube.com/watch?v=xyz --plain
inkwell transcribe https://youtube.com/watch?v=xyz --plain
```

See the [machine-readable output reference](./docs/reference/machine-readable-output.md) for envelope examples and the stdout/stderr contract.

Local CLI users may explicitly delegate extraction to a separately installed
Codex or Claude CLI. Use `--extractor codex` for Local Codex extraction or
`--extractor claude-code` for Local Claude extraction after configuring and
validating an explicit model. Direct Claude/Gemini APIs remain the defaults and
the only hosted path. See [Local Codex Extraction](./docs/user-guide/local-codex-extraction.md)
and [Local Claude Extraction](./docs/user-guide/local-claude-extraction.md).

### Cache Management

```bash
# View cache stats
inkwell cache stats

# Clear cached transcripts
inkwell cache clear

# Clear expired cached transcripts
inkwell cache clear-expired
```

`inkwell cache stats` reports transcript, extraction, and media/audio caches. `clear` and `clear-expired` currently operate on transcript cache entries; media/audio retention is controlled by `cache.media.*`.

## Output Structure

Each processed episode creates a directory:

```
output/
└── podcast-name-YYYY-MM-DD-episode-title/
    ├── .metadata.yaml        # Episode metadata and cost tracking
    ├── summary.md           # Episode summary with frontmatter
    ├── quotes.md            # Memorable quotes with context
    ├── key-concepts.md      # Main ideas and concepts
    ├── tools-mentioned.md   # Tools, software, frameworks
    ├── books-mentioned.md   # Books and resources
    ├── people-mentioned.md  # People discussed
    └── my-notes.md          # Your interview responses (if --interview)
```

**Frontmatter** (all .md files):
```yaml
---
podcast: Syntax FM
episode: Modern CSS Features
episode_date: 2025-11-13
duration_minutes: 42
topics: [css, web-development]
people: [Wes Bos, Scott Tolinski]
tags: [podcast, technical, web-development]
---
```

**Wikilinks** embedded in content:
- Books: `[[Atomic Habits]]`
- People: `[[James Clear]]`
- Concepts: `[[Habit Stacking]]`

## Requirements

- **Python**: 3.10 or higher
- **ffmpeg**: Required for audio processing
- **API Keys**:
  - Google AI (Gemini) API key (required)
  - Anthropic (Claude) API key (optional, for interview mode)

## Configuration

Inkwell uses XDG Base Directory specifications:

- **Config**: `~/.config/inkwell/config.yaml`
- **Feeds**: `~/.config/inkwell/feeds.yaml`
- **Costs**: `~/.config/inkwell/costs.json`
- **Cache**: `~/.cache/inkwell/transcripts/`
- **Extraction Cache**: `~/.cache/inkwell/extractions/`
- **Media Cache**: `~/.cache/inkwell/audio/`
- **Logs**: `~/.local/state/inkwell/inkwell.log`

### Configuration Options

Edit `~/.config/inkwell/config.yaml`:

```yaml
version: "1"
log_level: INFO
default_output_dir: ~/inkwell-notes
max_episodes_per_run: 10

transcription:
  api_key: ""  # or use GOOGLE_API_KEY
  model_name: gemini-2.5-flash
  youtube_check: true

cache:
  media:
    enabled: true
    max_mb: 2048
    ttl_days: 30

extraction:
  default_provider: gemini  # or "claude"
  gemini_api_key: ""        # optional; falls back to transcription.api_key
  claude_api_key: ""        # or use ANTHROPIC_API_KEY

# Templates to enable
default_templates:
  - summary
  - quotes
  - key-concepts

# Obsidian features
obsidian:
  wikilinks: true
  tags: true
  dataview: true
```

### Editing Configuration

You can edit the configuration file directly using `inkwell config edit`:

```bash
# Edit config file in your default editor
inkwell config edit
```

**Supported Editors**: atom, code, ed, emacs, gedit, helix, kate, micro, nano, notepad, notepad++, nvim, subl, vi, vim

Set your preferred editor with the `EDITOR` environment variable:
```bash
export EDITOR=vim
inkwell config edit
```

For security reasons, only whitelisted editors are supported. If you need to use a different editor, you can edit the config file manually:
```bash
# View config location
inkwell config show

# Edit manually
nano ~/.config/inkwell/config.yaml
```

## Architecture

### High-Level Pipeline

```text
Feed / URL / local file / image / PDF / stdin → Resolve source
       → [saved feed] Parse episodes
       → [text/stdin] Treat as source text
       → [image/PDF] Extract selectable text or run local OCR
       → [media] Check transcript cache
       → [YouTube] Check YouTube captions
       → [YouTube only] Gemini public URL fallback
       → [Final fallback] Download or read media
       → Transcribe (YouTube captions or Gemini)
       → Extract Content (Template-based LLM)
       → Generate Wikilinks & Tags
       → [Optional] Interactive Interview
       → Generate Markdown Files
       → Save to Output Directory
```

### Key Components

1. **Feed Management** (`src/inkwell/feeds/`)
   - RSS/Atom parsing with authentication
   - Secure credential encryption

2. **Transcription** (`src/inkwell/transcription/`)
   - YouTube transcript extraction (free)
   - Gemini public YouTube URL fallback for cloud-IP blocking
   - Gemini audio fallback (paid)
   - Explicit attempt policy for fallback ordering
   - 30-day cache with TTL

3. **Extraction** (`src/inkwell/extraction/`)
   - Template-based LLM prompts
   - Multi-provider support (Gemini, Claude)
   - Context-aware extraction

4. **Output Generation** (`src/inkwell/output/`)
   - Markdown rendering
   - Wikilinks and tags
   - Dataview-compatible frontmatter

5. **Interview Mode** (`src/inkwell/interview/`)
   - Claude Agent SDK integration
   - Interactive Q&A with streaming
   - Personal insights capture

6. **Cost Tracking** (`src/inkwell/utils/costs.py`)
   - Per-operation cost calculation
   - JSON-based persistence
   - Filtering and aggregation

7. **Error Handling** (`src/inkwell/utils/retry.py`)
   - Exponential backoff with jitter
   - Automatic retry for transient failures
   - Graceful degradation

8. **Input Resolution** (`src/inkwell/ingestion/`)
   - Conservative source classification
   - Saved feed, URL, local file, image, PDF, stdin, direct media, and YouTube source kinds
   - Local article, image, and PDF source-text extraction with inspectable provenance

### Project Structure

```
inkwell-cli/
├── src/inkwell/              # Main package
│   ├── cli.py               # CLI entry point
│   ├── config/              # Configuration management
│   ├── feeds/               # RSS parsing
│   ├── ingestion/           # Input source classification
│   ├── transcription/       # Transcription system
│   ├── audio/               # Audio download
│   ├── extraction/          # LLM extraction (Phase 3)
│   ├── interview/           # Interview mode (Phase 4)
│   ├── plugins/             # Plugin APIs and discovery
│   ├── templates/           # Bundled extraction templates
│   └── utils/               # Utilities (costs, retry, etc.)
├── tests/                   # Test suite (1,200+ tests)
│   ├── unit/               # Unit tests
│   ├── integration/        # Integration tests
│   └── e2e/                # End-to-end tests
├── docs/                    # Documentation (DKS)
│   ├── getting-started/    # Installation and first-run docs
│   ├── user-guide/         # Feature documentation
│   ├── reference/          # CLI/config/template reference
│   └── building-in-public/ # ADRs, devlogs, lessons, research
└── 2026-roadmap/            # Strategic roadmap notes
```

## Development

### Setup Development Environment

```bash
# Install development dependencies
uv sync --dev

# Install pre-commit hooks
uv run pre-commit install

# Run tests
uv run pytest

# Run with coverage
uv run pytest --cov=src/inkwell --cov-report=term-missing --cov-report=html

# Run linting
uv run ruff check .

# Format code
uv run ruff format .

# Type checking
uv run mypy src/
```

### Running Tests

```bash
# Run all tests
uv run pytest

# Run specific test types
uv run pytest tests/unit/           # Unit tests
uv run pytest tests/integration/    # Integration tests
uv run pytest tests/e2e/            # E2E tests

# Run with verbose output
uv run pytest -v

# Run specific test file
uv run pytest tests/unit/test_costs.py -v
```

### Code Quality Standards

This project maintains high code quality:
- **Type hints**: Full coverage with mypy validation
- **Linting**: Ruff for code style
- **Workflow linting**: actionlint for GitHub Actions changes
- **Testing**: 1,200+ tests with coverage reporting
- **Documentation**: Comprehensive DKS documentation
- **Error handling**: Robust retry logic
- **Performance**: Benchmarked and optimized

## Release Automation

Inkwell uses a branch-and-release flow that fits solo development:

1. Build features on a branch and open a pull request.
2. Let CI run linting, formatting, mypy, tests with the coverage gate, and strict docs.
3. Merge to `main` when the feature set feels release-ready.
4. Create a GitHub release tag such as `v0.20.1`.
5. GitHub generates categorized release notes, builds the package with `uv`, and publishes to PyPI through Trusted Publishing.

Manual workflow runs publish to TestPyPI only, which keeps release rehearsals safe.

## Roadmap

### ✅ Phase 1: Foundation (Complete)

- ✅ Project scaffolding and build system
- ✅ Configuration management with encryption
- ✅ RSS feed parsing and validation
- ✅ CLI with rich terminal output
- ✅ Comprehensive test suite

### ✅ Phase 2: Transcription (Complete)

- ✅ YouTube transcript API integration
- ✅ Google Gemini fallback transcription
- ✅ Audio download with yt-dlp
- ✅ Transcript caching with TTL
- ✅ Multi-tier orchestration with cost optimization

### ✅ Phase 3: LLM Extraction (Complete)

- ✅ Template-based LLM prompts
- ✅ Content extraction (quotes, concepts, etc.)
- ✅ Markdown generation
- ✅ Metadata management
- ✅ Multi-provider support (Gemini, Claude)

### ✅ Phase 4: Interactive Interview (Complete)

- ✅ Claude Agent SDK integration
- ✅ Interactive Q&A mode with streaming
- ✅ Personal insights capture
- ✅ Interview transcript storage

### ✅ Phase 5: Obsidian Integration (Complete)

- ✅ Wikilink generation from entities
- ✅ Smart tag generation with LLM
- ✅ Dataview-compatible frontmatter
- ✅ Cost tracking system
- ✅ Error handling with retry logic
- ✅ E2E test framework
- ✅ Complete user documentation

### 🔮 Future Enhancements

- Custom templates and prompts
- Batch processing automation
- Export formats (PDF, HTML)
- Slide/video-frame extraction
- Token-aware model routing
- Web dashboard for management
- Mobile app integration
- Community template marketplace

## Contributing

We welcome contributions! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes with tests
4. Run tests and linting (`uv run pytest && uv run ruff check .`)
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

See [CLAUDE.md](./CLAUDE.md) for development guidelines.

## License

[BSD 3-Clause License](LICENSE) - See LICENSE file for details.

## Acknowledgments

**Core Libraries**:
- **typer**: CLI framework
- **rich**: Terminal formatting
- **pydantic**: Data validation
- **feedparser**: RSS/Atom parsing
- **yt-dlp**: Audio download
- **google-genai**: Gemini API
- **anthropic**: Claude API

**Special Thanks**:
- The Obsidian community for inspiration
- Claude (Anthropic) for development assistance
- All podcast creators who make great content

## Support

- **Issues**: [GitHub Issues](https://github.com/chekos/inkwell-cli/issues)
- **Documentation**: [chekos.github.io/inkwell-cli](https://chekos.github.io/inkwell-cli/)
- **Quick Start**: [docs/getting-started/quickstart.md](./docs/getting-started/quickstart.md)
- **User Guide**: [docs/user-guide/index.md](./docs/user-guide/index.md)
- **Reference**: [docs/reference/index.md](./docs/reference/index.md)

---

**Built with ❤️ for knowledge workers who love podcasts.**

*Transform passive listening into active learning.*
