---
status: complete
priority: p3
issue_id: "079"
tags: [code-review, simplification, plugin-architecture]
dependencies: []
---

# Simplify Dual Code Paths in Extractors/Transcribers

## Problem Statement

The `ExtractionEngine` and `TranscriptionManager` maintain BOTH legacy direct instantiation (`self.claude_extractor`, `self.gemini_extractor`) AND new plugin registry access. This creates ~100+ lines of redundant code and two parallel code paths that must both be maintained.

**Why it matters:** Technical debt that increases maintenance burden. The legacy paths are preserved for backward compatibility but could be deprecated and removed.

## Findings

**Locations:**
- `src/inkwell/extraction/engine.py:230-254` (legacy properties)
- `src/inkwell/extraction/engine.py:802-848` (`_select_extractor_legacy` method)
- `src/inkwell/transcription/manager.py:119-141` (legacy properties)
- `src/inkwell/transcription/manager.py:450-631` (duplicate transcription logic)

**Dual path example in engine.py:**
```python
# Legacy path
@property
def claude_extractor(self) -> ClaudeExtractor:
    # Direct instantiation

# Plugin path
@property
def extraction_registry(self) -> PluginRegistry[ExtractionPlugin]:
    # Registry-based access
```

**Impact:**
- 150+ lines of code maintaining backward compatibility
- Two selection methods (`_select_extractor_legacy` vs `_select_extractor_from_registry`)
- Duplicate transcription logic in `transcribe` vs `_transcribe_with_override`

## Proposed Solutions

### Option A: Deprecate and remove in v2.0 (Recommended)
Document deprecation now, remove legacy paths in next major version.

**Pros:** Clean break, reduced complexity
**Cons:** Breaking change for direct extractor users
**Effort:** Low (documentation) → Medium (removal in v2.0)
**Risk:** Medium (breaking change)

### Option B: Unify to plugin-only path now
Remove legacy code and force all users through plugin registry.

**Pros:** Immediate simplification (~150 LOC removed)
**Cons:** Breaking change in minor version
**Effort:** Medium (4-6 hours)
**Risk:** High (breaking change)

### Option C: Keep dual paths indefinitely
Maintain backward compatibility forever.

**Pros:** No breaking changes
**Cons:** Permanent maintenance burden
**Effort:** Ongoing
**Risk:** Low (but tech debt accumulates)

## Recommended Action

Use Option B: Remove legacy code paths now. Single user project, no backward compatibility needed.

## Technical Details

**Affected files:**
- `src/inkwell/extraction/engine.py`
- `src/inkwell/transcription/manager.py`

**Estimated LOC reduction:** 150+ lines

**Components affected:**
- ExtractionEngine
- TranscriptionManager
- Any code using direct extractor properties

**Database changes:** None

## Acceptance Criteria

- [ ] Legacy extractor properties removed from ExtractionEngine
- [ ] Legacy transcription properties removed from TranscriptionManager
- [ ] `_select_extractor_legacy` method removed
- [ ] Duplicate transcription logic consolidated
- [ ] All tests pass with plugin-only paths

## Work Log

| Date | Actor | Action | Learnings |
|------|-------|--------|-----------|
| 2026-01-06 | Code Simplicity Reviewer | Identified dual code paths | ~150 LOC maintaining backward compatibility |
| 2026-01-06 | Triage Session | Approved for work (pending → ready) | Deprecation path preferred over breaking change |
| 2026-01-06 | User | Changed to Option B | Single user project, no need for deprecation warnings |

## Resources

- PR #34: Plugin Architecture Implementation
- `src/inkwell/extraction/engine.py:230-254, 802-848`
- `src/inkwell/transcription/manager.py:119-141, 450-631`
