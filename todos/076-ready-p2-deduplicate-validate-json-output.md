---
status: ready
priority: p2
issue_id: "076"
tags: [code-review, code-duplication, plugin-architecture]
dependencies: []
---

# Deduplicate _validate_json_output() Across Extractors

## Problem Statement

The `_validate_json_output()` method is duplicated nearly identically (~25 lines each) in both `ClaudeExtractor` and `GeminiExtractor`. Both implementations:
- Use `safe_json_loads()` with identical parameters (5MB max, depth 10)
- Perform identical schema validation logic
- Raise `ValidationError` with similar messages

**Why it matters:** Code duplication increases maintenance burden and risk of divergent behavior. This is a clear DRY violation.

## Findings

**Locations:**
- `src/inkwell/extraction/extractors/claude.py:223-248`
- `src/inkwell/extraction/extractors/gemini.py:244-268`

**Identical patterns:**
```python
def _validate_json_output(self, output: str, schema: dict) -> dict:
    try:
        from inkwell.utils.validation import safe_json_loads
        # ... identical parsing logic ...
    except json.JSONDecodeError as e:
        raise ValidationError(f"{self.NAME}: Invalid JSON output: {e}") from e
    # ... identical schema validation ...
```

**Only difference:** The provider name in error messages (`Claude` vs `Gemini`).

## Proposed Solutions

### Option A: Move to ExtractionPlugin base class (Recommended)
Add the method to `ExtractionPlugin` with `self.NAME` for provider identification.

**Pros:** Clean inheritance, single source of truth
**Cons:** Minor API change (method moves up the hierarchy)
**Effort:** Small (1-2 hours)
**Risk:** Low

```python
# In src/inkwell/plugins/types/extraction.py
class ExtractionPlugin(InkwellPlugin, BaseExtractor):
    def _validate_json_output(self, output: str, schema: dict) -> dict:
        try:
            from inkwell.utils.validation import safe_json_loads
            parsed = safe_json_loads(output, max_size=5_000_000, max_depth=10)
        except json.JSONDecodeError as e:
            raise ValidationError(f"{self.NAME}: Invalid JSON output: {e}") from e
        # ... shared validation logic using self.NAME ...
```

### Option B: Create shared utility function
Add to `inkwell/utils/validation.py` as a standalone function.

**Pros:** No class hierarchy changes
**Cons:** Requires passing provider name as parameter
**Effort:** Small (1-2 hours)
**Risk:** Low

```python
# In src/inkwell/utils/validation.py
def validate_extraction_json_output(output: str, schema: dict, provider: str) -> dict:
    """Validate JSON output against schema with security limits."""
    # ... shared logic ...
```

## Recommended Action

Use Option A: Move `_validate_json_output()` to `ExtractionPlugin` base class with `self.NAME` for provider identification.

## Technical Details

**Affected files:**
- `src/inkwell/extraction/extractors/claude.py`
- `src/inkwell/extraction/extractors/gemini.py`
- `src/inkwell/plugins/types/extraction.py` (if Option A)
- `src/inkwell/utils/validation.py` (if Option B)

**Components affected:**
- ClaudeExtractor
- GeminiExtractor
- ExtractionPlugin (if Option A)

**Database changes:** None

## Acceptance Criteria

- [ ] Single implementation of JSON validation logic
- [ ] Both extractors use the shared implementation
- [ ] Error messages still include provider name
- [ ] All extraction tests pass

## Work Log

| Date | Actor | Action | Learnings |
|------|-------|--------|-----------|
| 2026-01-06 | Pattern Recognition Agent | Identified code duplication | ~50 lines duplicated across extractors |
| 2026-01-06 | Triage Session | Approved for work (pending → ready) | Clear DRY violation with straightforward fix |

## Resources

- PR #34: Plugin Architecture Implementation
- `src/inkwell/extraction/extractors/claude.py:223-248`
- `src/inkwell/extraction/extractors/gemini.py:244-268`
