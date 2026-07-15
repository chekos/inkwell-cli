---
title: ADR 040 - Local OCR and document images
adr:
  author: Codex
  created: 15-Jul-2026
  status: accepted
  extends: [039-local-source-text-extraction]
---

# ADR 040: Local OCR and document images

**Date:** 2026-07-15
**Status:** Accepted

## Context

Inkwell's source-text pipeline already accepts selectable PDFs, but scans and
local images have no text layer. The CLI needs to handle private documents
without requiring a hosted account, permanent remote storage, or a second note
pipeline. OCR engines and PDF renderers also add large native dependency and
resource surfaces that should not burden users who only process media or text.

## Decision

Add OCR as an optional Inkwell plugin type and ship a built-in Tesseract plugin.
Use Pillow for image normalization and PDFium through `pypdfium2` for bounded,
page-at-a-time PDF rendering. Keep these Python packages in an `ocr` extra and
require the local Tesseract executable separately.

PDFs use selectable text first. In `auto` mode, only thin, empty, or unreadable
pages fall back to local OCR; `always` and `never` expose explicit overrides.
Images always require OCR. Both routes become source text and reuse the existing
pipeline, templates, markdown output, JSON output, interview support, and plugin
discovery.

OCR records deterministic source, text, page, engine, confidence, orientation,
and render provenance. It fails on untrustworthy results unless selectable text
is available as a safe fallback. Hosted document storage and hosted OCR are not
part of this decision.

## Consequences

- Base installs remain lean; image/scanned-PDF users install the `ocr` extra and
  Tesseract.
- Original document bytes stay local during OCR. Structured extraction can
  still send resulting text to the configured LLM, matching every other source.
- PDF page count, render pixels, OCR timeout, and confidence are bounded to
  avoid uncontrolled local resource use or uncertain durable notes.
- Third parties can add OCR engines through the same entry-point contract as
  extraction, transcription, and output plugins.
- Slide decks and video-frame OCR remain separate because they require temporal
  sampling and presentation-specific semantics.

## Alternatives Considered

1. Bundle a neural OCR model in the base package.
   - Pros: no system binary and potentially stronger layout understanding.
   - Cons: much larger downloads, model lifecycle complexity, and hardware
     variance for a feature many users never need.
2. Use Poppler for PDF rendering.
   - Pros: mature and familiar command-line tooling.
   - Cons: another system package and subprocess surface; PDFium has maintained
     wheels and an in-process page renderer.
3. Use hosted OCR and remote document storage.
   - Pros: centralized dependencies and scalable compute.
   - Cons: violates the settled CLI-first privacy and account-free boundary.

## References

- Epic: #102
- OCR/image PDF issue: #111
- Local source-text foundation: ADR 039
