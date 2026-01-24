---
status: complete
priority: p3
issue_id: "085"
tags: [code-review, consistency, cli, pr-35]
dependencies: []
---

# Standardize Error Symbols Across CLI Modules

## Problem Statement

The CLI modules use inconsistent symbols for error display. Some use lowercase `x` and others use the Unicode checkmark symbol `✗`. This creates visual inconsistency across the application.

**Why it matters:**
- Inconsistent user experience
- Different modules look like they're from different projects
- Minor polish issue

## Findings

**Agent Discovered:** pattern-recognition-specialist, git-history-analyzer

**Current Usage:**

| File | Symbol | Example |
|------|--------|---------|
| `cli.py` | Mixed (`✗` and `x`) | `[red]✗[/red]` (line 102), `[red]x[/red]` (line 130) |
| `cli_list.py` | `x` | `[red]x[/red]` (lines 75, 100, 144, 180) |
| `cli_plugins.py` | `x` | `[red]x[/red]` (lines 246, 253, 302) |

**Pattern Analysis:**
- Newer code (cli_list.py, cli_plugins.py) uses lowercase `x`
- Older code (cli.py) uses Unicode `✗` in some places
- This is likely due to different authors/times

## Proposed Solutions

### Option 1: Standardize on Unicode ✗ (Recommended)
**Pros:** More semantically correct (cross mark symbol), looks professional
**Cons:** May not render in all terminals
**Effort:** Low (30 min)
**Risk:** Very Low

```python
# Use Unicode cross mark
console.print(f"[red]✗[/red] Error: {e}")
```

### Option 2: Standardize on Lowercase x
**Pros:** Universal terminal support
**Cons:** Less visually distinct
**Effort:** Low (30 min)
**Risk:** Very Low

```python
# Use ASCII x
console.print(f"[red]x[/red] Error: {e}")
```

### Option 3: Create Shared Constants
**Pros:** Single source of truth, easy to change
**Cons:** Adds abstraction
**Effort:** Medium (1 hour)
**Risk:** Very Low

```python
# In utils/display.py
ERROR_SYMBOL = "[red]✗[/red]"
SUCCESS_SYMBOL = "[green]✓[/green]"
WARNING_SYMBOL = "[yellow]⚠[/yellow]"

# In CLI modules
from inkwell.utils.display import ERROR_SYMBOL
console.print(f"{ERROR_SYMBOL} Error: {e}")
```

## Recommended Action

This is low priority. If addressed, use **Option 3** to create shared constants - this prevents future drift and allows easy updates.

For now, document the inconsistency and leave for a future cleanup sprint.

## Technical Details

**Affected Files (if fixing):**
- `src/inkwell/cli.py` - 15+ error messages
- `src/inkwell/cli_list.py` - 4 error messages
- `src/inkwell/cli_plugins.py` - 5+ error messages

**Scope:** ~25 string replacements across 3 files

## Acceptance Criteria

- [x] All CLI modules use the same error symbol
- [ ] Constants defined in shared location (if Option 3) - skipped (Option 1 chosen)
- [x] Visual inspection confirms consistency
- [x] No functional changes to error handling

## Work Log

| Date | Action | Notes |
|------|--------|-------|
| 2026-01-07 | Created | Identified during PR #35 code review |
| 2026-01-07 | Completed | Replaced all `[red]x[/red]` with `[red]✗[/red]` in cli_list.py (4 occurrences) and cli_plugins.py (3 occurrences). cli.py already used Unicode ✗ throughout. |

## Resources

- PR #35: https://github.com/chekos/inkwell-cli/pull/35
- Unicode cross mark: https://www.compart.com/en/unicode/U+2717
