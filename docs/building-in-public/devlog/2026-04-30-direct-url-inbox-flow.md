# Rebuild Direct URL _inbox Flow

**Date:** 2026-04-30
**Author:** Diego

## Focus

Implement issue #60 by rebuilding direct URL captures so they route into `_inbox` by default, while keeping readable episode titles for URL-derived runs.

## Progress

- Updated metadata defaulting in `PipelineOrchestrator` to resolve podcast/title before `EpisodeMetadata` creation.
- Direct URL captures now default to podcast `_inbox` unless `--podcast-name` is provided.
- Added readable URL title extraction and fallback title (`Untitled capture`) for cases where URL paths are not informative.
- Extended YouTube URL resolution metadata to include optional episode title from yt-dlp and wired CLI fetch to pass it into pipeline options.
- Added tests for YouTube title pass-through, generic URL title derivation, fallback title behavior, and `--podcast-name` override behavior.

## Observations

The existing save-feed work already had the right pre-resolve hook (`resolve_youtube_url`), so adding episode title reuse was low-risk and avoided introducing a second yt-dlp query path.

## Next

Run targeted tests and open PR with `Closes #60` once green.

## Links

- Related ADR: `../adr/008-use-uv-for-python-tooling.md`
- PR: TBD
- Issue: #60
