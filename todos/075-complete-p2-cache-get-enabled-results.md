---
status: complete
priority: p2
issue_id: "075"
tags: [code-review, performance, plugin-architecture]
dependencies: []
---

# Cache get_enabled() Results in PluginRegistry

## Problem Statement

The `PluginRegistry.get_enabled()` method performs O(n) filtering plus O(n log n) sorting on every call. This method is called frequently during plugin selection, adding unnecessary overhead.

**Why it matters:** This is in the hot path for every extraction/transcription operation. With 20+ plugins, the repeated sorting becomes measurable.

## Findings

**Location:** `src/inkwell/plugins/registry.py:173-189`

```python
def get_enabled(self) -> list[tuple[str, T]]:
    usable = [
        (e.name, e.plugin)
        for e in self._entries.values()
        if e.is_usable
    ]
    return sorted(
        usable,
        key=lambda x: (-self._entries[x[0]].priority, x[0]),
    )
```

**Problem:** Sorts the entire list on every call, even when the underlying data hasn't changed.

**Call sites:**
- `ExtractionEngine._select_extractor_from_registry()`
- `TranscriptionManager._load_transcription_plugins()`
- `cli_plugins.py` list command

## Proposed Solutions

### Option A: Cache with invalidation (Recommended)
Add a cached result that's invalidated on register/enable/disable operations.

**Pros:** O(1) subsequent calls, minimal memory overhead
**Cons:** Requires tracking cache validity
**Effort:** Medium (2-4 hours)
**Risk:** Low

```python
class PluginRegistry(Generic[T]):
    def __init__(self, plugin_type: type[T]) -> None:
        self._plugin_type = plugin_type
        self._entries: dict[str, PluginEntry[T]] = {}
        self._enabled_cache: list[tuple[str, T]] | None = None

    def _invalidate_cache(self) -> None:
        self._enabled_cache = None

    def register(self, ...):
        self._invalidate_cache()
        # ... existing logic ...

    def enable(self, name: str) -> bool:
        self._invalidate_cache()
        # ... existing logic ...

    def disable(self, name: str) -> bool:
        self._invalidate_cache()
        # ... existing logic ...

    def get_enabled(self) -> list[tuple[str, T]]:
        if self._enabled_cache is None:
            usable = [(e.name, e.plugin) for e in self._entries.values() if e.is_usable]
            self._enabled_cache = sorted(usable, key=lambda x: (-self._entries[x[0]].priority, x[0]))
        return self._enabled_cache
```

### Option B: Lazy property with dirty flag
Similar to Option A but uses a property pattern.

**Pros:** Clean API
**Cons:** Same complexity as Option A
**Effort:** Medium (2-4 hours)
**Risk:** Low

## Recommended Action

Use Option A: Add `_enabled_cache` attribute with invalidation on register/enable/disable operations.

## Technical Details

**Affected files:**
- `src/inkwell/plugins/registry.py`

**Components affected:**
- PluginRegistry class
- All code that calls get_enabled()

**Database changes:** None

## Acceptance Criteria

- [ ] Cached result returned for subsequent calls when registry unchanged
- [ ] Cache invalidated on register/enable/disable operations
- [ ] All existing registry tests pass
- [ ] Add test for cache invalidation behavior

## Work Log

| Date | Actor | Action | Learnings |
|------|-------|--------|-----------|
| 2026-01-06 | Performance Oracle Agent | Identified repeated sorting overhead | Registry methods are in hot path |
| 2026-01-06 | Triage Session | Approved for work (pending → ready) | Cache invalidation pattern is well-understood |

## Resources

- PR #34: Plugin Architecture Implementation
- `src/inkwell/plugins/registry.py:173-189`
