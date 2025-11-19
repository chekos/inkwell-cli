---
status: completed
priority: p2
issue_id: "051"
tags: [code-review, code-quality, consistency, refactoring, pr-20]
dependencies: ["046"]
completed_date: "2025-11-18"
---

# Standardize Parameter Precedence Logic Across Services

## Problem Statement

`TranscriptionManager` and `ExtractionEngine` implement parameter precedence using different patterns. Even after fixing bug #046, the logic isn't consistent between the two services, making the codebase harder to understand, maintain, and extend to future services.

**Severity**: P2 - HIGH (Code consistency and maintainability)

## Findings

- Discovered during pattern recognition analysis by pattern-recognition-specialist agent
- Locations:
  - `src/inkwell/transcription/manager.py:66-74`
  - `src/inkwell/extraction/engine.py:75-83`
- Both implement same concept (config > params > defaults) differently
- Code duplication with subtle variations
- Future services will copy one pattern or the other inconsistently

**Current Inconsistency**:

```python
# TranscriptionManager (after fixing #046):
if config:
    effective_api_key = config.api_key or gemini_api_key
    effective_model = config.model_name or model_name
    effective_cost_threshold = config.cost_threshold_usd
else:
    effective_api_key = gemini_api_key
    effective_model = model_name or "gemini-2.5-flash"
    effective_cost_threshold = 1.0

# ExtractionEngine (different pattern):
if config:
    effective_claude_key = config.claude_api_key or claude_api_key
    effective_gemini_key = config.gemini_api_key or gemini_api_key
    effective_provider = config.default_provider  # No fallback logic
else:
    effective_claude_key = claude_api_key
    effective_gemini_key = gemini_api_key
    effective_provider = default_provider
```

**Pattern Differences**:
1. TranscriptionManager has `or` fallback in else branch (`model_name or "gemini-2.5-flash"`)
2. ExtractionEngine doesn't have this pattern (relies on Pydantic defaults)
3. Both duplicate same `if config:` structure
4. Neither handles `None` values consistently

**Impact Analysis**:
- **Maintenance burden**: Two patterns to understand and maintain
- **Bug risk**: Easy to copy wrong pattern to new services
- **Code review confusion**: "Which pattern should I use?"
- **Refactoring difficulty**: Can't extract common logic without unification

## Proposed Solutions

### Option 1: Extract Common Helper Method (Recommended)

**Pros**:
- DRY principle - single source of truth
- Explicit precedence rules
- Easy to test independently
- Reusable for future services

**Cons**:
- Adds one helper method (minimal overhead)

**Effort**: Medium (1 hour)
**Risk**: Low (pure refactor, no behavior change)

**Implementation**:

Create new file: `src/inkwell/config/precedence.py`

```python
"""Configuration parameter precedence resolution."""

from typing import TypeVar

T = TypeVar("T")


def resolve_config_value(
    config_value: T | None,
    param_value: T | None,
    default_value: T,
) -> T:
    """Resolve configuration value with precedence rules.

    Precedence (highest to lowest):
    1. Config object value (if not None)
    2. Individual parameter value (if not None)
    3. Default value

    Args:
        config_value: Value from config object (may be None)
        param_value: Value from individual parameter (may be None)
        default_value: Default fallback value

    Returns:
        Resolved value following precedence rules

    Example:
        >>> resolve_config_value(
        ...     config_value="from-config",
        ...     param_value="from-param",
        ...     default_value="default"
        ... )
        'from-config'  # Config wins

        >>> resolve_config_value(
        ...     config_value=None,
        ...     param_value="from-param",
        ...     default_value="default"
        ... )
        'from-param'  # Param wins when config is None
    """
    if config_value is not None:
        return config_value
    if param_value is not None:
        return param_value
    return default_value
```

Update `src/inkwell/transcription/manager.py`:

```python
from inkwell.config.precedence import resolve_config_value

def __init__(
    self,
    config: TranscriptionConfig | None = None,
    # ... other params
    gemini_api_key: str | None = None,
    model_name: str | None = None,
    # ...
):
    # Extract config values with standardized precedence
    effective_api_key = resolve_config_value(
        config.api_key if config else None,
        gemini_api_key,
        None  # Will fall back to environment in GeminiTranscriber
    )
    effective_model = resolve_config_value(
        config.model_name if config else None,
        model_name,
        "gemini-2.5-flash"
    )
    effective_cost_threshold = resolve_config_value(
        config.cost_threshold_usd if config else None,
        None,  # No individual param for this
        1.0
    )

    # ... rest of initialization
```

Update `src/inkwell/extraction/engine.py`:

```python
from inkwell.config.precedence import resolve_config_value

def __init__(
    self,
    config: ExtractionConfig | None = None,
    claude_api_key: str | None = None,
    gemini_api_key: str | None = None,
    # ...
):
    # Standardized precedence resolution
    effective_claude_key = resolve_config_value(
        config.claude_api_key if config else None,
        claude_api_key,
        None
    )
    effective_gemini_key = resolve_config_value(
        config.gemini_api_key if config else None,
        gemini_api_key,
        None
    )
    effective_provider = resolve_config_value(
        config.default_provider if config else None,
        default_provider,
        "gemini"
    )

    # ... rest of initialization
```

**Benefits**:
- Same pattern everywhere
- Easy to understand precedence rules
- Testable in isolation
- Self-documenting via function name

### Option 2: Keep Current Patterns, Document Clearly

**Pros**:
- No code changes needed
- Preserves existing behavior exactly

**Cons**:
- Doesn't solve the maintenance problem
- Future services will still be inconsistent

**Effort**: Small (just documentation)
**Risk**: None (no changes)

## Recommended Action

Implement Option 1. While both patterns work, having a single standardized approach:
- Reduces cognitive load for developers
- Prevents copy-paste inconsistencies
- Makes precedence rules explicit and testable
- Improves long-term maintainability

**Timeline**: Can be done post-merge as a refactoring task, not a blocker.

## Technical Details

**Affected Files**:
- `src/inkwell/config/precedence.py` (NEW - helper module)
- `src/inkwell/transcription/manager.py:66-74` (refactor to use helper)
- `src/inkwell/extraction/engine.py:75-83` (refactor to use helper)

**Related Components**:
- Any future services using DI pattern
- Tests for both services (update to verify same behavior)

**Testing Requirements**:

Create `tests/unit/test_config_precedence.py`:

```python
"""Tests for configuration precedence resolution."""

import pytest
from inkwell.config.precedence import resolve_config_value


def test_config_value_takes_precedence():
    """Config value should win over param and default."""
    result = resolve_config_value(
        config_value="config",
        param_value="param",
        default_value="default"
    )
    assert result == "config"


def test_param_value_when_config_none():
    """Param value should win when config is None."""
    result = resolve_config_value(
        config_value=None,
        param_value="param",
        default_value="default"
    )
    assert result == "param"


def test_default_when_both_none():
    """Default should be used when both config and param are None."""
    result = resolve_config_value(
        config_value=None,
        param_value=None,
        default_value="default"
    )
    assert result == "default"


def test_zero_is_valid_value():
    """Zero should not be treated as None."""
    result = resolve_config_value(
        config_value=0,
        param_value=5,
        default_value=10
    )
    assert result == 0  # Not 5 or 10


def test_empty_string_is_valid():
    """Empty string should not be treated as None."""
    result = resolve_config_value(
        config_value="",
        param_value="param",
        default_value="default"
    )
    assert result == ""  # Not "param" or "default"


def test_false_is_valid_value():
    """False should not be treated as None."""
    result = resolve_config_value(
        config_value=False,
        param_value=True,
        default_value=True
    )
    assert result is False  # Not True
```

Update existing service tests to verify same behavior after refactor.

## Acceptance Criteria

- [x] `src/inkwell/config/precedence.py` created with `resolve_config_value()`
- [x] TranscriptionManager refactored to use helper
- [x] ExtractionEngine refactored to use helper
- [x] Tests added for precedence helper (18 tests, exceeds 6+ requirement)
- [x] All existing service tests still pass (54/54 tests pass)
- [x] Code review confirms consistent pattern usage

## Work Log

### 2025-11-18 - Code Review Discovery
**By:** Claude Code Review System
**Actions:**
- Discovered during pattern recognition analysis
- Analyzed by pattern-recognition-specialist agent
- Categorized as P2 HIGH priority (maintainability)
- Identified code duplication with variations
- Proposed DRY refactoring solution

**Learnings:**
- Backward compatibility code tends to duplicate across services
- Small pattern differences compound over time
- Explicit helper functions make precedence rules testable
- Consistency is as important as correctness

### 2025-11-18 - Implementation Complete
**By:** Claude Code Assistant
**Actions:**
- Created `src/inkwell/config/precedence.py` with `resolve_config_value()` helper
- Refactored `TranscriptionManager` to use standardized helper (lines 67-82)
- Refactored `ExtractionEngine` to use standardized helper (lines 76-91)
- Created comprehensive test suite in `tests/unit/test_config_precedence.py`
- 18 tests covering all edge cases (zero, False, empty string, etc.)
- All 54 related tests pass (precedence + config injection + extraction tests)
- Zero regressions in existing functionality

**Implementation Summary:**
- New helper function uses explicit `is not None` checks for correctness
- Supports all Python types including falsy values (0, False, "", [], {})
- Both services now use identical precedence pattern
- Future services can import and use the same helper
- Code is DRY, testable, and maintainable

**Test Coverage:**
- Basic precedence: config > param > default
- Falsy value handling: 0, False, empty string/list/dict all valid
- Type preservation: str, int, float, bool, list, dict, custom objects
- Edge cases: None as default, complex types, type consistency

**Files Changed:**
- `src/inkwell/config/precedence.py` (NEW - 75 lines)
- `src/inkwell/transcription/manager.py` (refactored lines 9, 67-82)
- `src/inkwell/extraction/engine.py` (refactored lines 12, 76-91)
- `tests/unit/test_config_precedence.py` (NEW - 163 lines, 18 tests)

**Verification:**
- All precedence tests pass (18/18)
- All config injection tests pass (TranscriptionManager)
- All extraction engine tests pass
- No regressions in existing functionality
- Code follows project style and conventions

## Notes

**Why Not P1?**
This is P2 (not P1) because:
- Doesn't block functionality (both patterns work)
- Can be done post-merge as refactoring
- No user-facing impact
- Primarily a maintainability improvement

**When to Do This**:
Ideal timing:
1. After PR #20 merges
2. Before adding third service with DI pattern
3. During next refactoring sprint

**Future Services**:
Any new service that needs config DI can use:
```python
from inkwell.config.precedence import resolve_config_value

effective_value = resolve_config_value(
    config.field if config else None,
    deprecated_param,
    sensible_default
)
```

**Alternative Approach**:
Could also use a base class:
```python
class ConfigurableService:
    def _resolve(self, config_val, param_val, default):
        # ... precedence logic
```

But function is simpler and more Pythonic.

**Related Patterns**:
This is a common pattern in other projects:
- Django's settings resolution
- Flask's config hierarchy
- Click's parameter precedence

**Source**: Code review performed on 2025-11-18
**Review command**: /compounding-engineering:review PR20
