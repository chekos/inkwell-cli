# Changelog

All notable changes to Inkwell CLI will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.25.1] - 2026-07-20

### Fixed

- Preserve the non-secret `USER` environment value required for Claude Code to
  discover a macOS Keychain-backed subscription login while continuing to scrub
  API keys, tokens, cloud credentials, and unrelated environment values.
- Clarify that `runtime_not_authenticated` can mean the current sandbox cannot
  access the saved login, so users are not incorrectly told to authenticate
  again when the normal host CLI is already logged in.
- Accept Claude's documented terminal result when it reports a uniquely
  identifiable primary model plus auxiliary safe-mode model work, preserving
  every reported model and total token usage while rejecting ambiguous fallback.

## [0.25.0] - 2026-07-20

### Added

- Explicit Local Claude extraction through the separately installed and already
  authenticated Claude CLI with `--extractor claude-code`.
- Secret-free `claude --version` and `claude auth status --json` readiness,
  explicit requested/effective model provenance, subscription-limit billing
  state, runtime-aware caching, and an opt-in authenticated smoke.

### Security

- Local Claude runs only through bounded `claude -p` stdin in a private
  workspace with tools, MCP, customization, slash commands, and session
  persistence disabled.
- Anthropic API keys/tokens, setup tokens, cloud-provider selectors/credentials,
  and provider secrets are scrubbed so only Claude CLI's saved first-party
  subscription login can be used. The backend is explicit-only, local-only, and
  unavailable in hosted workers.

## [0.24.0] - 2026-07-20

### Added

- Explicit, local-only Codex CLI extraction through `--extractor codex` or
  `INKWELL_EXTRACTOR=codex`.
- Secret-free `inkwell plugins validate codex --json` readiness diagnostics and
  typed `inkwell plugins configure codex ...` settings.
- A provider-neutral local agent-runtime contract with bounded subprocess I/O,
  private workspaces, fail-closed tool controls, schema validation, cancellation,
  sanitized errors, and runtime/model provenance.
- Runtime-aware extraction cache keys and honest `runtime_managed` monetary
  state for subscription-backed work whose per-call USD amount is unknown.

### Security

- Codex child processes receive a scrubbed allowlisted environment, never a PTY
  or shell command, and receive prompts only through stdin.
- Codex remains opt-in and is never used by automatic provider routing or the
  hosted Modal worker. Inkwell does not inspect, copy, refresh, or broker Codex
  authentication state.

## [1.0.0] - 2025-11-13

### 🎉 v1.0.0 - Production Release

Complete implementation of podcast-to-markdown transformation with Obsidian integration.

### Added - Phase 5: Obsidian Integration & Polish

#### Interview Mode (Unit 2)
- Interactive interview mode with Claude Agent SDK
- `--interview` flag for CLI integration
- Three interview templates: reflective, analytical, creative
- Two output formats: structured, narrative
- Session persistence and resume capability
- Streaming responses with rich terminal UI
- Interview notes saved to `my-notes.md`

#### Wikilink Generation (Unit 3)
- Automatic `[[wikilink]]` generation from entities
- Entity extraction for books, people, tools, concepts
- Smart formatting with context preservation
- Configurable wikilink style (brackets, underscores)
- Integration with all markdown outputs

#### Smart Tag Generation (Unit 4)
- LLM-powered contextual tag generation
- Hierarchical tags support (`#parent/child`)
- Multi-level specificity (topic/subtopic/detail)
- Configurable tag count and style
- Integration with frontmatter

#### Dataview Integration (Unit 5)
- Dataview-compatible frontmatter in all markdown files
- Rich metadata: podcast, episode, date, duration, topics, people, tools, books
- 27 example Dataview queries in documentation
- Support for ratings, status tracking, and custom fields
- Query examples for discovery, analysis, and reporting

#### Error Handling & Retry Logic (Unit 6)
- Exponential backoff with jitter for API calls
- Automatic retry for transient failures (3 attempts)
- Specialized retry decorators for different operations
- Graceful degradation (YouTube → Gemini fallback)
- Comprehensive error classification
- Test-optimized retry configuration (305x speedup)

#### Cost Tracking System (Unit 7)
- Complete cost tracking for all LLM operations
- `inkwell costs` command with rich formatting
- Filtering by provider, operation, episode, date
- Cost breakdown by provider and operation
- Recent operations view
- Clear history functionality
- JSON-based persistence (`~/.config/inkwell/costs.json`)

#### E2E Testing Framework (Unit 8)
- Comprehensive E2E test suite (7 tests)
- 5 diverse test cases covering different content types:
  * Short Technical (15min, YouTube)
  * Long Interview (90min, Gemini)
  * Multi-Host Discussion (45min, YouTube)
  * Educational (30min, YouTube)
  * Storytelling (60min, Gemini)
- Simulation-based testing (fast, deterministic, no API costs)
- Output validation framework (files, frontmatter, wikilinks, tags)
- Benchmark aggregation and reporting
- Quality metrics with expected values

#### User Documentation (Unit 9)
- Complete user guide (300+ lines) - installation, commands, configuration
- Step-by-step tutorial (200+ lines) - 10-minute walkthrough
- Examples & workflows (250+ lines) - 15+ practical examples
- 6 workflow categories: daily processing, learning, knowledge base, cost optimization, batch operations, custom workflows
- Cost transparency throughout documentation
- Real-world podcast examples (Syntax FM, Huberman Lab, Tim Ferriss, etc.)

### Added - Phase 4: Interactive Interview

- Claude Agent SDK integration for interactive interviews
- Interview session management with context building
- Interview context builder with episode summarization
- Interview response formatting (structured and narrative)
- Session persistence and state management
- Rich terminal UI for interview display
- Resume capability for interrupted sessions

### Added - Phase 3: LLM Extraction

- Template-based LLM extraction system
- Multi-provider support (Gemini, Claude)
- Extraction engine with caching and cost tracking
- Template loader with YAML support
- Template selector for content-aware template selection
- Markdown generator with frontmatter, wikilinks, tags
- Output manager for file organization
- 6 default templates: summary, quotes, key-concepts, tools-mentioned, books-mentioned, people-mentioned
- Extraction cache to avoid redundant API calls
- Provider-specific extractors with retry logic

### Added - Phase 2: Transcription

- Multi-tier transcription system (Cache → YouTube → Gemini)
- YouTube transcript API integration (free)
- Google Gemini transcription fallback (paid)
- Audio downloader using yt-dlp
- Transcript cache with 30-day TTL
- Transcription manager for orchestration
- Cost confirmation before paid transcription
- `inkwell transcribe` command
- `inkwell cache` commands (stats, clear, clear-expired)
- Progress indicators with Rich terminal UI
- Metadata tracking (source, cost, duration, language)

### Added - Phase 1: Foundation

- Project scaffolding with uv build system
- Configuration management with Pydantic validation
- RSS/Atom feed parsing with authentication
- Secure credential encryption (Fernet)
- XDG Base Directory compliance
- CLI framework with Typer and Rich
- Logging system
- Comprehensive test suite (200+ tests)
- `inkwell add` - Add podcast feeds
- `inkwell list` - List configured feeds
- `inkwell remove` - Remove feeds
- `inkwell config` - Configuration management

### Changed

- README.md: Complete rewrite for v1.0.0 with all features
- Development status: Alpha (3) → Production/Stable (5)
- Version: 0.1.0 → 1.0.0
- Added classifiers: End Users/Desktop, Multimedia, Text Processing
- Improved CLI help text and command descriptions
- Enhanced error messages with actionable guidance
- Optimized test performance (retry tests: 305x speedup)
- Fixed 63 linting issues (imports, formatting, unused variables)

### Fixed

- Unused variable warnings in test files (4 instances)
- Import ordering and formatting (59 auto-fixes)
- Retry logic decorator inheritance (now uses DEFAULT_RETRY_CONFIG timing)
- Test configuration for fast execution

### Documentation

#### Developer Knowledge System (DKS)
- 27+ Architecture Decision Records (ADRs)
- 15+ Development logs documenting implementation
- 10+ Lessons learned documents with insights
- 3+ Research documents on technology decisions
- 3+ Experiment logs with benchmark results

#### User Documentation
- User Guide: Complete reference documentation
- Tutorial: 10-minute walkthrough for beginners
- Examples: 15+ practical workflows and automation scripts
- Dataview Queries: 27 example queries for Obsidian

### Performance

- Transcription: Multi-tier caching minimizes costs
- Extraction: Aggressive caching avoids redundant LLM calls
- Overall: ~2x realtime processing (30min episode in ~60min)
- Typical costs: $0.005-0.012 per episode (YouTube + extraction)

### Testing

- 200+ tests total
- Unit tests: 180+ covering all components
- Integration tests: 30+ for end-to-end workflows
- E2E tests: 7 validating complete pipeline
- Test coverage: Extensive across all modules

### Infrastructure

- Python 3.10+ support
- uv for package management
- Pre-commit hooks for code quality
- Ruff for linting and formatting
- mypy for type checking
- pytest for testing
- Rich for terminal UI

## [0.1.0] - Initial Development

### Added
- Initial project setup
- Basic CLI structure
- Configuration system foundation

---

**Legend:**
- 🎉 Major release
- ✨ New feature
- 🐛 Bug fix
- 📚 Documentation
- ⚡ Performance
- 🔧 Configuration
- 🧪 Testing
