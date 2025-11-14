---
status: pending
priority: p2
issue_id: "026"
tags: [code-review, architecture, error-handling, consistency]
dependencies: []
---

# Unify Error Hierarchy - Make ExtractionError Inherit from InkwellError

## Problem Statement

The error hierarchy is broken: `ExtractionError` in `extraction/errors.py` doesn't inherit from `InkwellError` in `utils/errors.py`, creating two separate exception trees. This prevents uniform error handling at the CLI level and violates exception design principles.

**Severity**: IMPORTANT (Architecture violation, inconsistent behavior)

## Findings

- Discovered during comprehensive architecture review by architecture-strategist agent
- Locations:
  - `src/inkwell/utils/errors.py` - Base hierarchy (InkwellError)
  - `src/inkwell/extraction/errors.py` - Separate hierarchy (ExtractionError)
- Pattern: Two independent exception hierarchies instead of unified tree
- Impact: CLI cannot catch all application errors with single `except InkwellError`

**Current broken hierarchy:**
```python
# utils/errors.py
class InkwellError(Exception):  # Base exception
    pass

class ConfigError(InkwellError):
    pass

class NetworkError(InkwellError):
    pass

# extraction/errors.py (SEPARATE TREE!)
class ExtractionError(Exception):  # ❌ Doesn't inherit from InkwellError!
    pass

class ProviderError(ExtractionError):
    pass

class ValidationError(ExtractionError):  # ❌ Name collision risk with Pydantic
    pass
```

**Problem in practice:**
```python
# cli.py - Cannot catch all errors uniformly
try:
    await engine.extract(...)
except InkwellError as e:  # ❌ Won't catch ExtractionError!
    console.print(f"Error: {e}")
except ExtractionError as e:  # Need separate handler
    console.print(f"Extraction error: {e}")
```

**Impact:**
- Error handling is inconsistent across codebase
- Cannot use single base exception handler
- Confusion about which exception hierarchy to use
- Duplicate error types (e.g., ValidationError)
- Breaks Liskov Substitution Principle

## Proposed Solutions

### Option 1: Consolidate All Errors in utils/errors.py (Recommended)

Move all error classes to single module with unified hierarchy:

```python
# src/inkwell/utils/errors.py (UNIFIED HIERARCHY)

class InkwellError(Exception):
    """Base exception for all Inkwell errors."""

    def __init__(self, message: str, context: dict | None = None):
        super().__init__(message)
        self.message = message
        self.context = context or {}

# Configuration errors
class ConfigError(InkwellError):
    """Configuration-related errors."""
    pass

class InvalidConfigError(ConfigError):
    pass

# Feed errors
class FeedError(InkwellError):
    """Feed-related errors."""
    pass

class FeedNotFoundError(FeedError):
    pass

# Network errors
class NetworkError(InkwellError):
    """Network and API errors."""
    pass

class ConnectionError(NetworkError):
    pass

class RateLimitError(NetworkError):
    pass

# Transcription errors
class TranscriptionError(InkwellError):  # ✅ Inherits from base
    """Transcription failures."""
    pass

class YouTubeTranscriptionError(TranscriptionError):
    pass

class GeminiTranscriptionError(TranscriptionError):
    pass

# Extraction errors (NOW UNIFIED!)
class ExtractionError(InkwellError):  # ✅ Now inherits from InkwellError
    """LLM extraction failures."""
    pass

class ProviderError(ExtractionError):
    pass

class SchemaValidationError(ExtractionError):  # ✅ Renamed to avoid Pydantic collision
    """Invalid extraction schema."""
    pass

class TemplateError(ExtractionError):
    pass

# Interview errors
class InterviewError(InkwellError):
    """Interactive interview failures."""
    pass

class SessionError(InterviewError):
    pass

class AgentError(InterviewError):
    pass

# Output errors
class OutputError(InkwellError):
    """File output failures."""
    pass

class PathTraversalError(OutputError):
    pass
```

**Update all imports:**
```python
# OLD (in extraction/engine.py, extractors/*.py)
from inkwell.extraction.errors import ExtractionError, ProviderError

# NEW
from inkwell.utils.errors import ExtractionError, ProviderError
```

**Delete obsolete file:**
```bash
rm src/inkwell/extraction/errors.py
```

**Pros**:
- Single source of truth for all exceptions
- Unified hierarchy enables consistent error handling
- Easy to find all error types in one place
- No name collisions
- Clear parent-child relationships

**Cons**:
- Breaking change (import paths change)
- Need to update all exception imports
- Large utils/errors.py file (~150 LOC)

**Effort**: Small (2 hours)
**Risk**: Low (mostly find-replace)

---

### Option 2: Keep Separate Files, Fix Inheritance

Keep domain-specific error files but fix inheritance:

```python
# utils/errors.py (keep base errors)
class InkwellError(Exception):
    pass

class ConfigError(InkwellError):
    pass

# extraction/errors.py (FIX INHERITANCE)
from inkwell.utils.errors import InkwellError  # ✅ Import base

class ExtractionError(InkwellError):  # ✅ Now inherits from base
    pass

class ProviderError(ExtractionError):
    pass
```

**Pros**:
- Preserves file organization
- Smaller change (only fix inheritance)
- Import paths stay the same

**Cons**:
- Still have scattered error definitions
- Harder to see full hierarchy
- Potential circular import issues

**Effort**: Trivial (30 minutes)
**Risk**: Low

---

### Option 3: Reduce to Minimal Error Set

Simplify to 5 core error types (per simplification review):

```python
# utils/errors.py (MINIMAL SET)
class InkwellError(Exception):
    """Base exception with rich context."""

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}

class ConfigError(InkwellError):
    """Configuration issues."""
    pass

class APIError(InkwellError):
    """External API failures (LLMs, YouTube, etc.)."""
    pass

class ValidationError(InkwellError):
    """Input validation failures."""
    pass

class NotFoundError(InkwellError):
    """Resource not found."""
    pass
```

**Pros**:
- Simplest approach (5 classes vs 35)
- Easier to maintain
- Sufficient for CLI error reporting
- Follows YAGNI principle

**Cons**:
- Loss of granularity
- Harder to distinguish error types programmatically
- May need to inspect error message instead

**Effort**: Medium (4 hours - update all raises)
**Risk**: Medium (significant change)

## Recommended Action

**Implement Option 1: Consolidate all errors in utils/errors.py**

Rationale:
1. Fixes broken hierarchy (primary goal)
2. Creates single source of truth
3. Enables consistent error handling
4. Maintains granularity (unlike Option 3)
5. Clean architecture (unlike Option 2)
6. Low risk (mostly import path updates)

Option 3 can be considered later as separate simplification effort.

## Technical Details

**Affected Files:**
- `src/inkwell/utils/errors.py` - Add extraction, interview, output errors
- `src/inkwell/extraction/errors.py` - DELETE this file
- `src/inkwell/extraction/engine.py` - Update imports
- `src/inkwell/extraction/extractors/base.py` - Update imports
- `src/inkwell/extraction/extractors/claude.py` - Update imports
- `src/inkwell/extraction/extractors/gemini.py` - Update imports
- `src/inkwell/cli.py` - Simplify error handling
- All test files that import extraction errors

**Find-replace operations:**
```bash
# Find all imports of extraction errors
rg "from inkwell.extraction.errors import" src/ tests/

# Replace with:
# from inkwell.utils.errors import
```

**Database Changes**: No

**Exception hierarchy (after fix):**
```
Exception (stdlib)
│
└── InkwellError ✅
    ├── ConfigError
    │   ├── InvalidConfigError
    │   └── EncryptionError
    ├── FeedError
    │   ├── FeedNotFoundError
    │   └── DuplicateFeedError
    ├── NetworkError
    │   ├── ConnectionError
    │   └── RateLimitError
    ├── TranscriptionError ✅
    │   ├── YouTubeTranscriptionError
    │   └── GeminiTranscriptionError
    ├── ExtractionError ✅ (NOW UNIFIED)
    │   ├── ProviderError
    │   ├── SchemaValidationError (renamed)
    │   └── TemplateError
    ├── InterviewError ✅
    │   ├── SessionError
    │   └── AgentError
    └── OutputError
        └── PathTraversalError
```

## Resources

- Architecture report: See architecture-strategist agent findings
- Python exception best practices: https://docs.python.org/3/tutorial/errors.html
- PEP 8 exception conventions: https://peps.python.org/pep-0008/#exception-names

## Acceptance Criteria

- [ ] All error classes inherit from InkwellError (verify with `issubclass()`)
- [ ] `extraction/errors.py` file deleted
- [ ] All imports updated to use `utils/errors`
- [ ] CLI can catch all errors with single `except InkwellError`
- [ ] No `ValidationError` name collision with Pydantic
- [ ] All existing error types preserved (just relocated)
- [ ] Tests updated to import from new location
- [ ] All tests pass after refactoring
- [ ] Documentation updated with new error hierarchy

## Work Log

### 2025-11-14 - Architecture Review Discovery
**By:** Claude Code Review System (architecture-strategist agent)
**Actions:**
- Discovered broken exception hierarchy
- Identified two separate error trees
- Found name collision risk (ValidationError)
- Proposed unified hierarchy in utils/errors.py
- Flagged as P2 architecture violation

**Learnings:**
- Exception hierarchies should have single root
- Domain-specific errors should still inherit from base
- Scattered error definitions lead to inconsistency
- Single module for exceptions aids discoverability
- Base exception enables uniform error handling

## Notes

**Why this matters:**
- Exceptions are part of API contract
- Unified hierarchy enables consistent error handling
- Makes code more maintainable
- Follows Python best practices

**Testing strategy:**
```python
# tests/unit/test_error_hierarchy.py
def test_all_errors_inherit_from_inkwell_error():
    """Verify all custom errors inherit from InkwellError."""
    from inkwell.utils import errors

    # Get all error classes
    error_classes = [
        getattr(errors, name)
        for name in dir(errors)
        if name.endswith('Error') and name != 'InkwellError'
    ]

    # Verify inheritance
    for error_class in error_classes:
        assert issubclass(error_class, errors.InkwellError), \
            f"{error_class.__name__} doesn't inherit from InkwellError"
```

**CLI error handling (after fix):**
```python
# Simplified CLI error handling
try:
    result = await orchestrator.process_episode(options)
except InkwellError as e:  # ✅ Catches ALL application errors
    console.print(f"[red]✗[/red] Error: {e}")
    if isinstance(e, RateLimitError):
        console.print("[dim]Tip: Wait a few minutes and try again[/dim]")
    sys.exit(1)
except Exception as e:  # Only for unexpected errors
    logger.exception("Unexpected error")
    console.print(f"[red]✗[/red] Unexpected error: {e}")
    sys.exit(1)
```

**Migration checklist:**
1. [ ] Move all error classes to utils/errors.py
2. [ ] Update all `from extraction.errors import` statements
3. [ ] Delete extraction/errors.py
4. [ ] Run tests to verify no import errors
5. [ ] Update documentation
