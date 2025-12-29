# Processing Episodes

Fetch and process podcast episodes with Inkwell.

---

## Basic Usage

### Process from URL

Process any YouTube video or podcast episode directly:

```bash
inkwell fetch https://youtube.com/watch?v=xyz
```

### Process from Feed

If you've added a feed, process by feed name:

```bash
# Latest episode
inkwell fetch my-podcast --latest

# Specific number of episodes
inkwell fetch my-podcast --count 5
```

---

## The Processing Pipeline

When you run `inkwell fetch`, here's what happens:

```
1. Download/Parse  → Get episode metadata and audio
2. Transcribe      → YouTube API (free) or Gemini (fallback)
3. Select Templates → Based on category or manual selection
4. Extract Content  → AI extracts information per template
5. Write Markdown  → Create structured note files
```

**Example output:**

```
Inkwell Extraction Pipeline

Step 1/4: Transcribing episode...
✓ Transcribed (youtube)
  Duration: 3600.0s
  Words: ~9500

Step 2/4: Selecting templates...
✓ Selected 3 templates:
  • summary (priority: 0)
  • quotes (priority: 5)
  • key-concepts (priority: 10)

Step 3/4: Extracting content...
  Estimated cost: $0.0090
✓ Extracted 3 templates
  • 0 from cache (saved $0.0000)
  • Total cost: $0.0090

Step 4/4: Writing markdown files...
✓ Wrote 3 files
  Directory: ./output/episode-2025-11-07-title/

✓ Complete!
```

---

## Command Options

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--output` | `-o` | Output directory | `~/inkwell-notes` |
| `--templates` | `-t` | Comma-separated template list | Auto-select |
| `--category` | `-c` | Episode category | Auto-detect |
| `--provider` | `-p` | LLM provider (claude, gemini) | Smart selection |
| `--skip-cache` | | Skip extraction cache | `false` |
| `--dry-run` | | Cost estimate only | `false` |
| `--overwrite` | | Overwrite existing directory | `false` |
| `--interview` | | Enable interview mode | `false` |

---

## Output Structure

Each episode creates a self-contained directory:

```
~/inkwell-notes/
└── podcast-2025-01-15-episode-title/
    ├── .metadata.yaml       # Episode metadata
    ├── summary.md           # Episode summary
    ├── quotes.md            # Notable quotes
    ├── key-concepts.md      # Key concepts
    └── tools-mentioned.md   # Tools and products
```

**Directory naming pattern:**

```
{podcast-name}-{YYYY-MM-DD}-{episode-title}/
```

### Metadata File

`.metadata.yaml` contains:

```yaml
podcast_name: Deep Questions
episode_title: Episode 42 - On Focus
episode_url: https://youtube.com/watch?v=xyz
transcription_source: youtube
templates_applied:
  - summary
  - quotes
  - key-concepts
total_cost_usd: 0.009
timestamp: 2025-11-07T10:30:00
```

### Markdown Files

Each template generates a markdown file with YAML frontmatter:

```markdown
---
template: summary
podcast: Deep Questions
episode: Episode 42 - On Focus
date: 2025-11-07
source: https://youtube.com/watch?v=xyz
---

# Summary

Episode overview and key takeaways...
```

---

## Example Workflows

### Quick Extract with Defaults

```bash
inkwell fetch https://youtube.com/watch?v=abc123
```

Uses auto-detected category, auto-selected templates, and smart provider selection.

### Custom Output Location

```bash
inkwell fetch URL --output ~/Documents/podcast-notes
```

### Specific Templates

```bash
inkwell fetch URL --templates summary,quotes,tools-mentioned
```

### Cost Check First

```bash
# Check cost without processing
inkwell fetch URL --dry-run

# If acceptable, process
inkwell fetch URL
```

### Re-extract with Different Templates

```bash
# Initial extraction
inkwell fetch URL --templates summary,quotes

# Add more templates later
inkwell fetch URL --templates summary,quotes,key-concepts --overwrite
```

---

## Transcription

### YouTube Transcripts (Free)

Inkwell first checks for existing YouTube transcripts. These are:

- **Free** - No API cost
- **Fast** - Already available
- **Accurate** - Human-corrected for popular videos

### Gemini Fallback

If no YouTube transcript exists, Inkwell uses Google's Gemini:

- Downloads audio
- Transcribes using Gemini Flash
- Cost: ~$0.01 per hour of audio

---

## Caching

Inkwell caches both transcripts and extractions:

- **Transcripts** - Cached indefinitely
- **Extractions** - Cached for 30 days

**Cache behavior:**

- Re-running the same extraction costs $0 (cache hit)
- Template version changes invalidate cache
- Use `--skip-cache` to force fresh extraction

---

## Error Handling

### Network Errors

```
✗ Failed to transcribe episode
  Reason: Network connection timeout

Suggestion: Check internet connection and retry
```

### Invalid URL

```
✗ Invalid episode URL
  URL: not-a-valid-url

Suggestion: Provide a valid YouTube or podcast URL
```

### Directory Exists

```
✗ Episode directory already exists
  Directory: ./output/podcast-2025-11-07-title/

Suggestion: Use --overwrite to replace, or delete manually
```

---

## Next Steps

- [Content Extraction](extraction.md) - Templates and providers
- [Interview Mode](interview.md) - Capture personal insights
- [Obsidian Integration](obsidian.md) - Use with Obsidian
