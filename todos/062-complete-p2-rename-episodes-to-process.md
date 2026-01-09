---
status: complete
priority: p2
issue_id: "062"
tags:
  - code-review
  - pr-22
  - code-quality
  - naming
dependencies: []
---

# Variable Naming: `episodes_to_process` is Misleading

## Problem Statement

The variable `episodes_to_process` implies a work queue or pending state, but it's actually just the list of **selected episodes**. This is misleading.

**Why it matters:** Variable names should describe what the data **is**, not what you **intend to do with it**.

## Findings

### Agent: Kieran Python Reviewer
**Severity:** HIGH (Blocking for code quality)

```python
# cli.py lines 842, 847, 850, 854, 860, 861, 868
episodes_to_process = [parser.get_latest_episode(feed, url_or_feed)]
console.print(f"[green]✓[/green] Latest episode: {episodes_to_process[0].title}")
```

**5-Second Rule:** "Does this variable track processing state?"
- No, it's just a list of episodes
- The name suggests a queue or pending work

## Proposed Solutions

### Solution 1: Rename to `selected_episodes` (Recommended)
**Pros:**
- Describes what the data is
- No implication of processing state
- Clear and accurate

**Cons:**
- None

**Effort:** Small (5 minutes)
**Risk:** None

```python
selected_episodes = [parser.get_latest_episode(feed, url_or_feed)]
console.print(f"[green]✓[/green] Latest episode: {selected_episodes[0].title}")
```

## Recommended Action

Rename all occurrences of `episodes_to_process` to `selected_episodes`.

## Technical Details

**Affected Files:**
- `src/inkwell/cli.py` lines 842, 847, 850, 854, 860, 861, 868

## Acceptance Criteria

- [ ] All occurrences of `episodes_to_process` renamed to `selected_episodes`
- [ ] 7 occurrences total updated

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2025-12-21 | Code quality review | Name variables for what they ARE, not what you'll DO with them |
| 2025-12-21 | Approved during triage - Status: ready | Quick win for code clarity |

## Resources

- PR #22: https://github.com/chekos/inkwell-cli/pull/22
- Kieran Python Review analysis
