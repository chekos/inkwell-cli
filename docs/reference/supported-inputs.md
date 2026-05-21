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
| Other HTTP(S) URL | `inkwell fetch https://example.com/watch/episode` | Supported when it is media or handled by `yt-dlp` | Media transcription, then extraction templates | Structured episode note directory |
| Local audio/video | `inkwell fetch ~/Downloads/interview.mp3` | Supported | Local file transcription through Gemini | Structured episode note directory |
| Local text/markdown | `inkwell fetch ./notes.md` | Supported | Existing text is treated as source text for extraction templates | Structured episode note directory |
| Stdin text | `inkwell fetch - < notes.txt` | Supported | Stdin is treated as source text for extraction templates | Structured episode note directory |
| Transcript-only media | `inkwell fetch URL --extract` | Supported | Transcription only | Transcript text or `.transcript.md` file |
| PDF | `inkwell fetch paper.pdf` | Not supported yet | Planned later | None |
| Web article extraction | `inkwell fetch https://example.com/article` | Not supported as article cleanup yet | Planned later | None |
| Slides/OCR/images | `inkwell fetch deck.pdf` | Not supported yet | Planned later | None |
| Non-HTTP URL schemes | `inkwell fetch ftp://example.com/file.mp3` | Not supported | Rejected as unknown URL | None |

---

## What Counts As Media

Direct media detection is conservative. Inkwell recognizes common audio/video extensions such as:

```text
.aac .aif .aiff .avi .flac .m4a .m4v .mkv .mov .mp3 .mp4
.mpeg .mpg .oga .ogg .opus .wav .webm
```

Some media pages do not end in a media extension. Those can still work when `yt-dlp` can resolve them to audio, but Inkwell does not currently extract readable article text from arbitrary web pages.

---

## Local Text And Stdin

Local `.txt` and `.md` files and stdin are treated as already-clean source text. They skip media transcription and go directly through the same extraction templates used for podcast transcripts.

```bash
inkwell fetch ./conference-notes.md --templates summary,key-concepts
pbpaste | inkwell fetch - --templates summary,quotes
```

This keeps the output shape consistent: markdown notes, metadata, templates, and optional interview support. It is not a generic web/PDF/OCR summarizer path.

---

## Transcript-Only Extraction

Use `--extract` when you want the transcript first and want to decide later whether to run structured extraction.

```bash
# Print transcript text to stdout; progress goes to stderr
inkwell fetch https://youtube.com/watch?v=abc --extract

# Write transcript files without creating episode note directories
inkwell fetch syntax --latest --extract --output-dir ~/transcripts --plain
```

`--extract` skips templates, structured extraction, interview mode, and the episode note writer.

---

## Planned Later

The current foundation intentionally leaves these as separate future phases:

- cleaned web/article extraction
- PDF text extraction
- slide decks
- OCR/image ingestion
- token-aware model routing for long documents
