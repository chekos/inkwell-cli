# Inkwell CLI User Guide

Complete guide to using Inkwell for podcast note-taking.

## Table of Contents

1. [Installation](#installation)
2. [Getting Started](#getting-started)
3. [Managing Feeds](#managing-feeds)
4. [Configuration](#configuration)
5. [Content Extraction](#content-extraction)
6. [Interview Mode](#interview-mode)
7. [Troubleshooting](#troubleshooting)
8. [Advanced Usage](#advanced-usage)

## Installation

### Requirements

- Python 3.10 or higher
- pip (Python package manager)

### Install from Source

```bash
# Clone the repository
git clone https://github.com/your-username/inkwell-cli.git
cd inkwell-cli

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install Inkwell
pip install -e .

# Verify installation
inkwell --help
```

## Getting Started

### First Run

When you run Inkwell for the first time, it will automatically create configuration files:

```bash
$ inkwell list
No feeds configured yet.

Add a feed: inkwell add <url> --name <name>
```

Configuration files are created in XDG-compliant locations:
- **Linux/Mac**: `~/.config/inkwell/`
- **Config**: `config.yaml`
- **Feeds**: `feeds.yaml`
- **Encryption key**: `.keyfile` (auto-generated)

### Adding Your First Feed

```bash
# Add a public podcast feed
inkwell add https://example.com/feed.rss --name my-podcast

# Success!
✓ Feed 'my-podcast' added successfully
```

### Viewing Your Feeds

```bash
inkwell list
```

This displays a formatted table:

```
╭─────────────────────────────────────────────────────────╮
│           Configured Podcast Feeds                      │
├────────────────┬───────────────────┬──────┬─────────────┤
│ Name           │ URL               │ Auth │ Category    │
├────────────────┼───────────────────┼──────┼─────────────┤
│ my-podcast     │ example.com/...   │ —    │ —           │
╰────────────────┴───────────────────┴──────┴─────────────╯

Total: 1 feed(s)
```

## Managing Feeds

### Adding Feeds

#### Basic Feed

```bash
inkwell add <RSS_URL> --name <FEED_NAME>
```

Example:

```bash
inkwell add https://feeds.example.com/tech-podcast.rss --name tech-show
```

#### Feed with Category

Organize feeds with categories:

```bash
inkwell add https://example.com/feed.rss --name startup-podcast --category business
```

Categories help organize your podcast library. Common categories:
- `tech` - Technology podcasts
- `business` - Business and entrepreneurship
- `interview` - Interview shows
- `education` - Educational content
- `news` - News podcasts

#### Private/Paid Feeds with Authentication

For premium podcasts that require authentication:

```bash
inkwell add https://private.com/feed.rss --name premium-show --auth
```

Inkwell will prompt for credentials:

```
Authentication required
Auth type (basic/bearer): basic
Username: user@example.com
Password: ********

✓ Feed 'premium-show' added successfully
  Credentials encrypted and stored securely
```

**Authentication Types:**
- **Basic Auth**: Username + password (most common)
- **Bearer Token**: API token or key

**Security:** All credentials are encrypted using Fernet symmetric encryption before being stored.

### Listing Feeds

View all configured feeds:

```bash
inkwell list
```

The output shows:
- **Name**: Your chosen feed identifier
- **URL**: Feed URL (truncated for display)
- **Auth**: ✓ if authentication configured, — if public
- **Category**: Feed category (if set)

### Removing Feeds

#### With Confirmation

```bash
inkwell remove my-podcast
```

Inkwell will ask for confirmation:

```
Feed: my-podcast
URL:  https://example.com/feed.rss

Are you sure you want to remove this feed? [y/N]: y

✓ Feed 'my-podcast' removed
```

#### Skip Confirmation

Use `--force` to skip the confirmation prompt:

```bash
inkwell remove my-podcast --force
```

## Configuration

### Viewing Configuration

Display current configuration:

```bash
inkwell config show
```

Output:

```
╭─────────────────────────────────────────────╮
│            Configuration                     │
├─────────────────────────────────────────────┤
│ version: "1"                                 │
│ log_level: INFO                              │
│ default_output_dir: ~/podcasts               │
│ youtube_check: true                          │
│ max_episodes_per_run: 10                     │
╰─────────────────────────────────────────────╯
```

### Editing Configuration

Open configuration file in your default editor:

```bash
inkwell config edit
```

This opens `~/.config/inkwell/config.yaml` in `$EDITOR` (defaults to `vi`).

### Setting Individual Values

Change a specific configuration value:

```bash
inkwell config set log_level DEBUG
inkwell config set default_output_dir ~/Documents/podcasts
```

### Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `version` | string | `"1"` | Config format version |
| `log_level` | string | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `default_output_dir` | path | `~/podcasts` | Where to save episode notes |
| `youtube_check` | boolean | `true` | Check YouTube for transcripts first (Phase 2) |
| `max_episodes_per_run` | integer | `10` | Max episodes to process in one run (Phase 2) |
| `gemini_api_key` | string | `""` | Google AI API key (Phase 2) |
| `anthropic_api_key` | string | `""` | Anthropic API key (Phase 2) |

### Configuration File Locations

Inkwell follows XDG Base Directory specifications:

```
~/.config/inkwell/
├── config.yaml          # Global configuration
├── feeds.yaml           # Feed definitions
└── .keyfile             # Encryption key (auto-generated)

~/.local/state/inkwell/
└── inkwell.log          # Application logs

~/.cache/inkwell/
└── (future: transcripts, downloads)
```

## Content Extraction

### Overview

Inkwell transforms podcast episodes into structured markdown notes using an AI-powered extraction pipeline:

```
Podcast URL → Transcribe → Select Templates → Extract Content → Write Markdown
```

**Key features:**
- **Auto-transcription**: YouTube transcripts or Gemini fallback
- **Template-based extraction**: Quotes, summaries, key concepts, tools mentioned, etc.
- **Smart provider selection**: Claude for precision, Gemini for cost efficiency
- **Cost transparency**: Estimates before extraction, actual costs reported
- **Caching**: Saves time and money on re-processing
- **Concurrent processing**: Fast parallel template extraction

### Basic Usage

Extract content from any podcast episode:

```bash
inkwell fetch https://youtube.com/watch?v=xyz
```

**Output:**
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

Episode:    Episode from URL
Templates:  3
Total cost: $0.0090
Output:     episode-2025-11-07-title
```

### Command Options

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--output` | `-o` | Output directory | `~/inkwell-notes` |
| `--templates` | `-t` | Comma-separated template list | Auto-select |
| `--category` | `-c` | Episode category (tech, business, interview) | Auto-detect |
| `--provider` | `-p` | LLM provider (claude, gemini) | Smart selection |
| `--skip-cache` | | Skip extraction cache | `false` |
| `--dry-run` | | Cost estimate only (no extraction) | `false` |
| `--overwrite` | | Overwrite existing episode directory | `false` |

### Custom Templates

By default, Inkwell auto-selects templates based on episode category. Override with `--templates`:

```bash
# Extract specific templates
inkwell fetch URL --templates summary,quotes

# Extract all available templates
inkwell fetch URL --templates summary,quotes,key-concepts,tools-mentioned,books-mentioned
```

**Available templates:**
- `summary` - Episode overview and key takeaways
- `quotes` - Notable quotes with speaker attribution
- `key-concepts` - Main ideas and concepts discussed
- `tools-mentioned` - Software, apps, products mentioned
- `books-mentioned` - Books and resources referenced

### Provider Selection

Inkwell uses smart provider selection by default:

- **Gemini (Google AI)**: Default for most templates (40x cheaper)
- **Claude (Anthropic)**: Used for precision tasks (quotes, book extraction)

**Cost comparison:**
```
Gemini: $0.003 per template (~1M tokens)
Claude: $0.120 per template (~1M tokens)
```

**Force a specific provider:**

```bash
# Use Gemini for all templates (lowest cost)
inkwell fetch URL --provider gemini

# Use Claude for all templates (highest quality)
inkwell fetch URL --provider claude
```

**Cost estimation with dry-run:**

```bash
inkwell fetch URL --dry-run
```

This shows estimated costs without performing extraction.

### Category Specification

Categories determine which templates are auto-selected:

```bash
# Tech podcast (auto-selects: summary, quotes, tools-mentioned)
inkwell fetch URL --category tech

# Business podcast (auto-selects: summary, quotes, key-concepts)
inkwell fetch URL --category business

# Interview podcast (auto-selects: summary, quotes)
inkwell fetch URL --category interview
```

### Output Structure

Each episode creates a self-contained directory:

```
~/inkwell-notes/
└── deep-questions-2025-11-07-on-focus/
    ├── .metadata.yaml       # Episode metadata
    ├── summary.md           # Episode summary
    ├── quotes.md            # Notable quotes
    ├── key-concepts.md      # Main concepts
    └── tools-mentioned.md   # Tools and products
```

**Directory naming pattern:**
```
{podcast-name}-{YYYY-MM-DD}-{episode-title}/
```

**Metadata file (`.metadata.yaml`):**
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

**Frontmatter fields:**
- `template` - Template name
- `podcast` - Podcast name
- `episode` - Episode title
- `date` - Extraction date (YYYY-MM-DD)
- `source` - Episode URL

### Example Workflows

#### Quick Extract with Defaults

```bash
inkwell fetch https://youtube.com/watch?v=abc123
```

Uses:
- Auto-detected category
- Auto-selected templates
- Smart provider selection
- Default output directory (`~/inkwell-notes`)

#### Custom Output Location

```bash
inkwell fetch URL --output ~/Documents/podcast-notes
```

#### Tech Podcast with Custom Templates

```bash
inkwell fetch URL \
  --category tech \
  --templates summary,quotes,tools-mentioned,key-concepts
```

#### Cost-Conscious Extraction

```bash
# Check cost first
inkwell fetch URL --dry-run

# If acceptable, extract with Gemini
inkwell fetch URL --provider gemini
```

#### Re-extract with Different Templates

```bash
# Initial extraction
inkwell fetch URL --templates summary,quotes

# Add more templates later (requires --overwrite)
inkwell fetch URL \
  --templates summary,quotes,key-concepts,tools-mentioned \
  --overwrite
```

### Performance & Costs

**Caching:**
- Extractions are cached for 30 days
- Cache key includes transcript + template version
- Re-running same extraction costs $0 (cache hit)
- Clear cache with `--skip-cache`

**Concurrency:**
- Templates extracted in parallel (5x speedup)
- Multiple episodes can be processed sequentially

**Typical costs per episode:**
```
Small episode (30 min, ~5k words):
  • 3 templates with Gemini: $0.003
  • 3 templates with Claude: $0.045

Large episode (120 min, ~20k words):
  • 5 templates with Gemini: $0.012
  • 5 templates with Claude: $0.180
```

### Obsidian Integration

Inkwell's output is Obsidian-compatible:

1. **Point Obsidian to output directory:**
   - Open Obsidian settings
   - Add vault or folder: `~/inkwell-notes`

2. **Browse notes:**
   - Each episode is a folder
   - Each template is a linked note
   - Frontmatter fields are searchable

3. **Link between notes:**
   ```markdown
   See also: [[episode-name/quotes]]
   Related concept: [[another-episode/key-concepts]]
   ```

4. **Search across episodes:**
   - Use Obsidian search for quotes, concepts, tools
   - Filter by podcast name or date in frontmatter

### Error Handling

**Network errors:**
```
✗ Failed to transcribe episode
  Reason: Network connection timeout

Suggestion: Check internet connection and retry
```

**Invalid URL:**
```
✗ Invalid episode URL
  URL: not-a-valid-url

Suggestion: Provide a valid YouTube or podcast URL
```

**Insufficient API credits:**
```
✗ LLM provider error (gemini)
  Status: 429 (Rate limit exceeded)

Suggestion: Wait a few minutes or use --provider claude
```

**Directory already exists:**
```
✗ Episode directory already exists
  Directory: ./output/podcast-2025-11-07-title/

Suggestion: Use --overwrite to replace, or delete manually
```

### Advanced: Template Versioning

Templates include version numbers to ensure cache invalidation:

```yaml
# templates/summary.yaml
name: summary
version: 2  # Incremented when prompt changes
expected_format: text
# ...
```

**When a template is updated:**
- New version number invalidates cache
- Next extraction uses updated prompt
- Old cached results are ignored

## Interview Mode

**NEW in Phase 5!** Interview mode adds interactive conversation to capture your thoughts and insights about an episode.

### Overview

Interview mode conducts a thoughtful AI-guided conversation after extraction, generating questions based on episode content. Your responses are saved as `my-notes.md`, creating a personal knowledge base.

**Key features:**
- **Context-aware questions**: Based on episode content, quotes, and concepts
- **Multiple interview styles**: Reflective, analytical, creative
- **Pause and resume**: Pick up where you left off
- **Pattern-based insights**: Automatically extracts action items and themes
- **Three output formats**: Structured, narrative, or Q&A style

### Basic Usage

Add the `--interview` flag to any `fetch` command:

```bash
inkwell fetch https://youtube.com/watch?v=xyz --interview
```

**Output:**
```
Inkwell Extraction Pipeline

Step 1/5: Transcribing episode...
✓ Transcribed (youtube)

Step 2/5: Selecting templates...
✓ Selected 3 templates

Step 3/5: Extracting content...
✓ Extracted 3 templates

Step 4/5: Writing markdown files...
✓ Wrote 3 files

Step 5/5: Conducting interview...
✓ Interview complete
  Questions: 5
  Saved to: my-notes.md

✓ Complete!

Episode:         Episode from URL
Templates:       3
Extraction cost: $0.0090
Interview cost:  $0.1500
Total cost:      $0.1590
Interview:       ✓ Completed
```

### Interview Templates

Choose from three interview styles:

#### Reflective (Default)
Focus on personal insights, connections, and applications.

```bash
inkwell fetch URL --interview  # Uses default template
```

**Example questions:**
- "How does this idea connect to your own experience?"
- "What surprised you most in this episode?"
- "How might you apply this to your work?"

#### Analytical
Deep critical thinking and evaluation.

```bash
inkwell fetch URL --interview --interview-template analytical
```

**Example questions:**
- "What assumptions underlie the main argument?"
- "What evidence supports or contradicts this view?"
- "What are the limitations of this approach?"

#### Creative
Imaginative connections and new possibilities.

```bash
inkwell fetch URL --interview --interview-template creative
```

**Example questions:**
- "How could you combine this with other ideas you've learned?"
- "What would happen if you took this to an extreme?"
- "What analogies help explain this concept?"

### Configuration

Customize defaults in `~/.config/inkwell/config.yaml`:

```yaml
interview:
  enabled: true
  auto_start: false              # Set to true to always interview

  # Style preferences
  default_template: reflective   # reflective, analytical, creative
  question_count: 5              # Target number of questions
  format_style: structured       # structured, narrative, qa

  # Personal guidelines
  guidelines: |
    Focus on how this applies to my work as a software engineer.
    Ask about connections to previous episodes.
    Probe for actionable insights and blog post topics.

  # Cost control
  max_cost_per_interview: 0.50
  confirm_high_cost: true

  # Advanced
  model: claude-sonnet-4-5
  session_timeout_minutes: 60
```

### Command Options

| Option | Description | Default |
|--------|-------------|---------|
| `--interview` | Enable interview mode | `false` |
| `--interview-template` | Template: reflective, analytical, creative | From config |
| `--interview-format` | Format: structured, narrative, qa | From config |
| `--max-questions` | Number of questions | From config |
| `--no-resume` | Don't resume previous session | `false` |

### Interview Commands

During an interview, use these commands:

| Command | Description |
|---------|-------------|
| `/help` | Show available commands |
| `/skip` | Skip current question |
| `/done` | End interview early (save progress) |
| `/quit` | Exit interview without saving |
| `/history` | View conversation so far |

### Output Formats

#### Structured (Default)
Organized by themes with extracted insights.

```markdown
# My Notes & Reflections

## Key Insights
- Insight 1 extracted from responses
- Insight 2 extracted from responses

## Action Items
- [ ] Action item 1
- [ ] Action item 2

## Themes
- Theme 1 (mentioned 3 times)
- Theme 2 (mentioned 2 times)

## Question 1: ...
My response...
```

#### Narrative
Flowing text combining questions and responses.

```markdown
# My Notes & Reflections

When asked about X, I realized that...

This connects to Y because...

The most surprising aspect was...
```

#### Q&A
Simple question-and-answer format.

```markdown
# My Notes & Reflections

**Q: Question 1**
A: My response...

**Q: Question 2**
A: My response...
```

### Session Management

#### Pause and Resume

Press `Ctrl+C` during an interview to pause:

```
Interview paused. Resume with:
  inkwell interview resume <session-id>

Or abandon with:
  inkwell interview abandon <session-id>
```

Resume later:
```bash
inkwell interview resume abc123
```

#### List Sessions

View all saved sessions:

```bash
inkwell interview sessions
```

#### Cleanup

Remove old completed sessions:

```bash
inkwell interview cleanup --older-than 90d
```

### Requirements

Interview mode requires an Anthropic API key:

```bash
# Set your API key
export ANTHROPIC_API_KEY=your-key-here

# Or add to ~/.bashrc or ~/.zshrc for persistence
echo 'export ANTHROPIC_API_KEY=your-key' >> ~/.bashrc
```

**Get an API key:** https://console.anthropic.com/

### Cost Estimation

Interview mode uses Claude Sonnet 4.5:

| Component | Cost |
|-----------|------|
| Extraction | ~$0.02 per episode |
| Interview (5 questions) | ~$0.15 per episode |
| **Total with interview** | **~$0.17 per episode** |

**Cost control:**
- Cache hit: $0 (free)
- Shorter interviews: Use `--max-questions 3` (~$0.09)
- Config limit: Set `max_cost_per_interview` to prevent overruns

### Tips

#### Custom Guidelines

Tailor interview questions to your interests:

```yaml
guidelines: |
  - Focus on practical applications for my startup
  - Ask about potential blog post angles
  - Probe connections to behavioral psychology
  - Challenge my assumptions when I'm too optimistic
```

#### Interview Frequency

You don't need to interview every episode:
- **Do interview:** Complex topics, controversial ideas, personal relevance
- **Skip interview:** News updates, routine episodes, time-constrained

#### Multi-Episode Patterns

Interview several related episodes together:
```bash
inkwell fetch URL1 --interview --max-questions 3
inkwell fetch URL2 --interview --max-questions 3
inkwell fetch URL3 --interview --max-questions 3

# Then synthesize insights across all three
```

### Troubleshooting

#### "ANTHROPIC_API_KEY not set"

**Problem:** Interview mode requires Anthropic API key.

**Solution:**
```bash
export ANTHROPIC_API_KEY=your-key-here
```

Make permanent by adding to `~/.bashrc` or `~/.zshrc`.

#### Interview Cost Too High

**Problem:** Interview costs more than expected.

**Solution 1:** Use fewer questions
```bash
inkwell fetch URL --interview --max-questions 3
```

**Solution 2:** Set cost limit in config
```yaml
interview:
  max_cost_per_interview: 0.20  # Will warn if exceeded
```

#### Interview Session Lost

**Problem:** Interview interrupted, can't find session to resume.

**Solution:**
```bash
# List all sessions
inkwell interview sessions

# Resume by ID
inkwell interview resume <session-id>
```

#### Questions Not Relevant

**Problem:** Interview questions don't match your interests.

**Solution:** Add custom guidelines in config:
```yaml
interview:
  guidelines: |
    Focus on these areas:
    - Technical implementation details
    - Business model implications
    - Historical context and precedents
```

## Troubleshooting

### Common Issues

#### "Feed already exists" Error

```bash
$ inkwell add https://example.com/feed.rss --name my-podcast
✗ Feed 'my-podcast' already exists. Use update to modify it.
  Use 'inkwell remove my-podcast' first, or choose a different name
```

**Solution**: Either remove the existing feed first or use a different name.

#### "Feed not found" Error

```bash
$ inkwell remove non-existent
✗ Feed 'non-existent' not found

Available feeds:
  • my-podcast
  • tech-show
```

**Solution**: Check feed name with `inkwell list` and use the correct name.

#### Invalid Configuration Error

```bash
$ inkwell config show
✗ Invalid configuration in config.yaml:
  • log_level: Input should be 'DEBUG', 'INFO', 'WARNING', or 'ERROR'

Run 'inkwell config edit' to fix
```

**Solution**:
1. Run `inkwell config edit`
2. Fix the invalid value
3. Save and exit

#### YAML Syntax Error

```bash
$ inkwell list
✗ Invalid YAML syntax in feeds.yaml:
mapping values are not allowed here
  in "/home/user/.config/inkwell/feeds.yaml", line 3, column 10

Check feeds.yaml for syntax errors
```

**Solution**:
1. Open `~/.config/inkwell/feeds.yaml` in editor
2. Fix YAML syntax (check indentation, colons, quotes)
3. Verify with online YAML validator if needed

### Getting Help

#### Command Help

Get help for any command:

```bash
inkwell --help                # General help
inkwell add --help            # Help for add command
inkwell list --help           # Help for list command
inkwell remove --help         # Help for remove command
inkwell config --help         # Help for config command
```

#### Version Information

Check Inkwell version:

```bash
inkwell version
```

#### Debug Mode

Enable debug logging to troubleshoot issues:

1. Edit configuration:
   ```bash
   inkwell config edit
   ```

2. Set log level to DEBUG:
   ```yaml
   log_level: DEBUG
   ```

3. Run commands and check logs:
   ```bash
   tail -f ~/.local/state/inkwell/inkwell.log
   ```

## Advanced Usage

### Feed Organization Strategies

#### By Category

Organize feeds by topic:

```bash
inkwell add https://tech1.com/feed.rss --name tech-podcast-1 --category tech
inkwell add https://tech2.com/feed.rss --name tech-podcast-2 --category tech
inkwell add https://biz.com/feed.rss --name business-show --category business
```

#### By Priority

Use naming conventions:

```bash
inkwell add https://example.com/feed.rss --name 1-daily-podcast
inkwell add https://example.com/feed.rss --name 2-weekly-podcast
inkwell add https://example.com/feed.rss --name 3-archive-podcast
```

### Batch Operations

Add multiple feeds from a script:

```bash
#!/bin/bash

# Add all your favorite podcasts
inkwell add https://feed1.com/rss --name podcast-1 --category tech
inkwell add https://feed2.com/rss --name podcast-2 --category business
inkwell add https://feed3.com/rss --name podcast-3 --category interview

echo "All feeds added!"
```

### Backup and Restore

#### Backup Configuration

```bash
# Backup entire configuration directory
tar -czf inkwell-backup-$(date +%Y%m%d).tar.gz ~/.config/inkwell/

# Backup just feeds
cp ~/.config/inkwell/feeds.yaml ~/backups/inkwell-feeds-$(date +%Y%m%d).yaml
```

#### Restore Configuration

```bash
# Restore from backup
tar -xzf inkwell-backup-20250101.tar.gz -C ~/
```

### Migration Between Machines

1. **Export from old machine:**
   ```bash
   cd ~/.config/inkwell
   tar -czf inkwell-export.tar.gz config.yaml feeds.yaml .keyfile
   ```

2. **Transfer file** to new machine (USB, scp, cloud storage)

3. **Import on new machine:**
   ```bash
   # Ensure Inkwell is installed
   inkwell --help

   # Extract configuration
   cd ~/.config/
   tar -xzf inkwell-export.tar.gz -C inkwell/
   ```

4. **Verify:**
   ```bash
   inkwell list
   ```

### Shell Completion

#### Bash

Add to `~/.bashrc`:

```bash
eval "$(_INKWELL_COMPLETE=bash_source inkwell)"
```

#### Zsh

Add to `~/.zshrc`:

```bash
eval "$(_INKWELL_COMPLETE=zsh_source inkwell)"
```

#### Fish

Add to `~/.config/fish/completions/inkwell.fish`:

```fish
eval (env _INKWELL_COMPLETE=fish_source inkwell)
```

## Tips & Best Practices

### Naming Conventions

- Use lowercase and hyphens: `tech-podcast`, `startup-stories`
- Keep names short but descriptive
- Avoid special characters: `my_podcast!` → `my-podcast`

### Security Best Practices

- **Never commit `.keyfile`** to version control
- Backup `.keyfile` securely (needed to decrypt credentials)
- Use environment-specific credentials for different machines
- Rotate credentials periodically

### Performance

- Organize feeds with meaningful categories
- Remove inactive feeds to keep configuration clean
- Use descriptive names for easy identification

### Workflow Integration

#### With Task Managers

```bash
# Add to daily routine
inkwell list | grep tech  # See tech podcasts
```

#### With Note-Taking Apps

Once Phase 2 is complete:
```bash
# Output will be in ~/podcasts/ by default
# Point your note-taking app (Obsidian, etc.) to this directory
```

## Next Steps

### Available Features

✅ **Feed Management** - Add, list, and remove podcast feeds
✅ **Configuration** - Flexible YAML-based configuration
✅ **Transcription** - Automatic audio transcription (YouTube API + Gemini fallback)
✅ **Content Extraction** - AI-powered key information extraction
✅ **Markdown Generation** - Structured notes in markdown format
✅ **Template System** - Customizable extraction templates
✅ **Cost Optimization** - Smart provider selection and caching

### Upcoming Features (Phase 4)

🔜 **Interview Mode**: Interactive Q&A to capture your insights
🔜 **RSS Feed Processing**: Process full podcast feeds, not just single episodes
🔜 **Batch Processing**: Extract multiple episodes in one run
🔜 **Custom Templates**: Create your own extraction templates

### Stay Updated

- Check the [README](../README.md) for latest updates
- Review [roadmap](../README.md#roadmap) for upcoming features
- See [docs/](.) for technical documentation
- Read [devlogs](./devlog/) for development progress

---

For bugs, feature requests, or questions, please open an issue on GitHub.
