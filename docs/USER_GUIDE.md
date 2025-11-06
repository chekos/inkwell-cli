# Inkwell CLI User Guide

Complete guide to using Inkwell for podcast note-taking.

## Table of Contents

1. [Installation](#installation)
2. [Getting Started](#getting-started)
3. [Managing Feeds](#managing-feeds)
4. [Configuration](#configuration)
5. [Troubleshooting](#troubleshooting)
6. [Advanced Usage](#advanced-usage)

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

### Phase 2 Features (Coming Soon)

- **Transcription**: Automatic audio transcription
- **Content Extraction**: AI-powered key information extraction
- **Markdown Generation**: Structured notes in markdown format
- **Interview Mode**: Interactive Q&A to capture your insights

### Stay Updated

- Check the [README](../README.md) for latest updates
- Review [roadmap](../README.md#roadmap) for upcoming features
- See [docs/](.) for technical documentation

---

For bugs, feature requests, or questions, please open an issue on GitHub.
