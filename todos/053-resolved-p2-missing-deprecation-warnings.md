---
status: resolved
priority: p2
issue_id: "053"
tags: [code-review, developer-experience, deprecation, backward-compatibility, pr-20]
dependencies: []
resolved_date: 2025-11-18
---

# Add Deprecation Warnings for Individual Parameters

## Problem Statement

When users pass deprecated individual parameters (instead of config objects), there's no runtime warning to inform them they should migrate to the new pattern. This makes the deprecation silent, slowing migration adoption and making it harder to remove deprecated code in v2.0.

**Severity**: P2 - MEDIUM (Developer experience and migration clarity)

## Findings

- Discovered during comprehensive code review by kieran-python-reviewer agent
- Locations:
  - `src/inkwell/transcription/manager.py:__init__`
  - `src/inkwell/extraction/engine.py:__init__`
- Docstrings mention deprecation, but no runtime warnings
- Users unaware they should migrate
- Silent deprecation = slower adoption

**Current Silent Deprecation**:
```python
# User code (still using old pattern):
manager = TranscriptionManager(
    gemini_api_key="key",
    model_name="gemini-1.5-flash"
)

# Works fine, no warning printed
# User has no idea they should migrate to config objects
```

**What Should Happen**:
```python
# User code:
manager = TranscriptionManager(
    gemini_api_key="key",
    model_name="gemini-1.5-flash"
)

# Output:
# DeprecationWarning: Individual parameters (gemini_api_key, model_name)
# are deprecated. Use TranscriptionConfig instead. Will be removed in v2.0.
#   manager = TranscriptionManager(
```

**Impact Analysis**:
- **Slow migration**: Users don't know they should change
- **Surprise in v2.0**: Breaking changes without warning period
- **Support burden**: Users ask "why did this break in v2.0?"
- **Documentation gap**: Docs say deprecated, code doesn't warn
- **Best practices**: Python deprecation convention is to warn

## Proposed Solutions

### Option 1: Add DeprecationWarning (Recommended)

**Pros**:
- Standard Python deprecation pattern
- Can be filtered/silenced by users if needed
- Shows up in test suites (encourages migration)
- Clear communication about timeline

**Cons**:
- Adds small runtime overhead (negligible)
- Users might ignore warnings

**Effort**: Small (30 minutes for both services)
**Risk**: Low (pure warning, no behavior change)

**Implementation**:

Update `src/inkwell/transcription/manager.py`:

```python
import warnings

def __init__(
    self,
    config: TranscriptionConfig | None = None,
    cache: TranscriptCache | None = None,
    youtube_transcriber: YouTubeTranscriber | None = None,
    audio_downloader: AudioDownloader | None = None,
    gemini_transcriber: GeminiTranscriber | None = None,
    gemini_api_key: str | None = None,
    model_name: str | None = None,
    cost_confirmation_callback: Callable[[CostEstimate], bool] | None = None,
    cost_tracker: "CostTracker | None" = None,
):
    """Initialize transcription manager.

    Args:
        config: Transcription configuration (recommended)
        cache: Transcript cache (default: new instance)
        youtube_transcriber: YouTube transcriber (default: new instance)
        audio_downloader: Audio downloader (default: new instance)
        gemini_transcriber: Gemini transcriber (default: new instance)
        gemini_api_key: **DEPRECATED** - Use config.api_key instead.
            Will be removed in v2.0.
        model_name: **DEPRECATED** - Use config.model_name instead.
            Will be removed in v2.0.
        cost_confirmation_callback: Callback for cost confirmation
        cost_tracker: Cost tracker for recording API usage

    Raises:
        DeprecationWarning: If deprecated parameters are used.
    """
    # Warn if using deprecated individual parameters
    if config is None and (gemini_api_key is not None or model_name is not None):
        warnings.warn(
            "Individual parameters (gemini_api_key, model_name) are deprecated. "
            "Use TranscriptionConfig instead. "
            "These parameters will be removed in v2.0.",
            DeprecationWarning,
            stacklevel=2
        )

    # ... rest of initialization
```

Update `src/inkwell/extraction/engine.py`:

```python
import warnings

def __init__(
    self,
    config: ExtractionConfig | None = None,
    claude_api_key: str | None = None,
    gemini_api_key: str | None = None,
    cache: ExtractionCache | None = None,
    default_provider: str = "gemini",
    cost_tracker: "CostTracker | None" = None,
) -> None:
    """Initialize extraction engine.

    Args:
        config: Extraction configuration (recommended)
        claude_api_key: **DEPRECATED** - Use config.claude_api_key instead.
            Will be removed in v2.0.
        gemini_api_key: **DEPRECATED** - Use config.gemini_api_key instead.
            Will be removed in v2.0.
        cache: Cache instance (defaults to new ExtractionCache)
        default_provider: **DEPRECATED** - Use config.default_provider instead.
            Will be removed in v2.0.
        cost_tracker: Cost tracker for recording API usage

    Raises:
        DeprecationWarning: If deprecated parameters are used.
    """
    # Warn if using deprecated individual parameters
    deprecated_params = []
    if claude_api_key is not None:
        deprecated_params.append("claude_api_key")
    if gemini_api_key is not None:
        deprecated_params.append("gemini_api_key")
    if default_provider != "gemini":  # Non-default value
        deprecated_params.append("default_provider")

    if config is None and deprecated_params:
        warnings.warn(
            f"Individual parameters ({', '.join(deprecated_params)}) are deprecated. "
            f"Use ExtractionConfig instead. "
            f"These parameters will be removed in v2.0.",
            DeprecationWarning,
            stacklevel=2
        )

    # ... rest of initialization
```

**User Experience**:
```python
# User runs their code:
manager = TranscriptionManager(gemini_api_key="key")

# They see:
# DeprecationWarning: Individual parameters (gemini_api_key, model_name)
# are deprecated. Use TranscriptionConfig instead.
# These parameters will be removed in v2.0.

# Migration guide in output suggests:
# Instead of:
#   manager = TranscriptionManager(gemini_api_key="key", model_name="model")
# Use:
#   config = TranscriptionConfig(api_key="key", model_name="model")
#   manager = TranscriptionManager(config=config)
```

### Option 2: Add FutureWarning Instead

**Pros**:
- FutureWarning is shown by default (DeprecationWarning is hidden by default)
- More visible to end users

**Cons**:
- FutureWarning is for deprecated features affecting users, not developers
- DeprecationWarning is the correct category for API deprecation

**Not Recommended** - DeprecationWarning is the correct choice for API deprecation.

### Option 3: Add Logging Instead of Warnings

**Pros**:
- Can be controlled by log level
- Doesn't pollute stderr

**Cons**:
- Not standard Python deprecation practice
- Easier to miss
- Users don't expect deprecations in logs

**Not Recommended**

## Recommended Action

Implement Option 1 (DeprecationWarning). This follows Python best practices and gives users clear migration guidance.

**Timeline**:
- v1.x: Add warnings (this issue)
- v1.6-1.9: Users see warnings, have time to migrate
- v2.0: Remove deprecated parameters

## Technical Details

**Affected Files**:
- `src/inkwell/transcription/manager.py:44-60` (add warning)
- `src/inkwell/extraction/engine.py:52-74` (add warning)

**Related Components**:
- All code using these services (will see warnings)
- Test suites (may need to filter warnings in tests)
- CI/CD (may want to fail on DeprecationWarning)

**Testing Requirements**:

Add to `tests/unit/test_transcription_manager.py`:

```python
import warnings

def test_deprecated_params_trigger_warning():
    """Using deprecated individual params should trigger DeprecationWarning."""
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")

        manager = TranscriptionManager(
            gemini_api_key="test-key",
            model_name="test-model"
        )

        # Should have triggered exactly one warning
        assert len(w) == 1
        assert issubclass(w[0].category, DeprecationWarning)
        assert "deprecated" in str(w[0].message).lower()
        assert "TranscriptionConfig" in str(w[0].message)
        assert "v2.0" in str(w[0].message)


def test_config_object_no_warning():
    """Using config object should NOT trigger warning."""
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")

        config = TranscriptionConfig(api_key="test-key")
        manager = TranscriptionManager(config=config)

        # Should have no warnings
        assert len(w) == 0


def test_both_config_and_params_warns():
    """Using both config and individual params should still warn."""
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")

        config = TranscriptionConfig(api_key="config-key")
        manager = TranscriptionManager(
            config=config,
            gemini_api_key="param-key"  # Unnecessary, should warn
        )

        # Should warn about using deprecated params
        # (even though config is also provided)
        # Actually, reconsidering: if config is provided, maybe don't warn?
        # This is a design decision to make during implementation
```

Add similar tests for `ExtractionEngine`.

**Filter Warnings in Tests** (if needed):
```python
# pytest.ini or pyproject.toml
[tool.pytest.ini_options]
filterwarnings = [
    "ignore::DeprecationWarning:inkwell.*",  # Ignore our own deprecations in tests
]
```

## Acceptance Criteria

- [x] DeprecationWarning added to TranscriptionManager
- [x] DeprecationWarning added to ExtractionEngine
- [x] Warning message includes:
  - [x] What is deprecated
  - [x] What to use instead
  - [x] When it will be removed (v2.0)
- [x] Warning only triggers when deprecated params used (not config)
- [x] Tests added for warning behavior
- [x] Tests added for no-warning with config object
- [x] Existing tests still pass (may need warning filters)

## Work Log

### 2025-11-18 - Code Review Discovery
**By:** Claude Code Review System
**Actions:**
- Discovered during comprehensive code review
- Analyzed by kieran-python-reviewer agent
- Categorized as P2 MEDIUM priority
- Identified gap between docstring deprecation and runtime behavior
- Proposed standard Python warnings approach

**Learnings:**
- Docstring deprecation is not enough
- Runtime warnings help users discover needed changes
- DeprecationWarning is standard Python practice
- `stacklevel=2` shows warning at call site, not in library

### 2025-11-18 - Implementation Complete
**By:** Claude Code (Resolving TODO #053)
**Actions:**
- Added `import warnings` to both manager files
- Updated `TranscriptionManager.__init__` to add DeprecationWarning when individual params used
- Updated `ExtractionEngine.__init__` to add DeprecationWarning when individual params used
- Added 7 tests for TranscriptionManager deprecation warnings
- Added 10 tests for ExtractionEngine deprecation warnings
- All tests pass (62 passed, 8 expected warnings)
- Verified warnings work correctly with demo script

**Implementation Details:**
- TranscriptionManager warns when `config=None` and (`gemini_api_key` or `model_name` provided)
- ExtractionEngine warns when `config=None` and any of (`claude_api_key`, `gemini_api_key`, or non-default `default_provider`)
- Warning message includes: what is deprecated, what to use instead, and removal version (v2.0)
- Uses `stacklevel=2` to show warning at call site, not in library
- No warning when config object is provided (user is using new pattern)

**Test Coverage:**
- Warning triggered when deprecated params used
- No warning when config object used
- No warning when no params provided
- Warning message includes migration info
- Multiple deprecated params listed in warning
- Config with individual params doesn't warn (config takes precedence)

**Files Modified:**
- `/Users/sergiosanchez/projects/gh/inkwell-cli/src/inkwell/transcription/manager.py`
- `/Users/sergiosanchez/projects/gh/inkwell-cli/src/inkwell/extraction/engine.py`
- `/Users/sergiosanchez/projects/gh/inkwell-cli/tests/unit/test_transcription_manager.py`
- `/Users/sergiosanchez/projects/gh/inkwell-cli/tests/unit/test_extraction_engine.py`

## Notes

**Python Deprecation Best Practices**:
```python
warnings.warn(
    "Deprecated message",
    DeprecationWarning,
    stacklevel=2  # Show warning at caller's location
)
```

**Why stacklevel=2?**
- `stacklevel=1`: Warning appears inside the library (confusing)
- `stacklevel=2`: Warning appears at user's call site (clear)

**Warning Categories**:
- `DeprecationWarning`: For deprecated APIs (developers)
- `PendingDeprecationWarning`: For future deprecations
- `FutureWarning`: For deprecated features (end users)
- `UserWarning`: General warnings

**Filtering Warnings**:
```python
# In user code:
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

# Or specific to module:
warnings.filterwarnings("ignore", category=DeprecationWarning, module="inkwell")
```

**CI/CD Integration**:
```bash
# Optionally fail CI if deprecation warnings present
pytest -W error::DeprecationWarning
```

**Migration Path**:
1. v1.x: Add warnings (this issue)
2. v1.5: Update all examples/docs to use new pattern
3. v1.6+: Warnings visible to all users
4. v2.0: Remove deprecated parameters

**Related Standards**:
- PEP 565: Show DeprecationWarning in __main__
- PEP 387: Backwards Compatibility Policy

**Source**: Code review performed on 2025-11-18
**Review command**: /compounding-engineering:review PR20
