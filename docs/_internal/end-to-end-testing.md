# End-to-End Testing Guide

**Purpose**: Test the complete Inkwell pipeline from RSS feed to markdown output.

**Time Required**: ~5 minutes
**Prerequisites**:
- Project cloned and `uv sync --dev` complete
- Google AI API key configured (see Step 1.5 below)
- (Optional) Anthropic API key for interview mode

---

## Step 1: Verify Installation

```bash
uv run inkwell version
```

**Expected output**:
```
Inkwell CLI v1.0.0
```

---

## Step 1.5: Configure API Key

Set your Google AI API key using the CLI:

```bash
uv run inkwell config set transcription.api_key "YOUR_GOOGLE_AI_API_KEY"
```

**Expected output**:
```
✓ API key configured: ••••••••••••_KEY
  Saved to transcription settings
```

---

## Step 2: Check Configuration

```bash
uv run inkwell config show
```

**Expected output**: Shows your config including API key status:
```
Transcription API key  ✓ ••••••••_KEY (config)
Extraction API key     not set
Interview API key      not set
```

The `(config)` indicator confirms your key was saved. You'll see `(env)` if using environment variables.

---

## Step 3: Add a Podcast Feed

Use any public RSS feed. Here's a reliable test feed:

```bash
uv run inkwell add "https://feeds.simplecast.com/54nAGcIl" --name syntax --category tech
```

**Expected output**:
```
Feed added: syntax
  URL: https://feeds.simplecast.com/54nAGcIl
  Category: tech
```

**Verify it was saved**:
```bash
uv run inkwell list
```

---

## Step 4: List Episodes from the Feed

```bash
uv run inkwell episodes syntax --limit 5
```

**Expected output**: Table showing episode titles, dates, and durations.

---

## Step 5: Fetch and Process an Episode

### Option A: Fetch Latest Episode

```bash
uv run inkwell fetch syntax --latest
```

### Option B: Fetch Specific Episode by Keyword

```bash
uv run inkwell fetch syntax --episode "CSS"
```

### Option C: Fetch by Direct URL

If you have a specific episode URL:

```bash
uv run inkwell fetch "https://www.youtube.com/watch?v=VIDEO_ID"
```

**What happens during fetch**:

1. **Metadata extraction** - Gets episode title, date, duration
2. **Transcription** - Tries YouTube API first (free), falls back to Gemini
3. **Content extraction** - Uses LLM to extract summaries, quotes, concepts
4. **Markdown generation** - Creates structured files with wikilinks

**Expected output**:
```
Processing: [Episode Title]

Transcription: YouTube API (free)
Extraction: gemini-2.0-flash

Templates: 3 (summary, quotes, key-concepts)
Cost: $0.XX

Output: ./output/syntax-YYYY-MM-DD-episode-title/

Complete!
```

---

## Step 6: Verify Output Files

```bash
ls -la output/
```

Navigate into the created directory:

```bash
cd output/syntax-*/  # Tab-complete to the right directory
ls -la
```

**Expected files**:
```
.metadata.yaml      # Episode metadata, timestamps, costs
summary.md          # AI-generated summary
quotes.md           # Notable quotes extracted
key-concepts.md     # Key concepts explained
```

If you used `--category tech`, you'll also see:
```
tools-mentioned.md  # Tools and resources mentioned
```

### View the Summary

```bash
cat summary.md
```

**Check for**:
- YAML frontmatter with metadata
- Wikilinks like `[[Topic Name]]`
- Tags like `#podcast #tech`
- Structured sections (Overview, Key Takeaways, etc.)

---

## Step 7: Check Costs

```bash
uv run inkwell costs
```

**Expected output**: Table showing costs by provider and operation.

For more detail:
```bash
uv run inkwell costs --recent 5
```

---

## Step 8: Check Cache Stats

```bash
uv run inkwell cache stats
```

**Expected output**: Shows cached transcripts (saves money on re-runs).

---

## Step 9: (Optional) Test Interview Mode

Requires `ANTHROPIC_API_KEY`:

```bash
uv run inkwell fetch syntax --latest --interview
```

This starts an interactive Q&A session. Answer 3-5 questions, then check:

```bash
cat output/syntax-*/my-notes.md
```

---

## Step 10: Clean Up (Optional)

Remove test feed:
```bash
uv run inkwell remove syntax
```

Clear cache:
```bash
uv run inkwell cache clear
```

---

## Troubleshooting

### "Feed not found"

Check the feed URL is accessible:
```bash
curl -I "https://feeds.simplecast.com/54nAGcIl"
```

### "API key not found"

Verify environment variable:
```bash
echo $GOOGLE_API_KEY
```

### "Transcription failed"

Try with verbose logging:
```bash
uv run inkwell fetch syntax --latest -v
```

### "No YouTube transcript available"

This is normal for many podcasts. Gemini fallback will be used (costs ~$0.05-0.15).

---

## Test with Your Own Feed

Replace the Syntax feed with your own:

```bash
# Add your feed
uv run inkwell add "YOUR_RSS_FEED_URL" --name myfeed

# List episodes to verify
uv run inkwell episodes myfeed --limit 5

# Process latest
uv run inkwell fetch myfeed --latest
```

### Private/Paid Feeds

If your feed requires authentication:

```bash
uv run inkwell add "YOUR_PRIVATE_FEED_URL" --name premium --auth
# You'll be prompted for credentials
```

---

## Quick Reference

| Command | Purpose |
|---------|---------|
| `inkwell add <url> --name <name>` | Add feed |
| `inkwell list` | Show all feeds |
| `inkwell episodes <name>` | List episodes |
| `inkwell fetch <name> --latest` | Process latest episode |
| `inkwell fetch <name> --episode "keyword"` | Process episode matching keyword |
| `inkwell costs` | View API costs |
| `inkwell cache stats` | View cache info |
| `inkwell config show` | View configuration |

---

## Success Criteria

Your end-to-end test is successful if:

- [ ] `inkwell version` shows version
- [ ] `inkwell add` successfully adds a feed
- [ ] `inkwell list` shows the added feed
- [ ] `inkwell episodes` lists episodes from the feed
- [ ] `inkwell fetch` creates output directory with markdown files
- [ ] Output files contain proper frontmatter and wikilinks
- [ ] `inkwell costs` shows the operation cost

