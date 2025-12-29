# Quick Start

Process your first podcast episode in under 5 minutes.

---

## Prerequisites

- Inkwell installed (`pip install inkwell-cli`)
- ffmpeg installed
- Google AI API key

---

## Step 1: Set Your API Key

```bash
inkwell config set transcription.api_key "your-google-ai-api-key"
```

Or use an environment variable:

```bash
export GOOGLE_API_KEY="your-google-ai-api-key"
```

---

## Step 2: Process an Episode

You can process any YouTube video or podcast episode directly:

```bash
inkwell fetch https://youtube.com/watch?v=your-video-id
```

**What happens:**

1. Inkwell checks for a free YouTube transcript
2. If unavailable, it transcribes using Gemini
3. AI extracts key information (summary, quotes, concepts)
4. Markdown files are created in your output directory

---

## Step 3: View Your Notes

```bash
ls ~/inkwell-notes/
```

You'll see a folder for each processed episode:

```
~/inkwell-notes/
└── podcast-2025-01-15-episode-title/
    ├── .metadata.yaml
    ├── summary.md
    ├── quotes.md
    ├── key-concepts.md
    └── tools-mentioned.md
```

Open any `.md` file to see your structured notes!

---

## Optional: Add a Podcast Feed

For recurring podcasts, add the feed once:

```bash
# Add a feed
inkwell add "https://example.com/podcast/feed.rss" --name my-podcast

# List your feeds
inkwell list

# Process the latest episode
inkwell fetch my-podcast --latest
```

---

## Optional: Interview Mode

Capture your personal insights with guided Q&A:

```bash
# Requires Anthropic API key
export ANTHROPIC_API_KEY="your-key"

# Process with interview
inkwell fetch my-podcast --latest --interview
```

---

## Check Your Costs

```bash
inkwell costs
```

**Typical costs:**

- YouTube transcript: **Free**
- Gemini transcription: ~$0.01/hour of audio
- Extraction (3 templates): ~$0.005

---

## Next Steps

- [Your First Episode](first-episode.md) - Detailed tutorial
- [Managing Feeds](../user-guide/feeds.md) - Add more podcasts
- [Content Extraction](../user-guide/extraction.md) - Customize templates
- [Obsidian Integration](../user-guide/obsidian.md) - Use with Obsidian
