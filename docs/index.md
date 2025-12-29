# Inkwell

**Transform podcast episodes into structured, searchable markdown notes.**

Inkwell downloads podcast audio, transcribes it, extracts key information using AI, and generates Obsidian-compatible notes—all from the command line.

---

## Quick Start

```bash
# Install with pip
pip install inkwell-cli

# Set your API key
export GOOGLE_API_KEY="your-key-here"

# Process your first episode
inkwell fetch https://youtube.com/watch?v=your-video-id
```

That's it! Your structured notes are now in `~/inkwell-notes/`.

---

## Features

### Automatic Transcription
Inkwell first checks for free YouTube transcripts. If unavailable, it uses Google's Gemini for accurate audio transcription.

### AI-Powered Extraction
Extract what matters from each episode:

- **Summaries** - Episode overview and key takeaways
- **Quotes** - Notable quotes with speaker attribution
- **Key Concepts** - Main ideas and themes discussed
- **Tools Mentioned** - Software, apps, and products referenced
- **Books Mentioned** - Reading recommendations

### Obsidian Integration
Output is designed for Obsidian with:

- YAML frontmatter for Dataview queries
- Wikilinks to connect concepts across episodes
- Tags for easy filtering and search
- Episode folders that work as Obsidian vaults

### Interview Mode
Capture your personal insights with guided Q&A after processing. Your thoughts become `my-notes.md`—turning passive listening into active learning.

### Cost Tracking
Know exactly what you're spending. Inkwell tracks API costs per episode and shows estimates before processing.

---

## What You Get

Each processed episode creates a folder with structured markdown:

```
~/inkwell-notes/podcast-2025-01-15-episode-title/
├── .metadata.yaml      # Episode metadata and costs
├── summary.md          # Episode overview
├── quotes.md           # Notable quotes
├── key-concepts.md     # Main ideas explained
├── tools-mentioned.md  # Software and resources
└── my-notes.md         # Your insights (with --interview)
```

---

## Next Steps

<div class="grid cards" markdown>

-   :material-download:{ .lg .middle } **Installation**

    ---

    Detailed setup instructions for all platforms

    [:octicons-arrow-right-24: Installation Guide](getting-started/installation.md)

-   :material-rocket-launch:{ .lg .middle } **Quick Start**

    ---

    Process your first episode in 5 minutes

    [:octicons-arrow-right-24: Quick Start](getting-started/quickstart.md)

-   :material-book-open-variant:{ .lg .middle } **User Guide**

    ---

    Complete feature documentation

    [:octicons-arrow-right-24: User Guide](user-guide/index.md)

-   :material-code-tags:{ .lg .middle } **Reference**

    ---

    CLI commands, templates, and configuration

    [:octicons-arrow-right-24: Reference](reference/index.md)

</div>

---

## Building in Public

Inkwell is built in public. Browse our [engineering notes](building-in-public/index.md) to see:

- **Architecture Decisions** - Why we made the choices we did
- **Engineering Logs** - Day-by-day development progress
- **Research** - Technology evaluations and best practices
- **Experiments** - Benchmarks and proof-of-concepts
- **Lessons Learned** - What worked, what didn't

---

## Requirements

- Python 3.10+
- ffmpeg (for audio processing)
- Google AI API key (for transcription and extraction)
- Anthropic API key (optional, for interview mode)

---

## Get Help

- [Troubleshooting Guide](reference/troubleshooting.md)
- [GitHub Issues](https://github.com/chekos/inkwell-cli/issues)
- [GitHub Discussions](https://github.com/chekos/inkwell-cli/discussions)
