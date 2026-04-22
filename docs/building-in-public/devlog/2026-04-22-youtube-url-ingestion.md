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

- **Unit 1 — Parser YouTube branch** (commit `9b3f351`): captured a synthetic YouTube media-RSS fixture, added 6 parser tests (regular / Short / live VOD / `yt_videoid` + missing `link` fallback / get_latest_episode / non-YouTube regression). Green after a ~10-line branch in `_extract_enclosure_url`.
- **Unit 2 — YouTube URL resolver** (commit `863fe5f`): new `src/inkwell/feeds/youtube_resolver.py`. 19 tests covering pure URL-shape detection, yt-dlp-backed resolution, playlist rejection, error mapping. Resolver uses its own `YoutubeDL` invocation with `extract_flat: "in_playlist", playlist_items: "0"` to avoid walking whole channel video lists (a real risk when pasting `/@handle` URLs).
- **Unit 3 — `inkwell add` wires the resolver** (commit `e5ef290`): 6 integration tests (watch URL, channel URL, already-resolved feed URL, non-YouTube regression, playlist rejection, resolver failure propagation). Implementation is 2 lines in `add_feed`: `asyncio.run(resolve_youtube_url(url))` → substitute `feed_url` if the resolver returned a tuple.
- **Unit 4 + 5 — `--save-source` flag + YouTube URL hint** (commit `ba83859`): combined into one commit because the hint is only meaningful when the flag it points at actually exists. Added `_should_show_save_source_hint` helper (4 direct unit tests), `--save-source` / `--source-name` typer options, pre-fetch validation (3 tests), post-fetch save block + dimmed hint rendering after the success summary. End-to-end save-source behavior covered by the smoke test rather than a full `PipelineOrchestrator` mock.
- **Unit 6 — ADR 036 + devlog close-out + docs** (this commit): ADR at `docs/building-in-public/adr/036-youtube-url-resolution.md`, updates to `docs/reference/cli-commands.md` + `docs/user-guide/feeds.md`, devlog finalized.
- **End-to-end smoke test**: pending pre-PR (see execution plan at `~/.claude/plans/misty-yawning-squirrel.md`).
- **PR**: pending smoke test pass.

## Lessons Learned

- **Empirical check saves design cycles.** The feedparser probe during planning (see `context.md`) reshaped the whole parser branch: once I confirmed `entry.link` already carries the watch URL, no construction was needed. Shorts keep `/shorts/` in the URL but yt-dlp handles both shapes, so "assert `youtube.com in url`" is the right test shape — not a hardcoded `/watch?v=` match.
- **`extract_flat: False` is expensive for channel URLs.** The feasibility review caught this before implementation — reusing `AudioDownloader.get_info` would have silently made `inkwell add https://www.youtube.com/@handle` spin for tens of seconds enumerating every video. The resolver needing its own yt-dlp opts is a critical decision buried in a seemingly mundane "reuse the existing helper" choice.
- **Test mock target at the import site, not the source.** `patch("inkwell.feeds.youtube_resolver.YoutubeDL")`, not `patch("yt_dlp.YoutubeDL")` — patching the latter leaves the resolver's bound reference unchanged. The design plan calling this out explicitly probably saved a debugging session.
- **Combining Units 4 + 5 was the right atomic boundary.** Shipping a dead `--save-source` flag in Unit 4 only to make it do something in Unit 5 would have created a confusing commit-level story. The "one unit one commit" rule is guidance, not gospel; the atomic-feature rule wins when they conflict.
- **`--save-source` pre-fetch validation pays for itself.** Catching missing `--source-name` before the 5-minute transcription pipeline runs is a meaningful UX win — users don't pay API costs to discover their CLI typo.
