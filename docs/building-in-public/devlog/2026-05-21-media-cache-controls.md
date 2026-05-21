# Media Cache Controls

**Date:** 2026-05-21
**Author:** Codex

## Focus

Implement Phase 4 of the summarize-inspired CLI evolution: add bounded media/audio cache controls without changing transcript or extraction cache semantics.

## Plan

- Add `cache.media.enabled`, `cache.media.max_mb`, and `cache.media.ttl_days` to the config schema and generated default config.
- Apply TTL and size policy to the downloaded media/audio cache used by `AudioDownloader`.
- Wire the media cache config through CLI and pipeline transcription paths.
- Document the new configuration fields.
- Add focused tests for config defaults, cache eviction, disabled cache behavior, and transcription wiring.

## Notes

This phase should only govern downloaded media/audio files. Transcript cache keys, extraction cache keys, JSON/plain output, provider attempt policy, local file ingestion, and extract-only mode stay out of scope.

## Progress

- Started implementation on `codex/media-cache-controls`.
- Added media cache config schema/defaults and docs.
- Applied TTL/size/enabled policy to `AudioDownloader` while preserving existing cache behavior by default.
- Wired media cache config through CLI and pipeline transcription manager creation.
- Added focused tests for config defaults, media cache eviction, disabled cache behavior, and transcription wiring.
- Verified focused tests, formatting, linting, and the full test suite locally.

## Links

- Related devlog: `./2026-05-21-cache-key-observability.md`
- Related roadmap: `../../../2026-roadmap/03-universal-content-ingestion.md`
- PR: TBD
- Issue: TBD
