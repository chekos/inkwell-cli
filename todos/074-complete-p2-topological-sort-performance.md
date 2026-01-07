---
status: complete
priority: p2
issue_id: "074"
tags: [code-review, performance, plugin-architecture]
dependencies: []
---

# Inefficient Topological Sort in Dependency Resolution

## Problem Statement

The `resolve_dependencies()` function in `loader.py` has suboptimal performance due to calling `queue.sort()` inside the main loop and using `list.pop(0)` which is O(n) on Python lists. This creates O(n² log n) complexity instead of the optimal O(V + E) for topological sort.

**Why it matters:** While current plugin counts are small (<10), this scales poorly and represents unnecessary technical debt. At 50+ plugins, this could add measurable latency.

## Findings

**Location:** `src/inkwell/plugins/loader.py:126-128`

```python
while queue:
    queue.sort()  # Sorts on every iteration!
    name = queue.pop(0)  # O(n) operation on list
```

**Current complexity:** O(V² log V) where V = number of plugins
**Optimal complexity:** O(V + E) where E = dependency edges

**Impact projection:**
| Plugins | Current Time | Optimal Time |
|---------|--------------|--------------|
| 10      | ~0.1ms       | ~0.05ms      |
| 50      | ~2ms         | ~0.3ms       |
| 200     | ~50ms        | ~2ms         |

## Proposed Solutions

### Option A: Use collections.deque (Recommended)
Replace list with deque for O(1) popleft operations. Sort once at start for determinism.

**Pros:** Simple fix, O(1) pops, standard library
**Cons:** Minor code change required
**Effort:** Small (30 minutes)
**Risk:** Low

```python
from collections import deque

def resolve_dependencies(plugins):
    # ... setup code ...
    queue = deque(sorted(name for name, degree in in_degree.items() if degree == 0))

    while queue:
        name = queue.popleft()  # O(1)
        for dependent in dependents[name]:
            in_degree[dependent] -= 1
            if in_degree[dependent] == 0:
                # Maintain order with bisect for determinism
                import bisect
                bisect.insort(queue, dependent)
```

### Option B: Remove sorting entirely
Since plugin loading order doesn't matter semantically, skip sorting.

**Pros:** Simplest fix
**Cons:** Non-deterministic output could make debugging harder
**Effort:** Trivial (10 minutes)
**Risk:** Low

## Recommended Action

Use Option A: Replace list with `collections.deque` for O(1) popleft operations. Sort once at start for determinism.

## Technical Details

**Affected files:**
- `src/inkwell/plugins/loader.py`

**Components affected:**
- Plugin loading system
- Dependency resolution

**Database changes:** None

## Acceptance Criteria

- [ ] `resolve_dependencies()` uses O(1) pop operations
- [ ] No sorting inside the main loop
- [ ] All existing plugin tests pass
- [ ] Performance is O(V + E) for V plugins and E dependency edges

## Work Log

| Date | Actor | Action | Learnings |
|------|-------|--------|-----------|
| 2026-01-06 | Performance Oracle Agent | Identified performance issue | Kahn's algorithm should use deque not list |
| 2026-01-06 | Triage Session | Approved for work (pending → ready) | Small fix with clear solution |

## Resources

- PR #34: Plugin Architecture Implementation
- `src/inkwell/plugins/loader.py:90-143`
