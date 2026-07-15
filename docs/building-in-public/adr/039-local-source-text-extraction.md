---
title: ADR 039 - Local source-text extraction
adr:
  author: Codex
  created: 07-Jul-2026
  status: accepted
---

# ADR 039: Local source-text extraction

**Date:** 2026-07-07
**Status:** Accepted

## Context

Inkwell started as a podcast/media pipeline, but the same template extraction
and markdown output path is useful for short notes, web articles, and documents.
The active roadmap calls for local-only article extraction and text-only PDFs,
while deferring OCR/image PDFs and hosted article fallbacks.

The OCR deferral in this decision was later resolved by ADR 040. Hosted article
fallbacks and slide/video-frame extraction remain separate boundaries.

The key boundary is source text. Once source text is available, the existing
pipeline can skip media transcription and reuse template selection, extraction
caching, markdown output, interview mode, and machine-readable output.

## Decision

Add source-text extraction paths for:

1. Readable web article URLs, using local HTML fetch and `trafilatura` cleanup.
2. Local text PDFs, using `pypdf` selectable-text extraction.

These inputs become source text and bypass the transcription attempt policy.
They still run through normal template extraction unless `--extract` is used.

Keep these out of scope for now:

- hosted article extraction fallbacks for blocked or script-rendered pages
- OCR or image-only PDFs
- slide/deck OCR

## Consequences

- Direct YouTube and direct media inputs keep their existing transcription
  behavior.
- Generic HTTP(S) pages now route as article extraction and must return readable
  HTML.
- Local PDFs are accepted only when they contain selectable text.
- `--extract` now prints cleaned source text for article/PDF/text inputs, not
  only media transcripts.
- Machine-readable output can distinguish `article` and `pdf` input kinds.

## Alternatives Considered

1. Hosted extraction fallback first.
   - Pros: better success on blocked and script-rendered pages.
   - Cons: new service boundary, more error cases, and not needed for the first
     local CLI slice.
2. OCR PDFs in the same release.
   - Pros: handles scans and image-heavy documents.
   - Cons: larger dependency and performance surface; better handled as a
     separate issue.
3. Treat generic URLs as media pages until transcription fails.
   - Pros: preserves old direct URL behavior for some media landing pages.
   - Cons: ambiguous routing, more wasted transcription attempts, and weaker
     article support.

## References

- Epic: #102
- Article extraction issue: #104
- PDF extraction issue: #106
- Hosted fallback issue: #112
- OCR/image PDF issue: #111
