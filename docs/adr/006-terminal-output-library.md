---
title: ADR 006 - Terminal Output Enhancement Library
adr:
  author: Claude
  created: 06-Nov-2025
  status: accepted
---

# ADR-006: Terminal Output Enhancement Library

**Status**: Accepted
**Date**: 2025-11-06
**Context**: Day 5 - CLI command implementation

## Context

Inkwell is a CLI tool that will be used interactively by developers and knowledge workers. Users need clear, scannable output for feed management, configuration display, and error messages. Plain text output is functional but lacks visual hierarchy and can be hard to parse quickly.

## Decision

Use the **rich** library for terminal output formatting, tables, and colors.

## Options Considered

### 1. rich (Chosen)

**Pros**:
- Comprehensive terminal formatting (colors, tables, panels, progress bars)
- Beautiful default styling
- Automatic terminal capability detection
- Support for markdown, syntax highlighting, and more
- Active development and maintenance
- Good documentation
- Type hints included

**Cons**:
- Additional dependency (~250KB)
- Adds complexity for simple use cases
- May be overkill for minimal CLI

### 2. colorama

**Pros**:
- Lightweight (cross-platform ANSI color support)
- Simple API
- Well-established

**Cons**:
- Only handles colors, not tables or layouts
- Manual formatting for complex output
- Windows compatibility requires more code

### 3. click (terminal utilities)

**Pros**:
- Built-in to many environments
- Simple color support via `click.style()`
- Good for basic formatting

**Cons**:
- Limited table/layout capabilities
- Would require additional library for tables
- We're already using Typer (built on Click)

### 4. tabulate

**Pros**:
- Excellent table formatting
- Multiple table styles
- Lightweight

**Cons**:
- Only handles tables, not colors or other formatting
- Would need separate library for colors
- Less modern API

### 5. Plain text

**Pros**:
- No dependencies
- Universal compatibility
- Simplest approach

**Cons**:
- Poor visual hierarchy
- Hard to scan large amounts of data
- Less professional appearance
- More work to format output manually

## Rationale

rich provides the best combination of features for a professional CLI tool:

1. **Tables**: The `list` command displays feeds in a formatted table with columns. rich's Table API is simple and produces beautiful output.

2. **Colors and styling**: Semantic color coding (green for success, red for errors, yellow for warnings) improves usability.

3. **Panels**: Configuration display uses panels for clear visual boundaries.

4. **Future-proof**: As Inkwell grows, we'll need progress bars (for downloads), syntax highlighting (for markdown preview), and more. rich provides all of this.

5. **Professional appearance**: Users expect modern CLI tools to have polished output. rich delivers this with minimal code.

6. **Terminal detection**: Automatically detects terminal capabilities and degrades gracefully (e.g., no colors in non-TTY contexts).

The 250KB dependency cost is acceptable for the UX benefits. Most Python developers already have rich installed from other tools.

## Implementation Examples

### Feed List Table
```python
from rich.console import Console
from rich.table import Table

console = Console()

table = Table(title="[bold]Configured Podcast Feeds[/bold]")
table.add_column("Name", style="cyan", no_wrap=True)
table.add_column("URL", style="blue")
table.add_column("Auth", justify="center", style="yellow")
table.add_column("Category", style="green")

for name, feed in feeds.items():
    auth_status = "✓" if feed.auth.type != "none" else "—"
    table.add_row(name, str(feed.url)[:50], auth_status, feed.category or "—")

console.print(table)
```

### Success/Error Messages
```python
# Success
console.print(f"\n[green]✓[/green] Feed '[bold]{name}[/bold]' added successfully")

# Error
console.print(f"[red]✗[/red] {error_message}")

# Warning
console.print("[yellow]No feeds configured yet.[/yellow]")
```

### Configuration Display
```python
from rich.panel import Panel

config_yaml = yaml.dump(config.model_dump())
console.print(Panel(config_yaml, title="Configuration", border_style="blue"))
```

## Consequences

**Positive**:
- Professional, polished terminal output
- Better UX - easier to scan and understand output
- Semantic color coding improves error visibility
- Future capabilities (progress bars, markdown rendering) available
- Consistent visual language across all commands

**Negative**:
- Additional 250KB dependency
- Output includes ANSI escape codes (requires careful testing)
- May not render perfectly in all terminal emulators

**Neutral**:
- Need to test output in non-TTY contexts (CI/CD logs)
- Should avoid over-using colors/formatting (keep it professional)

## Guidelines for Use

To maintain consistency and professionalism:

1. **Color semantics**:
   - Green: Success, completion
   - Red: Errors, failures
   - Yellow: Warnings, empty states
   - Blue/Cyan: Data, metadata
   - Bold: Emphasis on key terms

2. **When to use tables**:
   - List commands (feeds, episodes, templates)
   - Any output with 3+ columns
   - Not for simple key-value pairs

3. **When to use panels**:
   - Configuration display
   - Long text blocks
   - Visual separation of sections

4. **When NOT to use rich**:
   - Logging output (use standard logging)
   - Machine-readable output (JSON, etc.)
   - Simple progress indicators (use plain text)

## References

- rich documentation: https://rich.readthedocs.io/
- rich GitHub: https://github.com/Textualize/rich
- Implementation: `src/inkwell/cli.py`

## Related ADRs

- ADR-002: Phase 1 Architecture (CLI layer design)
