# Inkwell CLI

Transform podcast episodes into structured, searchable markdown notes.

**Inkwell** downloads audio from RSS feeds (including private/paid feeds), transcribes content, extracts key information through LLM processing, and optionally conducts an interactive interview to capture personal insights.

> **Vision:** Transform passive podcast listening into active knowledge building by capturing both *what was said* and *what you thought about it*.

## Status

🎉 **Phase 2 Complete** - Full transcription pipeline ready!

Current capabilities:
- ✅ Podcast feed management (add, list, remove)
- ✅ RSS/Atom feed parsing with authentication
- ✅ Secure credential encryption
- ✅ Configuration management
- ✅ XDG-compliant paths
- ✅ **YouTube transcript extraction** (free, instant)
- ✅ **Audio download** with yt-dlp
- ✅ **Gemini transcription** (paid fallback)
- ✅ **Multi-tier transcription** (cache → YouTube → Gemini)
- ✅ **Transcript caching** (30-day TTL)
- ✅ **CLI transcription commands**

Coming in Phase 3:
- 🔄 LLM-based content extraction
- 🔄 Interactive interview mode with Claude
- 🔄 Markdown output generation

## Quick Start

### Installation

```bash
# Clone repository
git clone https://github.com/your-username/inkwell-cli.git
cd inkwell-cli

# Install dependencies using uv
uv sync --dev
```

### Basic Usage

#### Feed Management

```bash
# Add a podcast feed
inkwell add https://example.com/feed.rss --name my-podcast

# Add a feed with authentication
inkwell add https://private.com/feed.rss --name premium --auth

# List configured feeds
inkwell list

# Remove a feed
inkwell remove my-podcast

# View configuration
inkwell config show
```

#### Transcription

```bash
# Transcribe a YouTube video (free, uses YouTube transcripts)
inkwell transcribe https://youtube.com/watch?v=VIDEO_ID

# Transcribe any audio URL (downloads audio, uses Gemini)
inkwell transcribe https://example.com/podcast.mp3

# Save transcript to file
inkwell transcribe https://youtube.com/watch?v=VIDEO_ID --output transcript.txt

# Force re-transcription (bypass cache)
inkwell transcribe https://youtube.com/watch?v=VIDEO_ID --force

# Skip YouTube, use Gemini directly (for better quality)
inkwell transcribe https://youtube.com/watch?v=VIDEO_ID --skip-youtube
```

#### Cache Management

```bash
# View cache statistics
inkwell cache stats

# Clear all cached transcripts
inkwell cache clear

# Remove only expired transcripts
inkwell cache clear-expired
```

#### Help

```bash
# Get help
inkwell --help

# Get command-specific help
inkwell transcribe --help
inkwell cache --help
```

## Features

### Multi-Tier Transcription System

Inkwell uses an intelligent multi-tier transcription strategy that optimizes for both cost and quality:

1. **Cache (Free)**: Check local cache first (30-day TTL)
2. **YouTube Transcripts (Free)**: Extract existing transcripts from YouTube videos
3. **Gemini Transcription (Paid)**: Download audio and transcribe with Gemini API as fallback

**Key Features:**
- **Cost Optimization**: Always tries free methods first
- **Quality Control**: Gemini fallback ensures transcription always succeeds
- **Caching**: Avoids redundant API calls and downloads
- **Progress Indicators**: Real-time progress with Rich terminal UI
- **Cost Confirmation**: Interactive approval before spending money on Gemini
- **Metadata Tracking**: Records source, cost, duration, and language

### Secure Feed Management

- **RSS & Atom Support**: Works with any podcast RSS or Atom feed
- **Authentication**: Supports Basic Auth and Bearer tokens for private feeds
- **Encrypted Credentials**: All credentials encrypted at rest using Fernet symmetric encryption
- **Feed Categories**: Organize feeds with custom categories

### Smart Configuration

- **XDG Base Directory**: Configuration stored in standard locations (`~/.config/inkwell/`)
- **YAML Configuration**: Human-readable and editable config files
- **Validation**: Friendly error messages for configuration issues
- **Automatic Setup**: Creates default configuration on first run

### Developer Experience

- **Rich Terminal Output**: Colorful tables and formatted output using rich library
- **Helpful Error Messages**: Clear, actionable error messages
- **Type Safety**: Full type hints with mypy validation
- **Comprehensive Tests**: 313 tests with 100% pass rate

## Requirements

- **Python**: 3.10 or higher
- **ffmpeg**: Required for audio processing (Phase 2)
- **API Keys** (Phase 2):
  - Google AI (Gemini) API key for transcription
  - Anthropic (Claude) API key for interview mode

## Configuration

Inkwell uses XDG Base Directory specifications:

- **Config**: `~/.config/inkwell/config.yaml`
- **Feeds**: `~/.config/inkwell/feeds.yaml`
- **Encryption Key**: `~/.config/inkwell/.keyfile` (auto-generated)
- **Logs**: `~/.local/state/inkwell/inkwell.log`

### Configuration Options

Edit your configuration:

```bash
inkwell config edit
```

Example `config.yaml`:

```yaml
version: "1"
log_level: INFO
default_output_dir: ~/podcasts
youtube_check: true
max_episodes_per_run: 10
gemini_api_key: ""  # Added when needed
anthropic_api_key: ""  # Added when needed
```

### Feed Configuration

Feeds are stored in `feeds.yaml`:

```yaml
feeds:
  tech-podcast:
    url: https://example.com/feed.rss
    auth:
      type: none
    category: tech

  premium-show:
    url: https://private.com/feed.rss
    auth:
      type: basic
      username: <encrypted>
      password: <encrypted>
    category: interview
```

## Architecture

### Current Components (Phase 1-2)

1. **Feed Management**: Add/list/remove podcast feeds with auth support
2. **Configuration Layer**: YAML config with Pydantic validation
3. **Credential Encryption**: Fernet symmetric encryption for credentials
4. **RSS Parser**: Async feed fetching with feedparser
5. **CLI Interface**: Typer-based CLI with rich terminal output
6. **Transcription System**: Multi-tier transcription (Cache → YouTube → Gemini)
7. **Audio Downloader**: yt-dlp wrapper for audio extraction
8. **Transcript Cache**: Local caching with TTL management

### Transcription Pipeline (Implemented)

```
Episode URL
    ↓
[1] Check Cache (30-day TTL)
    ↓ (miss)
[2] Check if YouTube URL
    ↓ (yes)
    Extract YouTube Transcript (FREE)
    ↓ (no or fail)
[3] Download Audio (yt-dlp)
    ↓
[4] Transcribe with Gemini (PAID, with cost confirmation)
    ↓
[5] Cache Result
    ↓
Return Transcript + Metadata
```

### Planned Architecture (Phase 3+)

```
Transcript
    ↓
LLM Extraction Pipeline
    ↓
[Optional] Interactive Interview
    ↓
Generate Markdown Files
    ↓
Save to Output Directory
```

### Output Structure (Phase 2)

Each processed episode creates a directory:

```
podcast-name-YYYY-MM-DD-episode-title/
├── .metadata.yaml
├── summary.md
├── quotes.md
├── key-concepts.md
├── [context-specific].md  # tools-mentioned, books-mentioned, etc.
└── my-notes.md            # if --interview used
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

# Run linting
uv run ruff check .

# Format code
uv run ruff format .
```

### Project Structure

```
inkwell-cli/
├── src/inkwell/            # Main package
│   ├── cli.py             # CLI entry point
│   ├── config/            # Configuration management
│   │   ├── manager.py     # ConfigManager
│   │   ├── schema.py      # Pydantic models
│   │   ├── crypto.py      # Credential encryption
│   │   └── defaults.py    # Default configuration
│   ├── feeds/             # RSS parsing
│   │   ├── parser.py      # RSSParser
│   │   ├── models.py      # Episode model
│   │   └── validator.py   # Feed validation
│   ├── transcription/     # Transcription system (NEW in Phase 2)
│   │   ├── manager.py     # TranscriptionManager (orchestrator)
│   │   ├── youtube.py     # YouTubeTranscriber
│   │   ├── gemini.py      # GeminiTranscriber
│   │   ├── cache.py       # TranscriptCache
│   │   ├── models.py      # Transcript models
│   │   └── __init__.py    # Public API
│   ├── audio/             # Audio download (NEW in Phase 2)
│   │   └── downloader.py  # AudioDownloader (yt-dlp wrapper)
│   └── utils/             # Utilities
│       ├── paths.py       # XDG paths
│       ├── errors.py      # Custom exceptions
│       ├── display.py     # Terminal output helpers
│       └── logging.py     # Logging setup
├── tests/                 # Test suite (313 tests)
│   ├── unit/             # Unit tests
│   │   ├── audio/        # Audio tests
│   │   ├── transcription/ # Transcription tests
│   │   └── ...           # Other unit tests
│   └── integration/      # Integration tests
└── docs/                 # Documentation (DKS)
    ├── adr/              # Architecture Decision Records
    ├── devlog/           # Development logs
    ├── lessons/          # Lessons learned
    ├── research/         # Research notes
    └── experiments/      # Performance benchmarks
```

### Running Tests

```bash
# Run all tests
uv run pytest

# Run with verbose output
uv run pytest -v

# Run specific test file
uv run pytest tests/unit/test_config_manager.py

# Run with coverage
uv run pytest --cov=inkwell --cov-report=html
```

### Code Quality

```bash
# Type checking
uv run mypy src/

# Linting
uv run ruff check .

# Formatting
uv run ruff format .
```

## Documentation

This project uses a **Developer Knowledge System (DKS)** for comprehensive documentation:

- **ADRs** (`docs/adr/`): Architecture decisions and rationale
- **Devlogs** (`docs/devlog/`): Implementation journals
- **Lessons** (`docs/lessons/`): Retrospectives and insights
- **Research** (`docs/research/`): Technology research notes

See [docs/README.md](./docs/README.md) for full documentation.

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests (`make test`)
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

## License

[MIT License](LICENSE) - See LICENSE file for details.

## Roadmap

### Phase 1: Foundation ✅ (Complete)

- ✅ Project scaffolding and build system
- ✅ Configuration management with encryption
- ✅ RSS feed parsing and validation
- ✅ CLI with rich terminal output
- ✅ Comprehensive test suite (154 tests)

### Phase 2: Transcription ✅ (Complete)

- ✅ YouTube transcript API integration
- ✅ Google Gemini fallback transcription
- ✅ Audio download with yt-dlp
- ✅ Transcript caching and storage (30-day TTL)
- ✅ Multi-tier orchestration with cost optimization
- ✅ CLI commands (transcribe, cache)
- ✅ Test suite expanded (313 tests, 77% coverage)

### Phase 3: LLM Extraction

- 🔄 Template-based LLM prompts
- 🔄 Content extraction (quotes, concepts, etc.)
- 🔄 Markdown generation
- 🔄 Metadata management

### Phase 4: Interactive Interview

- 🔄 Claude Agent SDK integration
- 🔄 Interactive Q&A mode
- 🔄 Personal insights capture
- 🔄 Interview transcript storage

### Phase 5: Polish & Extensions

- 🔄 Obsidian integration
- 🔄 Batch processing
- 🔄 Custom templates
- 🔄 Export formats

## Acknowledgments

- **typer**: CLI framework
- **rich**: Terminal formatting
- **feedparser**: RSS/Atom parsing
- **pydantic**: Data validation
- **cryptography**: Fernet encryption

## Support

- **Issues**: [GitHub Issues](https://github.com/your-username/inkwell-cli/issues)
- **Documentation**: See `docs/` directory
- **PRD**: See [docs/PRD_v0.md](./docs/PRD_v0.md)

---

Built with ❤️ for knowledge workers who love podcasts.
