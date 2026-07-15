# Supported Inputs

Inkwell is still a structured knowledge-note tool for podcast and media learning workflows. The CLI now accepts more source shapes, but they all route into either transcription, template extraction, Obsidian-friendly note output, or the narrow transcript-only escape hatch.

---

## Input Matrix

| Input | Example | Status | Route | Primary output |
|-------|---------|--------|-------|----------------|
| Saved feed | `inkwell fetch syntax --latest` | Supported | RSS feed selection, then episode media processing | Structured episode note directory |
| YouTube video URL | `inkwell fetch https://youtube.com/watch?v=abc` | Supported | YouTube metadata, captions, Gemini URL fallback, then audio fallback | Structured episode note directory |
| YouTube channel URL | `inkwell add https://youtube.com/@creator --feed-name creator` | Supported for feed add | Resolved to YouTube media RSS | Saved feed |
| Direct media URL | `inkwell fetch https://example.com/episode.mp3` | Supported | Media transcription, then extraction templates | Structured episode note directory |
| Web article URL | `inkwell fetch https://example.com/article` | Supported for readable HTML pages | Local HTML fetch and cleanup, then extraction templates | Structured source note directory |
| Local audio/video | `inkwell fetch ~/Downloads/interview.mp3` | Supported | Local file transcription through Gemini | Structured episode note directory |
| Local text/markdown | `inkwell fetch ./notes.md` | Supported | Existing text is treated as source text for extraction templates | Structured episode note directory |
| Local PDF | `inkwell fetch ./paper.pdf` | Supported; OCR extra required for image-based pages | Selectable text first, then local per-page OCR fallback | Structured source note directory |
| Local image | `inkwell fetch ./whiteboard.png` | Supported with OCR extra | Local OCR, then extraction templates | Structured source note directory |
| Stdin text | `inkwell fetch - < notes.txt` | Supported | Stdin is treated as source text for extraction templates | Structured episode note directory |
| Transcript/source-text only | `inkwell fetch URL --extract` | Supported | Transcription or local source extraction only | Transcript/source text or `.transcript.md` file |
| Slide decks/video frames | `inkwell fetch deck.pptx` | Not supported yet | Planned separately | None |
| Non-HTTP URL schemes | `inkwell fetch ftp://example.com/file.mp3` | Not supported | Rejected as unknown URL | None |

---

## What Counts As Media

Direct media detection is conservative. Inkwell recognizes common audio/video extensions such as:

```text
.aac .aif .aiff .avi .flac .m4a .m4v .mkv .mov .mp3 .mp4
.mpeg .mpg .oga .ogg .opus .wav .webm
```

Generic HTTP(S) pages that do not look like YouTube or direct media are treated as article URLs and must return readable HTML.

---

## Local Text, Articles, Images, PDFs, And Stdin

Local `.txt` and `.md` files, web articles, PDFs, images, and stdin are treated
as source text. They skip media transcription and go through the same extraction
templates used for podcast transcripts.

```bash
inkwell fetch ./conference-notes.md --templates summary,key-concepts
inkwell fetch ./paper.pdf --templates summary,key-concepts
inkwell fetch ./whiteboard.png --templates summary,key-concepts
inkwell fetch https://example.com/article --templates summary,quotes
pbpaste | inkwell fetch - --templates summary,quotes
```

Article extraction is local-only: Inkwell fetches HTML and cleans readable text on your machine. Blocked, script-rendered, or very thin pages fail clearly; hosted extraction fallbacks are tracked separately for later.

PDF extraction checks every page for selectable text. In the default `auto`
mode, pages with enough text stay on the fast `pypdf` path and thin, empty, or
unreadable pages render locally through PDFium and Tesseract. `always` forces
OCR for every page; `never` disables OCR and accepts selectable text only.

```bash
inkwell fetch ./scan.pdf --ocr-mode auto
inkwell fetch ./scan.pdf --ocr-mode always --ocr-language eng+spa
inkwell fetch ./text-paper.pdf --ocr-mode never
```

Supported image inputs are PNG, JPEG, TIFF, BMP, GIF, WebP, and PNM-family
files. EXIF orientation is normalized first; Tesseract orientation detection
can then rotate readable text before extraction. Multipage PDFs are processed
one page at a time.

Local OCR requires the `ocr` package extra, a Tesseract executable on `PATH`,
and any requested Tesseract language data. Missing pieces fail with install
commands instead of silently switching to a hosted service.

Source image/PDF bytes are never uploaded by OCR. Inkwell records the source
hash, extracted-text hash, page method, confidence, orientation correction,
render DPI, OCR engine/version, and language under `custom_fields.source_extraction`
in `.metadata.yaml`. Normal structured extraction may send the extracted text
to the configured Claude or Gemini API. Use `--extract` to print or write the
locally extracted text without template or interview calls.

Limits are deliberate: PDFs are capped at 250 pages for OCR, standalone images
and rendered pages are bounded to 40 million pixels (PDFs render at up to 300
DPI), each OCR call has a 120-second timeout, and results below 30% mean word
confidence fail unless `auto` mode can retain selectable text. Handwriting,
unusual layouts, low-resolution scans, and missing language packs can still
produce incomplete results.

This keeps the output shape consistent: markdown notes, metadata, templates, and optional interview support.

---

## Transcript-Only Extraction

Use `--extract` when you want the transcript or cleaned source text first and want to decide later whether to run structured extraction.

```bash
# Print transcript text to stdout; progress goes to stderr
inkwell fetch https://youtube.com/watch?v=abc --extract

# Print cleaned article text to stdout
inkwell fetch https://example.com/article --extract

# Write transcript files without creating episode note directories
inkwell fetch syntax --latest --extract --output-dir ~/transcripts --plain
```

`--extract` skips templates, structured extraction, interview mode, and the episode note writer.

---

## Planned Later

The current foundation intentionally leaves these as separate future phases:

- hosted article extraction fallbacks for blocked or script-rendered pages
- slide decks
- video-frame/slide OCR
