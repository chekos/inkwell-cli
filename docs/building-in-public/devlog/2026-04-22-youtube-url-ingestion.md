# Devlog: YouTube URL Ingestion

**Date:** 2026-04-22
**Focus:** Let users paste YouTube URLs into `inkwell add` and `inkwell fetch`; fix the parser so YouTube-channel feeds work end-to-end.

## Context

Session opened with a user trying to add `@orenmeetsworld` as a feed. Two distinct failures surfaced within five minutes:

1. **Ingestion UX:** `inkwell add https://www.youtube.com/watch?v=pKeZ5XK2vp4 --name X` isn't supported — user had to shell out to `yt-dlp --print channel_id` and hand-craft `https://www.youtube.com/feeds/videos.xml?channel_id=UC_tSQ6UQy2pROm-I0J7UBoA`.
2. **Parser:** Even once the media-RSS URL was added, `inkwell fetch oren-meets-world --latest` failed at `RSSParser.extract_episode_metadata` with `Episode 'Is anything cool anymore?' has no audio enclosure`. YouTube media-RSS uses `<yt:videoId>` + `<media:group>` instead of podcast `<enclosure>` tags.

User framing: *"We should be able to point to a video and help the user figure out the rest. The user shouldn't have to know how to navigate and find the YouTube RSS feeds."*

## Goals

- [ ] Parser extracts a watchable URL from YouTube media-RSS entries (Gap B)
- [ ] `inkwell add <youtube-url>` resolves any standard YouTube URL shape to the channel's media-RSS feed (Gap A)
- [ ] `inkwell fetch <youtube-url>` stays one-time by default; `--save-source --source-name X` opts into saving the channel as a feed after a successful fetch
- [ ] Post-fetch hint on YouTube URLs guides users toward `--save-source`
- [ ] Playlist URLs rejected explicitly to prevent silent channel-widening
- [ ] No `FeedConfig` schema change; no migration

## Planning

Design plan: `docs/plans/2026-04-22-001-feat-youtube-url-ingestion-plan.md`
ADR: `docs/building-in-public/adr/036-youtube-url-resolution.md` (to be written at close-out)

**Key decisions** (see design plan for full rationale):
- yt-dlp Python API (not subprocess) with its own opts (`extract_flat: "in_playlist", playlist_items: "0"`) — do NOT reuse `AudioDownloader.get_info`, which would enumerate every video on a channel.
- Parser uses `entry.yt_videoid` as the YouTube-namespace discriminator and returns `entry.link` as the watch URL (empirically verified via feedparser on a live channel feed).
- `--save-source` requires explicit `--source-name` — auto-derivation deferred to #38 to land with general name slugification (#37).
- Playlist URLs rejected at the resolver boundary with an actionable error.

## Deferred / Tracked

- [#37](https://github.com/chekos/inkwell-cli/issues/37) — general feed-name slugification
- [#38](https://github.com/chekos/inkwell-cli/issues/38) — `--save-source` auto-derived names + channel-collision detection

## Implementation Trace

(To be filled in as units land.)

- Unit 1 (parser YouTube branch):
- Unit 2 (YouTube URL resolver):
- Unit 3 (add wiring):
- Unit 4 (fetch hint):
- Unit 5 (--save-source flag):
- Unit 6 (ADR + docs):
- End-to-end smoke test:
- PR:

## Lessons Learned

(To be filled in at close-out.)
