# PRD: Inkwell - Podcast Transcriber & Note Extractor

## Overview

Inkwell is a CLI tool that transforms podcast episodes into structured, searchable markdown notes. It downloads audio from RSS feeds (including private/paid feeds), transcribes content, extracts key information through LLM processing, and optionally conducts an interactive interview to capture personal insights. All output is saved as organized markdown files ready for knowledge management systems like Obsidian.

## Vision

Enable deep learning from podcasts by creating a system that not only captures *what was said* but also *what you thought about it*. Transform passive listening into active knowledge building.

## Goals

- **Automated transcription pipeline**: From RSS feed URL to structured markdown with minimal user intervention
- **Flexible extraction**: Smart, content-aware categorization that adapts to different podcast types
- **Interactive reflection**: LLM-guided interview process to capture personal insights and connections
- **Knowledge management ready**: Output structured for Obsidian and similar PKM systems
- **Simple UX**: Follow the `llm` tool pattern - config files, intuitive CLI, minimal friction

## Non-Goals (v0.1-0.3)

- Web UI or GUI interface
- Real-time transcription during listening
- Automatic episode detection/scheduling
- Multi-language transcription (English only initially)
- Audio quality enhancement
- Integration with podcast players

## User Stories

**As a podcast listener, I want to...**
- Add my private Substack podcast feed so I can process paid content
- Run a single command to process the latest episode and get structured notes
- Have quotes and key concepts automatically extracted so I don't have to manually highlight
- Be asked thoughtful questions about the episode to help me process what I learned
- Save all outputs to my Obsidian vault in a consistent format

**As a tech podcast enthusiast, I want to...**
- Automatically track tools and frameworks mentioned in episodes
- Have a searchable archive of technical concepts across episodes

**As someone who listens to interview podcasts, I want to...**
- Extract book recommendations automatically
- Track interesting people mentioned for future research

---

## Technical Architecture

### Stack
```yaml
Language: Python 3.10+
CLI Framework: typer
RSS Parsing: feedparser
Audio Download: yt-dlp
Transcript Extraction: youtube-transcript-api (primary), google-generativeai (fallback)
Interview Mode: claude-agent-sdk
Config Management: pyyaml
HTTP Client: httpx
Terminal Output: rich (via typer)
```

### System Flow

```
[RSS Feed] 
    → Parse → Check YouTube → Download Audio
    → Transcribe (YouTube API or Gemini)
    → LLM Extraction Pipeline
    → [Optional] Interactive Interview
    → Generate Markdown Files
    → Save to Output Directory
```

---

## Feature Breakdown

### v0.1 - Core Pipeline (No Interview)

**Goal**: Get basic extract-and-save working

#### Features:
1. **Feed Management**
   - `add`: Add feed with URL, optional auth
   - `list`: Show configured feeds
   - `remove`: Remove feed by name

2. **Episode Processing**
   - `fetch <podcast-name> --latest`: Process most recent episode
   - `fetch <podcast-name> --episode <title>`: Process specific episode
   - `fetch <url>`: Process direct episode URL

3. **Transcription**
   - Check YouTube for existing transcript first
   - Fall back to Gemini Flash transcription if unavailable
   - Handle authentication for private feeds

4. **LLM Extraction Pipeline**
   - Generate summary
   - Extract quotes
   - Identify key concepts
   - Apply contextual templates based on podcast type

5. **Output Generation**
   - Create episode directory: `podcast-name-YYYY-MM-DD-episode-title/`
   - Generate multiple markdown files per template
   - Save to configured output directory

#### Success Criteria:
- Can add/manage feeds via CLI
- Successfully processes both public and private podcast feeds
- Generates structured markdown output
- Handles YouTube transcript extraction
- Falls back to Gemini gracefully

---

### v0.2 - Interview Mode

**Goal**: Add interactive conversation layer

#### Features:
1. **Interview Flag**
   - `fetch <podcast> --latest --interview`: Trigger interview after extraction
   - Terminal-based Q&A using Claude Agent SDK

2. **Interview Flow**
   - Display extracted content summary
   - Generate contextual questions based on:
     - Episode content
     - User's interview guidelines
     - Detected themes/topics
   - Stream responses in terminal (Claude Code style)
   - Allow iterative conversation
   - Save transcript to `my-notes.md`

3. **Interview Configuration**
   - Customizable interview guidelines in config
   - Per-podcast interview styles (optional)

#### Success Criteria:
- Interview mode feels natural (like Claude Code terminal interaction)
- LLM asks relevant, content-aware questions
- Conversation transcript saved as markdown
- Can exit interview gracefully at any time

---

### v0.3 - Obsidian Integration

**Goal**: Make output Obsidian-native

#### Features:
1. **Frontmatter**
   - YAML metadata (date, podcast, episode, tags)
   - Custom fields per template

2. **Wikilinks**
   - Auto-generate `[[wikilinks]]` for:
     - Tools mentioned
     - People mentioned
     - Related concepts
   - Link to other episodes in vault

3. **Tag Generation**
   - LLM-suggested tags based on content
   - Podcast-specific tag prefixes

4. **Template System**
   - User-customizable markdown templates
   - Variable substitution
   - Per-podcast template overrides

#### Success Criteria:
- Files open seamlessly in Obsidian
- Wikilinks work and create note connections
- Tags are sensible and useful
- Templates are easily customizable

---

## Data Models

### Feed Configuration
```yaml
# ~/.config/inkwell/feeds.yaml
my-podcast:
  url: https://feed.url/rss
  auth:
    type: basic  # or none, bearer
    username: encrypted_value
    password: encrypted_value
  category: tech  # uses template_categories[tech]
  custom_templates:
    - architecture-patterns
    - startup-mentions
```

### Global Configuration
```yaml
# ~/.config/inkwell/config.yaml
default_output_dir: ~/obsidian-vault/podcasts/
transcription_model: gemini-2.0-flash-exp
interview_model: claude-sonnet-4-5
youtube_check: true

default_templates:
  - summary
  - quotes
  - key-concepts

template_categories:
  tech:
    - tools-mentioned
    - frameworks-mentioned
  interview:
    - books-mentioned
    - people-mentioned

interview_guidelines: |
  Ask about how this applies to the listener's work.
  Probe for connections to past episodes.
  Ask what surprised them or challenged their thinking.
  Keep questions open-ended and thoughtful.
```

### Episode Metadata
```yaml
# Stored in each episode directory as .metadata.yaml
podcast_name: "my-podcast"
episode_title: "Episode 123: The Future of AI"
episode_url: "https://..."
published_date: "2025-11-03"
duration_seconds: 3600
processed_date: "2025-11-03T10:30:00Z"
transcription_source: "youtube"  # or "gemini"
templates_applied:
  - summary
  - quotes
  - tools-mentioned
interview_conducted: true
```

---

## CLI Commands

### Setup & Configuration
```bash
# First-time setup
inkwell keys set gemini
inkwell keys set anthropic

# Configuration management
inkwell config show
inkwell config edit
inkwell config set output_dir ~/my-vault/podcasts/
```

### Feed Management
```bash
# Add feed
inkwell add https://feed.url/rss --name "my-podcast"
inkwell add https://feed.url/rss --name "private-podcast" --auth

# List feeds
inkwell list

# Remove feed
inkwell remove "my-podcast"
```

### Episode Processing
```bash
# Process latest episode
inkwell fetch "my-podcast" --latest

# Process with interview
inkwell fetch "my-podcast" --latest --interview

# Process specific episode
inkwell fetch "my-podcast" --episode "episode-title-keyword"

# Process direct URL (no feed required)
inkwell fetch https://episode-url.mp3

# Process and override output directory
inkwell fetch "my-podcast" --latest --output ~/different-dir/
```

---

## Output Format

### Directory Structure
```
output_dir/
  └── podcast-name-2025-11-03-episode-title/
      ├── .metadata.yaml           # Episode metadata
      ├── summary.md                # Episode summary
      ├── quotes.md                 # Extracted quotes
      ├── key-concepts.md           # Main ideas/concepts
      ├── tools-mentioned.md        # (if tech podcast)
      ├── books-mentioned.md        # (if interview podcast)
      └── my-notes.md              # (if --interview used)
```

### Markdown File Format

**summary.md**
```markdown
# Episode Title

**Podcast**: My Podcast  
**Date**: November 3, 2025  
**Duration**: 1h 23m

## Summary

[LLM-generated summary of 2-3 paragraphs]

## Key Takeaways

- Main point 1
- Main point 2
- Main point 3
```

**quotes.md**
```markdown
# Quotes

> "Quote text here with context"
> — Speaker Name [12:34]

> "Another impactful quote"
> — Speaker Name [45:12]
```

**my-notes.md** (interview output)
```markdown
# My Notes & Reflections

## How this applies to my work

[User's response to interview question]

## Connections to previous episodes

[User's response]

## What surprised me

[User's response]

## Action items

[User's response]
```

---

## Implementation Phases

### Phase 1: Foundation (Week 1)
- [ ] Project setup (pyproject.toml, structure)
- [ ] Config system (YAML read/write, encryption for auth)
- [ ] Feed management commands (add, list, remove)
- [ ] RSS parsing with feedparser

### Phase 2: Transcription (Week 2)
- [ ] YouTube transcript extraction
- [ ] yt-dlp audio download
- [ ] Gemini transcription integration
- [ ] Transcript caching

### Phase 3: Extraction Pipeline (Week 2-3)
- [ ] LLM extraction system
- [ ] Template system
- [ ] Contextual template selection
- [ ] Markdown generation
- [ ] File output

### Phase 4: Interview Mode (Week 3-4)
- [ ] Claude Agent SDK integration
- [ ] Interview question generation
- [ ] Terminal streaming interface
- [ ] Conversation state management
- [ ] Interview transcript saving

### Phase 5: Polish & Obsidian (Week 4-5)
- [ ] Error handling & retries
- [ ] Progress indicators
- [ ] Obsidian frontmatter
- [ ] Wikilink generation
- [ ] Testing & documentation

---

## Success Metrics

**v0.1 Success**
- 90%+ successful transcription rate
- <5 minute average processing time per episode
- Zero manual intervention required for public feeds

**v0.2 Success**
- Interview feels natural and engaging
- Users complete 70%+ of interview sessions
- Questions are contextually relevant

**v0.3 Success**
- Files integrate seamlessly in Obsidian
- Wikilinks create useful connections
- Users report improved knowledge retention

---

## Open Questions

1. **Transcript accuracy**: What's acceptable error rate for Gemini transcription vs. cost?
2. **Interview length**: Should there be a max number of questions, or let it flow naturally?
3. **Template discovery**: Should the tool auto-detect new template types over time?
4. **Caching strategy**: Cache transcripts? For how long?
5. **Error recovery**: Should partial failures save what's completed?

---

## Future Considerations (Post v0.3)

- Multi-language support
- Video podcast support (extract visual references)
- Automatic episode monitoring (cron-style)
- Export to other formats (Notion, Roam)
- Semantic search across episode archive
- Episode comparison/analysis
- Guest speaker tracking across episodes
- Automatic topic clustering
- Integration with spaced repetition systems
- Mobile companion app for on-the-go notes

---

## Dependencies & Requirements

**System Requirements:**
- Python 3.10+
- ffmpeg (for yt-dlp audio processing)
- 2GB RAM minimum
- Internet connection for API calls

**API Keys Required:**
- Google AI (Gemini) - Free tier available
- Anthropic (Claude) - For interview mode

**Estimated Costs:**
- Transcription: ~$0.01-0.05 per hour of audio (Gemini Flash)
- Interview: ~$0.05-0.15 per interview session (Claude Sonnet)
- Typical episode: <$0.20 total

---

## Project Name Origin

**Inkwell** - A container that holds ink for writing, symbolizing the tool's purpose: capturing the flowing content of podcasts and distilling it into written knowledge. The name evokes both the permanence of written notes and the depth of thoughtful reflection.
