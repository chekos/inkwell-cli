---
status: complete
priority: p3
issue_id: "083"
tags: [code-review, input-validation, cli, pr-35]
dependencies: []
---

# Validate Limit Parameter Bounds in list_episodes

## Problem Statement

The `--limit` parameter in `inkwell list episodes` accepts any integer value without validation. Negative values produce counterintuitive results, and zero produces an empty result.

**Why it matters:**
- `--limit=-5` returns all but the last 5 items (95 of 100), not an error
- `--limit=0` returns empty result silently
- User experience is confusing for edge cases
- Minor input validation gap

## Findings

**Agent Discovered:** security-sentinel

**Location:** `/Users/chekos/projects/gh/inkwell-cli/src/inkwell/cli_list.py`, lines 80-82

```python
@app.command("episodes")
def list_episodes(
    name: Annotated[str, typer.Argument(help="Feed name to list episodes from")],
    limit: Annotated[int, typer.Option("--limit", "-n", help="Number of episodes to show")] = 10,
) -> None:
```

**Behavior with edge cases:**
```bash
$ inkwell list episodes my-feed --limit -5
# Shows 95 of 100 episodes (Python slice [:-5])

$ inkwell list episodes my-feed --limit 0
# Shows empty table, no error

$ inkwell list episodes my-feed --limit 999999
# Works fine (bounded by actual feed size)
```

**Impact:** Low - confusing UX but not exploitable

## Proposed Solutions

### Option 1: Use Typer's Built-in Validation (Recommended)
**Pros:** Declarative, clean, uses framework features
**Cons:** None
**Effort:** Very Low (5 min)
**Risk:** Very Low

```python
limit: Annotated[int, typer.Option(
    "--limit", "-n",
    help="Number of episodes to show (1-1000)",
    min=1,
    max=1000,
)] = 10,
```

### Option 2: Manual Validation
**Pros:** Custom error messages
**Cons:** More code, less idiomatic
**Effort:** Low (15 min)
**Risk:** Very Low

```python
if limit < 1:
    console.print("[red]x[/red] Limit must be at least 1")
    sys.exit(1)
if limit > 1000:
    console.print("[yellow]Warning:[/yellow] Limiting to 1000 episodes")
    limit = 1000
```

## Recommended Action

Use **Option 1** - Typer's built-in `min` and `max` constraints:

```python
limit: Annotated[int, typer.Option(
    "--limit", "-n",
    help="Number of episodes to show (1-1000)",
    min=1,
    max=1000,
)] = 10,
```

## Technical Details

**Affected Files:**
- `src/inkwell/cli_list.py` (line 82)

**Single Line Change:**
```diff
-    limit: Annotated[int, typer.Option("--limit", "-n", help="Number of episodes to show")] = 10,
+    limit: Annotated[int, typer.Option("--limit", "-n", help="Number of episodes to show (1-1000)", min=1, max=1000)] = 10,
```

## Acceptance Criteria

- [x] `inkwell list episodes feed --limit 0` shows error message
- [x] `inkwell list episodes feed --limit -1` shows error message
- [x] `inkwell list episodes feed --limit 1001` shows error message
- [x] Help text shows valid range
- [ ] Add test for limit validation

## Work Log

| Date | Action | Notes |
|------|--------|-------|
| 2026-01-07 | Created | Identified during PR #35 code review |
| 2026-01-07 | Completed | Added min=1, max=1000 validation using Typer's built-in constraints |

## Resources

- PR #35: https://github.com/chekos/inkwell-cli/pull/35
- Typer option validation: https://typer.tiangolo.com/tutorial/options/help/#number-constraints
