# PR #20 Action Items - Critical Fixes Required

**Date:** 2025-01-18
**Priority:** HIGH
**Status:** BLOCKING MERGE

---

## Critical Issue: Inconsistent Parameter Precedence

### Problem

`TranscriptionManager` and `ExtractionEngine` have **different precedence rules** for config vs parameter values:

```python
# ExtractionEngine: Config preferred ✅
effective_gemini_key = config.gemini_api_key or gemini_api_key

# TranscriptionManager: Param preferred ❌
effective_model = model_name or config.model_name  # BACKWARDS!
```

### Impact

Users passing both config object and individual parameters get **unpredictable behavior**:

```python
config = TranscriptionConfig(model_name="gemini-2.5-flash")
manager = TranscriptionManager(
    config=config,
    model_name="gemini-1.5-flash"  # This wins! (unexpected)
)
# Uses "gemini-1.5-flash" instead of config's "gemini-2.5-flash"
```

### Fix Required

**File:** `/Users/sergiosanchez/projects/gh/inkwell-cli/src/inkwell/transcription/manager.py`
**Line:** 69

**Change FROM:**
```python
effective_model = model_name or config.model_name
```

**Change TO:**
```python
effective_model = config.model_name or model_name
```

### Test Required

Add test to verify config wins over param:

```python
def test_config_precedence_over_params():
    """Verify config values take precedence over individual params."""
    config = TranscriptionConfig(model_name="gemini-2.5-flash")
    manager = TranscriptionManager(
        config=config,
        model_name="gemini-1.5-flash",  # Should be ignored
        gemini_api_key="key-from-param"  # Should be ignored
    )
    # Config should win
    assert manager.gemini_transcriber.model_name == "gemini-2.5-flash"
```

---

## Secondary Issue: Missing Parameter Fallbacks

### Problem

Some config values have **no fallback** to individual parameters:

```python
# ExtractionEngine
effective_provider = config.default_provider  # No "or default_provider"

# TranscriptionManager
effective_cost_threshold = config.cost_threshold_usd  # No "or cost_threshold"
```

This means if user passes config, their explicit parameters are **silently ignored**.

### Fix Options

**Option 1: Add Fallbacks (Recommended)**

```python
# ExtractionEngine - line 79
effective_provider = (
    config.default_provider if config else None
) or default_provider or "gemini"

# TranscriptionManager - line 70
effective_cost_threshold = (
    config.cost_threshold_usd if config else None
) or cost_threshold or 1.0
```

**Option 2: Remove Params (Simpler, Breaking)**

If these should be config-only:
1. Remove `default_provider` and `cost_threshold` from `__init__`
2. Update docstring to clarify config-only
3. Add deprecation warning if params provided

**Recommendation:** Use Option 1 for backward compatibility.

---

## Documentation Updates

### 1. Add Precedence Policy to Docstrings

**Files:**
- `/Users/sergiosanchez/projects/gh/inkwell-cli/src/inkwell/extraction/engine.py`
- `/Users/sergiosanchez/projects/gh/inkwell-cli/src/inkwell/transcription/manager.py`

**Add to both `__init__` docstrings:**

```python
"""Initialize extraction engine.

Parameter Precedence:
    When both config and individual parameters are provided, config values
    take precedence. Individual parameters serve as fallback if config
    values are None.

    Example:
        config = ExtractionConfig(default_provider="claude")
        engine = ExtractionEngine(
            config=config,
            default_provider="gemini"  # Ignored, config wins
        )
        # Uses "claude" from config

    For backward compatibility, either approach works:
        # New approach (recommended):
        engine = ExtractionEngine(config=config)

        # Old approach (deprecated, but supported):
        engine = ExtractionEngine(claude_api_key="...", gemini_api_key="...")

Args:
    config: Extraction configuration (recommended, new approach)
    ...
"""
```

### 2. Update ADR-031

Add clarification about precedence policy:

```markdown
## Parameter Precedence Policy

When both config object and individual parameters are provided:

1. **Config values take precedence** if not None
2. **Individual parameters are fallback** if config value is None
3. **Hard-coded defaults** are used if both are None

This ensures config objects are "source of truth" while maintaining
backward compatibility with individual parameters.

Example:
    config.api_key or param_api_key or env_var or default
```

---

## Integration Tests

### Missing Test Coverage

Currently no integration tests verify config DI works end-to-end.

**Create:** `/Users/sergiosanchez/projects/gh/inkwell-cli/tests/integration/test_config_injection.py`

```python
"""Integration tests for configuration dependency injection."""

import pytest
from inkwell.config.schema import TranscriptionConfig, ExtractionConfig
from inkwell.transcription import TranscriptionManager
from inkwell.extraction import ExtractionEngine


class TestTranscriptionManagerConfigDI:
    """Test TranscriptionManager with config object."""

    def test_config_only(self):
        """Service works with config object only."""
        config = TranscriptionConfig(
            model_name="gemini-2.5-flash",
            cost_threshold_usd=0.5,
            youtube_check=True
        )
        manager = TranscriptionManager(config=config)
        # Verify values from config used
        assert manager.gemini_transcriber is not None

    def test_legacy_params_only(self):
        """Service works with legacy params only (backward compat)."""
        manager = TranscriptionManager(
            gemini_api_key="test-key",
            model_name="gemini-2.5-flash"
        )
        # Should still work
        assert manager.gemini_transcriber is not None

    def test_config_precedence(self):
        """Config takes precedence over individual params."""
        config = TranscriptionConfig(
            model_name="gemini-2.5-flash",
            api_key="config-key"
        )
        manager = TranscriptionManager(
            config=config,
            model_name="gemini-1.5-flash",  # Should be ignored
            gemini_api_key="param-key"      # Should be ignored
        )
        # Config values should win
        # Note: Implementation needed to expose these for testing
        # or use integration test that runs transcription

    def test_config_with_param_fallback(self):
        """Params used as fallback when config values are None."""
        config = TranscriptionConfig(
            api_key=None,  # Explicitly None
            model_name="gemini-2.5-flash"
        )
        manager = TranscriptionManager(
            config=config,
            gemini_api_key="fallback-key"  # Should be used
        )
        # Should use param as fallback when config.api_key is None


class TestExtractionEngineConfigDI:
    """Test ExtractionEngine with config object."""

    def test_config_only(self, monkeypatch):
        """Service works with config object only."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        monkeypatch.setenv("GOOGLE_API_KEY", "test-key")

        config = ExtractionConfig(
            default_provider="gemini",
            claude_api_key="config-claude-key",
            gemini_api_key="config-gemini-key"
        )
        engine = ExtractionEngine(config=config)
        assert engine.default_provider == "gemini"

    def test_config_precedence(self, monkeypatch):
        """Config takes precedence over individual params."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        monkeypatch.setenv("GOOGLE_API_KEY", "test-key")

        config = ExtractionConfig(
            default_provider="claude",
            claude_api_key="config-key"
        )
        engine = ExtractionEngine(
            config=config,
            default_provider="gemini",    # Should be ignored
            claude_api_key="param-key"    # Should be ignored
        )
        # Config should win
        assert engine.default_provider == "claude"
```

---

## Summary of Required Changes

### Files to Modify

1. **`src/inkwell/transcription/manager.py`**
   - Line 69: Fix `effective_model` precedence
   - Line 70: Add fallback for `effective_cost_threshold`
   - Docstring: Add precedence policy

2. **`src/inkwell/extraction/engine.py`**
   - Line 79: Add fallback for `effective_provider`
   - Docstring: Add precedence policy

3. **`docs/adr/031-gradual-dependency-injection-migration.md`**
   - Add precedence policy section

4. **`tests/integration/test_config_injection.py`** (new file)
   - Add integration tests for config DI

5. **`tests/unit/test_schema.py`**
   - Add test for precedence rules

### Verification Steps

```bash
# 1. Run unit tests
uv run pytest tests/unit/test_schema.py -v

# 2. Run new integration tests
uv run pytest tests/integration/test_config_injection.py -v

# 3. Verify all tests still pass
uv run pytest tests/unit/test_extraction_engine.py tests/unit/transcription/test_manager.py -v

# 4. Run full test suite
uv run pytest --lf  # Run only previously failed tests
uv run pytest        # Run all tests
```

---

## Timeline

**Priority:** CRITICAL - Blocking merge
**Estimated Time:** 2-3 hours

1. **Fix precedence logic** (30 min)
2. **Update docstrings** (30 min)
3. **Add integration tests** (60 min)
4. **Update ADR** (15 min)
5. **Run test suite and verify** (15 min)

---

## Approval Checklist

Before merging PR #20:

- [ ] `effective_model` precedence fixed (config first)
- [ ] `effective_provider` has fallback to param
- [ ] `effective_cost_threshold` has fallback to param
- [ ] Precedence policy documented in both docstrings
- [ ] Integration tests added and passing
- [ ] All existing tests still pass (870/886 minimum)
- [ ] ADR-031 updated with precedence policy
- [ ] Code review by second developer

---

## Additional Notes

This PR demonstrates **excellent architectural thinking** with the gradual migration strategy. The precedence inconsistency is a **tactical error** that's easily fixed, not a fundamental design flaw.

The pattern established here (config object DI with backward compatibility) should be:
1. **Fixed** per above
2. **Documented** as standard pattern
3. **Reused** for future service classes

Once fixed, this becomes a **reference implementation** for DI in the codebase.
