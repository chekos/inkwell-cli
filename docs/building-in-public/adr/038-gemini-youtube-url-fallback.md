---
title: ADR 038 - Gemini YouTube URL fallback
adr:
  author: Codex
  created: 10-May-2026
  status: accepted
---

# ADR 038: Gemini YouTube URL fallback

**Date:** 2026-05-10
**Status:** Accepted

## Context

The web worker runs in Modal, so YouTube can block both `youtube-transcript-api`
caption requests and `yt-dlp` media downloads as cloud-provider traffic. This
breaks imports even for public videos that are accessible from a user's browser.

The CLI's existing strategy was cache, YouTube captions, then downloaded audio
with Gemini. That still works locally, but it is not reliable enough for the
production web worker.

## Decision

Add a YouTube-specific Gemini fallback between YouTube captions and audio
download:

1. Try cached transcripts.
2. Try free YouTube captions, including available non-English captions when
   preferred English captions are missing.
3. For public YouTube URLs, use Gemini video URL input with bounded clips.
4. Fall back to downloaded audio with Gemini for non-YouTube sources or when URL
   input fails.

The worker also resolves public YouTube titles through oEmbed before invoking
the pipeline so saved web notes are named by title rather than video id.

## Consequences

- Web imports can succeed when YouTube blocks Modal from captions and media
  download.
- The fallback stays inside the Python transcription layer, so the CLI and web
  worker share the same behavior.
- Gemini's public YouTube URL input is currently a preview feature, so pricing,
  limits, and behavior may change.
- The fallback is a transcript-style extraction rather than a guaranteed
  word-for-word transcript. It is good enough for note extraction but should not
  be treated as court-record transcription.
- Production logs now show clip-level progress for long YouTube imports.

## Alternatives Considered

1. Pass browser cookies to `yt-dlp`.
   - Pros: preserves the exact audio-download path.
   - Cons: risky for user accounts and brittle against YouTube bot detection.
2. Add a residential proxy for transcript and media requests.
   - Pros: keeps the original caption/download behavior.
   - Cons: new vendor, credential handling, cost, and abuse-risk surface.
3. Move YouTube processing out of Modal.
   - Pros: could use a different network origin.
   - Cons: undermines the simple Vercel + Supabase + Modal worker architecture.

## References

- Gemini video understanding docs: https://ai.google.dev/gemini-api/docs/video-understanding
- Related devlog: `../devlog/2026-05-10-youtube-cloud-block-fallback.md`
- Production verification job: `58802f98-1899-4b7d-ad5b-ee8accd14a63`
