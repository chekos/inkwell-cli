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
| Local text PDF | `inkwell fetch ./paper.pdf` | Supported for selectable text PDFs | Local PDF text extraction, then extraction templates | Structured source note directory |
| Stdin text | `inkwell fetch - < notes.txt` | Supported | Stdin is treated as source text for extraction templates | Structured episode note directory |
| Transcript/source-text only | `inkwell fetch URL --extract` | Supported | Transcription or local source extraction only | Transcript/source text or `.transcript.md` file |
| Slides/OCR/images | `inkwell fetch deck.pdf` | Not supported yet | Planned later | None |
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

## Local Text, Articles, PDFs, And Stdin

Local `.txt` and `.md` files, web articles, text PDFs, and stdin are treated as source text. They skip media transcription and go directly through the same extraction templates used for podcast transcripts.

```bash
inkwell fetch ./conference-notes.md --templates summary,key-concepts
inkwell fetch ./paper.pdf --templates summary,key-concepts
inkwell fetch https://example.com/article --templates summary,quotes
pbpaste | inkwell fetch - --templates summary,quotes
```

Article extraction is local-only: Inkwell fetches HTML and cleans readable text on your machine. Blocked, script-rendered, or very thin pages fail clearly; hosted extraction fallbacks are tracked separately for later.

PDF support is text-only: Inkwell extracts selectable text from local PDFs. Scanned/image PDFs and OCR are deferred.

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
- OCR/image PDFs
- slide decks
- image ingestion
