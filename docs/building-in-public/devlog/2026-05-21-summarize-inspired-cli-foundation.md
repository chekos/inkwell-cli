# Summarize-Inspired CLI Foundation

**Date:** 2026-05-21
**Author:** Codex

## Focus

Start the first phase of the summarize-inspired CLI evolution by adding a conservative input-resolution foundation without changing Inkwell's core identity or feed behavior.

## Progress

- Read the summarize architecture research, universal ingestion roadmap, multi-export roadmap, CLI, pipeline, transcription, extraction, cache, and audio downloader code.
- Scoped this pass to Phase 1: `InputResolver` / `ContentSource` models, CLI classification cleanup, and focused unit tests.
- Added `src/inkwell/ingestion/` with conservative source kinds for saved feeds, URLs, local files, stdin, direct media, YouTube, and unknown URLs.
- Wired `inkwell fetch` to use the resolver for URL normalization/classification while keeping `ConfigManager.get_feed()` as the authority for saved-feed lookup.
- Added tests for resolver behavior and fetch handling of recognized-but-not-yet-routed local file/stdin inputs.
- Preserved later phases as follow-up work: machine-readable output, cache key migration, media cache policy, extract-only mode, local/stdin ingestion routing, and provider attempt policy.

## Observations

The current `fetch` command already has several careful direct-URL behaviors, especially YouTube pre-resolution and `--save-feed` validation. The safest foundation is a small classification layer that makes those decisions explicit while leaving RSS episode selection and pipeline processing untouched.

## Next

Move to Phase 2: add machine-readable output modes for `fetch` and `transcribe`, with primary JSON/plain output on stdout and progress/warnings on stderr.

## Links

- Related research: summarize CLI architecture analysis from task context
- Related roadmap: `../../../2026-roadmap/03-universal-content-ingestion.md`
- Related roadmap: `../../../2026-roadmap/09-multi-export-system.md`
- PR: TBD
- Issue: TBD
