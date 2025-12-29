# Configuration Options

Complete reference of all Inkwell configuration options.

---

## Configuration File

Location: `~/.config/inkwell/config.yaml`

---

## General Settings

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `version` | string | `"1"` | Config format version (do not modify) |
| `log_level` | enum | `INFO` | Logging verbosity |
| `default_output_dir` | path | `~/podcasts` | Default output directory |

### log_level

Valid values: `DEBUG`, `INFO`, `WARNING`, `ERROR`

```yaml
log_level: DEBUG  # Verbose logging for troubleshooting
```

### default_output_dir

Supports `~` expansion and environment variables.

```yaml
default_output_dir: ~/ObsidianVault/podcasts
default_output_dir: $HOME/notes/podcasts
```

---

## Transcription Settings

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `transcription.api_key` | string | `""` | Google AI API key |
| `youtube_check` | boolean | `true` | Check YouTube for transcripts first |

### transcription.api_key

Your Google AI API key for Gemini transcription.

```yaml
transcription:
  api_key: "AIza..."
```

!!! tip
    Use `inkwell config set transcription.api_key "your-key"` to set this securely.

### youtube_check

When `true`, Inkwell checks for free YouTube transcripts before using Gemini.

```yaml
youtube_check: true  # Recommended: saves money
youtube_check: false # Always use Gemini transcription
```

---

## Extraction Settings

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `max_episodes_per_run` | int | `10` | Maximum episodes per batch |
| `extraction.default_provider` | enum | `gemini` | Default LLM provider |
| `extraction.cache_days` | int | `30` | Cache duration in days |

### extraction.default_provider

Valid values: `gemini`, `claude`

```yaml
extraction:
  default_provider: gemini  # Cost-effective (recommended)
  default_provider: claude  # Higher quality, 40x more expensive
```

### extraction.cache_days

How long to cache extraction results. Set to `0` to disable caching.

```yaml
extraction:
  cache_days: 30   # Default
  cache_days: 90   # Longer cache
  cache_days: 0    # No caching
```

---

## Interview Settings

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `interview.enabled` | boolean | `true` | Enable interview mode |
| `interview.auto_start` | boolean | `false` | Auto-start after extraction |
| `interview.default_template` | enum | `reflective` | Default interview style |
| `interview.question_count` | int | `5` | Target number of questions |
| `interview.format_style` | enum | `structured` | Output format |
| `interview.max_cost_per_interview` | float | `0.50` | Cost limit in USD |
| `interview.confirm_high_cost` | boolean | `true` | Warn before high-cost interviews |
| `interview.model` | string | `claude-sonnet-4-5` | Claude model to use |
| `interview.session_timeout_minutes` | int | `60` | Session timeout |
| `interview.guidelines` | string | `""` | Custom interview guidelines |

### interview.default_template

Valid values: `reflective`, `analytical`, `creative`

```yaml
interview:
  default_template: reflective  # Personal insights
  default_template: analytical  # Critical thinking
  default_template: creative    # Imaginative connections
```

### interview.format_style

Valid values: `structured`, `narrative`, `qa`

```yaml
interview:
  format_style: structured  # Themes, insights, action items
  format_style: narrative   # Flowing prose
  format_style: qa          # Simple Q&A format
```

### interview.guidelines

Custom instructions for generating questions.

```yaml
interview:
  guidelines: |
    Focus on practical applications for my startup.
    Ask about potential blog post angles.
    Probe connections to behavioral psychology.
    Challenge my assumptions when I'm too optimistic.
```

---

## Obsidian Settings

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `obsidian.wikilinks` | boolean | `true` | Generate `[[wikilinks]]` |
| `obsidian.tags` | boolean | `true` | Generate `#tags` |
| `obsidian.max_tags` | int | `10` | Maximum tags per note |
| `obsidian.dataview` | boolean | `true` | Dataview-compatible frontmatter |
| `obsidian.extra_frontmatter` | object | `{}` | Additional frontmatter fields |

### obsidian.extra_frontmatter

Add custom fields to all notes.

```yaml
obsidian:
  extra_frontmatter:
    vault: podcasts
    type: podcast-note
    project: learning
```

---

## Full Example

```yaml
# ~/.config/inkwell/config.yaml

# General
version: "1"
log_level: INFO
default_output_dir: ~/ObsidianVault/podcasts

# Transcription
transcription:
  api_key: "your-google-ai-key"
youtube_check: true

# Extraction
max_episodes_per_run: 10
extraction:
  default_provider: gemini
  cache_days: 30

# Interview
interview:
  enabled: true
  auto_start: false
  default_template: reflective
  question_count: 5
  format_style: structured
  max_cost_per_interview: 0.50
  confirm_high_cost: true
  model: claude-sonnet-4-5
  session_timeout_minutes: 60
  guidelines: |
    Focus on practical applications.
    Ask about connections to my work.
    Probe for actionable insights.

# Obsidian
obsidian:
  wikilinks: true
  tags: true
  max_tags: 10
  dataview: true
  extra_frontmatter:
    vault: podcasts
```

---

## Environment Variables

Override config with environment variables:

| Variable | Overrides | Example |
|----------|-----------|---------|
| `GOOGLE_API_KEY` | `transcription.api_key` | `export GOOGLE_API_KEY="AIza..."` |
| `ANTHROPIC_API_KEY` | Anthropic key for interview | `export ANTHROPIC_API_KEY="sk-..."` |
| `INKWELL_CONFIG_DIR` | Config directory | `export INKWELL_CONFIG_DIR="/custom/path"` |
| `INKWELL_OUTPUT_DIR` | `default_output_dir` | `export INKWELL_OUTPUT_DIR="~/notes"` |
| `INKWELL_LOG_LEVEL` | `log_level` | `export INKWELL_LOG_LEVEL="DEBUG"` |

**Priority order:**
1. Environment variable (highest)
2. Config file
3. Default value (lowest)

---

## Validation

Inkwell validates config on load. Invalid values produce errors:

```
✗ Invalid configuration in config.yaml:
  • log_level: Input should be 'DEBUG', 'INFO', 'WARNING', or 'ERROR'
  • interview.question_count: Input should be >= 1
```

Fix with:

```bash
inkwell config edit
```

---

## Next Steps

- [Configuration Guide](../user-guide/configuration.md) - How to configure
- [CLI Commands](cli-commands.md) - Command reference
