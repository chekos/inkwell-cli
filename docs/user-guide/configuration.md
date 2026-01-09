# Configuration

All configuration options for Inkwell.

---

## Overview

Inkwell uses YAML configuration files stored in your config directory:

| Platform | Location |
|----------|----------|
| Linux/macOS | `~/.config/inkwell/` |
| Windows | `%APPDATA%\inkwell\` |

---

## Configuration Files

```
~/.config/inkwell/
├── config.yaml    # Global settings
├── feeds.yaml     # Feed definitions
└── .keyfile       # Encryption key (auto-generated)
```

---

## Viewing Configuration

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

---

## Setting Values

### Via CLI

```bash
inkwell config set <key> <value>
```

**Examples:**

```bash
inkwell config set log_level DEBUG
inkwell config set default_output_dir ~/Documents/podcasts
inkwell config set transcription.api_key "your-key"
```

### Via Editor

```bash
inkwell config edit
```

Opens `config.yaml` in your `$EDITOR` (defaults to `vi`).

---

## All Options

### General

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `version` | string | `"1"` | Config format version |
| `log_level` | string | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `default_output_dir` | path | `~/podcasts` | Default output directory |

### Transcription

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `transcription.api_key` | string | `""` | Google AI API key |
| `youtube_check` | boolean | `true` | Check YouTube for transcripts first |

### Extraction

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `max_episodes_per_run` | integer | `10` | Max episodes per batch |
| `extraction.default_provider` | string | `gemini` | Default LLM provider |
| `extraction.cache_days` | integer | `30` | Extraction cache duration |

### Interview

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `interview.enabled` | boolean | `true` | Enable interview mode |
| `interview.auto_start` | boolean | `false` | Auto-start after extraction |
| `interview.default_template` | string | `reflective` | Default template |
| `interview.question_count` | integer | `5` | Target questions |
| `interview.format_style` | string | `structured` | Output format |
| `interview.max_cost_per_interview` | float | `0.50` | Cost limit |
| `interview.model` | string | `claude-sonnet-4-5` | Model to use |
| `interview.guidelines` | string | `""` | Custom guidelines |

### Obsidian

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `obsidian.wikilinks` | boolean | `true` | Generate wikilinks |
| `obsidian.tags` | boolean | `true` | Generate tags |
| `obsidian.max_tags` | integer | `10` | Maximum tags per note |
| `obsidian.dataview` | boolean | `true` | Dataview-compatible frontmatter |

---

## Example Configuration

```yaml
# ~/.config/inkwell/config.yaml
version: "1"
log_level: INFO
default_output_dir: ~/ObsidianVault/podcasts

# Transcription
transcription:
  api_key: your-google-ai-key-here
youtube_check: true

# Extraction
extraction:
  default_provider: gemini
  cache_days: 30
max_episodes_per_run: 10

# Interview
interview:
  enabled: true
  auto_start: false
  default_template: reflective
  question_count: 5
  format_style: structured
  max_cost_per_interview: 0.50
  guidelines: |
    Focus on practical applications.
    Ask about connections to my work.
    Probe for blog post ideas.

# Obsidian
obsidian:
  wikilinks: true
  tags: true
  max_tags: 10
  dataview: true
```

---

## Environment Variables

Environment variables override config file values:

| Variable | Overrides |
|----------|-----------|
| `GOOGLE_API_KEY` | `transcription.api_key` |
| `ANTHROPIC_API_KEY` | Anthropic API key for interview |
| `INKWELL_CONFIG_DIR` | Config directory location |
| `INKWELL_OUTPUT_DIR` | `default_output_dir` |
| `INKWELL_LOG_LEVEL` | `log_level` |

**Priority:** Environment variable > Config file > Default

---

## File Locations

### Logs

```
~/.local/state/inkwell/inkwell.log
```

View logs:

```bash
tail -f ~/.local/state/inkwell/inkwell.log
```

### Cache

```
~/.cache/inkwell/
├── transcripts/    # Cached transcripts
└── extractions/    # Cached extractions
```

Clear cache:

```bash
rm -rf ~/.cache/inkwell/
```

---

## Backup and Restore

### Backup

```bash
tar -czf inkwell-backup-$(date +%Y%m%d).tar.gz ~/.config/inkwell/
```

### Restore

```bash
tar -xzf inkwell-backup-20250101.tar.gz -C ~/
```

### Migration Between Machines

1. **Export:**
   ```bash
   cd ~/.config/inkwell
   tar -czf inkwell-export.tar.gz config.yaml feeds.yaml .keyfile
   ```

2. **Transfer** to new machine

3. **Import:**
   ```bash
   mkdir -p ~/.config/inkwell
   tar -xzf inkwell-export.tar.gz -C ~/.config/inkwell/
   ```

4. **Verify:**
   ```bash
   inkwell list
   ```

---

## Troubleshooting

### Invalid Configuration

```
✗ Invalid configuration in config.yaml:
  • log_level: Input should be 'DEBUG', 'INFO', 'WARNING', or 'ERROR'

Run 'inkwell config edit' to fix
```

**Solution:** Edit config and fix the invalid value.

### YAML Syntax Error

```
✗ Invalid YAML syntax in config.yaml:
mapping values are not allowed here
  in "config.yaml", line 3, column 10
```

**Solution:** Check YAML syntax (indentation, colons, quotes).

### Config Not Found

Inkwell creates default config on first run. Force creation:

```bash
inkwell config show
```

---

## Next Steps

- [CLI Commands](../reference/cli-commands.md) - Command reference
- [Troubleshooting](../reference/troubleshooting.md) - Common issues
