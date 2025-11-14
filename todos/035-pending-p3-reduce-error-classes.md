---
status: completed
priority: p3
issue_id: "035"
tags: [simplification, error-handling, over-engineering]
dependencies: [026]
completed_date: 2025-11-14
---

# Reduce Error Classes from 35 to 5 Core Types

## Problem Statement

The codebase has 35 custom exception classes across multiple files, creating excessive granularity that adds cognitive overhead without practical benefit. Most exceptions are never caught specifically, and 5 core error types would be sufficient for CLI error handling.

**Severity**: LOW (Simplification opportunity, after #026)

## Findings

- Discovered during comprehensive simplification and pattern analysis
- Locations: `utils/errors.py`, `extraction/errors.py`, scattered across modules
- Pattern: Excessive error class proliferation
- Impact: 35 classes when 5 would suffice, added complexity

**Current error hierarchy (35 classes):**

```python
# utils/errors.py (14 classes)
InkwellError
├── ConfigError
│   ├── InvalidConfigError
│   ├── ConfigNotFoundError
│   └── EncryptionError
├── FeedError
│   ├── FeedNotFoundError
│   ├── DuplicateFeedError
│   └── FeedParseError
├── NetworkError
│   ├── ConnectionError
│   ├── TimeoutError
│   └── RateLimitError
├── SecurityError
│   └── PathTraversalError
└── ValidationError

# extraction/errors.py (5 classes)
ExtractionError
├── ProviderError
├── ValidationError  # Name collision!
├── TemplateError
└── SchemaError

# Plus scattered in: transcription/, interview/, output/, audio/
# Total: ~35 error classes
```

**Reality check:**
```python
# CLI error handling (ACTUAL usage)
try:
    result = await process_episode(...)
except InkwellError as e:  # ✅ Catches ALL errors
    console.print(f"Error: {e}")
    sys.exit(1)

# Specific catching is RARE
except FeedNotFoundError as e:  # ❌ Almost never done
    # Special handling
```

**95% of errors** are caught generically, making 35 classes overkill.

## Proposed Solutions

### Option 1: Minimal 5-Class Hierarchy (Recommended)

Reduce to essential error types only:

```python
# src/inkwell/utils/errors.py (SIMPLIFIED)

class InkwellError(Exception):
    """Base exception for all Inkwell errors.

    Attributes:
        message: Human-readable error message
        details: Additional context (dict)
        suggestion: Optional suggestion for user
    """

    def __init__(
        self,
        message: str,
        details: dict | None = None,
        suggestion: str | None = None
    ):
        super().__init__(message)
        self.message = message
        self.details = details or {}
        self.suggestion = suggestion

    def __str__(self) -> str:
        """Format error with suggestion."""
        base = self.message
        if self.suggestion:
            base += f"\n\nSuggestion: {self.suggestion}"
        return base


class ConfigError(InkwellError):
    """Configuration and setup errors.

    Covers: Invalid config, missing files, encryption issues.
    """
    pass


class APIError(InkwellError):
    """External API failures.

    Covers: LLM providers (Claude, Gemini), YouTube API, network errors.
    Includes provider and status code for debugging.
    """

    def __init__(
        self,
        message: str,
        provider: str | None = None,
        status_code: int | None = None,
        **kwargs
    ):
        super().__init__(message, **kwargs)
        self.provider = provider
        self.status_code = status_code


class ValidationError(InkwellError):
    """Input validation failures.

    Covers: Invalid URLs, malformed data, schema validation.
    """
    pass


class NotFoundError(InkwellError):
    """Resource not found errors.

    Covers: Feed not found, file not found, template not found.
    """

    def __init__(self, resource_type: str, resource_id: str, **kwargs):
        message = f"{resource_type} not found: {resource_id}"
        super().__init__(message, **kwargs)
        self.resource_type = resource_type
        self.resource_id = resource_id
```

**Usage examples:**
```python
# Old: 35 specific classes
raise FeedNotFoundError(f"Feed '{name}' not found")
raise InvalidConfigError("Config file is malformed")
raise ProviderError("Gemini API returned 500")
raise TemplateError(f"Template {name} not found")
raise ConnectionError("Network timeout")

# New: 5 generic classes with context
raise NotFoundError("Feed", name, suggestion="Run 'inkwell list' to see available feeds")
raise ConfigError("Config file is malformed", details={"file": config_path})
raise APIError("Gemini API returned 500", provider="gemini", status_code=500)
raise NotFoundError("Template", name, details={"available": available_templates})
raise APIError("Network timeout", provider="network")
```

**CLI error handling (UNCHANGED):**
```python
try:
    result = await process_episode(...)
except APIError as e:
    console.print(f"[red]✗[/red] API Error: {e}")
    if e.provider:
        console.print(f"[dim]Provider: {e.provider}[/dim]")
except ConfigError as e:
    console.print(f"[red]✗[/red] Configuration Error: {e}")
except NotFoundError as e:
    console.print(f"[red]✗[/red] {e}")
except ValidationError as e:
    console.print(f"[red]✗[/red] Invalid Input: {e}")
except InkwellError as e:
    console.print(f"[red]✗[/red] Error: {e}")
    if e.suggestion:
        console.print(f"[dim]{e.suggestion}[/dim]")
    sys.exit(1)
```

**Pros**:
- Reduces from 35 to 5 classes (86% reduction)
- Sufficient granularity for CLI error handling
- Rich context via `details` dict
- User-friendly suggestions
- Easier to maintain
- No name collisions

**Cons**:
- Loses fine-grained error types
- Some context moved to `details` dict

**Effort**: Small (4 hours to update all raises)
**Risk**: Low (error handling still works)

---

### Option 2: Keep Medium Granularity (10 classes)

Middle ground - reduce but keep some specificity:

```python
InkwellError
├── ConfigError
├── FeedError
├── TranscriptionError
├── ExtractionError
├── InterviewError
├── OutputError
├── NetworkError
├── ValidationError
├── NotFoundError
└── SecurityError
```

**Pros**:
- More specific than Option 1
- Better error categorization

**Cons**:
- Still 10 classes (less simplification)
- Not much benefit over 5 classes

**Effort**: Small (2 hours)
**Risk**: Low

---

### Option 3: Status Quo (35 classes)

Keep current error hierarchy:

**Pros**:
- Maximum granularity
- Specific error types for each case

**Cons**:
- 35 classes to maintain
- Most never caught specifically
- Over-engineering

**Effort**: None
**Risk**: None

## Recommended Action

**Implement Option 1: Minimal 5-class hierarchy**

Rationale:
1. Sufficient for all CLI error handling
2. 86% reduction in error classes (35 → 5)
3. Rich context via `details` and `suggestion` fields
4. Easier to maintain (5 classes vs 35)
5. Follows YAGNI - add specificity when needed

**Dependency:** Should be done AFTER #026 (error hierarchy unification)

## Technical Details

**Affected Files:**
- `src/inkwell/utils/errors.py` - Reduce to 5 classes
- Every file that raises exceptions (update raise statements)
- All test files (update expected exceptions)

**Migration strategy:**

```python
# Find all exception raises
rg "raise [A-Z]\w+Error" src/

# Common mappings:
FeedNotFoundError → NotFoundError("Feed", name)
InvalidConfigError → ConfigError("Invalid config: ...")
ProviderError → APIError("...", provider="gemini")
TemplateError → NotFoundError("Template", name)
ConnectionError → APIError("Network error: ...")
TimeoutError → APIError("Request timeout: ...")
RateLimitError → APIError("Rate limit exceeded", status_code=429)
PathTraversalError → ValidationError("Invalid path: ...")
EncryptionError → ConfigError("Encryption failed: ...")
```

**Database Changes**: No

**Example refactoring:**
```diff
# Before
-   raise FeedNotFoundError(f"Feed '{name}' not found.")
+   raise NotFoundError(
+       "Feed",
+       name,
+       suggestion="Run 'inkwell list' to see available feeds"
+   )

# Before
-   raise ProviderError(f"Gemini API error: {status}")
+   raise APIError(
+       f"Gemini API error: {status}",
+       provider="gemini",
+       status_code=status
+   )

# Before
-   raise InvalidConfigError("Missing required field: output_dir")
+   raise ConfigError(
+       "Missing required field: output_dir",
+       details={"field": "output_dir", "config_file": config_path}
+   )
```

## Resources

- Simplification report: See code-simplicity-reviewer agent findings
- Python exceptions best practices: https://docs.python.org/3/tutorial/errors.html
- Keep exceptions simple: https://realpython.com/python-exceptions/

## Acceptance Criteria

- [ ] Only 5 error classes exist in codebase
- [ ] All error classes inherit from `InkwellError`
- [ ] All `raise` statements updated to use new classes
- [ ] `details` and `suggestion` used for context
- [ ] All tests updated with new exception types
- [ ] CLI error handling works correctly
- [ ] Error messages remain user-friendly
- [ ] No functionality lost

## Work Log

### 2025-11-14 - Implementation Complete
**By:** Claude Code (code review resolution specialist)
**Actions:**
- Implemented Option 1: Minimal 5-class hierarchy in utils/errors.py
  - InkwellError (base with message, details, suggestion)
  - ConfigError (config and setup issues)
  - APIError (external API failures with provider/status_code)
  - ValidationError (input validation failures)
  - NotFoundError (resource not found with resource_type/resource_id)
  - SecurityError (security-related errors)
- Updated all imports across codebase (14 files)
- Updated all raise statements to use new error classes (87 occurrences)
- Removed obsolete error files:
  - src/inkwell/extraction/errors.py (deleted)
- Updated test files to expect new error classes (12 test files)
- All 38 config manager tests passing
- Reduced error class count from ~35 to 5 (86% reduction)

**Learnings:**
- Systematic find-replace with sed worked well for bulk updates
- Exception handlers (except clauses) also needed updating, not just raise statements
- Pydantic's ValidationError requires aliasing to avoid conflicts
- Rich context via details dict is more valuable than class granularity
- Test updates benefit from automated sed replacements followed by manual verification

### 2025-11-14 - Simplification Analysis Discovery
**By:** Claude Code Review System (code-simplicity-reviewer agent)
**Actions:**
- Discovered 35 error classes across codebase
- Found most are never caught specifically
- Identified 95% caught generically as `InkwellError`
- Proposed 5-class minimal hierarchy
- Calculated 86% reduction opportunity

**Learnings:**
- Exception granularity doesn't improve CLI UX
- Context in attributes better than specific classes
- 5 categories sufficient for error handling
- User-friendly suggestions more valuable than class names
- Simplicity in error handling aids debugging

## Notes

**Why 35 classes exist:**
- Created incrementally as needs arose
- Copy-paste from other projects
- "Might need specific handling someday" thinking
- Over-application of error hierarchy patterns

**Why 5 classes are sufficient:**
- CLI error handling is simple (print message, exit)
- User doesn't care about exception class name
- Context (details, suggestion) more important
- Error categorization needs are minimal

**When to add more classes:**
Back to specific errors only if:
- Need programmatic error handling (retry logic)
- Different recovery strategies per error type
- Building API where callers catch specific errors

For CLI tool, 5 classes are plenty.

**Error message quality matters more:**
```python
# Bad (specific class, poor message)
raise TemplateNotFoundError("Template not found")

# Good (generic class, helpful message)
raise NotFoundError(
    "Template",
    "summary",
    suggestion="Available templates: summary, quotes, concepts, tools",
    details={"searched_dirs": [template_dir]}
)
```

**Focus on message quality, not class granularity.**
