---
status: complete
priority: p3
issue_id: "066"
tags:
  - code-review
  - pr-22
  - architecture
  - technical-debt
dependencies: []
---

# Future: Extract EpisodeSelector Class

## Problem Statement

The `parse_and_fetch_episodes()` method in RSSParser mixes two concerns:
1. Parsing selector syntax (regex matching, position extraction)
2. Fetching episodes from feed (domain logic)

This violates Single Responsibility Principle and will make adding new selector types harder.

**Why it matters:** As more selector types are added ("all", "last-N", date ranges), the method will grow and become harder to maintain.

## Findings

### Agent: Architecture Strategist
**Severity:** Medium (OCP violation)

The selector pattern is not extensible without modifying RSSParser. Future scenarios include:
- `"all"` - select all episodes
- `"last-3"` - select last 3 episodes
- Date ranges
- Guest name search

### Agent: Code Simplicity Reviewer
**Alternate View:** Current implementation is acceptable for v0.2. Premature abstraction is worse than current state.

## Proposed Solutions

### Solution 1: Add TODO Comment Now, Extract Later (Recommended)
**Pros:**
- Documents the technical debt
- No immediate code changes
- Aligns with gradual migration (ADR-031)

**Cons:**
- Debt remains until addressed

**Effort:** Small (2 minutes)
**Risk:** None

```python
# TODO(v0.3): Extract to EpisodeSelector class when adding "all", "last-N", date ranges
# See architectural review PR#22 for rationale
def parse_and_fetch_episodes(self, ...):
```

### Solution 2: Extract Now
**Pros:**
- Cleaner architecture
- Better testability

**Cons:**
- Scope creep for PR
- Premature abstraction
- 150+ lines of new classes

**Effort:** Large
**Risk:** Medium

## Recommended Action

Add TODO comment for future extraction. Do not extract in PR #22.

## Technical Details

**Future Structure:**
```python
# src/inkwell/feeds/selector.py
class EpisodeSelector:
    """Parses episode selection syntax and returns positions."""

    def parse(self, selector: str, feed_size: int) -> list[int]:
        """Parse selector string into episode positions."""
        # Move current logic here
```

## Acceptance Criteria

- [ ] TODO comment added to parse_and_fetch_episodes method
- [ ] Comment references architectural review
- [ ] No actual extraction in this PR

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2025-12-21 | Architecture review | Document tech debt with TODOs, don't prematurely abstract |
| 2025-12-21 | Approved during triage - Status: ready | Add TODO comment, defer extraction to v0.3 |

## Resources

- PR #22: https://github.com/chekos/inkwell-cli/pull/22
- Architecture Strategist analysis
- ADR-031 (Gradual Dependency Injection Migration)
