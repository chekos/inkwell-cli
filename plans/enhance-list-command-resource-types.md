# Plan: Enhance `list` command to support multiple resource types

**Issue:** [#32](https://github.com/chekos/inkwell-cli/issues/32)
**Type:** Enhancement

## Overview

Consolidate listing commands under `inkwell list <resource>` following the kubectl pattern. Move existing `list` and `episodes` commands into a subcommand group and add template listing.

## What We're Building

```bash
inkwell list                    # Default: list feeds (backward compatible)
inkwell list feeds              # Explicit: list feeds
inkwell list templates          # List available templates
inkwell list episodes <feed>    # List episodes (migrate from `inkwell episodes`)
```

**Not building:** `list cache` - the existing `inkwell cache stats` already serves this purpose.

---

## Implementation

### Files to Create

**`src/inkwell/cli_list.py`**

```python
"""List subcommands for Inkwell CLI."""

import asyncio
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from inkwell.config.manager import ConfigManager
from inkwell.extraction.templates import TemplateLoader
from inkwell.feeds.parser import RSSParser

list_app = typer.Typer(
    name="list",
    help="List Inkwell resources (feeds, templates, episodes)",
    invoke_without_command=True,
)
console = Console()


@list_app.callback()
def list_default(ctx: typer.Context) -> None:
    """List resources. Defaults to feeds if no subcommand given."""
    if ctx.invoked_subcommand is None:
        _list_feeds_impl()


@list_app.command("feeds")
def list_feeds() -> None:
    """List all configured podcast feeds."""
    _list_feeds_impl()


@list_app.command("templates")
def list_templates() -> None:
    """List available extraction templates."""
    loader = TemplateLoader()
    names = loader.list_templates()

    if not names:
        console.print("[yellow]No templates found.[/yellow]")
        return

    table = Table(title="Extraction Templates")
    table.add_column("Name", style="cyan")
    table.add_column("Description")

    for name in names:
        try:
            info = loader.get_template_info(name)
            table.add_row(name, info.get("description", "-"))
        except Exception:
            table.add_row(name, "[dim]failed to load[/dim]")

    console.print(table)
    console.print(f"\n[dim]Total: {len(names)} template(s)[/dim]")


@list_app.command("episodes")
def list_episodes(
    feed: Annotated[str, typer.Argument(help="Feed name to list episodes from")],
    limit: Annotated[int, typer.Option("--limit", "-n", help="Number of episodes")] = 10,
) -> None:
    """List episodes from a configured feed."""
    # Migrate implementation from cli.py:223-291
    # Uses asyncio.run() wrapper pattern like existing code
    ...


def _list_feeds_impl() -> None:
    """Display configured feeds."""
    # Migrate implementation from cli.py:141-176
    ...
```

### Files to Modify

**`src/inkwell/cli.py`**

1. **Line 40-48** - Add registration:
```python
def _register_subcommands() -> None:
    from inkwell.cli_plugins import app as plugins_app
    from inkwell.cli_list import list_app  # ADD

    app.add_typer(plugins_app, name="plugins")
    app.add_typer(list_app, name="list")  # ADD
```

2. **Lines 141-176** - Delete `list_feeds()` command (moved to cli_list.py)

3. **Lines 223-291** - Delete `episodes_command()` (moved to cli_list.py)

---

## Tests

**`tests/integration/test_cli_list.py`**

```python
"""Tests for list subcommands."""

import os
from typer.testing import CliRunner
from inkwell.cli import app

os.environ["NO_COLOR"] = "1"
runner = CliRunner()


def test_list_shows_feeds():
    """inkwell list defaults to showing feeds."""
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0


def test_list_feeds_explicit():
    """inkwell list feeds works."""
    result = runner.invoke(app, ["list", "feeds"])
    assert result.exit_code == 0


def test_list_templates_shows_builtin():
    """inkwell list templates shows built-in templates."""
    result = runner.invoke(app, ["list", "templates"])
    assert result.exit_code == 0
    assert "summary" in result.output


def test_list_episodes_requires_feed():
    """inkwell list episodes requires feed argument."""
    result = runner.invoke(app, ["list", "episodes"])
    assert result.exit_code != 0


def test_list_episodes_unknown_feed():
    """inkwell list episodes with unknown feed shows error."""
    result = runner.invoke(app, ["list", "episodes", "nonexistent"])
    assert result.exit_code == 1


def test_list_help_shows_subcommands():
    """inkwell list --help shows all subcommands."""
    result = runner.invoke(app, ["list", "--help"])
    assert "feeds" in result.output
    assert "templates" in result.output
    assert "episodes" in result.output
```

---

## Acceptance Criteria

- [ ] `inkwell list` shows feeds (backward compatible)
- [ ] `inkwell list feeds` shows feeds explicitly
- [ ] `inkwell list templates` shows built-in templates with descriptions
- [ ] `inkwell list episodes <feed>` works with `--limit` flag
- [ ] `inkwell episodes` command removed
- [ ] Help text shows available subcommands
- [ ] Tests pass

---

## Decisions Made

| Question | Decision |
|----------|----------|
| Include `list cache`? | No - use existing `cache stats` |
| Add `--json` flags? | No - add later if requested |
| Add `--category` filter? | No - 7 templates don't need filtering |
| Template type column (built-in/user)? | No - adds complexity for minimal value |
| Breaking change for `episodes`? | Yes - acceptable per issue |

---

## References

- Subcommand pattern: `src/inkwell/cli_plugins.py`
- Template loader: `src/inkwell/extraction/templates.py:200-236`
- Current list command: `src/inkwell/cli.py:141-176`
- Current episodes command: `src/inkwell/cli.py:223-291`
