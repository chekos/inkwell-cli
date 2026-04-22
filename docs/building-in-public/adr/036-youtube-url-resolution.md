---
title: ADR 036 - YouTube URL Resolution in Feed Ingestion
adr:
  author: Sergio Sánchez (sergio@cimarron.io) + Claude
  created: 22-Apr-2026
  status: accepted
---

# ADR-036: YouTube URL Resolution in Feed Ingestion

**Status**: Accepted
**Date**: 2026-04-22
**Context**: Closing two gaps so users can paste a YouTube URL instead of hand-crafting the channel's media-RSS endpoint.

## Context

`inkwell add` historically accepted only pre-resolved RSS URLs. For YouTube channels — a common user ask — that meant:

1. Finding the channel ID (not exposed in any browser-copyable URL shape: watch, `@handle`, `/c/`, `/live/`, `/shorts/`).
2. Constructing `https://www.youtube.com/feeds/videos.xml?channel_id=UC…` manually.
3. Running `inkwell add` with that URL.

Even when a user completed all three steps, `inkwell fetch <saved-feed> --latest` failed because `RSSParser` looked for `<enclosure>` tags and YouTube media-RSS uses `<yt:videoId>` + `<media:group>` instead.

User framing (from the originating session): *"We should be able to point to a video and help the user figure out the rest. The user shouldn't have to know how to navigate and find the YouTube RSS feeds."*

## Decision

Add YouTube URL resolution at the CLI layer and a YouTube-aware fallback to the RSS parser. Specifically:

1. A new module `src/inkwell/feeds/youtube_resolver.py` exports `resolve_youtube_url(url) -> tuple[str, str | None] | None`. It recognizes YouTube URL shapes, resolves them to the channel's media-RSS feed URL, and returns `None` for non-YouTube URLs so callers fall through to the existing flow.
2. `inkwell add` calls the resolver before constructing `FeedConfig`.
3. `inkwell fetch` gains `--save-source` / `--source-name` flags so users can opt into saving the channel as a feed after a one-off video fetch.
4. `RSSParser._extract_enclosure_url` gains a YouTube branch: when `entry.yt_videoid` is present, return `entry.link` (feedparser already surfaces the watch URL; yt-dlp handles both `/watch?v=` and `/shorts/` shapes downstream).

## Key Choices

### yt-dlp Python API (not subprocess)

The project already imports `yt_dlp.YoutubeDL` (see `src/inkwell/audio/downloader.py`). Shelling out would add a PATH dependency that doesn't exist today and introduce four extra failure modes: subprocess timeout, stderr parsing, `--print` flag drift, missing binary.

### Resolver has its own yt-dlp opts — does NOT reuse `AudioDownloader.get_info`

`AudioDownloader.get_info` uses `extract_flat: False`, which for channel or `@handle` URLs causes yt-dlp to enumerate *every* video on the page — seconds to minutes of latency, many HTTP requests. The resolver wants only channel metadata, so it calls `YoutubeDL` directly with `extract_flat: "in_playlist", playlist_items: "0", skip_download: True`.

### `entry.yt_videoid` as the parser discriminator

feedparser normalizes the YouTube namespace (`yt:videoId`) to `entry.yt_videoid`. Using the YouTube-namespace-specific field avoids false positives for any non-YouTube podcast feed that happens to include `<media:*>` tags. Defensive fallback: if `entry.link` is absent, construct `https://www.youtube.com/watch?v={yt_videoid}`.

### No `FeedConfig` schema change

Resolver output is always normalized to `?channel_id=UC…` form. Channel-ID is recoverable from any stored URL via query-string parse; no migration needed. If future work needs a first-class `channel_id` field (issue #38, collision detection), it can land as a separate opt-in addition.

### `--save-source` requires `--source-name` in v1

Auto-derivation of names from YouTube channel metadata is deferred to issue #38 so it can land alongside the general feed-name slugification work in issue #37. Requiring `--source-name` is clear, collision-free, and zero-ambiguity. Users still save in one command; they just supply the name.

### `--save-source` runs after successful fetch; save failures are warnings

Matches user mental model ("I liked this video, now save it"). Save errors degrade to yellow warnings — the fetched content has already been produced; discarding it because the save step failed would be worse UX than a partial-success notice. Pre-fetch validation errors (missing `--source-name`, non-YouTube URL) still exit non-zero *before* the pipeline starts.

### Incremental, not architectural

The 2026 Q2 roadmap (`2026-roadmap/03-universal-content-ingestion.md`) proposes a generalized `ContentSource` / `URLSource` abstraction across platforms (Vimeo, Loom, Spotify, courses, local files). That is explicitly deferred. This PR patches the existing RSS flow with one resolver module and one parser branch. When the generalized abstraction lands, it absorbs this resolver as one provider among many — no rewrite required of consumers.

## Alternatives Considered

### Subprocess to `yt-dlp` CLI
Rejected — adds PATH dependency, surface area for breakage, and duplicate failure modes. Python API is already a project dep.

### Reuse `AudioDownloader.get_info` verbatim
Rejected — its `extract_flat: False` triggers full channel walks. Documented in plan and tested via separate resolver with tuned opts.

### Add `channel_id` field to `FeedConfig` now
Rejected for v1 — requires a migration for zero functional benefit today. Collision detection (the main use case) is deferred to #38, which can add the field at the same time. Scope-tightness wins.

### Auto-derive `--source-name` from channel metadata now
Rejected for v1 — overlaps with #37's general slugification. Combining avoids duplicate slug logic. Requiring `--source-name` is one extra flag; not a hardship.

### New `ContentSource` / `URLSource` abstraction (Q2 roadmap)
Deferred — XL scope. This PR is incremental.

## Consequences

**Positive**:
- Users paste any standard YouTube URL and it Just Works.
- No migration — existing feeds unaffected.
- Resolver is isolated to one module; easy to extend or replace.
- Parser change is a single defensive branch that only triggers on YouTube-namespace entries.

**Negative**:
- yt-dlp extractor breakage (periodic against YouTube) could block URL resolution. Mitigation: `ValidationError` messages explicitly preserve the manual-escape-hatch (`inkwell add <feeds/videos.xml?channel_id=…>` still works).
- Explicit `--source-name` requirement is less ergonomic than auto-derive. Follow-up issue #38 resolves this.
- Host allow-list (`youtube.com`, `www.youtube.com`, `m.youtube.com`, `youtu.be`) may need expansion for `music.youtube.com`, `gaming.youtube.com`, `youtube-nocookie.com` if users report pasting those.

**Risks**:
- YouTube media-RSS endpoint shape could change. Mitigation: out of our control; documented as a known externality.
- YouTube rate-limiting / bot-check during resolution (`"Sign in to confirm you're not a bot"`). Mitigation: resolver surfaces yt-dlp's original error plus manual-escape-hatch suggestion.

## References

- Design plan: `docs/plans/2026-04-22-001-feat-youtube-url-ingestion-plan.md`
- Devlog: `docs/building-in-public/devlog/2026-04-22-youtube-url-ingestion.md`
- Issue #37 — feed-name slugification
- Issue #38 — `--save-source` auto-derive + channel-collision detection
- Roadmap: `2026-roadmap/03-universal-content-ingestion.md`
- Resolver: `src/inkwell/feeds/youtube_resolver.py`
- Parser change: `src/inkwell/feeds/parser.py` (`_extract_enclosure_url`)

## Related ADRs

- ADR-005: RSS Parser Library (extended, not replaced)
- ADR-009: Transcription Strategy (yt-dlp usage predates this ADR)
