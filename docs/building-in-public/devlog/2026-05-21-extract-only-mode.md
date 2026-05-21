# Extract-Only Mode

**Date:** 2026-05-21
**Author:** Codex

## Focus

Implement Phase 5 of the summarize-inspired CLI evolution: add a narrow extract-only media flow that emits transcript text without structured extraction, interview capture, or default note-directory output.

## Plan

- Choose the smallest CLI surface that fits existing fetch/transcribe behavior.
- Reuse existing transcription, feed resolution, and progress/error patterns.
- For media URLs and saved feed episodes, emit transcript text only.
- Add optional file output without creating an episode note directory.
- Keep local files, stdin, text cleanup, PDF/web article extraction, cache-key changes, and provider attempt policy out of scope.
- Add focused tests for transcript-only behavior and compatibility.

## Notes

This is not a generic summarizer mode. It is a utility escape hatch for Inkwell media-learning workflows: get the transcript/clean source text, then decide what structured knowledge-note flow to run later.

## Progress

- Started implementation on `codex/extract-only-mode`.
- Added `inkwell fetch --extract` for transcript-only media extraction.
- Routed extract-only progress to stderr and transcript text to stdout by default.
- Added explicit `--output-dir` handling for `.transcript.md` files without creating episode note directories.
- Preserved saved-feed episode selection for extract-only mode.
- Rejected structured extraction/interview options when `--extract` is active.
- Documented the new flag and verified focused CLI tests, formatting, linting, and the full test suite locally.

## Links

- Related devlog: `./2026-05-21-media-cache-controls.md`
- Related roadmap: `../../../2026-roadmap/03-universal-content-ingestion.md`
- PR: TBD
- Issue: TBD
