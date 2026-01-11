---
status: complete
priority: p2
issue_id: "086"
tags: [code-review, security, rich-markup, pr-36]
dependencies: []
---

# Missing Rich Markup Escape in list_latest Output

## Problem Statement

The `_output_latest_table()` function in `cli_list.py` displays episode titles, feed names, and error messages directly in Rich table cells without escaping Rich markup characters. A malicious RSS feed could inject Rich markup codes to spoof terminal output or create misleading visual output.

**Why it matters**: An attacker who controls an RSS feed could craft episode titles containing Rich markup to mislead users about the state of their system or mask error messages.

**Example**: An episode title like `[green]✓ All checks passed![/green]` would render as green success text instead of the literal string.

## Findings

**Location**: `/Users/chekos/projects/gh/inkwell-cli/src/inkwell/cli_list.py`, lines 377-394

```python
def _output_latest_table(results: list[LatestEpisodeResult]) -> None:
    for result in results:
        if result.episode:
            title = (
                result.episode.title[:47] + "..."
                if len(result.episode.title) > 50
                else result.episode.title
            )
            # VULNERABILITY: title and feed_name are not escaped
            table.add_row(result.feed_name, title, date, duration)
        else:
            error = result.error or "Unknown error"
            error_msg = error[:40] + "..." if len(error) > 40 else error
            # VULNERABILITY: error_msg is not escaped
            table.add_row(result.feed_name, f"[red]Error: {error_msg}[/red]", "-", "-")
```

**Note**: The `escape()` function is already imported at line 16:
```python
from rich.markup import escape
```

And is used correctly in other places in the file (lines 137, 143, 182, 208, 209), showing awareness of the issue.

## Proposed Solutions

### Option A: Add escape() calls (Recommended)

**Pros**: Simple, consistent with existing patterns in the file
**Cons**: None
**Effort**: Small (15 minutes)
**Risk**: Very low

```python
def _output_latest_table(results: list[LatestEpisodeResult]) -> None:
    for result in results:
        if result.episode:
            title = (
                result.episode.title[:47] + "..."
                if len(result.episode.title) > 50
                else result.episode.title
            )
            table.add_row(escape(result.feed_name), escape(title), date, duration)
        elif result.success:
            table.add_row(escape(result.feed_name), "[dim]No episodes yet[/dim]", "-", "-")
        else:
            error = result.error or "Unknown error"
            error_msg = error[:40] + "..." if len(error) > 40 else error
            table.add_row(escape(result.feed_name), f"[red]Error: {escape(error_msg)}[/red]", "-", "-")
```

### Option B: Create wrapper function for table rows

**Pros**: Centralizes escaping logic
**Cons**: Over-engineering for this case
**Effort**: Medium
**Risk**: Low

## Recommended Action

**Option A**: Add `escape()` calls to all user-controlled data in `_output_latest_table()`.

## Technical Details

**Affected Files**:
- `/Users/chekos/projects/gh/inkwell-cli/src/inkwell/cli_list.py`

**Lines to modify**: 386, 389, 394

## Acceptance Criteria

- [ ] Episode titles are escaped before display in table
- [ ] Feed names are escaped before display in table
- [ ] Error messages are escaped before display in table
- [ ] Test added for Rich markup in episode title
- [ ] Existing tests still pass

## Work Log

| Date | Action | Notes |
|------|--------|-------|
| 2026-01-11 | Created | From PR #36 code review by security-sentinel agent |

## Resources

- PR #36: https://github.com/chekos/inkwell-cli/pull/36
- Rich markup escape docs: https://rich.readthedocs.io/en/stable/markup.html#escaping
- Similar fix in file: lines 137, 143, 182, 208, 209 show correct pattern
