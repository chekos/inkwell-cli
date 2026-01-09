---
status: complete
priority: p3
issue_id: "065"
tags:
  - code-review
  - pr-22
  - documentation
  - architecture
dependencies: []
---

# Document Error Type Semantics

## Problem Statement

The code uses both `NotFoundError` (for out-of-bounds positions) and `ValidationError` (for keyword search failures). The distinction is unclear without documentation.

**Why it matters:** Consistent error handling helps users and developers understand and handle errors appropriately.

## Findings

### Agent: Architecture Strategist
**Issue:** Mixed error types for similar failures

```python
# Position errors -> NotFoundError (lines 203-209)
raise NotFoundError(
    resource_type="Episode position",
    resource_id=str(invalid),
    # ...
)

# Keyword search -> ValidationError (line 153)
raise ValidationError(f"No episode found matching '{title_keyword}' in feed")
```

### Analysis

According to error hierarchy:
- `NotFoundError`: "Episode not found" when selector is valid but matches nothing
- `ValidationError`: "Invalid request parameters" when selector syntax is invalid

Current split is semantically appropriate but not documented.

## Proposed Solutions

### Solution 1: Add Docstring Documentation (Recommended)
**Pros:**
- Clear documentation
- No code changes
- Helps future maintainers

**Cons:**
- None

**Effort:** Small (5 minutes)
**Risk:** None

```python
def parse_and_fetch_episodes(
    self,
    feed: feedparser.FeedParserDict,
    selector: str,
    podcast_name: str,
) -> list[Episode]:
    """Parse selector and return matching episodes.

    Raises:
        ValidationError: If selector syntax is malformed (e.g., "abc-def")
            or keyword search finds no matches
        NotFoundError: If numeric positions are valid but out of bounds
            for the feed (e.g., position 50 in a 10-episode feed)
    """
```

## Recommended Action

Add clear Raises documentation to the method docstring.

## Technical Details

**Affected Files:**
- `src/inkwell/feeds/parser.py:155-178`

## Acceptance Criteria

- [ ] Docstring updated with Raises section
- [ ] Distinction between NotFoundError and ValidationError documented
- [ ] Examples provided for each error type

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2025-12-21 | Architecture review | Document error semantics to reduce surprise |

## Resources

- PR #22: https://github.com/chekos/inkwell-cli/pull/22
- Architecture Strategist analysis
