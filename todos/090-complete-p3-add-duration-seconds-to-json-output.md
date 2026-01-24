---
status: complete
priority: p3
issue_id: "090"
tags: [code-review, agent-native, api-design, pr-36]
dependencies: []
---

# Add duration_seconds to JSON Output for Agent Accessibility

## Problem Statement

The JSON output from `list latest --json` returns formatted duration strings like "45:30" but not the raw `duration_seconds` value. Agents/scripts performing calculations need the raw numeric value.

**Why it matters**: Agent-native design principle - agents should have access to machine-friendly data formats for calculations and comparisons.

## Findings

**Location**: `/Users/chekos/projects/gh/inkwell-cli/src/inkwell/cli_list.py`, lines 418-428

```python
episodes.append(
    {
        "feed": result.feed_name,
        "status": "success",
        "episode": {
            "title": result.episode.title,
            "date": result.episode.published.strftime("%Y-%m-%d"),
            "duration": (  # Only formatted string, not raw seconds
                result.episode.duration_formatted
                if result.episode.duration_seconds
                else None
            ),
            "url": str(result.episode.url),
        },
    }
)
```

The `Episode` model has `duration_seconds` (line 42 of models.py) but JSON only exposes `duration_formatted`.

**Use case example**:
```python
# Agent wants to filter episodes > 1 hour
# Current: must parse "1:02:15" string
# Better: use duration_seconds > 3600
```

## Proposed Solutions

### Option A: Add duration_seconds alongside duration (Recommended)

**Pros**: Backward compatible, agents can use either format
**Cons**: Slightly larger JSON output
**Effort**: Small (10 minutes)
**Risk**: Very low

```python
"episode": {
    "title": result.episode.title,
    "date": result.episode.published.strftime("%Y-%m-%d"),
    "duration": (
        result.episode.duration_formatted
        if result.episode.duration_seconds
        else None
    ),
    "duration_seconds": result.episode.duration_seconds,  # Add this
    "url": str(result.episode.url),
},
```

### Option B: Replace duration with duration_seconds only

**Pros**: Simpler, lets agents format as needed
**Cons**: Breaking change, human-readable output lost
**Effort**: Small
**Risk**: Medium - breaks existing consumers

### Option C: Leave as-is

**Pros**: No changes
**Cons**: Agents must parse formatted duration strings
**Effort**: None
**Risk**: None

## Recommended Action

**Option A**: Add `duration_seconds` field while keeping formatted `duration` for backward compatibility.

## Technical Details

**Affected Files**:
- `/Users/chekos/projects/gh/inkwell-cli/src/inkwell/cli_list.py`

**Lines to modify**: 418-428 in `_output_latest_json()`

## Acceptance Criteria

- [ ] JSON output includes `duration_seconds` field
- [ ] Formatted `duration` field still present
- [ ] Test updated to verify duration_seconds in JSON
- [ ] Existing tests still pass

## Work Log

| Date | Action | Notes |
|------|--------|-------|
| 2026-01-11 | Created | From PR #36 code review by agent-native-reviewer agent |

## Resources

- PR #36: https://github.com/chekos/inkwell-cli/pull/36
- Episode model: `src/inkwell/feeds/models.py`
