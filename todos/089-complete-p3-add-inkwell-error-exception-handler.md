---
status: complete
priority: p3
issue_id: "089"
tags: [code-review, consistency, error-handling, pr-36]
dependencies: []
---

# Add InkwellError Exception Handler to list_latest

## Problem Statement

The `run_latest()` async function does not wrap its logic in a `try/except InkwellError` block, unlike `list_templates`, `list_feeds`, and `list_episodes`. This is an inconsistency in error handling patterns.

**Why it matters**: Unexpected `InkwellError` exceptions could propagate with raw tracebacks instead of user-friendly messages.

## Findings

**Location**: `/Users/chekos/projects/gh/inkwell-cli/src/inkwell/cli_list.py`, lines 323-366

The `list_latest` command delegates error handling to `_fetch_latest_for_feed`, but the outer function lacks the standard pattern.

**Existing pattern in other commands**:

`list_templates` (lines 67-106):
```python
try:
    loader = TemplateLoader()
    names = loader.list_templates()
    # ... logic
except InkwellError as e:
    console.print(f"[red]✗[/red] Error: {e}")
    sys.exit(1)
```

`list_episodes` (lines 127-213):
```python
async def run_episodes() -> None:
    try:
        manager = ConfigManager()
        # ... logic
    except InkwellError as e:
        console.print(f"[red]✗[/red] Error: {e}")
        sys.exit(1)
```

**Missing in list_latest**:
```python
async def run_latest() -> None:
    manager = ConfigManager()  # No try/except wrapper
    feeds = manager.list_feeds()
    # ...
```

## Proposed Solutions

### Option A: Add try/except InkwellError (Recommended)

**Pros**: Consistent with other commands, better UX for unexpected errors
**Cons**: Minor code addition
**Effort**: Small (10 minutes)
**Risk**: Very low

```python
async def run_latest() -> None:
    try:
        manager = ConfigManager()
        feeds = manager.list_feeds()

        if not feeds:
            # ... early return logic unchanged

        parser = RSSParser()
        tasks = [_fetch_latest_for_feed(parser, name, config) for name, config in feeds.items()]

        # ... rest of logic unchanged

    except InkwellError as e:
        console.print(f"[red]✗[/red] Error: {e}")
        sys.exit(1)
```

### Option B: Leave as-is

**Pros**: Works currently since errors are caught in _fetch_latest_for_feed
**Cons**: Inconsistent pattern, potential for raw tracebacks
**Effort**: None
**Risk**: Low - but inconsistent

## Recommended Action

**Option A**: Add the standard `try/except InkwellError` wrapper for consistency.

## Technical Details

**Affected Files**:
- `/Users/chekos/projects/gh/inkwell-cli/src/inkwell/cli_list.py`

**Lines to modify**: Wrap lines 324-366 in try/except

## Acceptance Criteria

- [ ] `run_latest()` wrapped in try/except InkwellError
- [ ] Error display format matches other commands
- [ ] Existing tests still pass
- [ ] Test added for InkwellError handling in list_latest

## Work Log

| Date | Action | Notes |
|------|--------|-------|
| 2026-01-11 | Created | From PR #36 code review by architecture-strategist agent |

## Resources

- PR #36: https://github.com/chekos/inkwell-cli/pull/36
- Existing pattern: `list_templates` lines 67-106, `list_episodes` lines 127-213
