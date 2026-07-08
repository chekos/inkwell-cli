# Summarize Roadmap Implementation

**Date:** 2026-07-07
**Author:** Codex

## Focus

Implement the active summarize-inspired CLI roadmap tracked in GitHub issue #102, starting with resolver documentation cleanup and provider capability metadata.

## Plan

- Refresh stale `InputResolver` documentation without changing behavior.
- Add typed provider capability metadata for transcription and extraction plugins.
- Surface provider capabilities in plugin listing output.
- Keep hosted web extraction fallbacks, OCR/image PDFs, and slides OCR outside this active implementation slice.

## Progress

- Started implementation on `codex/summarize-roadmap-foundation`.
- Confirmed #108 only requires documentation cleanup around `InputResolver` boundaries.
- Opened #110 implementation by reviewing plugin base classes, built-in providers, transcription policy, manager wiring, and plugin CLI output.
- Added typed transcription/extraction capability metadata and surfaced it in plugin listing output.
- Added token-aware extraction routing with provider/model-specific cache keys.
- Added explicit transcript, extraction, and media cache lifecycle controls.
- Added default-on short-content summary bypass with `--force-extraction`.
- Added local-only article extraction and text-only PDF extraction as source-text routes.
- Recorded the local source-text boundary in ADR 039.

## Observations

The existing transcription policy already gives provider fallback ordering a clean extension point. Capability metadata can inform that policy without changing today's default provider order.

Article and PDF ingestion fit the pipeline best as source text, not as new transcription attempts. That keeps media-specific fallbacks separate from document cleanup and lets `--extract` work as a clean source-text escape hatch.

## Links

- Epic: #102
- Issues: #103, #104, #106, #107, #108, #109, #110
