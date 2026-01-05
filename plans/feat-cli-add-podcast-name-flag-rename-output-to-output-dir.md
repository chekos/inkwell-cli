# feat(cli): Add --podcast-name flag and rename --output to --output-dir

**Issue:** [#28](https://github.com/chekos/inkwell-cli/issues/28)
**Type:** Enhancement
**Estimated effort:** ~30 minutes

---

## Overview

Add `--podcast-name` / `-n` flag to `fetch` command and rename `--output` to `--output-dir`.

**Key insight:** Infrastructure already exists. Just expose `PipelineOptions.podcast_name` as a CLI flag.

## Problem

```bash
inkwell fetch "https://youtu.be/TqC1qOfiVcQ"
# Creates: unknown-podcast/2026-01-05-episode-from-httpsyoutubetqc1qofivcq/
```

No way to specify podcast name for standalone URLs. Also, `--output` is misleading (expects directory).

## Solution

```bash
inkwell fetch "https://youtu.be/TqC1qOfiVcQ" --podcast-name "Python Tutorials"
# Creates: python-tutorials/2026-01-05-episode-title/

inkwell fetch <url> --output-dir ~/notes  # Clear it's a directory
```

---

## Implementation

### 1. Add `--podcast-name` option (`cli.py` ~line 695)

```python
podcast_name: str | None = typer.Option(
    None,
    "--podcast-name",
    "-n",
    help="Podcast name for output directory (overrides auto-detection)",
),
```

### 2. Rename `--output` to `--output-dir` (`cli.py` lines 686-688)

```python
output_dir: Path | None = typer.Option(
    None, "--output-dir", "-o", help="Base directory for output (default: ~/inkwell-notes)"
),
```

### 3. Fix variable shadowing (`cli.py` ~line 857)

The local variable `podcast_name` at line 857 will shadow the new CLI parameter. Rename it:

```python
# Current (line 857-860)
podcast_name: str | None = None
if ep is not None:
    episode_title = ep.title
    podcast_name = ep.podcast_name or url_or_feed

# Change to
episode_title: str | None = None
detected_podcast_name: str | None = None
if ep is not None:
    episode_title = ep.title
    detected_podcast_name = ep.podcast_name or url_or_feed

# Then at PipelineOptions (line 893):
podcast_name=podcast_name or detected_podcast_name,
```

### 4. Add test (`test_cli.py`)

```python
class TestFetchCommand:
    """Tests for fetch command options."""

    def test_fetch_help_shows_new_options(self) -> None:
        """Test new options appear in help output."""
        result = runner.invoke(app, ["fetch", "--help"])

        assert result.exit_code == 0
        # New flag names
        assert "--output-dir" in result.stdout
        assert "--podcast-name" in result.stdout
        # Short forms
        assert "-o" in result.stdout
        assert "-n" in result.stdout
```

### 5. Update docs (`docs/reference/cli-commands.md`)

Update the options table for `inkwell fetch`:

```markdown
| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| `--output-dir` | `-o` | path | `~/inkwell-notes` | Base directory for output |
| `--podcast-name` | `-n` | string | Auto | Podcast name for output directory |
```

---

## Key Behavior

- **CLI flag overrides auto-detection:** `--podcast-name "Custom"` wins over RSS metadata
- **Empty string falls through:** `--podcast-name ""` behaves like not passing the flag (uses auto-detection)
- **Sanitization handled:** Existing `podcast_slug` property handles special characters

---

## Acceptance Criteria

- [ ] `--podcast-name` / `-n` flag added to `fetch` command
- [ ] `--output` renamed to `--output-dir` (keep `-o`)
- [ ] CLI flag overrides auto-detected podcast name
- [ ] Test verifies flags appear in help
- [ ] `docs/reference/cli-commands.md` updated

---

## References

- `src/inkwell/cli.py:683-732` - fetch command
- `src/inkwell/pipeline/models.py:35` - PipelineOptions.podcast_name
- `src/inkwell/output/models.py:89-96` - podcast_slug sanitization
