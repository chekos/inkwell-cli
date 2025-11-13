# Inkwell CLI

Transform podcast episodes into structured, searchable markdown notes for Obsidian.

**Inkwell** downloads audio from RSS feeds (including private/paid feeds), transcribes content, extracts key information through LLM processing, and optionally conducts an interactive interview to capture personal insights.

> **Vision:** Transform passive podcast listening into active knowledge building by capturing both *what was said* and *what you thought about it*.

## Status

🎉 **v1.0.0 - Production Ready!**

All core features implemented and thoroughly tested:
- ✅ Podcast feed management (add, list, remove)
- ✅ Multi-tier transcription (YouTube → Gemini)
- ✅ LLM-based content extraction with templates
- ✅ Interactive interview mode with Claude
- ✅ Obsidian integration (wikilinks, tags, Dataview)
- ✅ Cost tracking and optimization
- ✅ Error handling with retry logic
- ✅ Comprehensive E2E testing
- ✅ Complete user documentation

## Quick Start

### Installation

```bash
# Clone repository
git clone https://github.com/your-username/inkwell-cli.git
cd inkwell-cli

# Install dependencies using uv
uv sync --dev
```

### API Keys

```bash
# Set your API keys
export GOOGLE_API_KEY="your-gemini-api-key"
export ANTHROPIC_API_KEY="your-claude-api-key"  # Optional, for interview mode
```

### Process Your First Episode

```bash
# Add a podcast feed
uv run inkwell add "https://feed.syntax.fm/rss" --name syntax

# Process the latest episode
uv run inkwell fetch syntax --latest

# Output:
# Processing: Modern CSS Features (Episode 789)
# Transcription: YouTube API (free) ✓
# Extraction:    Gemini Flash      ✓
# Templates:     4
# Cost:          $0.0055
# Output:        ./output/syntax-2025-11-13-modern-css-features/
# ✓ Complete!
```

That's it! You now have a structured markdown directory ready for Obsidian.

## Features

### 🎙️ Smart Transcription

**Multi-tier transcription** that optimizes for cost and quality:
1. **Cache (Free)**: Check local cache first (30-day TTL)
2. **YouTube (Free)**: Extract existing transcripts from YouTube videos
3. **Gemini (Paid)**: Download audio and transcribe as fallback (~$0.115/episode)

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
- **Dataview**: Rich frontmatter for Obsidian Dataview queries

### 💬 Interactive Interview Mode

**Capture your thoughts** while the episode is fresh:

```bash
uv run inkwell fetch syntax --latest --interview
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
uv run inkwell costs

# View recent operations
uv run inkwell costs --recent 10

# Filter by provider
uv run inkwell costs --provider gemini --days 30

# See today's costs
uv run inkwell costs --days 1
```

**Typical Costs**:
- YouTube + Gemini extraction: $0.005-0.012
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

**Dataview Queries**: See [docs/dataview-queries.md](./docs/dataview-queries.md) for 27 example queries

### 🔄 Robust Error Handling

**Automatic retry** with exponential backoff:
- API failures: 3 attempts with backoff
- Rate limits: Intelligent retry timing
- Network errors: Automatic recovery
- Transient failures: Handled gracefully

**Graceful degradation**: If YouTube fails, falls back to Gemini

### 🧪 Comprehensive Testing

- **Unit Tests**: 180+ tests covering all components
- **Integration Tests**: 30+ tests for end-to-end workflows
- **E2E Tests**: 7 tests validating complete pipeline
- **Total**: 200+ tests with extensive coverage

**E2E Test Coverage**:
- 5 diverse content types (technical, interview, discussion, educational, storytelling)
- Duration range: 15-90 minutes
- Quality validation: Files, frontmatter, wikilinks, tags
- Cost benchmarking: Expected vs actual costs

## Documentation

### For Users

- **[Tutorial](./docs/tutorial.md)**: 10-minute walkthrough for beginners
- **[User Guide](./docs/user-guide.md)**: Complete reference documentation
- **[Examples & Workflows](./docs/examples.md)**: Common use cases and automation
- **[Dataview Queries](./docs/dataview-queries.md)**: 27 example Obsidian queries

### For Developers

- **[Developer Knowledge System](./docs/README.md)**: Complete DKS overview
- **[Architecture Decision Records](./docs/adr/)**: Design decisions and rationale
- **[Development Logs](./docs/devlog/)**: Implementation journals
- **[Lessons Learned](./docs/lessons/)**: Retrospectives and insights
- **[Research Docs](./docs/research/)**: Technology research notes

## Basic Usage

### Feed Management

```bash
# Add a podcast
uv run inkwell add "https://feed.syntax.fm/rss" --name syntax

# Add with authentication
uv run inkwell add "https://private.com/feed.rss" --name premium --auth

# List your podcasts
uv run inkwell list

# Remove a podcast
uv run inkwell remove syntax
```

### Processing Episodes

```bash
# Process latest episode
uv run inkwell fetch syntax --latest

# Process specific episode number
uv run inkwell fetch syntax --episode 789

# Process multiple episodes
uv run inkwell fetch syntax --count 5

# Process with interview mode
uv run inkwell fetch syntax --latest --interview

# Overwrite existing output
uv run inkwell fetch syntax --latest --overwrite

# Use specific provider
uv run inkwell fetch syntax --latest --provider claude
```

### Cost Management

```bash
# View all costs
uv run inkwell costs

# View last 10 operations
uv run inkwell costs --recent 10

# View by date range
uv run inkwell costs --days 7

# Filter by provider
uv run inkwell costs --provider gemini

# Filter by operation
uv run inkwell costs --operation transcription

# Clear cost history
uv run inkwell costs --clear
```

### Cache Management

```bash
# View cache stats
uv run inkwell cache stats

# Clear all cache
uv run inkwell cache clear

# Clear expired only
uv run inkwell cache clear-expired
```

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
- **Logs**: `~/.local/state/inkwell/inkwell.log`

### Configuration Options

Edit `~/.config/inkwell/config.yaml`:

```yaml
version: "1"
log_level: INFO
default_output_dir: ./output
default_provider: gemini  # or "claude"
youtube_check: true
max_episodes_per_run: 10

# Optional API keys (or use environment variables)
gemini_api_key: ""
anthropic_api_key: ""

# Templates to enable
templates_enabled:
  - summary
  - quotes
  - key-concepts
  - tools-mentioned
  - books-mentioned
  - people-mentioned

# Obsidian features
wikilinks_enabled: true
tags_enabled: true
dataview_frontmatter: true
```

### Editing Configuration

You can edit the configuration file directly using `inkwell config edit`:

```bash
# Edit config file in your default editor
uv run inkwell config edit
```

**Supported Editors**: atom, code, ed, emacs, gedit, helix, kate, micro, nano, notepad, notepad++, nvim, subl, vi, vim

Set your preferred editor with the `EDITOR` environment variable:
```bash
export EDITOR=vim
uv run inkwell config edit
```

For security reasons, only whitelisted editors are supported. If you need to use a different editor, you can edit the config file manually:
```bash
# View config location
uv run inkwell config show

# Edit manually
nano ~/.config/inkwell/config.yaml
```

## Architecture

### High-Level Pipeline

```
RSS Feed → Parse Episodes → Check YouTube → Download Audio
       → Transcribe (YouTube or Gemini)
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
   - Gemini API fallback (paid)
   - 30-day cache with TTL

3. **Extraction** (`src/inkwell/extraction/`)
   - Template-based LLM prompts
   - Multi-provider support (Gemini, Claude)
   - Context-aware extraction

4. **Obsidian Integration** (`src/inkwell/obsidian/`)
   - Wikilink generation from entities
   - Smart tag generation with LLM
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

### Project Structure

```
inkwell-cli/
├── src/inkwell/              # Main package
│   ├── cli.py               # CLI entry point
│   ├── config/              # Configuration management
│   ├── feeds/               # RSS parsing
│   ├── transcription/       # Transcription system
│   ├── audio/               # Audio download
│   ├── extraction/          # LLM extraction (Phase 3)
│   ├── obsidian/            # Obsidian integration (Phase 5)
│   ├── interview/           # Interview mode (Phase 4)
│   └── utils/               # Utilities (costs, retry, etc.)
├── tests/                   # Test suite (200+ tests)
│   ├── unit/               # Unit tests
│   ├── integration/        # Integration tests
│   └── e2e/                # End-to-end tests
├── docs/                    # Documentation (DKS)
│   ├── adr/                # Architecture decisions
│   ├── devlog/             # Development logs
│   ├── lessons/            # Lessons learned
│   ├── research/           # Research notes
│   ├── experiments/        # Benchmarks
│   ├── user-guide.md       # Complete user reference
│   ├── tutorial.md         # 10-minute tutorial
│   ├── examples.md         # Workflows and examples
│   └── dataview-queries.md # Obsidian Dataview examples
└── templates/               # LLM extraction templates
    ├── summary.md
    ├── quotes.md
    ├── key-concepts.md
    └── ...
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
uv run pytest --cov=inkwell --cov-report=html

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
- **Testing**: 200+ tests with extensive coverage
- **Documentation**: Comprehensive DKS documentation
- **Error handling**: Robust retry logic
- **Performance**: Benchmarked and optimized

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

[MIT License](LICENSE) - See LICENSE file for details.

## Acknowledgments

**Core Libraries**:
- **typer**: CLI framework
- **rich**: Terminal formatting
- **pydantic**: Data validation
- **feedparser**: RSS/Atom parsing
- **yt-dlp**: Audio download
- **google-generativeai**: Gemini API
- **anthropic**: Claude API
- **claude-agent-sdk**: Interactive interview mode

**Special Thanks**:
- The Obsidian community for inspiration
- Claude (Anthropic) for development assistance
- All podcast creators who make great content

## Support

- **Issues**: [GitHub Issues](https://github.com/your-username/inkwell-cli/issues)
- **Documentation**: See `docs/` directory
- **Tutorial**: [docs/tutorial.md](./docs/tutorial.md)
- **User Guide**: [docs/user-guide.md](./docs/user-guide.md)
- **Examples**: [docs/examples.md](./docs/examples.md)

---

**Built with ❤️ for knowledge workers who love podcasts.**

*Transform passive listening into active learning.*
