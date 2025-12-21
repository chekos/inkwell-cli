---
status: complete
priority: p2
issue_id: "063"
tags:
  - code-review
  - pr-22
  - performance
  - code-quality
dependencies: []
---

# Pre-compile Regex Patterns as Class Constants

## Problem Statement

Regex patterns are inline strings compiled on every method invocation. While the performance impact is negligible for CLI usage, this violates best practices and makes patterns harder to maintain.

**Why it matters:** Pre-compiled patterns are cleaner, faster, and self-documenting.

## Findings

### Agent: Kieran Python Reviewer
**Severity:** Should Fix

```python
# parser.py lines 184, 188, 193 - Magic regex strings
if re.match(r"^\d+$", selector):
elif match := re.match(r"^(\d+)-(\d+)$", selector):
elif re.match(r"^\d+(,\s*\d+)+$", selector):
```

### Agent: Performance Oracle
**Benchmark Results:**
- Uncompiled: 119ms per 100,000 invocations
- Compiled: 42ms per 100,000 invocations
- **65% overhead from runtime compilation**

**Real-world impact:** ~0.0008ms per call (negligible for CLI)

## Proposed Solutions

### Solution 1: Class-level Constants (Recommended)
**Pros:**
- Compiled once at import time
- Self-documenting pattern names
- DRY principle
- Standard Python practice

**Cons:**
- None

**Effort:** Small (5 minutes)
**Risk:** None

```python
class RSSParser:
    """Parses RSS feeds and extracts episode information."""

    # Pre-compiled regex patterns for episode selection
    _SINGLE_POSITION_PATTERN = re.compile(r"^\d+$")
    _RANGE_PATTERN = re.compile(r"^(\d+)-(\d+)$")
    _LIST_PATTERN = re.compile(r"^\d+(,\s*\d+)+$")

    def parse_and_fetch_episodes(self, ...):
        if self._SINGLE_POSITION_PATTERN.match(selector):
            positions = [int(selector)]
        elif range_match := self._RANGE_PATTERN.match(selector):
            start, end = int(range_match.group(1)), int(range_match.group(2))
            positions = list(range(min(start, end), max(start, end) + 1))
        elif self._LIST_PATTERN.match(selector):
            positions = [int(x.strip()) for x in selector.split(",")]
```

## Recommended Action

Extract patterns as class-level constants with descriptive names.

## Technical Details

**Affected Files:**
- `src/inkwell/feeds/parser.py:184-193`

## Acceptance Criteria

- [ ] Three regex patterns extracted as class constants
- [ ] Constants named descriptively (_SINGLE_POSITION_PATTERN, etc.)
- [ ] Method updated to use compiled patterns
- [ ] All tests still pass

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2025-12-21 | Performance and code quality review | Pre-compile regex for clarity even when performance gain is negligible |
| 2025-12-21 | Approved during triage - Status: ready | Best practice even when perf gain is negligible |

## Resources

- PR #22: https://github.com/chekos/inkwell-cli/pull/22
- Kieran Python Review analysis
- Performance Oracle analysis
