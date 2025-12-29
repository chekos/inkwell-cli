# User Guide

Complete documentation for all Inkwell features.

---

## Core Features

### [Managing Feeds](feeds.md)
Add, list, and remove podcast feeds. Includes support for private/paid feeds with authentication.

### [Processing Episodes](processing.md)
Fetch and process episodes from your feeds. Understand the transcription and extraction pipeline.

### [Content Extraction](extraction.md)
Configure templates, choose providers (Claude vs Gemini), manage costs, and understand caching.

### [Interview Mode](interview.md)
Capture your personal insights with guided Q&A. Turn passive listening into active learning.

### [Obsidian Integration](obsidian.md)
Wikilinks, tags, frontmatter, and Dataview queries. Make the most of your notes in Obsidian.

### [Configuration](configuration.md)
All configuration options, file locations, and environment variables.

---

## Quick Reference

### Common Commands

```bash
# Add a feed
inkwell add <url> --name <name>

# List feeds
inkwell list

# Process latest episode
inkwell fetch <feed-name> --latest

# Process with interview
inkwell fetch <feed-name> --latest --interview

# Check costs
inkwell costs
```

### Output Structure

```
~/inkwell-notes/
└── podcast-2025-01-15-episode-title/
    ├── .metadata.yaml
    ├── summary.md
    ├── quotes.md
    ├── key-concepts.md
    ├── tools-mentioned.md
    └── my-notes.md
```

### Configuration Files

```
~/.config/inkwell/
├── config.yaml    # Global settings
├── feeds.yaml     # Feed definitions
└── .keyfile       # Encryption key
```

---

## Need Help?

- [Troubleshooting Guide](../reference/troubleshooting.md) - Common issues and solutions
- [CLI Reference](../reference/cli-commands.md) - All commands and options
- [GitHub Issues](https://github.com/chekos/inkwell-cli/issues) - Report bugs
