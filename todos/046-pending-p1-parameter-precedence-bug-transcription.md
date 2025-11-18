---
status: pending
priority: p1
issue_id: "046"
tags: [code-review, bug, dependency-injection, pr-20, critical]
dependencies: []
---

# Fix Parameter Precedence Bug in TranscriptionManager

## Problem Statement

The parameter precedence logic in `TranscriptionManager.__init__()` is backwards. When both a config object AND individual parameters are provided, the deprecated individual parameter (`model_name`) takes precedence over the config object value (`config.model_name`). This breaks the entire dependency injection migration strategy.

**Severity**: CRITICAL (Blocks PR #20 merge)

## Findings

- Discovered during comprehensive Python code review by kieran-python-reviewer agent
- Location: `src/inkwell/transcription/manager.py:69`
- Current code: `effective_model = model_name or config.model_name`
- Expected: `effective_model = config.model_name or model_name`
- Violates documented migration strategy in ADR-031
- Inconsistent with ExtractionEngine (which implements correct precedence)

**Impact Analysis**:
- Users migrating to config objects cannot rely on them
- Deprecated parameters silently override new config values
- Creates confusion during migration period
- Undermines the entire gradual migration strategy
- Tests would fail if parameter precedence was tested (but aren't)

**Example Bug**:
```python
# User attempts to migrate to new pattern
config = TranscriptionConfig(model_name="gemini-2.5-flash")
manager = TranscriptionManager(
    config=config,
    model_name="gemini-1.5-flash"  # BUG: This wins! Should be ignored.
)

# Expected: Uses "gemini-2.5-flash" from config
# Actual: Uses "gemini-1.5-flash" from deprecated param
```

## Proposed Solutions

### Option 1: Fix Precedence Order (Recommended)

**Pros**:
- Matches expected behavior
- Consistent with ExtractionEngine
- Aligns with ADR-031 documentation
- Simple one-line fix

**Cons**:
- None

**Effort**: Small (2 minutes)
**Risk**: Low (pure bug fix, no functionality change)

**Implementation**:
```python
# src/inkwell/transcription/manager.py lines 66-74

# Extract config values (prefer config object, fall back to individual params)
if config:
    effective_api_key = config.api_key or gemini_api_key
    effective_model = config.model_name or model_name  # FIX: Config first!
    effective_cost_threshold = config.cost_threshold_usd
else:
    effective_api_key = gemini_api_key
    effective_model = model_name or "gemini-2.5-flash"
    effective_cost_threshold = 1.0
```

## Recommended Action

Implement Option 1 immediately. This is a critical bug that blocks PR #20 from being merged safely.

## Technical Details

**Affected Files**:
- `src/inkwell/transcription/manager.py:69` (single line fix)

**Related Components**:
- ExtractionEngine (has correct implementation for reference)
- ADR-031 (documents expected behavior)
- GlobalConfig migration logic

**Testing Requirements**:
- Add test case for config precedence
- Add test case for individual param fallback
- Add test case for both provided (config should win)
- Verify all existing tests still pass

**Regression Prevention**:
Add this test to `tests/unit/test_transcription_manager.py`:
```python
def test_config_overrides_individual_params():
    """Config object should take precedence over individual parameters."""
    config = TranscriptionConfig(
        model_name="gemini-2.5-flash",
        api_key="config-key"
    )

    manager = TranscriptionManager(
        config=config,
        gemini_api_key="deprecated-key",
        model_name="deprecated-model"
    )

    # Config values should win
    assert manager.gemini_transcriber.model_name == "gemini-2.5-flash"
    # NOT "deprecated-model"
```

## Acceptance Criteria

- [ ] Line 69 changed to prioritize config.model_name
- [ ] Test added for config precedence scenario
- [ ] Test added for fallback when config is None
- [ ] Test added for both config and params provided
- [ ] All existing tests pass
- [ ] ExtractionEngine checked for consistency (already correct)

## Work Log

### 2025-11-18 - Code Review Discovery
**By:** Claude Code Review System
**Actions:**
- Discovered during comprehensive code review of PR #20
- Analyzed by kieran-python-reviewer agent
- Categorized as P1 CRITICAL priority (blocks merge)
- Identified inconsistency with ExtractionEngine implementation
- Verified bug via manual code inspection

**Learnings:**
- Parameter precedence must be tested explicitly
- Backward compatibility code needs thorough test coverage
- ADR documentation doesn't guarantee correct implementation
- Complex conditional logic requires edge case testing

## Notes

**Related Issues**:
- PR #20: Complete dependency injection pattern
- Issue #17: Complete Dependency Injection Pattern
- ADR-031: Gradual Dependency Injection Migration

**Why This Matters**:
The entire value of the gradual migration strategy is that users can start using config objects while old code continues to work. If config objects are silently ignored when individual params are present, the migration is broken.

**Comparison with ExtractionEngine**:
ExtractionEngine implements this correctly:
```python
# ExtractionEngine.__init__ lines 76-83 (CORRECT)
if config:
    effective_claude_key = config.claude_api_key or claude_api_key
    effective_gemini_key = config.gemini_api_key or gemini_api_key
    effective_provider = config.default_provider
```

**Source**: Code review performed on 2025-11-18
**Review command**: /compounding-engineering:review PR20
