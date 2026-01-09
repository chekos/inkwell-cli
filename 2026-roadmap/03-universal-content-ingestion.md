# Universal Content Ingestion

**Category:** New Feature | Architecture
**Quarter:** Q2
**T-shirt Size:** XL

## Why This Matters

Inkwell currently transforms podcasts into knowledge, but podcasts represent only one slice of audio/video learning content. YouTube tutorials, conference talks, audiobooks, online courses, recorded meetings, and lecture series all contain valuable knowledge that benefits from the same treatment: transcription, extraction, and reflection.

Expanding to universal content ingestion transforms Inkwell from "podcast note-taker" to "learning content processor"—a fundamentally larger market and use case. The core pipeline (transcribe → extract → interview → output) is content-agnostic; the limiting factor is input handling.

This positions Inkwell as the definitive tool for transforming any audio/video content into structured, searchable knowledge. Competitors like Snipd focus solely on podcasts; going universal creates clear differentiation.

## Current State

**Existing capabilities:**
- RSS feed parsing for podcasts
- YouTube transcript extraction (via `youtube-transcript-api`)
- Audio download via `yt-dlp` (already supports 1000+ sites)
- Gemini audio transcription fallback
- URL-based processing (`inkwell fetch <url>`)

**Current limitations:**
- Feed management designed around RSS/Atom only
- Episode selection assumes podcast-style episodic content
- Metadata extraction assumes podcast structure
- No support for playlists, channels, or course structures
- No video processing (visual content ignored)
- Single-file focus—no batch URLs

**Files involved:**
- `src/inkwell/feeds/parser.py` - RSS-centric parsing
- `src/inkwell/feeds/models.py` - Episode model
- `src/inkwell/audio/downloader.py` - yt-dlp wrapper (already flexible)

## Proposed Future State

Inkwell ingests any audio/video content from:

1. **Direct URLs:**
   - YouTube videos, playlists, channels
   - Vimeo, Wistia, Loom videos
   - Coursera, Udemy, LinkedIn Learning courses
   - Spotify podcast episodes
   - Conference talk recordings (InfoQ, Strange Loop, etc.)
   - Local audio/video files

2. **Structured sources:**
   - YouTube playlists → maintain episode order
   - Online courses → preserve module/lesson hierarchy
   - Conference proceedings → speaker/session metadata
   - Audiobook chapters → book structure

3. **Visual intelligence (optional):**
   - Extract slides/diagrams from video
   - OCR text from screen recordings
   - Identify and link mentioned resources

4. **Smart metadata:**
   - Auto-detect content type and structure
   - Extract rich metadata (speakers, topics, duration)
   - Cross-reference with external databases (Goodreads for books, IMDb for talks)

## Key Deliverables

- [ ] Create `ContentSource` abstraction replacing RSS-specific feed parsing
- [ ] Implement `YouTubePlaylistSource` for playlist/channel ingestion
- [ ] Implement `LocalFileSource` for local audio/video files
- [ ] Implement `URLSource` for arbitrary URLs (using yt-dlp flexibility)
- [ ] Create `CourseSource` for structured learning content (chapters, modules)
- [ ] Add content type detection and appropriate template selection
- [ ] Support batch URL processing (`inkwell fetch urls.txt` or stdin)
- [ ] Add `--preserve-structure` flag for hierarchical content
- [ ] Create category-specific templates: `course/`, `talk/`, `audiobook/`
- [ ] Implement video frame extraction for visual content (slides, diagrams)
- [ ] Add OCR for screen recordings using Gemini vision
- [ ] Update documentation with new content type workflows

## Prerequisites

- **Initiative #02 (Plugin Architecture):** Content sources should be plugins
- **Initiative #01 (CI/CD Pipeline Excellence):** Testing for new content types

## Risks & Open Questions

- **Risk:** Some platforms block automated access. Mitigation: Use yt-dlp's browser cookie support, respect rate limits.
- **Risk:** Video processing significantly increases complexity. Mitigation: Make visual extraction optional, start with audio-only.
- **Risk:** Course/audiobook ingestion may hit paywalls. Mitigation: Same auth pattern as private podcast feeds.
- **Question:** Should visual extraction happen automatically or be opt-in?
- **Question:** How to handle content without clear "episodes" (e.g., 2-hour lecture)?
- **Question:** Should we support live/streaming content or recorded only?

## Notes

**yt-dlp already supports:**
- YouTube, Vimeo, Dailymotion, Twitch VODs
- Coursera, Udemy, LinkedIn Learning (with authentication)
- SoundCloud, Bandcamp (audio)
- 1000+ other sites

**Content type mapping:**
```yaml
content_types:
  youtube_video: uses template "video/default"
  youtube_playlist: creates directory per video, maintains order
  course: creates module/lesson hierarchy
  audiobook: creates chapter structure
  conference_talk: enriches with speaker bio, event metadata
```

**Related files:**
- `src/inkwell/audio/downloader.py` - yt-dlp integration point
- `src/inkwell/templates/` - Add new category templates
- `src/inkwell/output/models.py` - Extend for hierarchical output
