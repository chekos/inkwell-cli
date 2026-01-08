---
status: complete
priority: p3
issue_id: "084"
tags: [code-review, security, cli, pr-35]
dependencies: []
---

# Escape Rich Markup in User-Provided Data

## Problem Statement

User-controlled data (feed names, episode titles) is interpolated into Rich console output without escaping. If a user creates a feed with Rich markup in its name, it will be rendered with formatting.

**Why it matters:**
- Feed named `[red]ALERT[/red]` displays as red "ALERT"
- Could create misleading/confusing terminal output
- Minor visual injection concern

**Note:** This is low severity because it's a local CLI tool - an attacker would need to modify the user's own config file.

## Findings

**Agent Discovered:** security-sentinel

**Locations:** `/Users/chekos/projects/gh/inkwell-cli/src/inkwell/cli_list.py`

Line 100:
```python
console.print(f"[red]x[/red] Feed '{name}' not found.")
```

Line 105:
```python
console.print(f"[bold]Fetching episodes from:[/bold] {name}\n")
```

Lines 140-141:
```python
console.print(f"  inkwell fetch {name} --latest")
console.print(f'  inkwell fetch {name} --episode "keyword"')
```

**Verified behavior:**
```python
>>> console.print(f"Feed: {'[red]malicious[/red]'}")
Feed: malicious  # Displayed in red
```

## Proposed Solutions

### Option 1: Use rich.markup.escape() (Recommended)
**Pros:** Simple, explicit, follows Rich best practices
**Cons:** Adds import, slightly more verbose
**Effort:** Very Low (15 min)
**Risk:** Very Low

```python
from rich.markup import escape

console.print(f"[red]x[/red] Feed '{escape(name)}' not found.")
```

### Option 2: Use Console with markup=False
**Pros:** No escaping needed per-string
**Cons:** Loses ability to use Rich formatting in that print
**Effort:** Low (10 min)
**Risk:** Very Low

```python
console.print(f"Feed: {name}", markup=False)
```

## Recommended Action

Use **Option 1** with `rich.markup.escape()` for user-controlled strings:

```python
from rich.markup import escape

# Feed name from user
console.print(f"[red]x[/red] Feed '{escape(name)}' not found.")
console.print(f"[bold]Fetching episodes from:[/bold] {escape(name)}\n")
console.print(f"  inkwell fetch {escape(name)} --latest")

# Episode title from RSS
title = escape(ep.title[:57] + "..." if len(ep.title) > 60 else ep.title)
```

## Technical Details

**Affected Files:**
- `src/inkwell/cli_list.py` (lines 100, 105, 127, 140-141, 172-173)

**Changes Required:**
1. Add `from rich.markup import escape` to imports
2. Wrap user-controlled strings in `escape()` before interpolating into Rich output

## Acceptance Criteria

- [x] Feed name with Rich markup `[red]test[/red]` displays as literal text
- [x] Episode title with markup displays as literal text
- [x] Normal names without markup still work correctly
- [ ] Add test with feed name containing brackets

## Work Log

| Date | Action | Notes |
|------|--------|-------|
| 2026-01-07 | Created | Identified during PR #35 code review |
| 2026-01-07 | Completed | Added `rich.markup.escape()` to all user-controlled strings |

## Resources

- PR #35: https://github.com/chekos/inkwell-cli/pull/35
- Rich markup escaping: https://rich.readthedocs.io/en/stable/markup.html#escaping
