---
title: "feat: YouTube URL ingestion for inkwell feeds"
type: feat
status: active
date: 2026-04-22
---

# feat: YouTube URL ingestion for inkwell feeds

## Overview

Close two gaps that currently block end-to-end processing of YouTube channels in `inkwell-cli`:

1. **Ingestion UX (Gap A):** `inkwell add` and `inkwell fetch` accept only pre-resolved RSS URLs today. Users must manually locate a YouTube channel's media-RSS endpoint (`https://www.youtube.com/feeds/videos.xml?channel_id=UC…`) before handing it to inkwell. This plan adds YouTube URL detection and auto-resolution in the CLI layer so users can paste any standard YouTube URL.
2. **Parser (Gap B):** `RSSParser` fails on YouTube media-RSS entries with `Episode '...' has no audio enclosure`. YouTube feeds use `<yt:videoId>` + `<media:group>` instead of podcast `<enclosure>` tags. This plan teaches the parser to recognize YouTube entries.

A new `--save-source` flag on `inkwell fetch` lets users opt into saving the channel as a recurring feed when they process a one-off video. Fetch remains one-time by default to match user intent.

## Problem Frame

While adding `@orenmeetsworld` as a feed (session trace: 2026-04-22), two concrete failures surfaced:

- `inkwell add https://www.youtube.com/watch?v=pKeZ5XK2vp4 --name X` isn't supported — user had to shell out to `yt-dlp --print channel_id` and hand-craft the RSS URL.
- `inkwell fetch <saved-youtube-feed> --latest` fails at `RSSParser.extract_episode_metadata` (parser.py:259) because YouTube entries have no `<enclosure>` element.

User framing: *"We should be able to point to a video and help the user figure out the rest. The user shouldn't have to know how to navigate and find the YouTube RSS feeds."*

## Requirements Trace

- **R1.** `inkwell add <youtube-url> --name X` accepts YouTube URL shapes (watch, shorts, youtu.be, channel, @handle, /c/, /user/, /live/, /embed/, tab-suffixed like `/@handle/videos`) and stores the resolved channel-RSS URL (always normalized to `?channel_id=UC…` form). (Gap A)
- **R2.** `inkwell add <youtube-feeds-url>` (already-resolved `feeds/videos.xml?channel_id=…`) passes through unchanged — no re-resolution. (Gap A, edge case)
- **R3.** `inkwell fetch <youtube-url>` continues to process a single video by default. No feed is saved unless `--save-source` is passed. (UX invariant)
- **R4.** `inkwell fetch <youtube-url> --save-source [--source-name X]` processes the video, then saves the channel as a feed. Save runs *after* successful fetch; save failure emits a warning but does not change fetch exit code. (New behavior)
  - **Amended during code review (2026-04-22):** the original plan made `--source-name` REQUIRED and deferred auto-derivation to #38. Reversed: `--source-name` is **optional**; when omitted, the feed name is slugified from the channel metadata (fallback: channel ID; collisions get a numeric suffix) and a rename hint is printed. Rationale: requiring the flag contradicts the ingestion-UX principle that motivated the feature. See ADR-036 "Alternatives Considered" #4.
- **R5.** On `inkwell fetch <youtube-url>` (without `--save-source`, successful fetch only), display a dimmed hint guiding the user to `--save-source` for future saves. (UX)
- **R6.** `inkwell fetch <saved-youtube-feed> --latest` succeeds end-to-end: parser extracts a watchable URL from YouTube media-RSS entries; downloader + transcription + extraction proceed normally. (Gap B)
- **R7.** Non-YouTube URLs behave exactly as today. Resolver is a no-op for unrecognized URLs. (Backwards compat)
- **R8.** Playlist URLs (`?list=…`) are rejected with a clear error when passed to `add` or `fetch --save-source`. Playlist feed ingestion itself is out of scope. (Explicit error vs. silent channel-widening)

**Terminology:** "Saved source" and "saved feed" refer to the same thing — a `FeedConfig` entry persisted by `ConfigManager`. `--save-source` is the user-facing term; `FeedConfig` is the internal persistence unit.

## Scope Boundaries

- No new `ContentSource` / `URLSource` abstraction — that's the Q2 roadmap XL work in `2026-roadmap/03-universal-content-ingestion.md`. This plan patches the existing RSS flow incrementally.
- No playlist support (`?list=…`). YouTube exposes a different feed endpoint for playlists — separate work.
- No non-YouTube video platforms (Vimeo, Loom, Spotify, etc.).
- No visual extraction, OCR, or video-frame analysis.
- No schema change to `FeedConfig`. Channel-ID is parsed from the stored URL at read-time (always `?channel_id=UC…` for YouTube feeds) — no migration, no new field.

### Deferred to Separate Tasks

- **Feed-name slugification** — accepting `"Oren Meets World"` as `--name` and slugifying to `oren-meets-world`: tracked in [#37](https://github.com/chekos/inkwell-cli/issues/37).
- **`--save-source` auto-derived names + channel-collision detection** — tracked in [#38](https://github.com/chekos/inkwell-cli/issues/38). This PR requires explicit `--source-name`.
- **Playlist ingestion** — create follow-up issue if/when needed.
- **Universal `ContentSource` abstraction** — Q2 roadmap work at `2026-roadmap/03-universal-content-ingestion.md`.

## Context & Research

### Relevant Code and Patterns

- `src/inkwell/cli.py::add_feed` (line 70) — single-file CLI command. New resolution logic attaches here as a pre-processing step before `FeedConfig(url=…)`.
- `src/inkwell/cli.py::fetch_command` (line 569) — gains `--save-source` / `--source-name` options and the post-fetch hint.
- `src/inkwell/feeds/parser.py::RSSParser._extract_enclosure_url` (line 290) — gains a YouTube branch. Empirical check against a live YouTube channel feed confirms:
  - `entry.yt_videoid` is populated (feedparser normalizes `yt:videoId` → `yt_videoid`).
  - `entry.link` is already `https://www.youtube.com/watch?v={id}` — no URL construction needed.
  - `entry.summary` is populated from `<media:description>` → existing `_extract_description` works unchanged.
  - `entry.published_parsed` is a valid `time.struct_time` → existing `_extract_published_date` works unchanged.
  - Duration isn't in the feed; `Episode.duration_seconds` is already `int | None` and all call sites gate on truthiness (`cli_list.py:169`, `cli_list.py:197`, etc.) — `None` is safe downstream.
- `src/inkwell/audio/downloader.py` — already uses `yt_dlp.YoutubeDL` Python API (line 200+). `AudioDownloader.get_info(url)` at line 218 is the reusable metadata-extraction helper. Resolver will use the same import, not a subprocess.
- `src/inkwell/config/manager.py::add_feed` (line 340) — raises `ValidationError` with a suggestion on duplicate names; not idempotent. v1 of `--save-source` catches this exception and downgrades it to a warning (so a repeat `--save-source` after a successful save doesn't hard-fail).
- `src/inkwell/feeds/validator.py::FeedValidator.validate_feed_url` — HEAD→GET→status-check validation is fine for YouTube feed URLs (empirically 200 + `text/xml`). No changes.
- `src/inkwell/utils/errors.py` — `ValidationError(message, suggestion=…)` is the standard shape for CLI-surfaced errors.

### Test Patterns to Mirror

- CLI tests: `tests/integration/test_cli.py` uses `class TestCLI<Command>:` with module-level `CliRunner()` and `ConfigManager(config_dir=tmp_path)` or `monkeypatch.setattr("inkwell.utils.paths.get_config_dir", lambda: tmp_path)` for isolation. `os.environ["NO_COLOR"]="1"` already set.
- Parser tests: `tests/unit/test_feeds_parser.py` loads XML fixtures via `Path(__file__).parent.parent / "fixtures" / "<name>.xml"`. HTTP mocked with `respx` + `@pytest.mark.asyncio`. New YouTube fixture goes in `tests/fixtures/youtube_channel_feed.xml`.

### Institutional Learnings

- `docs/solutions/` does not yet exist in this repo; no prior learnings apply.
- ADR 005 (`docs/building-in-public/adr/005-rss-parser-library.md`) documents `feedparser` as the chosen library — this plan extends its usage, not replaces it.

### External References

- YouTube media-RSS endpoint shape: `https://www.youtube.com/feeds/videos.xml?channel_id=UC…` (stable, undocumented but widely used; also supports `?user=` and `?playlist_id=` though those are out of scope).
- Empirical probe results from 2026-04-22 captured in the `Context & Research` section above.

## Key Technical Decisions

- **Use yt-dlp Python API, not subprocess.** Project already imports `YoutubeDL` (see `src/inkwell/audio/downloader.py`). Subprocess would add a PATH dependency that doesn't exist today and introduce ~4 extra failure modes (timeout, stderr parsing, version drift, missing binary).
- **Resolver uses its own yt-dlp opts — does NOT reuse `AudioDownloader.get_info`.** `get_info` uses `extract_flat: False`, which for channel/handle URLs causes yt-dlp to enumerate *all* videos on the channel (seconds to minutes of latency, many HTTP requests). Resolver calls `YoutubeDL` directly with `{quiet: True, no_warnings: True, extract_flat: "in_playlist", playlist_items: "0", skip_download: True}` so the call returns channel metadata without walking the video list. Mirror `AudioDownloader._get_info_sync`'s async-executor pattern for the wrapper.
- **Use `entry.yt_videoid` as the discriminator in the parser.** YouTube-specific namespace field makes it safe vs. any podcast feed that happens to include `<media:*>` tags. Fallback: `entry.id` starts with `yt:video:` if feedparser's namespace handling ever regresses.
- **Parser returns `entry.link` for YouTube entries.** No URL construction — feedparser already provides the watch URL. Tests assert whatever URL shape feedparser actually surfaces (may be `/shorts/…` or `/watch?v=…` depending on the entry); yt-dlp downstream handles both. Defensive fallback: if `link` is missing, construct `https://www.youtube.com/watch?v={yt_videoid}`.
- **No `FeedConfig` schema change.** Resolver always normalizes output to `feeds/videos.xml?channel_id=UC…` form, so every feed added through this path has `channel_id` parseable from the stored URL. Avoids migration. (Channel-collision detection is deferred to #38 and will add the host-guarded parse helper at that time.)
- **YouTube host allow-list — minimal set.** Explicit set: `youtube.com`, `www.youtube.com`, `m.youtube.com`, `youtu.be`. Hosts outside this set pass through unchanged. `music.youtube.com`, `gaming.youtube.com`, `youtube-nocookie.com` deliberately excluded — niche, add on demand.
- **Pre-resolved feed URL is a no-op.** If input URL host is `www.youtube.com` and path is `/feeds/videos.xml` with a `channel_id` query param, return it unchanged. Users who know the feed URL shouldn't be forced through resolution.
- **Playlist URLs rejected at the resolver boundary.** If the URL contains `?list=` OR path includes `/playlist`, raise `ValidationError("Playlist URLs aren't supported yet — try the channel URL instead", suggestion="Find the channel at youtube.com/@handle")`. Prevents silent widening to full channel or silent playlist ingestion (out of scope).
- **`--save-source` requires `--source-name`.** Auto-derivation of names from channel metadata is deferred to #38 (pairs with general slugification #37). v1 errors with a clear message when `--save-source` is passed without `--source-name`.
- **`--save-source` runs after successful fetch.** Matches user mental model ("I liked this video, now save it"). Save errors become warnings, not exit codes — partial success (video processed, save failed) is more useful than rollback. Pre-fetch validation errors (invalid URL, missing `--source-name`) still exit non-zero *before* the pipeline starts.
- **No emoji in the hint message.** Existing `inkwell` output has no emoji precedent (research confirmed). Style: `[dim]Want to track this channel? Re-run with [cyan]--save-source --source-name <name>[/cyan] to save it as a feed.[/dim]`.

## Open Questions

### Resolved During Planning

- *Use yt-dlp subprocess or Python API?* → Python API (reuses existing project pattern; fewer failure modes).
- *Reuse `AudioDownloader.get_info`?* → **No** — its `extract_flat: False` triggers full channel-video enumeration. Resolver has its own `YoutubeDL` invocation with `extract_flat: "in_playlist", playlist_items: "0"`.
- *Does `add <youtube-rss-url>` pass through?* → Yes, detect `feeds/videos.xml?channel_id=` and skip resolution.
- *Auto-derive `--source-name` from channel handle?* → **No (v1)** — deferred to #38 to land with general slugification. `--source-name` is required when `--save-source` is set.
- *Collision detection when channel already saved under different name?* → **Deferred to #38.** v1 relies on existing `ConfigManager.add_feed` duplicate-*name* error; duplicate-*channel* under different names is accepted (users can check with `inkwell list feeds`).
- *`--save-source` ordering?* → After successful fetch; save failure = warning, not exit code. Pre-fetch validation errors (missing `--source-name`, non-YouTube URL with `--save-source`, playlist URL) exit non-zero *before* fetch runs.
- *Hint timing on failed fetch or saved-feed fetch?* → Only on successful raw-YouTube-URL fetches when `--save-source` wasn't already passed.
- *Livestream/`/live/` URLs?* → In scope; yt-dlp resolves channel_id fine. Archived livestreams behave as regular videos.
- *Playlist URL (`?list=…`) handling?* → Rejected at resolver with actionable error. Prevents silent channel-widening.
- *Do we need a `channel_id` field on `FeedConfig`?* → No. Resolver output always has `?channel_id=` form; schema stays unchanged.

### Deferred to Implementation

- *Exact naming of resolver functions.* — shape is `resolve_youtube_url(url: str) -> tuple[str, str | None] | None` returning `(feed_url, channel_name)` or `None` for non-YouTube. Channel name is surfaced for #38's follow-up; unused by v1 code but populated. Final names to be decided during implementation.
- *Whether to cache resolver results within a single CLI invocation.* — defer; add only if a use case with repeated resolution surfaces.
- *Mock patch target for Unit 2 tests.* — resolver imports `YoutubeDL` directly (not `AudioDownloader`); test mock target is `inkwell.feeds.youtube_resolver.YoutubeDL`. Never `inkwell.audio.downloader.YoutubeDL` — that's a different import site.

## High-Level Technical Design

> *This illustrates the intended approach and is directional guidance for review, not implementation specification. The implementing agent should treat it as context, not code to reproduce.*

```
User input                       Resolver decision              Stored/processed
──────────────────────────────   ────────────────────────────   ─────────────────────────
inkwell add <youtube-watch-url>  ─► youtube host? ─► yt-dlp  ─► feeds/videos.xml?channel_id=UC…
inkwell add <youtube-channel>    ─► youtube host? ─► regex  ─► feeds/videos.xml?channel_id=UC…
inkwell add <youtube-feed-url>   ─► feed-form? ──► pass-through ─► feeds/videos.xml?channel_id=UC…
inkwell add <non-youtube-rss>    ─► unmatched  ──► pass-through ─► existing RSS flow

inkwell fetch <youtube-url>
  ├─ (default)                         ─► fetch single video; then print hint
  └─ --save-source --source-name X     ─► validate up front; fetch single video; then resolve channel; then ConfigManager.add_feed (failure = warning, fetch exit code unchanged)

inkwell fetch <saved-name> --latest
  └─ parser sees entry.yt_videoid ─► returns entry.link as episode URL ─► downloader handles watch URL via yt-dlp
```

## Implementation Units

Test-first execution posture throughout. Each unit starts with a failing test that pins the desired behavior.

- [ ] **Unit 1: Add YouTube media-RSS fixture and parser branch (Gap B)**

  **Goal:** `RSSParser.extract_episode_metadata` produces a valid `Episode` from YouTube media-RSS entries.

  **Requirements:** R6, R7

  **Dependencies:** None.

  **Files:**
  - Create: `tests/fixtures/youtube_channel_feed.xml` (captured sample, 3–5 entries including one Short, one regular video, one `/live/` URL)
  - Modify: `src/inkwell/feeds/parser.py` — extend `_extract_enclosure_url` (line 290)
  - Modify: `tests/unit/test_feeds_parser.py` — new test class `TestRSSParserYouTube`

  **Approach:**
  - Detect YouTube entries via `entry.get("yt_videoid")` presence. If truthy, return `entry.get("link")` (feedparser already surfaces the watch URL). Fall back to constructing `https://www.youtube.com/watch?v={videoid}` only if `link` is missing — defensive.
  - Do not alter the existing enclosure/link paths; YouTube branch is a new fallback after the existing two lookups.
  - Description, published date, duration all reuse existing extractors; empirical check confirms feedparser populates `summary`, `published_parsed`, and leaves duration out (None is downstream-safe).

  **Execution note:** Write the fixture-backed test first, watch it fail with `ValidationError: has no audio enclosure`, then add the branch.

  **Patterns to follow:**
  - Fixture loading: `Path(__file__).parent.parent / "fixtures" / "youtube_channel_feed.xml"` (mirrors `valid_rss_feed.xml` pattern at test line 15-33).
  - Test style: `class TestRSSParserYouTube` with `test_*` methods; no async for this pure parsing path.

  **Test scenarios:**
  - Happy path: fixture entry with `yt:videoId=abc123` → `Episode.url == "https://www.youtube.com/watch?v=abc123"`; title, summary, published all populated.
  - Happy path: YouTube Short entry → `Episode.url` is a downloadable YouTube URL (assert `"youtube.com" in url` rather than hardcoding `/watch?v=` vs `/shorts/` — both are yt-dlp-handleable).
  - Happy path: `/live/` VOD entry → `Episode.url` resolves normally; `duration_seconds is None`.
  - Edge case: entry with `yt_videoid` but missing `entry.link` → fallback constructs `https://www.youtube.com/watch?v={videoid}`.
  - Edge case: entry in a YouTube channel feed that is a playlist-reference (no `yt_videoid`) → parser raises the existing `has no audio enclosure` error (fall-through; not the new branch's problem).
  - Error path: non-YouTube entry (existing `valid_rss_feed.xml`) still extracts from `<enclosure>` — no regression.
  - Integration: `get_latest_episode` over the YouTube fixture returns the first entry with all fields populated; no exception.

  **Verification:**
  - `uv run pytest tests/unit/test_feeds_parser.py` passes.
  - Manually running `uv run inkwell fetch <temp-yt-feed> --latest --dry-run` on a test feed no longer raises `has no audio enclosure`.

- [ ] **Unit 2: YouTube URL resolver module**

  **Goal:** Pure function + thin yt-dlp wrapper that converts any recognized YouTube URL to the channel's `feeds/videos.xml?channel_id=…` URL; passes through unrecognized URLs; rejects playlists explicitly.

  **Requirements:** R1, R2, R7, R8

  **Dependencies:** None (Unit 1 independent, but Unit 5 depends on both).

  **Files:**
  - Create: `src/inkwell/feeds/youtube_resolver.py` (flat in `feeds/`, no `resolvers/` subpackage — only one resolver exists)
  - Create: `tests/unit/test_youtube_resolver.py`

  **Approach:**
  - Two layers:
    - Pure URL-shape detection (`_is_youtube_host`, `_is_already_resolved_feed_url`, `_channel_id_from_path`, `_is_playlist_url`). All regex / `urllib.parse`. No network.
    - Async resolver (`resolve_youtube_url(url) -> tuple[str, str | None] | None`) that first runs the pure layer. Returns:
      - `None` if URL host isn't in the YouTube allow-list (caller falls through to existing RSS flow).
      - `(original_url, None)` if URL is already a resolved feed URL (pass-through).
      - `(f"https://www.youtube.com/feeds/videos.xml?channel_id={UC_ID}", None)` if the channel-ID is derivable from the URL path (no network).
      - `(feed_url, channel_name)` after a yt-dlp call for URL shapes that require resolution.
    - `channel_name` populated opportunistically from the yt-dlp `channel` / `uploader` field; None when pure path handled everything. Used downstream by issue #38 when auto-derive ships.
  - Resolver calls `YoutubeDL` directly with its own opts: `{quiet: True, no_warnings: True, extract_flat: "in_playlist", playlist_items: "0", skip_download: True}`. **Do NOT reuse `AudioDownloader.get_info`** — its `extract_flat: False` would enumerate every video on a channel.
  - Async wrapper: `loop.run_in_executor(None, _resolve_sync, url, ydl_opts)`, mirroring `src/inkwell/audio/downloader.py:236-238`.
  - Allow-list of YouTube hosts: `{"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"}`. Case-insensitive host comparison.
  - Playlist rejection: if URL has `list=` query param OR path starts with `/playlist` → raise `ValidationError("Playlist URLs aren't supported yet — try the channel URL instead", suggestion="Visit the playlist on YouTube and copy the channel (@handle) URL from the creator.")`.
  - Error mapping: `DownloadError` / `ExtractorError` → `ValidationError("Couldn't resolve YouTube URL: {e}", suggestion="Verify the URL is public and accessible. If yt-dlp is temporarily broken by a YouTube-side change, you can still add the channel manually: inkwell add https://www.youtube.com/feeds/videos.xml?channel_id=UCxxx --name X")`. The suggestion explicitly preserves the manual escape hatch.

  **Execution note:** URL-shape tests first (fast, no network, no mock), then resolver tests with mocked `YoutubeDL`. **Mock target: `inkwell.feeds.youtube_resolver.YoutubeDL`** — NOT `inkwell.audio.downloader.YoutubeDL` — tests must patch the symbol at the resolver's import site.

  **Patterns to follow:**
  - `yt_dlp.YoutubeDL` usage: mirror `src/inkwell/audio/downloader.py:244-250` pattern (sync function, `run_in_executor`, catch `DownloadError`/`ExtractorError`).
  - `ValidationError` usage: same `(message, suggestion=…)` shape as existing `FeedValidator`.

  **Test scenarios:**
  - Happy path (pure, no network): `/channel/UCxxx` URL returns `("...channel_id=UCxxx", None)` without calling `YoutubeDL` — assert the mock was not invoked.
  - Happy path (pure, no network): already-resolved `feeds/videos.xml?channel_id=UC...` URL returns `(original_url, None)` — no yt-dlp call.
  - Happy path (mocked yt-dlp): `watch?v=VID` returns feed URL with `channel_id=UC…` + channel name populated from mock.
  - Happy path (mocked yt-dlp): `/@handle`, `/@handle/videos`, `/@handle/shorts`, `/@handle/featured`, `/@handle/streams` all produce the same feed URL (each test case passes a mock with identical `channel_id`).
  - Happy path (mocked yt-dlp): `youtu.be/VID`, `/shorts/VID`, `/live/VID`, `/embed/VID`, `m.youtube.com/watch?v=VID` all resolve.
  - Edge case (pure): URL with tracking params `?si=xxx&t=42s` doesn't confuse detection.
  - Edge case (pure): trailing slash, uppercase host, mixed-case path — all accepted.
  - Edge case (pure): `/user/LegacyUsername` URL → goes to yt-dlp path (no direct channel-ID extraction); mocked yt-dlp returns canonical `channel_id`. Result is a `?channel_id=` feed URL — normalizes legacy form.
  - Error path (pure): playlist URL `watch?v=X&list=PL123` → raises `ValidationError` with playlist suggestion.
  - Error path (pure): `/playlist?list=PL123` → raises `ValidationError` with playlist suggestion.
  - Error path (mocked): yt-dlp returns `info["channel_id"] is None` → `ValidationError` with actionable suggestion.
  - Error path (mocked): yt-dlp raises `ExtractorError("Sign in to confirm you're not a bot")` → `ValidationError` surfaces the original message AND the manual-escape-hatch suggestion.
  - Error path (pure): non-YouTube URL (`https://example.com/feed.rss`) returns `None` (caller uses existing RSS flow).
  - Error path (pure): malformed URL (empty string, `not-a-url`) returns `None` without raising.
  - **Assertion style note:** Do not hardcode the full feed URL in happy-path assertions; use `"channel_id=UCxxx" in result[0]` so URL-format tweaks (trailing slash, host normalization) don't break tests.

  **Verification:**
  - `uv run pytest tests/unit/test_youtube_resolver.py` passes without network access (every test that would call yt-dlp asserts `YoutubeDL.return_value.__enter__.return_value.extract_info.called`).
  - `uv run ruff check src/inkwell/feeds/youtube_resolver.py` clean.

- [ ] **Unit 3: `inkwell add` wires the resolver**

  **Goal:** `inkwell add <youtube-url> --name X` resolves the URL before constructing `FeedConfig`; non-YouTube URLs pass through untouched.

  **Requirements:** R1, R2, R7

  **Dependencies:** Unit 2.

  **Files:**
  - Modify: `src/inkwell/cli.py::add_feed` (line 70)
  - Modify: `tests/integration/test_cli.py` — extend `TestCLIAdd` (or add `TestCLIAddYouTube`)

  **Approach:**
  - Before the existing `FeedConfig(url=HttpUrl(url), …)` construction, call `resolve_youtube_url(url)`.
  - If resolver returns a `(resolved_feed_url, _channel_name)` tuple, substitute `resolved_feed_url` for `url` and proceed. If resolver returns `None`, use input URL as today.
  - On resolver-raised `ValidationError`, surface via the existing error-rendering path (line 125-128).
  - No changes to `--name`, `--auth`, `--category` handling. `--category` default could be thought about later; don't auto-tag.

  **Execution note:** Start with a red integration test for the YouTube path, then the pass-through test, then wire the call.

  **Patterns to follow:**
  - Existing `add_feed` error rendering style (`[red]✗[/red] {e}` + dimmed suggestion).
  - CLI tests: `runner.invoke(app, ["add", url, "--name", "foo"])`, assert `exit_code == 0` and inspect `ConfigManager(config_dir=tmp_path).get_feed("foo").url`.

  **Test scenarios:**
  - Happy path: `add https://www.youtube.com/watch?v=VID --name foo` (mocked resolver) stores `feed_url` with `channel_id` query param as `FeedConfig.url`.
  - Happy path: `add https://www.youtube.com/channel/UCxxx --name foo` resolves via pure URL layer (no yt-dlp mock needed).
  - Happy path: `add https://www.youtube.com/feeds/videos.xml?channel_id=UCxxx --name foo` passes through unchanged.
  - Happy path (regression): `add https://example.com/feed.rss --name foo` works exactly as before (resolver returns `None`, existing flow runs).
  - Error path: resolver raises `ValidationError` → CLI exits non-zero with rendered error + suggestion.
  - Edge case: existing feed with same `--name` errors via the existing `ConfigManager` duplicate-name path — YouTube resolution must happen *before* the duplicate check so the error UX is unchanged.

  **Verification:**
  - `uv run pytest tests/integration/test_cli.py` passes.
  - Manual smoke: `uv run inkwell add "https://www.youtube.com/watch?v=pKeZ5XK2vp4" --name smoke-test --category interview` succeeds; `inkwell list feeds` shows the channel RSS URL; `inkwell fetch smoke-test --latest --dry-run` proceeds past parsing (depends on Unit 1).

- [ ] **Unit 4: Hint message after YouTube-URL fetch**

  **Goal:** `inkwell fetch <youtube-url>` (successful, no `--save-source`) prints a dimmed hint guiding the user toward `--save-source`. Suppressed on failure, for saved-feed lookups, and when `--save-source` was already passed.

  **Requirements:** R3, R5

  **Dependencies:** Unit 2 (needs resolver to tell "is this a YouTube URL?"). Unit 5 runs in parallel — no code-level dependency.

  **Files:**
  - Modify: `src/inkwell/cli.py::fetch_command` (line 569; hint block near final success output)
  - Modify: `tests/integration/test_cli.py` — extend `TestCLIFetch`

  **Approach:**
  - After the fetch completes successfully, if input was recognized as a YouTube URL (resolver would've returned non-None) and `--save-source` was not passed, print: `[dim]Want to track this channel? Re-run with [cyan]--save-source --source-name <name>[/cyan] to save it as a feed.[/dim]`
  - A helper `_should_show_save_source_hint(url: str, save_source: bool, feed_name_arg: str) -> bool` centralizes the logic; unit-testable separately.

  **Execution note:** Test-first: write tests pinning each suppression condition, then the positive case. Implement last.

  **Patterns to follow:**
  - Dimmed/cyan rendering via `rich.console.Console.print` already used in `cli.py:690` (`Use [cyan]inkwell list[/cyan]...`).

  **Test scenarios:**
  - Happy path: fetch YouTube URL without `--save-source` on success → hint printed.
  - Suppressed: fetch with `--save-source` → no hint.
  - Suppressed: fetch non-YouTube URL → no hint.
  - Suppressed: fetch of a saved feed name (not a URL) → no hint.
  - Suppressed: fetch fails (exception raised) → no hint.
  - Integration (real console): capturing `runner.invoke(...).stdout` contains the hint text including the `--save-source` flag name.

  **Verification:**
  - `uv run pytest tests/integration/test_cli.py::TestCLIFetch` passes.
  - Manual: run `inkwell fetch <yt-url> --dry-run`, see the hint at end of output.

- [ ] **Unit 5: `--save-source` flag wires to `add_feed`**

  **Goal:** `inkwell fetch <youtube-url> --save-source --source-name X` saves the video's channel as a feed after a successful fetch. Save errors become warnings, not exit failures. Pre-fetch validation errors exit non-zero.

  **Requirements:** R3, R4

  **Dependencies:** Unit 2 (resolver).

  **Files:**
  - Modify: `src/inkwell/cli.py::fetch_command` — add `--save-source` / `--source-name` options and post-fetch save block (all logic inline — no new module; totals ~30 lines)
  - Modify: `tests/integration/test_cli.py` — new class `TestCLIFetchSaveSource`

  **Approach:**
  - New typer options on `fetch_command`:
    - `save_source: bool = typer.Option(False, "--save-source", help="Also save this video's channel as a feed")`
    - `source_name: str | None = typer.Option(None, "--source-name", help="Name for the saved source (required with --save-source)")`
  - **Pre-fetch validation (exit non-zero on failure — happens BEFORE fetch pipeline starts):**
    1. If `save_source` and `source_name is None` → raise `ValidationError("--save-source requires --source-name", suggestion="Pass --source-name <name> to save the channel with a specific name")`.
    2. If `save_source` and input URL is not a YouTube URL (i.e., resolver returns `None`) → raise `ValidationError("--save-source only supports YouTube URLs currently", suggestion="For non-YouTube sources, use 'inkwell add <feed-url> --name <name>' instead")`.
    3. If `save_source` and input URL is a saved feed name (not a URL at all) → same error as #2 (need a YouTube URL).
  - **Post-fetch save (warnings only on failure):**
    1. If `save_source` is False → skip entirely (Unit 4's hint block handles guidance when appropriate).
    2. Call `resolve_youtube_url(url)` to get `(resolved_feed_url, _channel_name)`.
    3. Call `ConfigManager.add_feed(source_name, FeedConfig(url=HttpUrl(resolved_feed_url), category=None))`.
    4. On success: `console.print(f"[green]✓[/green] Saved channel as feed '[bold]{source_name}[/bold]'")`.
    5. On any exception (duplicate name via existing `ConfigManager`, disk error, resolver failure): `console.print(f"[yellow]⚠[/yellow] Couldn't save source: {e}")` — do NOT re-raise; fetch exit code remains 0.

  **Execution note:** Start with failing tests for each pre-fetch validation branch, then each post-fetch save branch. Characterization-adjacent enough that test-first locks each branch cleanly.

  **Patterns to follow:**
  - Typer option declarations: mirror existing `fetch_command` options (line 569+).
  - Warning formatting: no existing `⚠` precedent — use `[yellow]⚠[/yellow]` to distinguish from hard errors (`[red]✗[/red]`).
  - `ConfigManager.add_feed` duplicate-name handling: rely on existing behavior (raises `ValidationError`); catch + downgrade to warning per post-fetch rule.

  **Test scenarios:**
  - Happy path: `fetch <watch-url> --save-source --source-name my-channel` (mocked fetch + resolver) saves feed named `my-channel`; `list feeds` shows it.
  - Pre-fetch error: `fetch <watch-url> --save-source` (no `--source-name`) → CLI exits non-zero with actionable ValidationError; fetch pipeline never runs.
  - Pre-fetch error: `fetch <non-youtube-rss> --save-source --source-name foo` → CLI exits non-zero; fetch pipeline never runs.
  - Pre-fetch error: `fetch <saved-feed-name> --save-source --source-name foo` → CLI exits non-zero (URL is not a YouTube URL).
  - Post-fetch error: fetch succeeds, `add_feed` raises duplicate-name → warning printed, fetch exit code remains 0.
  - Post-fetch error: fetch succeeds, resolver fails mid-run (yt-dlp transient error) → warning printed, fetch exit code remains 0.
  - Regression: `fetch <youtube-url>` without `--save-source` → no save happens; config unchanged; hint printed (Unit 4 behavior).
  - Integration: end-to-end with mocked fetch success — run `fetch --save-source --source-name foo`, assert feed persisted in `ConfigManager(config_dir=tmp_path).list_feeds()`.

  **Verification:**
  - `uv run pytest tests/integration/test_cli.py::TestCLIFetchSaveSource` passes.
  - Manual: `uv run inkwell fetch "https://www.youtube.com/watch?v=pKeZ5XK2vp4" --dry-run --save-source --source-name oren-meets-world` saves the feed; re-running errors-become-warning via existing duplicate-name handling.

- [ ] **Unit 6: ADR, devlog, and docs updates**

  **Goal:** Document the decisions and changes per the project's DKS and user-docs conventions.

  **Requirements:** (supports all)

  **Dependencies:** Decisions from Units 2, 3, 5 finalized.

  **Files:**
  - Create: `docs/building-in-public/adr/036-youtube-url-resolution.md`
  - Create: `docs/building-in-public/devlog/2026-04-22-youtube-url-ingestion.md` (start this as soon as the branch opens; close out when merged)
  - Modify: `docs/reference/cli-commands.md` — document `--save-source`, `--source-name`, and that `add`/`fetch` accept YouTube URLs
  - Modify: `docs/user-guide/feeds.md` — add a "YouTube channels" subsection showing the paste-a-URL workflow

  **Approach:**
  - ADR 036 follows the template at `docs/building-in-public/adr/000-template.md` — brief, per CLAUDE.md guidance. Captures: *why YouTube URL resolution belongs in the CLI layer and not a new `ContentSource` abstraction*; *why yt-dlp Python API over subprocess*; *why parse channel_id from URL rather than add a `FeedConfig` field*; *what the `--save-source` default-false UX trades off*.
  - Devlog: one entry per `docs/building-in-public/devlog/` template — record the user-session trace, empirical feedparser check, and decisions.
  - CLI reference: add flag rows matching existing table styles.
  - User guide: 3-paragraph section after existing `add` docs — show `inkwell add <channel-url>`, `inkwell fetch <video-url>`, and `--save-source`.

  **Patterns to follow:**
  - `docs/building-in-public/adr/005-rss-parser-library.md` is a good length reference for brief ADRs.
  - `docs/reference/cli-commands.md` — match the `## inkwell fetch` heading style and option table format.

  **Test scenarios:**
  - Test expectation: none — docs-only unit. Verification is human review.

  **Verification:**
  - `mkdocs build --strict` (or whatever the project's docs build command is) runs clean.
  - ADR 036 renders correctly in the `docs/building-in-public/adr/index.md` listing (check whether index needs manual update).

## System-Wide Impact

- **Interaction graph:** `cli.py::add_feed` gains a pre-processing call to `resolvers.youtube`; `cli.py::fetch_command` gains a post-fetch save block and hint block; `feeds/parser.py::_extract_enclosure_url` gains a YouTube branch. No other module changes.
- **Error propagation:** Resolver errors surface as `ValidationError` with suggestions, rendered by the existing CLI error path. `--save-source` save failures become warnings (yellow), do not affect exit code.
- **State lifecycle risks:** `--save-source` could leave config in a state where fetch succeeded but save failed — intentional per design decision. User sees an obvious warning; re-running with `--save-source` is safe (idempotent via collision detection).
- **API surface parity:** `inkwell add` and `inkwell fetch` both gain YouTube URL support. Other commands (`remove`, `list`, `config`, `transcribe`, `cache`, `costs`) unchanged — they operate on saved feeds by name, not on URLs.
- **Integration coverage:** Unit tests mock yt-dlp; at least one end-to-end manual smoke test (fetch a real YouTube channel feed via saved feed name) is required before merging to verify the parser + downloader + transcription path actually chains end-to-end. Note in PR checklist.
- **Unchanged invariants:** RSS-native `add` flow, `FeedConfig` schema, `ConfigManager.add_feed` duplicate-name semantics, `FeedValidator` behavior, existing `fetch` exit codes for non-YouTube URLs — all preserved.

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| yt-dlp extractor breaks against a YouTube-side change (happens periodically) | Resolver `ValidationError` explicitly surfaces the manual escape hatch in its `suggestion`: users can still `inkwell add https://www.youtube.com/feeds/videos.xml?channel_id=UCxxx --name X` directly. ADR 036 documents this externality. yt-dlp version pinned via `uv.lock`. |
| YouTube rate-limiting / bot-check interstitial ("Sign in to confirm you're not a bot") during resolution | yt-dlp surfaces this as `ExtractorError` — resolver catches and wraps in `ValidationError` whose message includes the original yt-dlp error text (so the cause is visible) plus the manual-escape-hatch suggestion. |
| feedparser upgrade changes `yt_videoid` surfacing | Test scenario covers `entry.id` fallback path; if feedparser regresses, tests surface it loudly. |
| YouTube changes RSS endpoint shape | Beyond our control. If it happens, `FeedValidator` catches the error at registration time. Documented in ADR 036 as a known externality. |
| User pastes a private/region-blocked video URL | Resolver raises `ValidationError` with a suggestion; no silent failure. |
| User pastes a playlist URL (`?list=`) expecting playlist subscription | Resolver explicitly rejects with actionable `ValidationError` directing them to the channel URL. Prevents silent channel-widening. |
| Existing users' stored feed URLs get mis-identified as YouTube on the *parsing* side | Parser uses `yt_videoid` key presence (YouTube-namespaced) — non-YouTube feeds never populate this. Risk is zero. |
| Unit 2 test mock targets wrong symbol (`inkwell.audio.downloader.YoutubeDL` vs resolver's own import) | Plan explicitly names mock target: `inkwell.feeds.youtube_resolver.YoutubeDL`. Flow-reviewer called this out as a common pytest foot-gun. |

## Documentation / Operational Notes

- No migration required — zero schema changes.
- No new config keys.
- No new required dependencies (yt-dlp already present).
- Release notes should call out: "Paste any YouTube URL into `inkwell add`" and "New `--save-source` flag on `inkwell fetch`".
- User docs updates (Unit 6) ship in the same PR.

## Sources & References

- Origin session: 2026-04-22 user conversation (no brainstorm doc; direct planning bootstrap).
- Roadmap context: `2026-roadmap/03-universal-content-ingestion.md` (this work is incremental; generalized `ContentSource` deferred).
- Related issue: [#37 — Auto-slugify feed names](https://github.com/chekos/inkwell-cli/issues/37) (deferred companion work).
- Target files:
  - `src/inkwell/cli.py` (add_feed, fetch_command)
  - `src/inkwell/feeds/parser.py` (RSSParser._extract_enclosure_url)
  - `src/inkwell/audio/downloader.py` (yt-dlp Python-API pattern to mirror)
  - `src/inkwell/utils/errors.py` (ValidationError shape)
- ADR 005 (RSS parser library) — context for parser extension.
- CLAUDE.md — DKS conventions.
