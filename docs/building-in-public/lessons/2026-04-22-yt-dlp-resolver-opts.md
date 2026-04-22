# Lesson: yt-dlp resolver opts must not be inherited from `AudioDownloader`

**Date:** 2026-04-22
**Author:** Sergio Sánchez
**Context:** YouTube URL ingestion (PR #39, ADR-036)

## What Happened

The first instinct when adding `youtube_resolver.py` was to reuse
`AudioDownloader.get_info`, which already wraps `YoutubeDL.extract_info`.
It would have worked for `/watch?v=…` URLs but silently walked the
entire video list for `/@handle` and `/channel/UC…` URLs — `extract_flat:
False` (AudioDownloader's default, correct for the download path) makes
yt-dlp enumerate every child entry on a channel page. Tens of seconds of
latency and many HTTP requests per `inkwell add @somehandle` call, most
of them hidden because the resolver only needs the channel metadata.

A parallel near-miss: test mocks initially targeted `yt_dlp.YoutubeDL`
instead of `inkwell.feeds.youtube_resolver.YoutubeDL`. Patching the
source module leaves the already-bound reference in the resolver
unchanged — tests "pass" while silently making real network calls.

## What We Learned

- Reuse is only cheap when the dependencies of the thing being reused
  match the caller's needs. `AudioDownloader` wants the full video
  metadata to download from; the resolver wants only
  `info["channel_id"]`. Those are different contracts against the same
  library, so they need different opts.
- `extract_flat: "in_playlist"` + `playlist_items: "0"` is the
  incantation for "give me the container, not its children" — worth
  remembering for any future yt-dlp wrapper that only needs channel /
  playlist metadata.
- `patch("…import.site.Name")`, not `patch("original.module.Name")`.
  Always mock at the import site, because Python imports bind names at
  import time.

## What We'll Do Differently

- When wrapping yt-dlp for a new purpose, start from an empty `ydl_opts`
  dict and add only what the new caller needs. Don't reach for an
  existing helper just because the library call shape matches.
- Default every new yt-dlp wrapper to an explicit `socket_timeout`. No
  timeout means indefinite hangs on slow YouTube responses; the CLI
  tool has no way to recover short of SIGKILL.
- Treat "mock target is the import site, not the source module" as a
  precondition to writing any test that patches a third-party library —
  not a debugging realization after a silently-passing test.

## Related

- ADR: [ADR-036](../adr/036-youtube-url-resolution.md)
- Devlog: [2026-04-22](../devlog/2026-04-22-youtube-url-ingestion.md)
