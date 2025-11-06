# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Inkwell** is a CLI tool that transforms podcast episodes into structured, searchable markdown notes. It downloads audio from RSS feeds (including private/paid feeds), transcribes content, extracts key information through LLM processing, and optionally conducts an interactive interview to capture personal insights.

**Vision:** Transform passive podcast listening into active knowledge building by capturing both *what was said* and *what you thought about it*.

See [docs/PRD_v0.md](./docs/PRD_v0.md) for complete product requirements.

## Tech Stack

**Language & Core:**
- Python 3.10+
- CLI Framework: `typer`
- Terminal Output: `rich`
- Config: `pyyaml`

**Podcast Processing:**
- RSS Parsing: `feedparser`
- Audio Download: `yt-dlp`
- Transcription: `youtube-transcript-api` (primary), `google-generativeai` (fallback)

**LLM & AI:**
- Interview Mode: `claude-agent-sdk`
- Content Extraction: Claude/Gemini APIs

**System Requirements:**
- ffmpeg (required for audio processing)
- Google AI (Gemini) API key
- Anthropic (Claude) API key for interview mode

## Development Setup

**Note:** No code has been implemented yet. This section will be updated as the project develops.

Once implemented, typical commands will include:
```bash
# Development environment (TBD)
# python -m venv .venv && source .venv/bin/activate
# pip install -e ".[dev]"

# Testing (TBD)
# pytest

# Linting (TBD)
# ruff check .
```

## Architecture

### Core Pipeline Flow
```
RSS Feed → Parse → Check YouTube → Download Audio
         → Transcribe (YouTube API or Gemini)
         → LLM Extraction Pipeline
         → [Optional] Interactive Interview
         → Generate Markdown Files
         → Save to Output Directory
```

### Key Components (To Be Implemented)

1. **Feed Management** - Add/list/remove podcast feeds with auth support
2. **Transcription Layer** - YouTube transcript extraction → Gemini fallback
3. **LLM Extraction** - Template-based content extraction (quotes, concepts, etc.)
4. **Interview Mode** - Interactive Q&A using Claude Agent SDK
5. **Output Generation** - Structured markdown with Obsidian compatibility

### Output Structure
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

## Documentation: Developer Knowledge System (DKS)

This project uses a structured documentation system in `docs/`. You MUST use it.

### When Working on Tasks:

**During Development:**
- Create a devlog entry in `docs/devlog/YYYY-MM-DD-description.md` when starting new features
- Document implementation decisions, surprises, and next steps as you go
- Link to related ADRs and issues

**When Making Significant Decisions:**
- Create an ADR in `docs/adr/NNN-decision-title.md` (use next sequential number)
- Keep it brief - document the decision and rationale, not implementation details
- Reference any research docs that informed the decision

**When Researching Technologies:**
- Create research doc in `docs/research/topic-name.md` before making decisions
- Include findings, recommendations, and references to external sources
- Link research docs in subsequent ADRs

**After Completing Work:**
- Add lessons learned to `docs/lessons/YYYY-MM-DD-topic.md`
- Update any related ADRs if decisions changed during implementation

### Templates

All templates are in their respective directories:
- `docs/adr/000-template.md`
- `docs/devlog/YYYY-MM-DD-template.md`
- `docs/experiments/YYYY-MM-DD-template.md`
- `docs/research/template.md`
- `docs/lessons/YYYY-MM-DD-template.md`

**IMPORTANT:** Follow templates exactly. Keep ADRs brief to avoid hallucination.

### DKS Overview

See [docs/README.md](./docs/README.md) for full DKS documentation.

## Development Workflow

When implementing features:
1. **Start:** Create devlog entry for the feature
2. **Research:** Document any technology research in `docs/research/`
3. **Decide:** Create ADR for significant architectural decisions
4. **Experiment:** Record experiments/benchmarks in `docs/experiments/`
5. **Reflect:** Add lessons learned to `docs/lessons/` when complete
6. **Update:** Keep this CLAUDE.md updated as the architecture evolves
