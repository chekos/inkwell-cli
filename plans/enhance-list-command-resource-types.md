# Plan: Enhance `list` command to support multiple resource types

**Issue:** [#32](https://github.com/chekos/inkwell-cli/issues/32)
**Type:** Enhancement
**Created:** 2026-01-07

## Overview

Transform the `inkwell list` command from a single-purpose feed lister into a flexible resource listing command following the `kubectl get <resource>` pattern. This creates a consistent CLI experience and improves discoverability of available resources.

## Problem Statement

Currently, Inkwell has fragmented listing commands:
- `inkwell list` - Lists feeds only
- `inkwell episodes <feed>` - Separate command for episodes
- No way to list available templates from CLI
- No way to list cached transcripts from CLI

Users must know multiple commands, and template discovery requires filesystem exploration.

## Proposed Solution

Implement a subcommand-based `list` command:

```bash
inkwell list                    # Default: list feeds (backward compatible)
inkwell list feeds              # Explicit: list feeds
inkwell list templates          # List available templates
inkwell list episodes <feed>    # List episodes from a feed
inkwell list cache              # List cached transcripts
```

---

## Technical Approach

### Architecture

Create a new subcommand group following the existing `plugins` pattern:

```
src/inkwell/
  cli.py              # Main app - remove old commands, register list_app
  cli_list.py         # NEW: List subcommands
  cli_plugins.py      # Existing pattern to follow
```

**Implementation Pattern** (from `cli_plugins.py`):

```python
# cli_list.py
import typer
from rich.console import Console
from rich.table import Table

list_app = typer.Typer(
    name="list",
    help="List Inkwell resources (feeds, templates, episodes, cache)",
    invoke_without_command=True,
)
console = Console()

@list_app.callback()
def list_default(ctx: typer.Context):
    """List resources. Defaults to feeds if no subcommand given."""
    if ctx.invoked_subcommand is None:
        list_feeds_impl()
```

**Registration in `cli.py`**:

```python
def _register_subcommands() -> None:
    from inkwell.cli_plugins import app as plugins_app
    from inkwell.cli_list import list_app  # NEW

    app.add_typer(plugins_app, name="plugins")
    app.add_typer(list_app, name="list")  # NEW
```

### Implementation Phases

#### Phase 1: Create List Subcommand Structure

**Files to create:**
- `src/inkwell/cli_list.py` - New list subcommands module

**Files to modify:**
- `src/inkwell/cli.py:40-48` - Add list_app registration

**Tasks:**
1. Create `cli_list.py` with `list_app` Typer instance
2. Implement callback for default behavior (`inkwell list` → feeds)
3. Register in `cli.py:_register_subcommands()`
4. Verify `inkwell list` still shows feeds (backward compat)

#### Phase 2: Migrate `list feeds` Command

**Source:** `src/inkwell/cli.py:141-176`

**Tasks:**
1. Move `list_feeds()` implementation to `cli_list.py`
2. Create `@list_app.command("feeds")` wrapper
3. Remove old `@app.command("list")` from `cli.py`
4. Preserve Rich table output format
5. Add `--json` flag for machine-readable output

**Output Format:**
```
$ inkwell list feeds

Configured Podcast Feeds
Name          URL                                    Auth   Category
-----------   ------------------------------------   ----   --------
my-podcast    https://feeds.example.com/rss.xml     -      tech
private-pod   https://private.example.com/feed      Yes    interview

Total: 2 feed(s)
```

#### Phase 3: Implement `list templates` Command

**Dependencies:**
- `src/inkwell/extraction/templates.py:TemplateLoader`
- `src/inkwell/extraction/models.py:ExtractionTemplate`

**Tasks:**
1. Create `@list_app.command("templates")`
2. Use `TemplateLoader.list_templates()` to get all templates
3. Get metadata via `TemplateLoader.get_template_info()`
4. Display Rich table with: Name, Type (built-in/user), Description
5. Handle template loading errors gracefully (skip with warning)
6. Add `--category` filter option
7. Add `--json` flag

**Output Format:**
```
$ inkwell list templates

Extraction Templates
Name              Type       Description
----------------  ---------  ------------------------------------------
summary           built-in   Extract key points and main themes
quotes            built-in   Notable quotes from guests and hosts
key-concepts      built-in   Important concepts and ideas discussed
tools-mentioned   built-in   Software, tools, and resources mentioned
books-mentioned   built-in   Books and publications referenced
step-by-step      built-in   Step-by-step guide extraction
my-custom         user       Custom extraction for tech podcasts

Total: 7 template(s)
```

**Template Discovery Logic:**
```python
def get_all_templates() -> list[dict]:
    loader = TemplateLoader()
    templates = []

    # Built-in templates
    builtin_dir = Path(__file__).parent / "templates"
    for path in builtin_dir.rglob("*.yaml"):
        try:
            info = loader.get_template_info(path.stem)
            info["type"] = "built-in"
            templates.append(info)
        except Exception as e:
            console.print(f"[yellow]Warning: Failed to load {path.name}: {e}[/yellow]")

    # User templates
    user_dir = Path.home() / ".config" / "inkwell" / "templates"
    if user_dir.exists():
        for path in user_dir.rglob("*.yaml"):
            try:
                info = loader.get_template_info(path.stem)
                info["type"] = "user"
                templates.append(info)
            except Exception as e:
                console.print(f"[yellow]Warning: Failed to load {path.name}: {e}[/yellow]")

    return templates
```

#### Phase 4: Migrate `list episodes` Command

**Source:** `src/inkwell/cli.py:223-291`

**Tasks:**
1. Create `@list_app.command("episodes")`
2. Move `episodes_command()` implementation to `cli_list.py`
3. Preserve `--limit` flag (default: 10)
4. Preserve async feed fetching pattern
5. Remove old `@app.command("episodes")` from `cli.py`
6. Add `--json` flag

**Signature:**
```python
@list_app.command("episodes")
def list_episodes(
    feed: str = typer.Argument(..., help="Feed name to list episodes from"),
    limit: int = typer.Option(10, "--limit", "-n", help="Number of episodes to show"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
) -> None:
```

#### Phase 5: Implement `list cache` Command

**Dependencies:**
- `src/inkwell/transcription/cache.py:TranscriptCache`

**Tasks:**
1. Create `@list_app.command("cache")`
2. Use `TranscriptCache` to enumerate cached transcripts
3. Display: URL (from metadata), Source, Size, Age
4. Show summary row (total entries, total size)
5. Handle empty cache gracefully
6. Add `--json` flag

**Output Format:**
```
$ inkwell list cache

Cached Transcripts
URL                                           Source    Size      Cached
--------------------------------------------  --------  --------  --------
youtube.com/watch?v=dQw4w9WgXcQ               YouTube   45 KB     3 days ago
feeds.example.com/episodes/ep-123.mp3         Gemini    1.2 MB    7 days ago

Total: 2 transcripts, 1.24 MB
```

**Implementation Note:**
Cache entries are keyed by SHA256 hash. Metadata contains the original `episode_url` which should be displayed (truncated if needed).

#### Phase 6: Update Help Text & Documentation

**Tasks:**
1. Ensure `inkwell list --help` shows all subcommands clearly
2. Update any existing documentation referencing `inkwell episodes`
3. Add examples to command docstrings

**Help Output:**
```
$ inkwell list --help

Usage: inkwell list [OPTIONS] COMMAND [ARGS]...

  List Inkwell resources (feeds, templates, episodes, cache)

Commands:
  cache      List cached transcripts
  episodes   List episodes from a configured feed
  feeds      List all configured podcast feeds
  templates  List available extraction templates

  Run 'inkwell list' without a command to list feeds (default).
```

---

## Acceptance Criteria

- [ ] `inkwell list` continues to work (backward compatible, defaults to feeds)
- [ ] `inkwell list feeds` explicitly lists feeds
- [ ] `inkwell list templates` shows built-in and user templates with descriptions
- [ ] `inkwell list episodes <feed>` works with `--limit` flag
- [ ] `inkwell list cache` shows cached transcripts with metadata
- [ ] `inkwell episodes` command removed from CLI
- [ ] Help text clearly shows available resource types
- [ ] All commands support `--json` flag for scripting
- [ ] Tests pass for all new commands

---

## Files to Create

### `src/inkwell/cli_list.py`

```python
"""List subcommands for Inkwell CLI.

Provides commands to list various Inkwell resources:
- feeds: Configured podcast feeds
- templates: Available extraction templates
- episodes: Episodes from a specific feed
- cache: Cached transcripts
"""

import json
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from inkwell.config.manager import ConfigManager
from inkwell.extraction.templates import TemplateLoader
from inkwell.transcription.cache import TranscriptCache
from inkwell.transcription.manager import TranscriptionManager
from inkwell.utils.rss import RSSParser

list_app = typer.Typer(
    name="list",
    help="List Inkwell resources (feeds, templates, episodes, cache)",
    invoke_without_command=True,
)
console = Console()


@list_app.callback()
def list_default(ctx: typer.Context) -> None:
    """List resources. Defaults to listing feeds."""
    if ctx.invoked_subcommand is None:
        _list_feeds_impl(json_output=False)


@list_app.command("feeds")
def list_feeds(
    json_output: Annotated[
        bool, typer.Option("--json", "-j", help="Output as JSON")
    ] = False,
) -> None:
    """List all configured podcast feeds."""
    _list_feeds_impl(json_output=json_output)


@list_app.command("templates")
def list_templates(
    category: Annotated[
        str | None, typer.Option("--category", "-c", help="Filter by category")
    ] = None,
    json_output: Annotated[
        bool, typer.Option("--json", "-j", help="Output as JSON")
    ] = False,
) -> None:
    """List available extraction templates."""
    # Implementation here...


@list_app.command("episodes")
def list_episodes(
    feed: Annotated[str, typer.Argument(help="Feed name to list episodes from")],
    limit: Annotated[
        int, typer.Option("--limit", "-n", help="Number of episodes to show")
    ] = 10,
    json_output: Annotated[
        bool, typer.Option("--json", "-j", help="Output as JSON")
    ] = False,
) -> None:
    """List episodes from a configured feed."""
    # Implementation here (migrate from cli.py:223-291)...


@list_app.command("cache")
def list_cache(
    json_output: Annotated[
        bool, typer.Option("--json", "-j", help="Output as JSON")
    ] = False,
) -> None:
    """List cached transcripts."""
    # Implementation here...


def _list_feeds_impl(json_output: bool = False) -> None:
    """Implementation for listing feeds."""
    # Migrate from cli.py:141-176
    ...
```

---

## Files to Modify

### `src/inkwell/cli.py`

**Line 40-48 - Add list_app registration:**
```python
def _register_subcommands() -> None:
    """Register subcommand apps (lazy import to avoid circular deps)."""
    from inkwell.cli_plugins import app as plugins_app
    from inkwell.cli_list import list_app  # ADD THIS

    app.add_typer(plugins_app, name="plugins")
    app.add_typer(list_app, name="list")  # ADD THIS
```

**Lines 141-176 - Remove `list_feeds()` command:**
```python
# DELETE this entire function - moved to cli_list.py
@app.command("list")
def list_feeds() -> None:
    ...
```

**Lines 223-291 - Remove `episodes_command()`:**
```python
# DELETE this entire function - moved to cli_list.py
@app.command("episodes")
def episodes_command(...) -> None:
    ...
```

---

## Test Files to Create

### `tests/integration/test_cli_list.py`

```python
"""Tests for list subcommands."""

import json
import os

import pytest
from typer.testing import CliRunner

from inkwell.cli import app

# Disable Rich formatting for tests
os.environ["NO_COLOR"] = "1"
os.environ["TERM"] = "dumb"

runner = CliRunner()


class TestListDefault:
    """Tests for `inkwell list` (default behavior)."""

    def test_list_no_args_shows_feeds(self, monkeypatch, tmp_path):
        """inkwell list with no args should show feeds (backward compat)."""
        # Setup mock config with feeds
        result = runner.invoke(app, ["list"])
        assert result.exit_code == 0
        assert "Configured" in result.output or "No feeds" in result.output


class TestListFeeds:
    """Tests for `inkwell list feeds`."""

    def test_list_feeds_empty(self, monkeypatch, tmp_path):
        """Empty feeds should show helpful message."""
        result = runner.invoke(app, ["list", "feeds"])
        assert result.exit_code == 0
        assert "No feeds configured" in result.output

    def test_list_feeds_json(self, monkeypatch, tmp_path):
        """--json flag should output valid JSON."""
        result = runner.invoke(app, ["list", "feeds", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)


class TestListTemplates:
    """Tests for `inkwell list templates`."""

    def test_list_templates_shows_builtin(self):
        """Should show built-in templates."""
        result = runner.invoke(app, ["list", "templates"])
        assert result.exit_code == 0
        assert "summary" in result.output
        assert "quotes" in result.output

    def test_list_templates_json(self):
        """--json flag should output valid JSON."""
        result = runner.invoke(app, ["list", "templates", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert any(t["name"] == "summary" for t in data)


class TestListEpisodes:
    """Tests for `inkwell list episodes <feed>`."""

    def test_list_episodes_feed_not_found(self):
        """Non-existent feed should show error."""
        result = runner.invoke(app, ["list", "episodes", "nonexistent"])
        assert result.exit_code == 1
        assert "not found" in result.output.lower()

    def test_list_episodes_with_limit(self, monkeypatch):
        """--limit should control episode count."""
        # Mock feed with episodes
        result = runner.invoke(app, ["list", "episodes", "test-feed", "--limit", "5"])
        # Assert based on mock


class TestListCache:
    """Tests for `inkwell list cache`."""

    def test_list_cache_empty(self, tmp_path, monkeypatch):
        """Empty cache should show helpful message."""
        result = runner.invoke(app, ["list", "cache"])
        assert result.exit_code == 0
        assert "No cached" in result.output or "empty" in result.output.lower()

    def test_list_cache_json(self, tmp_path, monkeypatch):
        """--json flag should output valid JSON."""
        result = runner.invoke(app, ["list", "cache", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)


class TestListHelp:
    """Tests for help text."""

    def test_list_help_shows_subcommands(self):
        """inkwell list --help should show all subcommands."""
        result = runner.invoke(app, ["list", "--help"])
        assert result.exit_code == 0
        assert "feeds" in result.output
        assert "templates" in result.output
        assert "episodes" in result.output
        assert "cache" in result.output
```

---

## Dependencies & Risks

### Dependencies
- `TemplateLoader.list_templates()` method exists at `src/inkwell/extraction/templates.py:200-236`
- `TranscriptCache` class exists at `src/inkwell/transcription/cache.py`
- Existing Rich table patterns in current `list` and `episodes` commands

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Breaking change removes `episodes` command | Medium | Medium | Issue explicitly allows this; document in release notes |
| Template loading errors crash listing | Low | High | Wrap in try/except, log warnings, continue |
| Cache metadata missing episode URL | Low | Medium | Fall back to showing truncated hash if URL unavailable |

---

## Questions Requiring Clarification

Before implementation, these questions should be answered:

### Critical
1. **Cache scope**: Should `list cache` show transcript cache only, or both transcript and extraction caches?
   - **Assumption**: Transcript cache only (per issue wording)

2. **Breaking change**: Confirm removing `inkwell episodes` without deprecation is acceptable?
   - **Assumption**: Yes (per issue statement)

### Important
3. **Template display fields**: Which metadata to show (name/version/description/category)?
   - **Assumption**: Name, Type (built-in/user), Description

4. **Template errors**: Skip corrupt templates with warning, or fail?
   - **Assumption**: Skip with warning

5. **Limit flag**: Preserve `--limit` for episodes?
   - **Assumption**: Yes, preserve with default=10

---

## References

### Internal References
- CLI architecture: `src/inkwell/cli.py:32-48`
- Plugins subcommand pattern: `src/inkwell/cli_plugins.py`
- Template loader: `src/inkwell/extraction/templates.py:21-283`
- Transcript cache: `src/inkwell/transcription/cache.py:19-262`
- Existing list command: `src/inkwell/cli.py:141-176`
- Existing episodes command: `src/inkwell/cli.py:223-291`
- CLI tests pattern: `tests/integration/test_cli.py`
- Plugin tests pattern: `tests/integration/test_cli_plugins.py`

### External References
- [Typer Subcommands Documentation](https://typer.tiangolo.com/tutorial/subcommands/)
- [Rich Tables Documentation](https://rich.readthedocs.io/en/latest/tables.html)
- [CLI Guidelines (CLIG)](https://clig.dev/)
- [Heroku CLI Style Guide](https://devcenter.heroku.com/articles/cli-style-guide)

### Related Issues
- This issue: [#32](https://github.com/chekos/inkwell-cli/issues/32)
