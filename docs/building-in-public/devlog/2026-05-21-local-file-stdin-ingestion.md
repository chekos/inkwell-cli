# Local File And Stdin Ingestion

**Date:** 2026-05-21
**Author:** Codex

## Focus

Implement Phase 6 of the summarize-inspired CLI evolution: let Inkwell ingest local audio/video files, local text/markdown files, and stdin without turning the CLI into a generic article/PDF/OCR summarizer.

## Plan

- Route local audio/video files through the existing transcription path.
- Route local `.txt` and `.md` files directly into extraction templates as source text.
- Route stdin text directly into extraction templates as source text.
- Preserve existing saved-feed and URL behavior.
- Keep PDF, web article extraction, OCR, and slide ingestion out of scope.
- Add focused tests and user-facing docs for the new input surfaces.

## Notes

This phase should continue to produce Inkwell-style structured knowledge notes. Local text/stdin are treated as already-clean source text for the same template extraction pipeline, not as generic summarizer inputs.

## Progress

- Started implementation on `codex/local-file-stdin-ingestion`.
- Routed local audio/video files through transcription without downloading through `yt-dlp`.
- Routed local `.txt`/`.md` files and stdin text into the existing template extraction pipeline as source text.
- Added explicit unsupported-local-file errors for PDF/article/OCR-style inputs.
- Documented local file/stdin usage and out-of-scope formats.
- Verified focused tests, formatting, linting, mypy, and the full test suite locally.

## Links

- Related devlog: `./2026-05-21-extract-only-mode.md`
- Related roadmap: `../../../2026-roadmap/03-universal-content-ingestion.md`
- PR: TBD
- Issue: TBD
