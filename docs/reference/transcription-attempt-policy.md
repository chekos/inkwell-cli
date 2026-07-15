# Transcription Attempt Policy

`TranscriptionAttemptPolicy` makes the transcription fallback order explicit without adding new providers. It uses typed provider capability metadata when available, while preserving the current built-in fallback order.

---

## Default Attempt Order

For a normal remote media or episode URL, the default policy can produce:

1. transcript cache
2. YouTube transcript
3. Gemini public YouTube URL fallback, for YouTube URLs
4. Gemini audio fallback

For local media files, the policy goes directly to Gemini local media transcription. Local media does not run through `yt-dlp`.

Source-text inputs such as local text/markdown, stdin, locally extracted
articles, images, and PDFs bypass this policy entirely and enter extraction as
text. Optional OCR is an ingestion plugin, not a transcription attempt.

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

Future provider work should extend capability-aware planning in the policy instead of embedding more fallback order in `TranscriptionManager`.

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
- slide/video-frame ingestion
- cross-provider quality scoring
