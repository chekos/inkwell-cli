# YouTube URL ingestion

**Date:** 2026-04-22
**Author:** Sergio Sánchez

## Focus

Close two gaps so users can paste any YouTube URL into `inkwell add` /
`inkwell fetch` and have channel-feed processing work end-to-end.

## Progress

- Parser gained a YouTube branch: `_extract_enclosure_url` now returns
  `entry.link` (or a constructed watch URL) when `yt_videoid` is set, so
  channel media-RSS entries no longer raise "no audio enclosure".
- New `src/inkwell/feeds/youtube_resolver.py` recognizes every standard
  YouTube URL shape and resolves to `feeds/videos.xml?channel_id=UC…`.
  Uses its own yt-dlp opts (`extract_flat: "in_playlist",
  playlist_items: "0"`) to avoid enumerating whole channel video lists.
- `inkwell add` calls the resolver; non-YouTube URLs pass through.
- `inkwell fetch` gained `--save-feed` / `--feed-name`; pre-fetch
  validation rejects missing name, non-YouTube URLs, and playlist URLs
  before any API spend.
- Dimmed post-fetch hint guides users toward `--save-feed` when they
  paste a raw YouTube URL without it.
- ADR 036 records the key decisions.

## Observations

- Empirical feedparser probing reshaped the whole parser branch —
  `entry.link` already carries the watch URL (including `/shorts/`),
  so no URL construction was needed.
- `extract_flat: False` on channel URLs silently walks the whole video
  list. Reusing `AudioDownloader.get_info` would have burned tens of
  seconds per `inkwell add @handle` call — caught pre-implementation.
- Mock target matters: `patch("inkwell.feeds.youtube_resolver.YoutubeDL")`,
  not `patch("yt_dlp.YoutubeDL")`. Patching the source module leaves the
  resolver's bound reference unchanged.

## Next

- End-to-end smoke test against a real `@handle` URL.
- Follow-ups tracked separately: #37 (general feed-name slugification),
  #38 (`--save-feed` auto-name + channel-collision detection).

## Links

- Related ADR: [ADR-036](../adr/036-youtube-url-resolution.md)
- Related lesson: [yt-dlp opts isolation](../lessons/2026-04-22-yt-dlp-resolver-opts.md)
- PR: #39
- Design plan: `docs/plans/2026-04-22-001-feat-youtube-url-ingestion-plan.md`
