---
status: pending
priority: p3
issue_id: "058"
tags: [epic, v2.0, cleanup, dependency-injection, simplification]
dependencies: [055, 056, 057]
---

# v2.0 Dependency Injection Cleanup - Tracking Epic

## Problem Statement

PR #20 successfully implements dependency injection with gradual migration strategy, but leaves ~420 LOC of temporary migration scaffolding that should be removed in v2.0 when backward compatibility is no longer needed.

**Severity**: Low (planned technical debt, intentionally deferred)

## Overview

This is a **tracking epic** for the planned v2.0 cleanup of the DI pattern introduced in PR #20. All simplification opportunities identified during code review are intentionally deferred to avoid scope creep.

**Purpose**: Single source of truth for v2.0 cleanup scope

## Scope

### Phase 1: Remove Abstraction Overhead (TODO #055)
- Remove `src/inkwell/config/precedence.py` module
- Inline precedence logic with `or` operators
- Remove associated tests
- **LOC Reduction**: ~90 lines
- **Effort**: 30 minutes

### Phase 2: Remove Backward Compatibility (TODO #056)
- Remove deprecated fields from GlobalConfig
- Remove model_post_init migration logic
- Remove migration tests
- **LOC Reduction**: ~140 lines
- **Effort**: 30 minutes

### Phase 3: Rationalize Validation (TODO #057)
- Keep security-critical validations only
- Remove arbitrary limits and defensive checks
- Simplify Field constraints
- **LOC Reduction**: ~50 lines
- **Effort**: 1 hour

### Phase 4: Remove Dual Parameter Support
- Remove individual params from service constructors
- Require config objects only
- Update all call sites
- **LOC Reduction**: ~60 lines
- **Effort**: 2 hours

### Phase 5: Simplify Deprecation Warnings
- Remove all deprecation warning logic
- Clean up warning tests
- **LOC Reduction**: ~30 lines
- **Effort**: 15 minutes

### Phase 6: Documentation Updates
- Update ADR-031 with v2.0 changes
- Document removed backward compatibility
- Update examples in docstrings
- **Effort**: 1 hour

## Total Impact

**LOC Reduction**: ~420 lines (30% of PR #20 additions)
**Total Effort**: ~5.5 hours
**Risk**: Low (backward incompatible, hence v2.0)

## Rationale for Deferral

**Why not do this in PR #20?**
1. PR #20 is already approved and comprehensive (9 issues fixed)
2. Simplifications are nice-to-haves, not blockers
3. Gradual migration strategy requires temporary scaffolding
4. v2.0 is natural breaking point for cleanup
5. Avoid scope creep on already-large PR

**Why track as epic?**
1. Intentional technical debt requires visibility
2. Multiple related TODOs need coordination
3. v2.0 planning requires scope understanding
4. Documents the "why" for future maintainers

## Migration Strategy for v2.0

### Breaking Changes
1. **Config objects required** - No individual parameters accepted
2. **Deprecated fields removed** - Only nested config structure supported
3. **No migration logic** - Old configs will fail with clear errors

### User Impact
- **Low**: Most users already on new pattern (it's preferred)
- **Migration path**: Clear error messages guide to new structure
- **Documentation**: Update migration guide in docs/

### Communication Plan
- Announce v2.0 breaking changes in CHANGELOG
- Provide migration script if needed (likely not)
- Update all examples to use new pattern only

## Dependencies

**Blocked by**: None (can start after v2.0 decision)
**Blocks**: v2.0 release
**Related**: TODOs #055, #056, #057

## Acceptance Criteria

- [ ] All simplification TODOs completed (#055-057)
- [ ] Dual parameter support removed from services
- [ ] Deprecation warnings removed
- [ ] ADR-031 updated for v2.0
- [ ] All tests pass with new patterns only
- [ ] CHANGELOG documents breaking changes
- [ ] Migration guide updated (if needed)
- [ ] LOC reduction: ~400+ lines

## Work Log

### 2025-11-19 - Epic Creation
**By:** Code Review Process
**Actions:**
- Consolidated simplification opportunities from PR #20 review
- Created tracking epic for v2.0 cleanup
- Documented rationale for deferral

**Learnings:**
- Intentional technical debt needs explicit tracking
- Gradual migration requires temporary complexity
- v2.0 is appropriate breaking point for cleanup
- Document "why defer" for future context

## Notes

Source: Comprehensive code review of PR #20 (2025-11-19)
Review command: /compounding-engineering:review PR20
Related PR: #20 (dependency injection implementation)
Related ADR: ADR-031 (gradual DI migration)
Timeline: Target for v2.0 release
Rationale: Avoid scope creep, clean break at major version
