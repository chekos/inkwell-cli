---
status: complete
priority: p2
issue_id: "067"
tags: [code-review, type-safety, python, pr-26]
dependencies: []
created: 2025-12-29
pr: "#26"
---

# Replace Assert Pattern with Explicit None Check

## Problem Statement

The PR uses `assert transcript is not None` to narrow optional types for mypy compliance. While this works, assertions can be disabled with `python -O`, silently converting this to a runtime bug in production.

**Location**: `/Users/chekos/projects/gh/inkwell-cli/src/inkwell/pipeline/orchestrator.py` (lines 180-182, 434)

**Why It Matters**:
- Assertions are stripped in optimized Python (`python -O`)
- This silently becomes a runtime bug in production when running optimized
- The proper solution is to narrow the type explicitly with a guard clause

## Findings

**Agent**: kieran-python-reviewer

**Current Code** (line 180-182):
```python
transcript = transcript_result.transcript
assert transcript is not None
```

**Similar Pattern Found** (line 434):
```python
assert transcript_result.transcript is not None
```

The `TranscriptionResult.transcript` field is typed as `Transcript | None`. After `_transcribe()` succeeds, we know it's not None, but mypy doesn't.

## Proposed Solutions

### Option A: Explicit Guard Clause (Recommended)

**Pros**: Safer, explicit error handling, never stripped
**Cons**: 2 lines instead of 1
**Effort**: Small
**Risk**: Low

```python
transcript = transcript_result.transcript
if transcript is None:
    raise InkwellError("Transcription succeeded but returned no transcript")
```

### Option B: Keep Assert with Message

**Pros**: Documents invariant, minimal change
**Cons**: Still stripped with -O flag
**Effort**: Small
**Risk**: Medium

```python
assert transcript is not None, "Transcript should exist after successful transcription"
```

### Option C: Accept Current Pattern

**Pros**: No change needed
**Cons**: Potential production bug with -O flag
**Effort**: None
**Risk**: Low (project doesn't use -O flag)

The codebase is not deployed with optimization flags, so this is technically safe. However, explicit is better than implicit.

## Recommended Action

**Option A** - Replace assert with explicit guard clause. This is the Pythonic way to handle invariants that should never fail but could due to implementation bugs.

## Technical Details

**Affected Files**:
- `src/inkwell/pipeline/orchestrator.py` (lines 180-182, 434)

**Type Context**:
```python
# From src/inkwell/transcription/models.py:206
class TranscriptionResult(BaseModel):
    transcript: Transcript | None = Field(None, description="The transcript if successful")
```

## Acceptance Criteria

- [ ] Replace `assert transcript is not None` with explicit `if transcript is None: raise`
- [ ] Replace `assert transcript_result.transcript is not None` with explicit guard
- [ ] Add descriptive error messages
- [ ] All existing tests pass
- [ ] Mypy passes without new errors

## Work Log

| Date | Action | Learning |
|------|--------|----------|
| 2025-12-29 | Created from PR #26 review | Assert pattern is common but risky |

## Resources

- **PR**: https://github.com/chekos/inkwell-cli/pull/26
- **Python Optimization**: https://docs.python.org/3/using/cmdline.html#cmdoption-O
