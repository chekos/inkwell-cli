---
status: complete
priority: p2
issue_id: "078"
tags: [code-review, code-duplication, plugin-architecture]
dependencies: []
---

# Deduplicate track_cost() Method Across Plugin Types

## Problem Statement

The `track_cost()` method is duplicated (~30 lines each) in both `ExtractionPlugin` and `TranscriptionPlugin`. Both implementations perform identical cost tracking with slight signature differences.

**Why it matters:** Maintenance burden and risk of divergent implementations. The cost tracking logic should be unified.

## Findings

**Locations:**
- `src/inkwell/plugins/types/extraction.py:89-117`
- `src/inkwell/plugins/types/transcription.py:196-221`

**Signature differences:**
```python
# ExtractionPlugin
def track_cost(self, input_tokens, output_tokens, operation="extraction",
               episode_title=None, template_name=None)

# TranscriptionPlugin
def track_cost(self, input_tokens, output_tokens, operation="transcription",
               episode_title=None)  # Missing template_name
```

**Identical logic:**
- Check if `_cost_tracker` is set
- Call `add_cost()` with provider/model/operation/tokens
- Return silently if no tracker

## Proposed Solutions

### Option A: Move to InkwellPlugin base class (Recommended)
Add the method to the base class with all parameters as optional.

**Pros:** Single implementation, all plugins get cost tracking
**Cons:** Base class grows slightly
**Effort:** Small (1-2 hours)
**Risk:** Low

```python
# In src/inkwell/plugins/base.py
class InkwellPlugin(ABC):
    def track_cost(
        self,
        input_tokens: int = 0,
        output_tokens: int = 0,
        operation: str = "unknown",
        episode_title: str | None = None,
        template_name: str | None = None,
    ) -> None:
        """Track cost with the injected cost tracker."""
        if self._cost_tracker:
            self._cost_tracker.add_cost(
                provider=self.NAME,
                model=getattr(self, "MODEL", "unknown"),
                operation=operation,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                episode_title=episode_title,
                template_name=template_name,
            )
```

### Option B: Create CostTrackingMixin
Use a mixin class for cost tracking functionality.

**Pros:** Composition over inheritance
**Cons:** Additional class to understand
**Effort:** Small (1-2 hours)
**Risk:** Low

## Recommended Action

Use Option A: Move `track_cost()` to `InkwellPlugin` base class with all parameters optional.

## Technical Details

**Affected files:**
- `src/inkwell/plugins/base.py`
- `src/inkwell/plugins/types/extraction.py`
- `src/inkwell/plugins/types/transcription.py`

**Components affected:**
- InkwellPlugin base class
- ExtractionPlugin
- TranscriptionPlugin

**Database changes:** None

## Acceptance Criteria

- [ ] Single implementation of track_cost() in base class
- [ ] ExtractionPlugin and TranscriptionPlugin use inherited method
- [ ] All parameters supported (input_tokens, output_tokens, operation, episode_title, template_name)
- [ ] All existing tests pass

## Work Log

| Date | Actor | Action | Learnings |
|------|-------|--------|-----------|
| 2026-01-06 | Pattern Recognition Agent | Identified code duplication | ~60 lines duplicated across plugin types |
| 2026-01-06 | Triage Session | Approved for work (pending → ready) | Clear DRY violation with straightforward fix |

## Resources

- PR #34: Plugin Architecture Implementation
- `src/inkwell/plugins/types/extraction.py:89-117`
- `src/inkwell/plugins/types/transcription.py:196-221`
