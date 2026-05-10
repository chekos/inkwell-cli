# YouTube Cloud Block Fallback

**Date:** 2026-05-10
**Author:** Codex

## Focus

Fix production web imports that failed when YouTube blocked Modal from fetching
captions or downloading media for a public YouTube URL.

## Progress

- Reproduced the production failure on a real web import job. The worker failed
  at `extracting_transcript` because YouTube asked `yt-dlp` to sign in and also
  blocked transcript requests from the cloud worker.
- Confirmed the same video had Spanish captions available from a local network,
  so the transcription layer now falls back to any available caption language
  when preferred English captions are missing.
- Added a Gemini public YouTube URL fallback between YouTube captions and audio
  download. Long or unknown-duration videos are processed as bounded clips with
  explicit request timeouts and clip-level logs.
- Added worker-side YouTube oEmbed title resolution so web notes use the public
  video title instead of the raw video id.
- Deployed the Modal worker and verified two production web imports from Chrome:
  one via available captions and one via the Gemini URL fallback after YouTube
  blocked both captions and `yt-dlp`.
- Fixed a remote CI mypy failure in extraction plugin registration.

## Observations

Changing Modal cloud providers did not eliminate YouTube blocking. The reliable
MVP path is to avoid server-side YouTube media download for public videos when
possible, then keep audio download as the final fallback for other sources.

Gemini URL processing is slower than captions but gives visible progress with
5-minute clips. The verified fallback import took several minutes, then moved
from `extracting_transcript` to `generating_notes` and saved a note.

## Next

- Watch Gemini's YouTube URL preview status, pricing, and rate limits.
- Add retry controls in the web app so failed jobs can be restarted without
  creating duplicate source rows.
- Consider a first-class transcript quality label in note metadata to distinguish
  exact captions from Gemini transcript-style fallback output.

## Links

- Related ADR: `../adr/038-gemini-youtube-url-fallback.md`
- Prior web app ADR: `../adr/037-web-app-stack-and-repo-boundary.md`
- Verified production job: `58802f98-1899-4b7d-ad5b-ee8accd14a63`
- Verified production note: `6051689f-7335-4759-bc77-54e9ceb7a14c`
