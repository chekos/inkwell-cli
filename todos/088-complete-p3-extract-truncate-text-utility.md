---
status: complete
priority: p3
issue_id: "088"
tags: [code-review, code-quality, duplication, pr-36]
dependencies: []
---

# Extract truncate_text() Utility Function

## Problem Statement

Title truncation logic is duplicated in multiple places with inconsistent parameters:
- `list_episodes` line 193: `title[:57] + "..." if len(title) > 60`
- `_output_latest_table` lines 379-382: `title[:47] + "..." if len(title) > 50`
- Error message truncation line 393: `error[:40] + "..."`

This creates maintenance burden and inconsistency.

**Why it matters**: DRY principle violation, potential for bugs when updating truncation logic in one place but not others.

## Findings

**Location 1**: `/Users/chekos/projects/gh/inkwell-cli/src/inkwell/cli_list.py`, line 193
```python
title = ep.title[:57] + "..." if len(ep.title) > 60 else ep.title
```

**Location 2**: `/Users/chekos/projects/gh/inkwell-cli/src/inkwell/cli_list.py`, lines 379-382
```python
title = (
    result.episode.title[:47] + "..."
    if len(result.episode.title) > 50
    else result.episode.title
)
```

**Location 3**: `/Users/chekos/projects/gh/inkwell-cli/src/inkwell/cli_list.py`, line 393
```python
error_msg = error[:40] + "..." if len(error) > 40 else error
```

**Note**: `truncate_url()` already exists in `inkwell/utils/display.py` (line 256 import), suggesting a pattern for utilities.

## Proposed Solutions

### Option A: Add truncate_text() to display.py (Recommended)

**Pros**: Consistent with existing `truncate_url()`, reusable across codebase
**Cons**: Minor refactor needed
**Effort**: Small (20 minutes)
**Risk**: Very low

```python
# inkwell/utils/display.py
def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
    """Truncate text to max_length, adding suffix if truncated.

    Args:
        text: The text to truncate
        max_length: Maximum length including suffix
        suffix: String to append when truncated (default "...")

    Returns:
        Truncated text with suffix, or original if shorter than max_length
    """
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix
```

Then update usages:
```python
from inkwell.utils.display import truncate_text, truncate_url

# In list_episodes:
title = truncate_text(ep.title, 60)

# In _output_latest_table:
title = truncate_text(result.episode.title, 50)
error_msg = truncate_text(error, 40)
```

### Option B: Leave as-is

**Pros**: No changes needed, code works
**Cons**: Continued duplication, inconsistency risk
**Effort**: None
**Risk**: None immediate

## Recommended Action

**Option A**: Extract `truncate_text()` utility for cleaner code and consistency.

## Technical Details

**Files to modify**:
- `/Users/chekos/projects/gh/inkwell-cli/src/inkwell/utils/display.py` - Add function
- `/Users/chekos/projects/gh/inkwell-cli/src/inkwell/cli_list.py` - Update usages

**Tests to add**:
- `tests/unit/utils/test_display.py` - Unit tests for truncate_text()

## Acceptance Criteria

- [ ] `truncate_text()` function added to `utils/display.py`
- [ ] All truncation usages in `cli_list.py` updated to use utility
- [ ] Unit tests cover edge cases (empty string, exact length, longer)
- [ ] Existing tests still pass

## Work Log

| Date | Action | Notes |
|------|--------|-------|
| 2026-01-11 | Created | From PR #36 code review by pattern-recognition-specialist agent |

## Resources

- PR #36: https://github.com/chekos/inkwell-cli/pull/36
- Existing utility: `truncate_url()` in `inkwell/utils/display.py`
