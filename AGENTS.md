# AGENTS.md

This file provides guidance to Codex when working in this repository.

## Project Overview

Inkwell is a CLI tool and small web app that transforms podcast episodes and
media URLs into structured, searchable Markdown notes. The Python pipeline
handles RSS/private-feed ingestion, direct URL ingestion, YouTube URL ingestion,
local image/PDF text extraction and OCR, transcription, LLM extraction, optional
interview capture, and Obsidian-friendly output. The web app lets signed-in users
paste URLs, run the Python pipeline
through a Modal worker, and save generated notes in Supabase.

Vision: transform passive podcast listening into active knowledge building by
capturing both what was said and what the user thought about it.

See `docs/_internal/prd.md` for complete product requirements.

## Tech Stack

Language and core:

- Python 3.10+
- CLI framework: `typer`
- Terminal output: `rich`
- Config: `pyyaml` and Pydantic settings
- Package/dependency management: `uv`

Podcast and source processing:

- RSS parsing: `feedparser`
- Audio download: `yt-dlp`
- Transcription: `youtube-transcript-api`, then `google-genai` / Gemini public
  YouTube URL and audio fallbacks
- Text, image, and PDF extraction for supported local inputs

LLM and AI:

- Content extraction: Claude and Gemini APIs plus explicit local Codex/Claude
  CLI backends
- Interview mode: Anthropic SDK via `AsyncAnthropic`
- Prompt-configured extraction templates in `src/inkwell/templates/`

Web app:

- Frontend: Next.js App Router in `apps/web/`
- Hosting/auth/data: Vercel and Supabase Auth/Postgres/RLS
- Worker: Modal in `workers/inkwell/`

System requirements:

- `ffmpeg` for audio processing
- Tesseract plus the `ocr` Python extra for optional local image/PDF OCR
- Google AI API key for Gemini transcription and fallback paths
- Anthropic API key for Claude extraction or interview mode
- Separately installed and authenticated Claude CLI for optional Local Claude
  extraction

## Development Setup

Install dependencies and hooks:

```bash
uv sync --dev
uvx pre-commit install
uvx pre-commit install --hook-type pre-push
```

If using the repo hook wrapper:

```bash
./.claude/hooks/install-git-hooks.sh
```

Run Python checks:

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

Format Python files:

```bash
uv run ruff format .
```

Run web checks from the repo root:

```bash
pnpm --dir apps/web test
pnpm --dir apps/web build
```

## Python Tooling

Always use `uv` for Python package management. Never use `pip install` or manual
virtualenv activation.

- `uv add <package>` adds a production dependency.
- `uv add --dev <package>` adds a dev dependency.
- `uv run <command>` runs commands in the project environment.
- `uv sync --dev` installs dependencies for local development.

See `docs/building-in-public/adr/008-use-uv-for-python-tooling.md`.

## Architecture

Core pipeline:

```text
RSS feed / direct URL / local source / local image or PDF
  -> parse or resolve source
  -> extract local source text or run local OCR when applicable
  -> check YouTube captions
  -> for public YouTube, try Gemini public URL fallback when captions/downloads fail
  -> download audio as final media fallback
  -> transcribe
  -> run LLM extraction templates
  -> optionally run interactive interview
  -> write Markdown output and metadata
```

Web import flow:

```text
Browser
  -> Next.js on Vercel
  -> Supabase source/import_jobs rows
  -> Modal Python worker
  -> shared Inkwell Python pipeline
  -> Supabase notes row
```

Key components:

- Feed management: add, list, rename, remove feeds with auth support.
- Source ingestion: RSS entries, direct URLs, YouTube URLs, local text/Markdown,
  images, selectable or image-based PDFs, local media, and stdin where supported.
- Transcription: YouTube transcripts, Gemini public YouTube URL fallback, Gemini
  audio fallback, and transcript caching.
- Extraction: YAML template selection, Claude/Gemini API routing, and explicit
  local Codex/Claude CLI backends.
- Interview: interactive Claude-powered reflective Q&A.
- Output: episode-scoped Markdown files with `.metadata.yaml`.
- Plugins: extraction, transcription, and output plugin registries.
- Web app: Supabase-backed import jobs, saved notes, and Modal dispatch.

Each processed episode creates a directory:

```text
podcast-name-YYYY-MM-DD-episode-title/
|-- .metadata.yaml
|-- _transcript.md
|-- summary.md
|-- quotes.md
|-- key-concepts.md
|-- [additional-template].md
`-- my-notes.md (if interview mode runs)
```

## Agentic Development Contract

Treat Inkwell as an agent-native product, not only a human CLI. Changes should
preserve these properties:

- Action parity: anything a user can do through the CLI or web UI should have a
  programmatic path an agent can call.
- Primitive capabilities: expose small operations and let prompts define the
  workflow.
- Shared workspace: generated notes, metadata, jobs, and saved notes should be
  visible to users and reusable by agents.
- Dynamic context: prompts should include available feeds, templates, output
  files, user preferences, job state, and relevant recent activity.
- Explicit completion: long-running agent loops should end through clear
  terminal state, not output-shape guessing.
- Verifiable output: every agent action should leave inspectable files, JSON,
  database rows, logs, tests, or command output.

## Local Agent Surfaces

Use existing APIs before scraping terminal output.

| User outcome | CLI surface | Programmatic surface |
| --- | --- | --- |
| Manage feeds | `inkwell add`, `inkwell rename`, `inkwell remove`, `inkwell list feeds --json` | `ConfigManager` |
| Inspect templates | `inkwell list templates --json` | `TemplateLoader` |
| Process source into notes | `inkwell fetch SOURCE --json` | `PipelineOrchestrator.process_episode()` |
| Transcribe only | `inkwell transcribe SOURCE --json` | `TranscriptionManager.transcribe()` |
| Inspect cache | `inkwell cache ...` | transcript, extraction, and media cache classes |
| Inspect costs | `inkwell costs ...` | `CostTracker` |
| Manage plugins | `inkwell plugins list/enable/disable/validate` | `PluginRegistry`, `PluginConfigManager` |

Agent-facing CLI behavior should:

- Route operational chatter to stderr when stdout carries structured data.
- Support `--json` for list, fetch, and transcription workflows where practical.
- Return stable schema fields before adding cosmetic display fields.
- Include paths to written files so agents can read back and verify results.
- Report cache hits, provider/model details, attempts, duration, and costs.
- Use nonzero exits for actionable failures.
- Avoid interactive prompts unless a noninteractive flag exists.

When adding a CLI action, add or update the matching programmatic API in the
same change. If no API exists, keep the CLI behavior easy to wrap and document
the gap in the PR.

## Cloud Agent Surfaces

The cloud path uses Supabase as the shared workspace and Modal as the only
runtime that executes media processing. Keep the Python pipeline authoritative;
do not reimplement pipeline behavior in TypeScript.

Cloud agent work should preserve:

- Durable state in `sources`, `import_jobs`, and `notes`.
- Owner-scoped mutations using `user_id` plus row id.
- Explicit terminal states: `succeeded`, `failed`, or `cancelled`.
- Idempotent result writes by `import_job_id`.
- Sanitized user-visible errors and detailed Modal logs.
- The YouTube fallback order: captions, Gemini public YouTube URL clips,
  Gemini audio fallback.

Hosted tools, if added, should be primitives such as `create_import_job`,
`read_import_job`, `update_import_job_stage`, `list_user_notes`, `read_note`,
`update_note`, `delete_note`, `run_pipeline_for_job`, and `complete_task`.

## Prompt-Native Behavior

Keep deterministic infrastructure in code:

- Authentication, path safety, and secret handling
- Rate limits and retry policies
- Atomic file writes and metadata integrity
- Schema validation and durable error codes
- Cost accounting and cache keys
- RLS and owner-scoped cloud mutations

Move editable behavior to templates or prompt files:

- Extraction instructions and quality criteria
- Interview style and question strategy
- Editorial category heuristics
- User-facing synthesis rules
- Agent workflow guidance

Behavior that should be adjustable as prose should not require a Python or
TypeScript refactor.

## Context Injection

Agents should not operate blindly. Build prompts from live state at session
start, and refresh context during long sessions when state can change.

Useful context for Inkwell:

- Configured feeds and display names
- Available extraction templates and template descriptions
- Selected source URL, source kind, title, podcast name, and episode date
- Existing output directory and generated files
- Transcript source, word count, media duration, and attempts
- Enabled plugins and active provider/transcriber overrides
- User preferences from config
- Cache status and estimated or actual costs
- Supabase source id, job id, job status/stage, and note id for web imports
- The capabilities available to the agent in user vocabulary

When a user says "fetch this", "make notes", "use the tech template", "add this
to my Obsidian notes", or "check my import", the agent should have enough
context to map that language to commands, templates, output paths, database
rows, and tools.

## Workspace And Safety

Generated notes are shared workspace artifacts. Read existing files before
overwriting user-editable Markdown. Use atomic writes for generated artifacts.
Keep ephemeral logs, checkpoints, and traces out of durable user content unless
the user asked for them.

Safety rules:

- Never print secrets or full auth configs.
- Do not expose `SUPABASE_SERVICE_ROLE_KEY`, `GOOGLE_API_KEY`,
  `ANTHROPIC_API_KEY`, or `INKWELL_WORKER_TOKEN` to the browser.
- Use Supabase service-role credentials only in trusted server/worker code.
- Keep RLS enabled for browser-visible tables.
- Keep destructive operations explicit and reversible where possible.
- Preserve user edits in generated Markdown.
- Redact private feed credentials and provider raw responses from logs.

## Documentation

User-facing documentation is built with MkDocs. Main sections:

- `docs/getting-started/`
- `docs/user-guide/`
- `docs/reference/`

Internal engineering knowledge lives in `docs/building-in-public/`.

Use the templates in that tree exactly:

- Devlog: `docs/building-in-public/devlog/YYYY-MM-DD-description.md`
- ADR: `docs/building-in-public/adr/NNN-decision-title.md`
- Research: `docs/building-in-public/research/topic-name.md`
- Lessons: `docs/building-in-public/lessons/YYYY-MM-DD-topic.md`

Keep evergreen docs free of temporal planning headings and open-ended task
lists. Put active priorities in issues, dated docs, or project updates.

## Testing Guidance

Let test scope match the blast radius:

- CLI JSON/schema behavior: focused CLI tests.
- Pipeline behavior: `uv run pytest` or targeted pipeline tests.
- Prompt/template behavior: rendering and outcome tests.
- Plugin behavior: discovery, validation, enable/disable persistence.
- Web behavior: `pnpm --dir apps/web test` and `pnpm --dir apps/web build`.
- Worker behavior: payload validation, Supabase mutations, and Modal smoke tests
  when dispatch or runtime behavior changes.
- Agentic parity: tests or review checklist entries proving each new user action
  has a programmatic path.

## Review Checklist

Use this checklist for agentic changes:

- User-facing actions have matching programmatic paths.
- New behavior is prompt/template-driven when prose should control it.
- Tools expose primitives, not hidden workflows.
- Agents can discover available resources without guessing.
- Outputs are shared, inspectable, and safe to overwrite only after reading.
- JSON output remains stable or is versioned.
- Supabase writes are owner-scoped and RLS remains enabled.
- Long-running work has durable progress and terminal state.
- Tests verify outcomes and failure modes.

## Releasing

Versions are managed through git tags via `dynamic = ["version"]` in
`pyproject.toml`.

```bash
gh release create v0.10.0 --generate-notes --title "v0.10.0 - Feature Name"
gh release create v0.10.1 --generate-notes --title "v0.10.1 - Bug Fixes"
```
