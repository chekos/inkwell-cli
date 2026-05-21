# Transcription Attempt Policy

`TranscriptionAttemptPolicy` makes the transcription fallback order explicit without adding new providers. It is a small developer-facing foundation for future provider capability work.

---

## Default Attempt Order

For a normal remote media or episode URL, the default policy can produce:

1. transcript cache
2. YouTube transcript
3. Gemini public YouTube URL fallback, for YouTube URLs
4. Gemini audio fallback

For local media files, the policy goes directly to Gemini local media transcription. Local media does not run through `yt-dlp`.

---

## Attempt Types

The current attempt kinds are:

| Attempt kind | Provider label | Purpose |
|--------------|----------------|---------|
| `CACHE` | `cache` | Reuse a cached transcript |
| `YOUTUBE_TRANSCRIPT` | `youtube` | Use free YouTube captions/transcripts |
| `GEMINI_YOUTUBE_URL` | `gemini` | Ask Gemini to process a public YouTube URL |
| `GEMINI_AUDIO` | `gemini` | Download media and transcribe audio with Gemini |
| `GEMINI_LOCAL_MEDIA` | `gemini` | Transcribe an already-local audio/video file |

The manager records attempts with stable labels such as `cache`, `youtube`, and `gemini`. Duplicate labels are recorded once.

---

## Extension Guidance

Future provider work should add capability-aware planning to the policy instead of embedding more fallback order in `TranscriptionManager`.

Good future policy inputs include:

- whether the source is YouTube
- whether the source is local media
- whether a provider can handle public URLs directly
- whether a provider can handle local media
- whether cache use is allowed
- whether the caller requested `--skip-youtube`

Keep provider additions narrow. The policy should decide which attempts are allowed and in what order; each attempt implementation should remain in the manager or a provider/plugin boundary.

---

## Current Non-Goals

This policy does not yet add:

- new transcription providers
- token-aware routing
- web article extraction
- PDF, slide, or OCR ingestion
- cross-provider quality scoring
