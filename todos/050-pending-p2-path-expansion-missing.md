---
status: pending
priority: p2
issue_id: "050"
tags: [code-review, data-integrity, filesystem, pr-20]
dependencies: []
---

# Add Path Expansion for Tilde (~) in Configuration Paths

## Problem Statement

The `default_output_dir` field in `GlobalConfig` accepts Path objects but doesn't expand tilde (`~`) notation. This causes the application to create literal directories named `~` instead of expanding to the user's home directory, leading to data being written to unexpected locations.

**Severity**: P2 - HIGH (Data integrity and user experience issue)

## Findings

- Discovered during data integrity review by data-integrity-guardian agent
- Location: `src/inkwell/config/schema.py:85`
- Current code: `default_output_dir: Path = Field(default=Path("~/podcasts"))`
- Path objects don't auto-expand `~` notation
- Creates literal `~/podcasts` directory in current working directory

**Impact Analysis**:
- **Data misplacement**: Files written to wrong location
- **User confusion**: "Where did my podcast notes go?"
- **Potential data loss**: Users might delete `~` thinking it's a typo
- **Inconsistent behavior**: Works on some systems, fails on others

**Example Bug**:
```python
# User config.yaml:
default_output_dir: ~/my-podcasts

# Expected: /Users/sergio/my-podcasts
# Actual: ./~/my-podcasts (literal tilde directory!)

# On macOS/Linux:
$ ls -la
drwxr-xr-x  ~          # Literal directory named "~"
```

**Real-World Scenario**:
```bash
# User runs inkwell
$ inkwell process https://example.com/podcast.mp3

# Output goes to:
./~/podcasts/podcast-2025-11-18/  # WRONG!

# User expects it at:
/Users/sergio/podcasts/podcast-2025-11-18/  # CORRECT
```

## Proposed Solutions

### Option 1: Add Pydantic field_validator (Recommended)

**Pros**:
- Automatic expansion for all paths
- Works for config files and programmatic creation
- Clean Pydantic pattern
- Validation happens once at model creation

**Cons**:
- None

**Effort**: Small (15 minutes)
**Risk**: Low (pure addition, no breaking changes)

**Implementation**:
```python
# src/inkwell/config/schema.py

from pathlib import Path
from pydantic import BaseModel, Field, field_validator

class GlobalConfig(BaseModel):
    """Global Inkwell configuration."""

    version: str = "1"
    default_output_dir: Path = Field(default=Path("~/podcasts"))
    log_level: LogLevel = "INFO"
    # ... other fields

    @field_validator('default_output_dir')
    @classmethod
    def expand_user_path(cls, v: Path) -> Path:
        """Expand ~ to user home directory."""
        return v.expanduser()

    # ... rest of class
```

**How it works**:
```python
# After validation:
config = GlobalConfig()
print(config.default_output_dir)
# Output: PosixPath('/Users/sergio/podcasts')  ✅

# From YAML:
config = GlobalConfig(default_output_dir=Path("~/my-podcasts"))
# Automatically expanded to: /Users/sergio/my-podcasts  ✅
```

### Option 2: Expand at Usage Time

**Pros**:
- Simple alternative

**Cons**:
- Must remember to expand everywhere path is used
- Error-prone (easy to forget)
- Not recommended

**Effort**: Small
**Risk**: Medium (easy to miss usage sites)

## Recommended Action

Implement Option 1 immediately. This prevents data loss and user confusion.

## Technical Details

**Affected Files**:
- `src/inkwell/config/schema.py:85` (add validator)

**Related Components**:
- OutputManager (uses default_output_dir)
- PipelineOrchestrator (passes paths to OutputManager)
- CLI commands (may override default_output_dir)

**Testing Requirements**:
Add to `tests/unit/test_schema.py`:

```python
def test_default_output_dir_expands_tilde():
    """Tilde paths should expand to user home directory."""
    config = GlobalConfig(default_output_dir=Path("~/test-podcasts"))

    # Should expand ~ to actual home directory
    assert not str(config.default_output_dir).startswith("~")
    assert config.default_output_dir.is_absolute()

    # Should contain user's home directory
    from pathlib import Path
    home = Path.home()
    assert str(config.default_output_dir).startswith(str(home))


def test_absolute_path_unchanged():
    """Absolute paths should not be modified."""
    config = GlobalConfig(default_output_dir=Path("/absolute/path"))

    assert config.default_output_dir == Path("/absolute/path")


def test_relative_path_unchanged():
    """Relative paths should not be modified."""
    config = GlobalConfig(default_output_dir=Path("relative/path"))

    # Relative paths stay relative (only ~ expands)
    assert config.default_output_dir == Path("relative/path")
```

**Verification**:
```bash
# Manual test:
python -c "
from inkwell.config.schema import GlobalConfig
from pathlib import Path

config = GlobalConfig(default_output_dir=Path('~/test'))
print(config.default_output_dir)
# Should print: /Users/sergio/test (expanded)
"
```

## Acceptance Criteria

- [ ] `@field_validator` added to GlobalConfig for default_output_dir
- [ ] Validator calls `expanduser()` on Path objects
- [ ] Test added for tilde expansion
- [ ] Test added for absolute paths (unchanged)
- [ ] Test added for relative paths (unchanged)
- [ ] All existing tests pass
- [ ] Manual verification with real config file

## Work Log

### 2025-11-18 - Code Review Discovery
**By:** Claude Code Review System
**Actions:**
- Discovered during data integrity review
- Analyzed by data-integrity-guardian agent
- Categorized as P2 HIGH priority
- Identified potential for data loss and user confusion
- Verified Python Path behavior with tilde

**Learnings:**
- Python's `Path` doesn't auto-expand `~` notation
- Must explicitly call `.expanduser()` method
- This is a common gotcha in Python path handling
- Pydantic validators are perfect for this use case

## Notes

**Python Path Behavior**:
```python
from pathlib import Path

# Tilde is NOT expanded automatically:
p = Path("~/test")
print(p)  # Output: ~/test (literal)

# Must call expanduser():
p = Path("~/test").expanduser()
print(p)  # Output: /Users/sergio/test (expanded)
```

**Why This Matters**:
Users expect `~/podcasts` to work like it does in their shell. Not expanding creates:
1. Literal `~` directories (confusing)
2. Data in wrong locations (data integrity)
3. Hard-to-debug issues (works for some users, not others)

**Platform Compatibility**:
- ✅ macOS/Linux: `~` expands to `/Users/name` or `/home/name`
- ✅ Windows: `~` expands to `C:\Users\name`
- Works correctly on all platforms via `expanduser()`

**Related Pydantic Patterns**:
```python
# Common pattern for path validation:
@field_validator('some_path')
@classmethod
def validate_path(cls, v: Path) -> Path:
    # Expand user home
    v = v.expanduser()
    # Optionally: resolve symlinks, make absolute, etc.
    return v
```

**Source**: Code review performed on 2025-11-18
**Review command**: /compounding-engineering:review PR20
