---
status: complete
priority: p3
issue_id: "068"
tags: [code-review, type-safety, architecture, pr-26]
dependencies: []
created: 2025-12-29
pr: "#26"
---

# Address Type Ignore Override in Cache Classes

## Problem Statement

The cache subclasses use `# type: ignore[override]` to suppress Liskov Substitution Principle violations. The subclass `set()` method has a different signature than the base `FileCache.set()`.

**Locations**:
- `/Users/chekos/projects/gh/inkwell-cli/src/inkwell/extraction/cache.py` (Line 147)
- `/Users/chekos/projects/gh/inkwell-cli/src/inkwell/transcription/cache.py` (Line 101)

**Why It Matters**:
- Violates Liskov Substitution Principle
- Code expecting a `FileCache[T]` but receiving an `ExtractionCache` will fail
- The `# type: ignore[override]` suppresses a legitimate type error

## Findings

**Agent**: kieran-python-reviewer

**Current Code** (extraction/cache.py:147):
```python
async def set(  # type: ignore[override]
    self, template_name: str, template_version: str, transcript: str, result: str
) -> None:
```

**Base Class Signature** (utils/cache.py):
```python
async def set(self, *args: str, value: T) -> None:
```

The signatures are incompatible - subclass expects positional args, base class expects variadic args plus named value.

## Proposed Solutions

### Option A: Composition Over Inheritance (Recommended)

**Pros**: Clean separation, no LSP violation
**Cons**: Slightly more verbose
**Effort**: Medium
**Risk**: Low

```python
class ExtractionCache:
    """Extraction-specific cache using FileCache internally."""

    def __init__(self, cache_dir: Path, extractor: str, model: str):
        self._cache = FileCache[str](cache_dir, namespace="extraction")
        self.extractor = extractor
        self.model = model

    async def get(self, template_name: str, template_version: str, transcript: str) -> str | None:
        return await self._cache.get(template_name, template_version, transcript)

    async def set(self, template_name: str, template_version: str, transcript: str, result: str) -> None:
        await self._cache.set(template_name, template_version, transcript, value=result)
```

### Option B: Protocol-Based Design

**Pros**: Flexible, mypy-friendly
**Cons**: More abstract
**Effort**: Medium-Large
**Risk**: Low

```python
from typing import Protocol

class Cache(Protocol[T]):
    async def get(self, *args: str) -> T | None: ...
    async def set(self, *args: str, value: T) -> None: ...
```

### Option C: Accept Current Pattern

**Pros**: No change needed
**Cons**: Type system lies to mypy
**Effort**: None
**Risk**: Medium (future maintenance confusion)

The current code works correctly at runtime. The `# type: ignore[override]` is a pragmatic solution for mypy compliance.

## Recommended Action

**Option C for now** (accept current pattern), but create this todo to track the technical debt. Address in a future refactoring PR when working on the cache system.

## Technical Details

**Affected Files**:
- `src/inkwell/extraction/cache.py`
- `src/inkwell/transcription/cache.py`

**Related Issue**: `032-pending-p3-consolidate-cache-implementations.md`

## Acceptance Criteria

- [ ] If addressed: Remove `# type: ignore[override]` comments
- [ ] If addressed: Cache classes pass mypy without suppressions
- [ ] All existing tests pass
- [ ] Document decision in ADR if architectural change

## Work Log

| Date | Action | Learning |
|------|--------|----------|
| 2025-12-29 | Created from PR #26 review | LSP violations should be tracked even if deferred |

## Resources

- **PR**: https://github.com/chekos/inkwell-cli/pull/26
- **Liskov Substitution**: https://en.wikipedia.org/wiki/Liskov_substitution_principle
