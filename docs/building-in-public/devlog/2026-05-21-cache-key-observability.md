# Cache Key And Observability Cleanup

**Date:** 2026-05-21
**Author:** Codex

## Focus

Implement Phase 3 of the summarize-inspired CLI evolution: make cache formats explicit, improve extraction cache key inputs, and expose broader cache observability without changing media retention policy yet.

## Plan

- Add explicit cache format version constants for transcript and extraction caches.
- Extend extraction cache keys with transcript hash, template identity, provider/model, prompt/template hash, and output schema version.
- Preserve existing cache files as safe misses when new key metadata is used.
- Expand cache stats so `inkwell cache stats` can report transcript, extraction, and audio/media cache sections.
- Keep TTL/size enforcement for media cache out of scope for the next phase.

## Notes

This phase should be a compatibility cleanup, not a cache eviction feature. Existing transcript and extraction entries must not be rewritten or corrupted just because key inputs changed.

## Progress

- Added explicit cache format version constants for transcript, extraction, and audio/media caches.
- Extended extraction cache keys with versioned metadata for transcript hash, template identity, provider/model, prompt hash, and output schema identity.
- Added cache stats for extraction and media caches alongside existing transcript cache stats.
- Documented the expanded `inkwell cache stats` output in the CLI reference.
- Verified focused cache/CLI tests and the full test suite locally.

## Links

- Related devlog: `./2026-05-21-machine-readable-output.md`
- Related roadmap: `../../../2026-roadmap/03-universal-content-ingestion.md`
- PR: #90
- Issue: TBD
