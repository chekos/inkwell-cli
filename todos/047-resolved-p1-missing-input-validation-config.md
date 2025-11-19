---
status: resolved
priority: p1
issue_id: "047"
tags: [code-review, security, data-integrity, validation, pr-20, critical]
dependencies: []
---

# Add Input Validation to Configuration Schema

## Problem Statement

Configuration schema models lack bounds checking on security-sensitive numeric fields. Pydantic models accept ANY values, including negatives, zeros, and extremely large numbers that could bypass cost limits, cause resource exhaustion, or create invalid application state.

**Severity**: CRITICAL (Security + Data Integrity risk)

## Findings

- Discovered during security and data integrity review of PR #20
- Location: `src/inkwell/config/schema.py` (lines 30-79)
- Multiple config classes lack Field constraints
- No bounds checking on numeric parameters
- No length validation on string fields
- Attack vectors: Cost bypass, DoS, invalid state

**Vulnerable Fields**:

1. **TranscriptionConfig**:
   - `model_name: str` - No length limits (could be empty or 10MB string)
   - `cost_threshold_usd: float` - Accepts negative values or infinity

2. **InterviewConfig**:
   - `question_count: int` - Could be -1 (infinite loop) or 999999 (DoS)
   - `max_depth: int` - Could be -1 or 999999
   - `session_timeout_minutes: int` - Could be negative (instant timeout)
   - `max_cost_per_interview: float` - Could be negative (bypass limit)

**Attack Scenarios**:
```yaml
# Malicious config.yaml
transcription:
  cost_threshold_usd: -1.0  # Bypass all cost limits!

interview:
  question_count: -1  # Infinite loop
  max_cost_per_interview: -999  # Bypass cost checks
  session_timeout_minutes: 0  # Instant timeout = DoS
```

## Proposed Solutions

### Option 1: Add Pydantic Field Constraints (Recommended)

**Pros**:
- Built-in Pydantic feature, very clean
- Automatic validation with clear error messages
- No custom code needed
- Self-documenting (constraints visible in schema)

**Cons**:
- None

**Effort**: Small (30 minutes)
**Risk**: Low (pure validation, no logic changes)

**Implementation**:
```python
# src/inkwell/config/schema.py

from pydantic import BaseModel, Field, field_validator

class TranscriptionConfig(BaseModel):
    """Transcription service configuration."""

    model_name: str = Field(
        default="gemini-2.5-flash",
        min_length=1,
        max_length=100,
        description="Gemini model name (e.g., gemini-2.5-flash)"
    )
    api_key: str | None = Field(
        default=None,
        min_length=20,
        max_length=500,
        description="Google AI API key (if None, uses environment variable)"
    )
    cost_threshold_usd: float = Field(
        default=1.0,
        ge=0.0,      # greater than or equal to 0
        le=1000.0,   # less than or equal to 1000
        description="Maximum cost in USD before requiring confirmation"
    )
    youtube_check: bool = True  # No validation needed for bool

    @field_validator('model_name')
    @classmethod
    def validate_model_name(cls, v: str) -> str:
        """Validate Gemini model name format."""
        if not v.startswith('gemini-'):
            raise ValueError('Model name must start with "gemini-"')
        return v


class ExtractionConfig(BaseModel):
    """Extraction service configuration."""

    default_provider: Literal["claude", "gemini"] = "gemini"  # Already validated by Literal
    claude_api_key: str | None = Field(
        default=None,
        min_length=20,
        max_length=500,
        description="Anthropic API key"
    )
    gemini_api_key: str | None = Field(
        default=None,
        min_length=20,
        max_length=500,
        description="Google AI API key"
    )


class InterviewConfig(BaseModel):
    """Interview mode configuration."""

    enabled: bool = True
    auto_start: bool = False

    # Style
    default_template: str = "reflective"
    question_count: int = Field(
        default=5,
        ge=1,       # At least 1 question
        le=100,     # Max 100 questions (prevent DoS)
        description="Number of interview questions"
    )
    max_depth: int = Field(
        default=3,
        ge=1,
        le=10,      # Reasonable max for follow-up depth
        description="Maximum depth for follow-up questions"
    )

    # User preferences
    guidelines: str = Field(
        default="",
        max_length=10000,  # Reasonable limit for guidelines text
        description="User guidelines for interview style"
    )

    # Session
    save_raw_transcript: bool = True
    resume_enabled: bool = True
    session_timeout_minutes: int = Field(
        default=60,
        ge=1,        # At least 1 minute
        le=1440,     # Max 24 hours (1440 minutes)
        description="Session timeout in minutes"
    )

    # Output
    include_action_items: bool = True
    include_key_insights: bool = True
    format_style: Literal["structured", "narrative", "qa"] = "structured"

    # Cost
    max_cost_per_interview: float = Field(
        default=0.50,
        ge=0.0,
        le=100.0,
        description="Maximum cost per interview in USD"
    )
    confirm_high_cost: bool = True

    # Advanced
    model: str = Field(
        default="claude-sonnet-4-5",
        min_length=1,
        max_length=100,
        description="Claude model for interview"
    )
    temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,      # Claude API accepts 0.0-2.0
        description="Model temperature for response variability"
    )
    streaming: bool = True
```

**Pydantic Field Constraint Reference**:
- `ge` = greater than or equal (≥)
- `gt` = greater than (>)
- `le` = less than or equal (≤)
- `lt` = less than (<)
- `min_length` / `max_length` for strings
- `@field_validator` for custom validation logic

## Recommended Action

Implement Option 1 immediately. This is critical security hardening that prevents:
- Cost limit bypass attacks
- Resource exhaustion (DoS)
- Invalid application state
- Configuration corruption

## Technical Details

**Affected Files**:
- `src/inkwell/config/schema.py` (lines 30-79)

**Related Components**:
- All services that consume these configs
- Cost tracking system (relies on valid thresholds)
- Interview orchestration (relies on valid bounds)

**Database Changes**: None

**Testing Requirements**:
Add validation tests to `tests/unit/test_schema.py`:

```python
def test_transcription_config_validates_cost_threshold():
    """Cost threshold must be non-negative and reasonable."""
    # Valid values
    config = TranscriptionConfig(cost_threshold_usd=0.0)
    assert config.cost_threshold_usd == 0.0

    config = TranscriptionConfig(cost_threshold_usd=100.0)
    assert config.cost_threshold_usd == 100.0

    # Invalid: negative
    with pytest.raises(ValidationError):
        TranscriptionConfig(cost_threshold_usd=-1.0)

    # Invalid: too large
    with pytest.raises(ValidationError):
        TranscriptionConfig(cost_threshold_usd=9999.0)


def test_interview_config_validates_question_count():
    """Question count must be positive and reasonable."""
    # Valid
    config = InterviewConfig(question_count=10)
    assert config.question_count == 10

    # Invalid: negative
    with pytest.raises(ValidationError):
        InterviewConfig(question_count=-1)

    # Invalid: zero
    with pytest.raises(ValidationError):
        InterviewConfig(question_count=0)

    # Invalid: too large (DoS risk)
    with pytest.raises(ValidationError):
        InterviewConfig(question_count=999)


def test_model_name_format_validation():
    """Model name must follow Gemini naming convention."""
    # Valid
    config = TranscriptionConfig(model_name="gemini-2.5-flash")
    assert config.model_name == "gemini-2.5-flash"

    # Invalid: doesn't start with 'gemini-'
    with pytest.raises(ValidationError):
        TranscriptionConfig(model_name="gpt-4")

    # Invalid: empty
    with pytest.raises(ValidationError):
        TranscriptionConfig(model_name="")

    # Invalid: too long
    with pytest.raises(ValidationError):
        TranscriptionConfig(model_name="x" * 200)
```

## Acceptance Criteria

- [ ] Field constraints added to TranscriptionConfig (model_name, cost_threshold_usd)
- [ ] Field constraints added to ExtractionConfig (API key lengths)
- [ ] Field constraints added to InterviewConfig (all numeric fields)
- [ ] @field_validator added for model_name format
- [ ] Tests added for valid boundary values
- [ ] Tests added for invalid values (negative, too large, empty)
- [ ] All existing tests still pass
- [ ] Pydantic generates clear validation error messages

## Work Log

### 2025-11-18 - Code Review Discovery
**By:** Claude Code Review System
**Actions:**
- Discovered during security audit by security-sentinel agent
- Validated by data-integrity-guardian agent
- Categorized as P1 CRITICAL priority
- Identified 8 vulnerable numeric fields
- Documented attack scenarios

**Learnings:**
- Pydantic models don't validate bounds by default
- Field constraints are opt-in, not automatic
- Security-sensitive configs need explicit validation
- Cost limits are security boundaries, not just features

## Notes

**Why Pydantic Field Constraints?**
- Built-in feature, no external dependencies
- Self-documenting (constraints visible in schema)
- Automatic error messages with field context
- Better than manual validation in __init__
- Works with model_dump(), model_validate(), etc.

**Alternative Approaches Considered**:
1. ❌ Manual validation in `__init__` - Verbose, error-prone
2. ❌ Regex patterns - Overkill for numeric validation
3. ✅ Pydantic Field constraints - Clean, Pythonic, built-in

**Security Impact**:
This prevents several OWASP Top 10 categories:
- A04:2021 Insecure Design (missing validation)
- A03:2021 Injection (malformed model names)
- A05:2021 Security Misconfiguration (invalid bounds)

**Related Security Findings**:
- Finding #3: Path expansion missing (separate issue)
- Finding #8: API key validation in error messages

**Source**: Code review performed on 2025-11-18
**Review command**: /compounding-engineering:review PR20
