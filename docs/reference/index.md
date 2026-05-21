# Reference

Technical reference documentation for Inkwell.

---

## Documentation

### [CLI Commands](cli-commands.md)
Complete reference for all Inkwell commands, options, and flags.

### [Supported Inputs](supported-inputs.md)
Input support matrix for saved feeds, URLs, local files, stdin, and planned future formats.

### [Machine-Readable Output](machine-readable-output.md)
JSON/plain output contracts for shell scripts and automation.

### [Cache Behavior](cache.md)
Transcript, extraction, and media/audio cache behavior, retention, and clearing semantics.

### [Templates](templates.md)
Available extraction templates, their outputs, and how to customize them.

### [Configuration Options](config-options.md)
All configuration options with defaults, types, and descriptions.

### [Transcription Attempt Policy](transcription-attempt-policy.md)
Developer-facing reference for transcription fallback ordering and future provider policy work.

### [Troubleshooting](troubleshooting.md)
Common issues, error messages, and their solutions.

---

## Quick Links

### Command Help

```bash
inkwell --help              # General help
inkwell <command> --help    # Command-specific help
```

### Version

```bash
inkwell version
```

### Debug Mode

```bash
inkwell config set log_level DEBUG
tail -f ~/.local/state/inkwell/inkwell.log
```

---

## File Locations

| File | Location | Purpose |
|------|----------|---------|
| Config | `~/.config/inkwell/config.yaml` | Global settings |
| Feeds | `~/.config/inkwell/feeds.yaml` | Feed definitions |
| Key | `~/.config/inkwell/.keyfile` | Encryption key |
| Logs | `~/.local/state/inkwell/inkwell.log` | Application logs |
| Cache | `~/.cache/inkwell/` | Transcripts, extractions, downloaded media/audio |
| Output | `~/inkwell-notes/` | Processed episodes (default) |

---

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `GOOGLE_API_KEY` | Google AI API key for transcription/extraction |
| `ANTHROPIC_API_KEY` | Anthropic API key for interview mode |
| `INKWELL_CONFIG_DIR` | Override config directory |
| `INKWELL_OUTPUT_DIR` | Override default output directory |
