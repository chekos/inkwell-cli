---
status: complete
priority: p2
issue_id: "060"
tags:
  - code-review
  - pr-22
  - security
  - performance
dependencies: []
---

# Resource Exhaustion from Large Ranges/Lists

## Problem Statement

The `parse_and_fetch_episodes()` method accepts ranges like `1-1000000000` and lists with unlimited items without any size limits. This can cause memory exhaustion and denial of service.

**Why it matters:** Malicious or accidental large inputs could crash the application or exhaust system resources.

## Findings

### Agent: Security Sentinel
**Severity:** MEDIUM (5.3 CVSS-like score)

```python
# parser.py line 190 - No limit on range size
positions = list(range(min(start, end), max(start, end) + 1))

# Attack vector:
# inkwell fetch my-podcast --episode "1-999999999"
# Creates list with ~1 billion elements
```

### Agent: Performance Oracle
Memory allocation analysis:
- Range "1-100": ~800 bytes
- Range "1-1000": ~8KB
- Range "1-1000000": ~8MB (problematic)
- Range "1-1000000000": ~8GB (DoS)

## Proposed Solutions

### Solution 1: Add MAX_EPISODES_PER_SELECTION Constant (Recommended)
**Pros:**
- Simple to implement
- Clear, documented limit
- Protects against both malicious and accidental abuse

**Cons:**
- Slightly limits legitimate use cases (edge case)

**Effort:** Small (10 minutes)
**Risk:** Low

```python
# At module level in parser.py
MAX_EPISODES_PER_SELECTION = 100

# In parse_and_fetch_episodes():
if len(positions) > MAX_EPISODES_PER_SELECTION:
    raise ValidationError(
        f"Selection contains {len(positions)} episodes, maximum is {MAX_EPISODES_PER_SELECTION}",
        suggestion="Select fewer episodes or use multiple smaller requests"
    )
```

### Solution 2: Early Validation Before List Creation
**Pros:**
- Prevents memory allocation entirely
- More efficient for large ranges

**Cons:**
- More complex validation logic

**Effort:** Medium
**Risk:** Low

```python
# For ranges, validate size before list creation
if match := re.match(r"^(\d+)-(\d+)$", selector):
    start, end = int(match.group(1)), int(match.group(2))
    range_size = abs(end - start) + 1
    if range_size > MAX_EPISODES_PER_SELECTION:
        raise ValidationError(...)
    positions = list(range(min(start, end), max(start, end) + 1))
```

## Recommended Action

**Solution 1** with the early validation from **Solution 2** for ranges specifically.

## Technical Details

**Affected Files:**
- `src/inkwell/feeds/parser.py:188-194`

**Components:** RSSParser.parse_and_fetch_episodes()

## Acceptance Criteria

- [ ] MAX_EPISODES_PER_SELECTION constant defined (default: 100)
- [ ] Range size validated before list creation
- [ ] List length validated after parsing
- [ ] Clear error message with suggestion
- [ ] Tests added for large range rejection
- [ ] Tests added for large list rejection

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2025-12-21 | Security review identified issue | Always validate input size before memory allocation |
| 2025-12-21 | Approved during triage - Status: ready | Defense in depth for user input validation |

## Resources

- PR #22: https://github.com/chekos/inkwell-cli/pull/22
- Security Sentinel analysis
- Performance Oracle analysis
