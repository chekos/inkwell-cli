---
status: pending
priority: p2
issue_id: "052"
tags: [code-review, data-integrity, migration, backward-compatibility, pr-20]
dependencies: []
---

# Fix Unsafe Migration Logic in GlobalConfig.model_post_init

## Problem Statement

The `model_post_init()` method unconditionally overwrites new nested config values with deprecated top-level fields. This makes it impossible for users to migrate from deprecated fields to the new structure, as their explicit new config values are silently ignored.

**Severity**: P2 - HIGH (Data integrity during migration period)

## Findings

- Discovered during data integrity review by data-integrity-guardian agent
- Location: `src/inkwell/config/schema.py:107-119`
- Migration logic overwrites explicit user choices
- Users cannot test new config while keeping old
- Silent data loss during migration

**Current Unsafe Implementation**:
```python
def model_post_init(self, __context: Any) -> None:
    """Handle deprecated config fields."""
    # UNSAFE: Always overwrites, even if user set new value
    if self.transcription_model is not None:
        self.transcription.model_name = self.transcription_model

    if self.interview_model is not None:
        self.interview.model = self.interview_model

    if self.youtube_check is not None:
        self.transcription.youtube_check = self.youtube_check
```

**Problem Scenario**:
```yaml
# User tries to migrate from old to new config
# config.yaml

# Old deprecated field (forgot to remove)
transcription_model: "gemini-1.5-flash"

# New nested structure (what user wants to use)
transcription:
  model_name: "gemini-2.5-flash"  # Explicitly set by user
  api_key: ${GEMINI_API_KEY}
  cost_threshold_usd: 2.0
```

**What Happens**:
```python
config = load_config("config.yaml")

# Expected: Uses "gemini-2.5-flash" from nested structure
# Actual: Uses "gemini-1.5-flash" from deprecated field!

print(config.transcription.model_name)
# Output: "gemini-1.5-flash"  ❌ WRONG!
# User's explicit choice was silently ignored
```

**Impact Analysis**:
- **Migration blocker**: Users cannot gradually migrate configs
- **Silent data loss**: Explicit values ignored without warning
- **Confusion**: "I set it to X, why is it Y?"
- **One-way migration**: Can't test new config while keeping old as fallback
- **Documentation mismatch**: Docs say new config works, but it doesn't if old exists

## Proposed Solutions

### Option 1: Only Migrate if New Field is Default (Recommended)

**Pros**:
- Safe migration path
- Respects user's explicit choices
- Allows gradual migration
- Clear precedence: explicit new > deprecated > defaults

**Cons**:
- Slightly more complex logic
- Need to know default values

**Effort**: Small (30 minutes)
**Risk**: Low (safer than current)

**Implementation**:
```python
from typing import Any

def model_post_init(self, __context: Any) -> None:
    """Handle deprecated config fields.

    Migration strategy: Only apply deprecated fields if the new nested
    field is still at its default value. This allows users to explicitly
    set new config values without being overridden.
    """
    # Migrate transcription_model only if user didn't set transcription.model_name
    if self.transcription_model is not None:
        # Check if transcription.model_name is still at default
        default_transcription = TranscriptionConfig()
        if self.transcription.model_name == default_transcription.model_name:
            self.transcription.model_name = self.transcription_model
        # else: User explicitly set new field, respect their choice

    # Migrate interview_model only if user didn't set interview.model
    if self.interview_model is not None:
        default_interview = InterviewConfig()
        if self.interview.model == default_interview.model:
            self.interview.model = self.interview_model

    # Migrate youtube_check only if user didn't set transcription.youtube_check
    if self.youtube_check is not None:
        default_transcription = TranscriptionConfig()
        if self.transcription.youtube_check == default_transcription.youtube_check:
            self.transcription.youtube_check = self.youtube_check
```

**Behavior After Fix**:
```python
# Scenario 1: Old field only (backward compat)
config = GlobalConfig(transcription_model="gemini-1.5-flash")
assert config.transcription.model_name == "gemini-1.5-flash"  # Migrated ✓

# Scenario 2: New field only (forward compat)
config = GlobalConfig(
    transcription=TranscriptionConfig(model_name="gemini-2.5-flash")
)
assert config.transcription.model_name == "gemini-2.5-flash"  # Preserved ✓

# Scenario 3: Both fields (user explicitly chose new)
config = GlobalConfig(
    transcription_model="gemini-1.5-flash",  # Deprecated
    transcription=TranscriptionConfig(model_name="gemini-2.5-flash")  # Explicit
)
assert config.transcription.model_name == "gemini-2.5-flash"  # Respects explicit ✓

# Scenario 4: Both fields, new is default (use deprecated)
config = GlobalConfig(
    transcription_model="gemini-1.5-flash",  # Deprecated
    transcription=TranscriptionConfig()  # Default, not explicit
)
assert config.transcription.model_name == "gemini-1.5-flash"  # Migrates ✓
```

### Option 2: Add Explicit Migration Warning

**Pros**:
- Alerts users to conflicting config
- Helps debug migration issues

**Cons**:
- Doesn't solve the data loss problem
- Just makes it visible

**Effort**: Small
**Risk**: Low

**Implementation**:
```python
import warnings

def model_post_init(self, __context: Any) -> None:
    if self.transcription_model is not None:
        if self.transcription.model_name != TranscriptionConfig().model_name:
            warnings.warn(
                f"Both 'transcription_model' (deprecated) and "
                f"'transcription.model_name' are set. "
                f"Using deprecated value '{self.transcription_model}'. "
                f"Remove 'transcription_model' from config to use new structure.",
                DeprecationWarning,
                stacklevel=2
            )
        self.transcription.model_name = self.transcription_model
```

### Option 3: Remove Migration Logic Entirely

**Pros**:
- Simplest solution
- Forces clean migration

**Cons**:
- Breaking change for existing configs
- Violates backward compatibility promise

**Not Recommended**

## Recommended Action

Implement Option 1 (safe migration with default checking). Optionally combine with Option 2 (add warnings) for even better UX.

**Timeline**: Should be fixed before v2.0 when deprecated fields are removed.

## Technical Details

**Affected Files**:
- `src/inkwell/config/schema.py:107-119` (update migration logic)

**Related Components**:
- YAML config loader (loads both old and new fields)
- Config validation (ensures values are valid)
- ADR-031 (documents migration strategy)

**Testing Requirements**:

Update `tests/unit/test_schema.py`:

```python
def test_migration_respects_explicit_new_config():
    """When user explicitly sets new config, don't override with deprecated."""
    config = GlobalConfig(
        transcription_model="old-model",  # Deprecated
        transcription=TranscriptionConfig(model_name="new-model")  # Explicit
    )

    # User's explicit choice should win
    assert config.transcription.model_name == "new-model"
    # NOT "old-model"


def test_migration_applies_when_new_is_default():
    """When new config is default, apply deprecated value."""
    config = GlobalConfig(
        transcription_model="old-model",
        transcription=TranscriptionConfig()  # Using defaults
    )

    # Should migrate since new field is default
    assert config.transcription.model_name == "old-model"


def test_migration_deprecated_only():
    """Using only deprecated field works (backward compat)."""
    config = GlobalConfig(transcription_model="old-model")

    assert config.transcription.model_name == "old-model"


def test_migration_new_only():
    """Using only new field works (forward compat)."""
    config = GlobalConfig(
        transcription=TranscriptionConfig(model_name="new-model")
    )

    assert config.transcription.model_name == "new-model"
    assert config.transcription_model is None


def test_migration_youtube_check_respects_explicit():
    """youtube_check migration also respects explicit new values."""
    config = GlobalConfig(
        youtube_check=False,  # Deprecated
        transcription=TranscriptionConfig(youtube_check=True)  # Explicit
    )

    # Explicit new value should win
    assert config.transcription.youtube_check is True
```

## Acceptance Criteria

- [ ] Migration logic checks if new field is at default before overwriting
- [ ] Test added for explicit new config (should be preserved)
- [ ] Test added for default new config (should be migrated)
- [ ] Test added for deprecated-only config (backward compat)
- [ ] Test added for new-only config (forward compat)
- [ ] All three deprecated fields use same logic
- [ ] Optional: Warning added when conflict detected
- [ ] All existing tests still pass

## Work Log

### 2025-11-18 - Code Review Discovery
**By:** Claude Code Review System
**Actions:**
- Discovered during data integrity review
- Analyzed by data-integrity-guardian agent
- Categorized as P2 HIGH priority
- Identified silent data loss during migration
- Proposed safe migration strategy

**Learnings:**
- Migration logic needs to respect explicit user choices
- Pydantic's model_post_init runs after validation
- Can't distinguish between explicit and default without checking
- Safe migrations require checking if field was explicitly set

## Notes

**Why This Matters**:
During migration periods, users need to:
1. Test new config structure
2. Keep old config as fallback
3. Gradually transition

Current logic prevents all three scenarios.

**Migration Timeline**:
- **v1.x**: Support both patterns (current)
- **v1.6+**: Add deprecation warnings
- **v2.0**: Remove deprecated fields

This fix enables safe migration in v1.x period.

**Pydantic Patterns**:
```python
# Can't detect if user explicitly set a field after __init__
# Must compare against default to infer intent

# Alternative: Use Pydantic's Field(default=..., default_factory=...)
# and check if value != default, but this approach is simpler
```

**Real-World Example**:
```yaml
# User's actual migration path:

# Week 1: Add new config, keep old as safety net
transcription_model: "gemini-1.5-flash"  # Keep working version
transcription:
  model_name: "gemini-2.5-flash"  # Test new version

# Week 2: Remove old after verifying new works
transcription:
  model_name: "gemini-2.5-flash"  # Now primary
```

Current code breaks Week 1 (can't test new config).

**Related Issues**:
- ADR-031 documents gradual migration strategy
- This fix enables that strategy to actually work

**Source**: Code review performed on 2025-11-18
**Review command**: /compounding-engineering:review PR20
