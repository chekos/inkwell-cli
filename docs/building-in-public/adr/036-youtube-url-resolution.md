---
title: ADR 036 - YouTube URL Resolution in Feed Ingestion
adr:
  author: Sergio Sánchez (sergio@cimarron.io) + Claude
  created: 22-Apr-2026
  status: accepted
---

# ADR-036: YouTube URL Resolution in Feed Ingestion

**Date:** 2026-04-22
**Status:** Accepted

## Context

`inkwell add` historically accepted only pre-resolved RSS URLs. For
YouTube channels this meant: find the channel ID (not exposed in any
browser-copyable URL shape), hand-craft
`feeds/videos.xml?channel_id=UC…`, then `inkwell add` it. Even after
that, `inkwell fetch <saved-feed> --latest` failed because
`RSSParser._extract_enclosure_url` looked for `<enclosure>` tags and
YouTube media-RSS uses `<yt:videoId>` + `<media:group>` instead.

## Decision

Patch the existing RSS flow with two narrow additions:

1. A new `src/inkwell/feeds/youtube_resolver.py` module that recognizes
   every standard YouTube URL shape (watch, `/shorts/`, `youtu.be`,
   `/channel/UC…`, `@handle` with tab suffixes, `/c/`, `/user/`,
   `/live/`, `/embed/`, `m.youtube.com`) and resolves to
   `feeds/videos.xml?channel_id=UC…`. Handles are resolved via yt-dlp's
   Python API with opts tuned to fetch only channel metadata
   (`extract_flat: "in_playlist", playlist_items: "0"`) so we never
   enumerate a channel's full video list. Non-YouTube URLs return
   `None` so callers fall through to the existing RSS flow.
2. A YouTube branch in `RSSParser._extract_enclosure_url`: when
   `entry.yt_videoid` is present, return `entry.link` (or construct a
   watch URL from `yt_videoid` as a fallback). The YouTube-namespace
   field avoids false positives on non-YouTube feeds that happen to
   include `<media:*>` tags.

`inkwell fetch` gains `--save-source` / `--source-name` so users can
opt into saving the channel as a feed after a one-off video fetch.
`--source-name` is **optional**: when omitted, the feed name is
auto-derived from the channel name (slugified), falling back to the
channel ID and appending a numeric suffix on collision. A dimmed hint
after a successful auto-named save tells the user the derived name and
how to rename it. Save runs *after* a successful fetch and degrades to
a warning on failure — discarding a successful fetch because the save
step failed is worse UX. Pre-fetch validation (non-YouTube URL,
playlist URL) still exits non-zero before the pipeline starts. No
`FeedConfig` schema change: channel ID is recoverable from any stored
URL.

## Consequences

- **Positive:** Users paste any standard YouTube URL and it works. No
  migration. Resolver is isolated to one module and one parser branch;
  when the Q2 roadmap's generalized `ContentSource` / `URLSource`
  abstraction lands, this resolver becomes one provider among many —
  no rewrite of consumers required.
- **Negative:** yt-dlp extractor breakage (periodic against YouTube)
  can block URL resolution. Mitigated by preserving the manual
  escape-hatch in `ValidationError.suggestion`
  (`inkwell add '…?channel_id=UCxxx' --name X` still works). Explicit
  `--source-name` is less ergonomic than auto-derive (resolved by #38).
- **Risks:** YouTube could change its media-RSS endpoint (externality;
  out of our control) or rate-limit resolution with the bot-check
  interstitial (surfaced via yt-dlp's original error + the
  manual-escape-hatch suggestion). The host allow-list currently
  excludes `music.youtube.com` / `gaming.youtube.com` /
  `youtube-nocookie.com` — may need expansion based on user reports.

## Alternatives Considered

1. **Shell out to `yt-dlp` CLI.** Rejected — adds a PATH dependency
   we don't have today plus four new failure modes (subprocess
   timeout, stderr parsing, `--print` flag drift, missing binary).
   The Python API is already a project dep.
2. **Reuse `AudioDownloader.get_info` as the resolver.** Rejected —
   its `extract_flat: False` walks every video on a channel for
   `/@handle` URLs. Tens of seconds of latency and many HTTP calls.
   The resolver needs its own tuned opts.
3. **Add a `channel_id` field to `FeedConfig` now.** Rejected for v1 —
   no functional benefit today; adds a migration. Collision detection
   (the main use case) is deferred to #38, which can add the field at
   the same time.
4. **Require `--source-name` in v1 (auto-derivation deferred to #38).**
   Initially accepted, then reversed during code review: requiring an
   explicit name contradicts the ingestion-UX principle ("user shouldn't
   have to know how to navigate YouTube"). Shipped a minimal inline
   slugifier (lowercase + `[^a-z0-9]` → `-`) with channel-ID fallback
   and numeric-suffix collision handling. #37's general slugifier can
   replace the inline helper later without changing the CLI contract.
5. **New `ContentSource` / `URLSource` abstraction.** Deferred — XL
   scope, Q2 roadmap (`2026-roadmap/03-universal-content-ingestion.md`).

## References

- Design plan: `docs/plans/2026-04-22-001-feat-youtube-url-ingestion-plan.md`
- Devlog: `docs/building-in-public/devlog/2026-04-22-youtube-url-ingestion.md`
- PR #39
- Follow-up issues: #37 (slugification), #38 (auto-name + collision detection)
- Resolver: `src/inkwell/feeds/youtube_resolver.py`
- Parser change: `src/inkwell/feeds/parser.py` (`_extract_enclosure_url`)
- Related: ADR-005 (RSS parser), ADR-009 (transcription strategy)
