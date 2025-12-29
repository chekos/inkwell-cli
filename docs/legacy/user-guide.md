# Inkwell User Guide

**Version**: 1.0.0
**Last Updated**: 2025-11-13

## Table of Contents

1. [Introduction](#introduction)
2. [Installation](#installation)
3. [Quick Start](#quick-start)
4. [Configuration](#configuration)
5. [Commands](#commands)
6. [Output Structure](#output-structure)
7. [Obsidian Integration](#obsidian-integration)
8. [Cost Management](#cost-management)
9. [Troubleshooting](#troubleshooting)

## Introduction

Inkwell transforms podcast episodes into structured, searchable markdown notes optimized for Obsidian. It automatically:

- Downloads audio from RSS feeds
- Transcribes content (YouTube API or Gemini)
- Extracts key information using LLM templates
- Generates markdown files with wikilinks and tags
- Optionally conducts an interactive interview to capture your insights

**Key Features**:
- ✅ Automated transcription (YouTube → Gemini fallback)
- ✅ LLM-powered extraction (quotes, concepts, people, books, tools)
- ✅ Obsidian integration (wikilinks, tags, Dataview frontmatter)
- ✅ Interactive interview mode (capture your thoughts)
- ✅ Cost tracking ($0.005-0.175 per episode)
- ✅ Error handling with retry logic

## Installation

### Prerequisites

- Python 3.10 or higher
- `ffmpeg` (for audio processing)
- Google AI (Gemini) API key
- Anthropic (Claude) API key (optional, for interview mode)

### Install with uv (Recommended)

```bash
# Install uv if you don't have it
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone repository
git clone https://github.com/yourusername/inkwell-cli
cd inkwell-cli

# Install dependencies
uv sync --dev

# Run inkwell
uv run inkwell --help
```

### Install ffmpeg

**macOS**:
```bash
brew install ffmpeg
```

**Ubuntu/Debian**:
```bash
sudo apt-get install ffmpeg
```

**Windows**:
```bash
choco install ffmpeg
```

### Set API Keys

```bash
# Required: Google AI (Gemini) for transcription and extraction
export GOOGLE_API_KEY="your-google-ai-api-key"

# Optional: Anthropic (Claude) for interview mode
export ANTHROPIC_API_KEY="your-anthropic-api-key"
```

**Get API Keys**:
- Google AI: https://aistudio.google.com/api-keys
- Anthropic: https://console.anthropic.com/

## Quick Start

### Process Your First Episode

```bash
# 1. Add a podcast feed
uv run inkwell add "https://feeds.simplecast.com/54nAGcIl" --name syntax

# 2. List available episodes
uv run inkwell list

# 3. Fetch and process an episode
uv run inkwell fetch syntax --latest

# Output will be in: ./output/syntax-YYYY-MM-DD-episode-title/
```

### What You'll Get

```
output/
└── syntax-2025-11-13-modern-css-features/
    ├── .metadata.yaml          # Episode metadata and costs
    ├── summary.md              # AI-generated summary
    ├── quotes.md               # Notable quotes
    ├── key-concepts.md         # Key concepts explained
    └── tools-mentioned.md      # Tools and resources
```

Each file includes:
- **Frontmatter**: Dataview-compatible metadata
- **Wikilinks**: `[[CSS Grid]]`, `[[Flexbox]]`
- **Tags**: `#css`, `#web-development`, `#frontend`
- **Structured content**: Formatted for easy reading

## Configuration

### View Current Config

```bash
uv run inkwell config --show
```

### Edit Config File

```bash
# Config location: ~/.config/inkwell/config.yaml
uv run inkwell config --edit
```

### Key Configuration Options

```yaml
# Output settings
output_directory: "~/podcasts"  # Where to save files
overwrite: false  # Don't overwrite existing files

# Extraction settings
default_provider: "gemini"  # or "claude"
templates_enabled:
  - summary
  - quotes
  - key-concepts
  - tools-mentioned
  - books-mentioned

# Obsidian integration
wikilinks_enabled: true
wikilink_style: "simple"  # "simple" or "prefixed"
tags_enabled: true
tag_style: "hierarchical"  # "flat" or "hierarchical"
max_tags: 7
dataview_enabled: true

# Cost management
max_cost_per_episode: 0.50  # Alert if exceeded
```

## Commands

### Feed Management

#### Add Feed
```bash
# Public RSS feed
uv run inkwell add "https://feed-url.com/rss" --name podcast-name

# Private/paid feed with authentication
uv run inkwell add "https://feed-url.com/rss" --name podcast-name --auth

# With category
uv run inkwell add "https://feed-url.com/rss" --name podcast-name --category tech
```

#### List Feeds
```bash
uv run inkwell list

# Output:
# Feeds:
#   syntax (https://feeds.simplecast.com/54nAGcIl)
#   tim-ferriss (https://feeds.feedburner.com/thetimferrissshow)
```

#### Remove Feed
```bash
uv run inkwell remove syntax
```

### Episode Processing

#### Fetch Latest Episode
```bash
uv run inkwell fetch podcast-name --latest
```

#### Fetch Specific Episode
```bash
uv run inkwell fetch podcast-name --episode 123
```

#### Fetch with Interview
```bash
# Interactive Q&A to capture your insights
uv run inkwell fetch podcast-name --latest --interview
```

#### Fetch Multiple Episodes
```bash
uv run inkwell fetch podcast-name --count 5
```

### Cost Management

#### View All Costs
```bash
uv run inkwell costs

# Output:
# ┌ Overall ─────────────────────┐
# │ Total Operations:  15         │
# │ Total Cost:        $0.4250    │
# └──────────────────────────────┘
```

#### Filter Costs
```bash
# By provider
uv run inkwell costs --provider gemini

# By time period
uv run inkwell costs --days 7

# Recent operations
uv run inkwell costs --recent 10

# By episode
uv run inkwell costs --episode "Building Better Software"
```

#### Clear Cost History
```bash
uv run inkwell costs --clear
```

### Transcription

#### Transcribe Only (No Extraction)
```bash
uv run inkwell transcribe "https://episode-url.com/audio.mp3" --output transcript.txt
```

### Cache Management

#### Clear Caches
```bash
uv run inkwell cache --clear transcriptions
uv run inkwell cache --clear extractions
uv run inkwell cache --clear all
```

## Output Structure

### Directory Layout

```
output/
└── [podcast-name]-[YYYY-MM-DD]-[episode-title]/
    ├── .metadata.yaml          # Episode metadata
    ├── summary.md              # Episode summary
    ├── quotes.md               # Notable quotes
    ├── key-concepts.md         # Key concepts
    ├── tools-mentioned.md      # Tools and resources
    ├── books-mentioned.md      # Book recommendations
    ├── people-mentioned.md     # People referenced
    └── my-notes.md             # Your interview notes (if --interview used)
```

### File Structure

Each markdown file includes:

```markdown
---
# Dataview frontmatter
title: Summary
podcast: Syntax FM
episode: Modern CSS Features
episode_date: 2025-11-13
duration_minutes: 15
rating: 4
status: inbox
tags: [podcast, css, web-development]
has_wikilinks: true
---

# Modern CSS Features

## Overview

Summary content here with [[CSS Grid]] and [[Flexbox]] wikilinks.

## Key Points

- Point 1 with #css tag
- Point 2 with #web-development tag

## Related

- [[CSS Basics]]
- [[Frontend Development]]
```

## Obsidian Integration

### Wikilinks

**Simple Style** (default):
```markdown
[[CSS Grid]]
[[Flexbox]]
[[Tailwind CSS]]
```

**Prefixed Style**:
```markdown
[[Tool - Tailwind CSS]]
[[Person - Wes Bos]]
[[Book - Deep Work]]
```

**Configuration**:
```yaml
wikilinks_enabled: true
wikilink_style: "simple"  # or "prefixed"
```

### Tags

**Flat Style**:
```markdown
#css #web-development #frontend #javascript
```

**Hierarchical Style** (default):
```markdown
#topic/css
#topic/web-development
#person/wes-bos
#tool/tailwind-css
```

**Configuration**:
```yaml
tags_enabled: true
tag_style: "hierarchical"  # or "flat"
max_tags: 7
```

### Dataview Queries

Example queries to use in Obsidian:

**List all podcast episodes**:
```dataview
TABLE podcast, episode_date, rating
FROM "podcasts"
WHERE template = "obsidian-note"
SORT episode_date DESC
```

**Episodes by topic**:
```dataview
TABLE episode, rating, duration_minutes
FROM "podcasts"
WHERE contains(topics, "ai")
SORT rating DESC
```

**Episodes with interviews**:
```dataview
LIST
FROM "podcasts"
WHERE has_interview = true
SORT episode_date DESC
```

**Cost analysis**:
```dataview
TABLE episode, cost_usd
FROM "podcasts"
SORT cost_usd DESC
LIMIT 10
```

See [docs/dataview-queries.md](../dataview-queries.md) for 27 more example queries.

## Cost Management

### Understanding Costs

**Transcription**:
- YouTube API: **Free** (when available)
- Gemini transcription: **$0.10-0.15** per 90min episode

**Extraction**:
- Gemini Flash: **$0.005-0.025** per episode
- Claude Sonnet: **$0.02-0.08** per episode (higher quality)

**Total**: Typically **$0.005-0.175** per episode

### Cost Optimization

1. **Prioritize YouTube transcripts**: Free and fast
2. **Use Gemini for extraction**: 5x cheaper than Claude
3. **Enable caching**: Avoid re-transcribing episodes
4. **Batch process**: Process multiple episodes together
5. **Monitor costs**: Use `inkwell costs` regularly

### Budget Alerts

Set cost limits in config:
```yaml
max_cost_per_episode: 0.50  # Alert if exceeded
monthly_budget: 10.00        # Track monthly spending
```

## Troubleshooting

### Common Issues

#### "No API key found"
```bash
# Set environment variables
export GOOGLE_API_KEY="your-key-here"
export ANTHROPIC_API_KEY="your-key-here"  # Optional
```

#### "ffmpeg not found"
```bash
# Install ffmpeg
brew install ffmpeg  # macOS
sudo apt-get install ffmpeg  # Ubuntu
```

#### "Episode already exists"
```bash
# Use --overwrite to replace existing files
uv run inkwell fetch podcast-name --latest --overwrite
```

#### "Rate limit exceeded"
```bash
# Inkwell automatically retries with exponential backoff
# If persistent, wait a few minutes and try again
```

#### "Empty transcript"
```bash
# YouTube transcript not available, will use Gemini
# Cost will be higher (~$0.10-0.15)
```

### Debug Mode

```bash
# Enable verbose logging
uv run inkwell --verbose fetch podcast-name --latest

# Check logs
cat ~/.config/inkwell/inkwell.log
```

### Getting Help

- **Documentation**: See `docs/` directory
- **Issues**: https://github.com/yourusername/inkwell-cli/issues
- **Discussions**: https://github.com/yourusername/inkwell-cli/discussions

## Advanced Usage

### Custom Templates

Create custom extraction templates in `~/.config/inkwell/templates/`:

```yaml
# actionable-advice.yaml
name: actionable-advice
description: Extract actionable advice
system_prompt: |
  Extract actionable advice from the podcast transcript.
  Focus on specific, practical steps the listener can take.
user_prompt_template: |
  Transcript:
  {transcript}

  Extract actionable advice in markdown format.
output_format: markdown
```

### Interview Mode

Interactive Q&A to capture your thoughts:

```bash
uv run inkwell fetch podcast-name --latest --interview

# You'll be prompted with questions like:
# - What was your main takeaway?
# - How does this relate to your work?
# - What will you do differently?
```

### Batch Processing

```bash
# Process last 10 episodes
uv run inkwell fetch podcast-name --count 10

# Process with interview for each
for i in {1..5}; do
  uv run inkwell fetch podcast-name --episode $i --interview
done
```

## Next Steps

- Read the [Tutorial](./tutorial.md) for a step-by-step walkthrough
- Explore [Example Workflows](./examples.md) for common use cases
- Check [Dataview Queries](../dataview-queries.md) for Obsidian integration
- Review [Cost Optimization](./cost-optimization.md) tips

## Changelog

### v1.0.0 (2025-11-13)
- Initial release
- Automated transcription (YouTube + Gemini)
- LLM-powered extraction
- Obsidian integration (wikilinks, tags, Dataview)
- Interactive interview mode
- Cost tracking
- Retry logic with exponential backoff
