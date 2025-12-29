# Getting Started

Welcome to Inkwell! This section will help you get up and running quickly.

## Choose Your Path

### New to Inkwell?

Start with the **Quick Start** guide to process your first episode in under 5 minutes:

[:octicons-arrow-right-24: Quick Start](quickstart.md)

### Need Detailed Setup?

The **Installation Guide** covers all platforms, dependencies, and configuration options:

[:octicons-arrow-right-24: Installation Guide](installation.md)

### Ready to Learn More?

The **First Episode Tutorial** walks through a complete workflow with explanations:

[:octicons-arrow-right-24: Your First Episode](first-episode.md)

---

## What You'll Need

Before you begin, make sure you have:

- **Python 3.10+** - Check with `python --version`
- **ffmpeg** - Required for audio processing
- **uv** - Modern Python package installer ([install uv](https://docs.astral.sh/uv/getting-started/installation/))
- **Google AI API key** - For transcription and extraction

Optional:
- **Anthropic API key** - For interview mode

---

## Quick Overview

```bash
# 1. Install Inkwell
uv tool install inkwell-cli

# 2. Set your API key
export GOOGLE_API_KEY="your-key"

# 3. Add a podcast feed
inkwell add "https://example.com/feed.rss" --name my-podcast

# 4. Process the latest episode
inkwell fetch my-podcast --latest
```

Your notes are now in `~/inkwell-notes/`!

---

## Next Steps

After getting started, explore the [User Guide](../user-guide/index.md) for complete feature documentation.
