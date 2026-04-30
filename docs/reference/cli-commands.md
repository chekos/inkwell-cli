# CLI Commands

Complete reference for all Inkwell commands.

---

## Global Options

These options work with any command:

| Option | Short | Description |
|--------|-------|-------------|
| `--verbose` | `-v` | Enable verbose (DEBUG) logging |
| `--log-file` | | Write logs to file |
| `--help` | | Show help message |

---

## inkwell add

Add a podcast feed.

```bash
inkwell add <URL> --feed-name <NAME> [OPTIONS]
```

### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `URL` | Yes | RSS feed URL **or** a YouTube URL (watch, `/shorts/`, `/live/`, `/channel/UC…`, `@handle`, `/c/`, `/user/`, `youtu.be`). YouTube URLs are auto-resolved to the channel's media-RSS feed. |

### Options

| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| `--feed-name` | `-n` | string | Required | Feed identifier |
| `--name` | | string | Required | Backward-compatible alias for `--feed-name` |
| `--category` | `-c` | string | None | Feed category |
| `--auth` | | flag | false | Prompt for authentication |

### Examples

```bash
# Basic feed
inkwell add https://example.com/feed.rss --feed-name my-podcast

# With category
inkwell add https://example.com/feed.rss --feed-name tech-show --category tech

# With authentication
inkwell add https://private.com/feed.rss --feed-name premium --auth

# YouTube channel — paste any shape; inkwell resolves the feed URL
inkwell add https://www.youtube.com/@orenmeetsworld --feed-name oren-meets-world
inkwell add https://www.youtube.com/watch?v=abc123 --feed-name some-creator
inkwell add https://www.youtube.com/channel/UCxxxxxxxxxxxxxxxxxxxx --feed-name some-creator
```

> **Note:** Playlist URLs (`?list=…`) are rejected with a clear error — playlist ingestion is not yet supported. If you pass a video URL that includes a playlist query param (e.g. `watch?v=X&list=Y`), `inkwell` will tell you to use the channel URL instead.
> `--name` is still accepted for existing scripts, but new examples use `--feed-name`.

---

## inkwell list

List configured feeds.

```bash
inkwell list
```

### Output

```
╭─────────────────────────────────────────────────────────╮
│           Configured Podcast Feeds                      │
├────────────────┬───────────────────┬──────┬─────────────┤
│ Name           │ URL               │ Auth │ Category    │
├────────────────┼───────────────────┼──────┼─────────────┤
│ my-podcast     │ example.com/...   │ —    │ tech        │
╰────────────────┴───────────────────┴──────┴─────────────╯

Total: 1 feed(s)
```

---

## inkwell remove

Remove a podcast feed.

```bash
inkwell remove <NAME> [OPTIONS]
```

### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `NAME` | Yes | Feed name to remove |

### Options

| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| `--force` | `-f` | flag | false | Skip confirmation |

### Examples

```bash
# With confirmation
inkwell remove my-podcast

# Skip confirmation
inkwell remove my-podcast --force
```

---

## inkwell rename

Rename a podcast feed while preserving URL, category, and authentication settings.

```bash
inkwell rename <OLD_NAME> <NEW_NAME> [OPTIONS]
```

### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `OLD_NAME` | Yes | Existing feed name |
| `NEW_NAME` | Yes | New feed name. Inkwell normalizes this to a lowercase slug. |

### Options

| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| `--force` | `-f` | flag | false | Overwrite an existing destination feed |

### Examples

```bash
inkwell rename orenmeetsworld oren-meets-world
inkwell rename old-name new-name --force
```

---

## inkwell fetch

Process podcast episodes.

```bash
inkwell fetch <SOURCE> [OPTIONS]
```

### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `SOURCE` | Yes | Feed name or episode URL |

### Options

| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| `--output-dir` | `-o` | path | `~/inkwell-notes` | Base directory for output |
| `--podcast-name` | `-n` | string | Auto | Podcast name for output directory (overrides auto-detection) |
| `--latest` | `-l` | flag | false | Process only latest episode |
| `--episode` | `-e` | string | | Position (3), range (1-5), list (1,3,7), or title keyword |
| `--templates` | `-t` | string | Auto | Comma-separated template list |
| `--category` | `-c` | string | Auto | Episode category |
| `--provider` | `-p` | string | Auto | LLM provider (gemini, claude, auto) |
| `--skip-cache` | | flag | false | Skip extraction cache |
| `--dry-run` | | flag | false | Show cost estimate only |
| `--overwrite` | | flag | false | Overwrite existing directory |
| `--interview` | | flag | false | Enable interview mode |
| `--interview-template` | | string | Config | Interview template (reflective, analytical, creative) |
| `--interview-format` | | string | Config | Output format (structured, narrative, qa) |
| `--max-questions` | | int | Config | Number of questions |
| `--no-resume` | | flag | false | Don't resume previous session |
| `--resume-session` | | string | | Resume specific interview session by ID |
| `--extractor` | | string | Auto | Force specific extraction plugin (e.g., claude, gemini) |
| `--transcriber` | | string | Auto | Force specific transcription plugin (e.g., youtube, gemini) |
| `--save-feed` | | flag | false | After a successful YouTube URL fetch, also save the channel as a feed. Auto-names the feed from channel metadata unless `--feed-name` is set. |
| `--feed-name` | | string | auto | Feed name for `--save-feed`. Optional; derived from channel metadata if omitted. |

### Examples

```bash
# From URL
inkwell fetch https://youtube.com/watch?v=xyz

# From URL with custom podcast name
inkwell fetch https://youtube.com/watch?v=xyz --podcast-name "Python Tutorials"

# Latest from feed
inkwell fetch my-podcast --latest

# Specific episode by position
inkwell fetch my-podcast --episode 3

# Range of episodes
inkwell fetch my-podcast --episode 1-5

# Multiple specific episodes
inkwell fetch my-podcast --episode 1,3,7

# Search by title keyword
inkwell fetch my-podcast --episode "AI security"

# Custom templates
inkwell fetch URL --templates summary,quotes,tools-mentioned

# With interview
inkwell fetch URL --interview --max-questions 3

# Cost check
inkwell fetch URL --dry-run

# Force provider
inkwell fetch URL --provider gemini

# Force specific plugins
inkwell fetch URL --extractor claude --transcriber youtube

# One-time YouTube video; save the channel for future fetches (auto-named)
inkwell fetch https://www.youtube.com/watch?v=abc123 --save-feed

# Same, with an explicit feed name
inkwell fetch https://www.youtube.com/watch?v=abc123 --save-feed --feed-name some-creator

# Using environment variable overrides
INKWELL_EXTRACTOR=gemini inkwell fetch URL
```

---

## inkwell plugins

Manage Inkwell plugins.

### inkwell plugins list

List all installed plugins.

```bash
inkwell plugins list [OPTIONS]
```

**Options:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--type` | string | All | Filter by type (extraction, transcription, output) |
| `--all` | flag | false | Include disabled plugins |

**Example Output:**

```
Extraction Plugins:
  claude (built-in)     ✓ enabled   [priority: 100]  Claude API extractor
  gemini (built-in)     ✓ enabled   [priority: 100]  Google Gemini extractor

Transcription Plugins:
  youtube (built-in)    ✓ enabled   [priority: 100]  YouTube transcript API
  gemini (built-in)     ✓ enabled   [priority: 100]  Gemini audio transcription
  whisper (installed)   ✓ enabled   [priority: 50]   Local Whisper transcription

Output Plugins:
  markdown (built-in)   ✓ enabled   [priority: 100]  Markdown file generation

Broken Plugins:
  broken-plugin         ✗ error     ImportError: No module named 'torch'
                                    Recovery: pip install torch
```

**Examples:**

```bash
# List all plugins
inkwell plugins list

# List only extraction plugins
inkwell plugins list --type extraction

# Include disabled plugins
inkwell plugins list --all
```

### inkwell plugins enable

Enable a disabled plugin.

```bash
inkwell plugins enable <NAME>
```

**Note:** This only enables for the current session. For permanent changes, edit `~/.config/inkwell/config.yaml`.

### inkwell plugins disable

Disable a plugin.

```bash
inkwell plugins disable <NAME>
```

**Note:** This only disables for the current session. For permanent changes, edit `~/.config/inkwell/config.yaml`.

### inkwell plugins validate

Validate plugin configuration.

```bash
inkwell plugins validate [NAME]
```

| Argument | Required | Description |
|----------|----------|-------------|
| `NAME` | No | Plugin name (validates all if omitted) |

**Examples:**

```bash
# Validate all plugins
inkwell plugins validate

# Validate specific plugin
inkwell plugins validate whisper
```

**Example Output:**

```
Validating plugins...

✓ claude: OK
✓ gemini: OK
✓ youtube: OK
✗ whisper: FAILED
  - openai-whisper not installed. Run: pip install openai-whisper
  - ffmpeg not found in PATH
```

---

## inkwell config

Manage configuration.

### inkwell config show

Display current configuration.

```bash
inkwell config show
```

### inkwell config edit

Open config in editor.

```bash
inkwell config edit
```

### inkwell config set

Set a configuration value.

```bash
inkwell config set <KEY> <VALUE>
```

**Examples:**

```bash
inkwell config set log_level DEBUG
inkwell config set default_output_dir ~/Documents/podcasts
inkwell config set transcription.api_key "your-key"
```

---

## inkwell costs

View cost tracking.

```bash
inkwell costs [OPTIONS]
```

### Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--recent` | int | All | Show last N operations |

### Examples

```bash
# All costs
inkwell costs

# Recent only
inkwell costs --recent 10
```

---

## inkwell interview

Manage interview sessions.

### inkwell interview resume

Resume a paused interview.

```bash
inkwell interview resume <SESSION_ID>
```

### inkwell interview sessions

List all sessions.

```bash
inkwell interview sessions
```

### inkwell interview abandon

Abandon a session.

```bash
inkwell interview abandon <SESSION_ID>
```

### inkwell interview cleanup

Remove old sessions.

```bash
inkwell interview cleanup --older-than <DURATION>
```

**Example:**

```bash
inkwell interview cleanup --older-than 90d
```

---

## inkwell version

Show version information.

```bash
inkwell version
```

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Any error (configuration, network, API, validation) |
| 130 | Interrupted (SIGINT) |

> Inkwell currently returns a single non-zero code (`1`) for all error
> categories. Fine-grained codes per error class may be added in a future
> release; scripts should gate retry logic on the stderr message rather
> than the exit code.

---

## Shell Completion

### Bash

Add to `~/.bashrc`:

```bash
eval "$(_INKWELL_COMPLETE=bash_source inkwell)"
```

### Zsh

Add to `~/.zshrc`:

```bash
eval "$(_INKWELL_COMPLETE=zsh_source inkwell)"
```

### Fish

Add to `~/.config/fish/completions/inkwell.fish`:

```fish
eval (env _INKWELL_COMPLETE=fish_source inkwell)
```
