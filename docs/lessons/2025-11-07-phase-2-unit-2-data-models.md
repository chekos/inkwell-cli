# Lessons Learned: Phase 2 Unit 2 - Data Models

**Date**: 2025-11-07
**Context**: Pydantic data models for transcription system
**Related**: [Devlog](../devlog/2025-11-07-phase-2-unit-2-data-models.md)

---

## Summary

Unit 2 focused on creating Pydantic models for transcripts. Key lessons: validators run in order, post-init hooks are powerful, and cross-field validation requires the `info` parameter.

---

## Key Lessons

### 1. Pydantic Validators Run in Declaration Order

**What We Learned**: Validators execute in the order they're declared in the class.

**Why It Matters**: If one validator depends on another's output, order is critical.

**Example**:
```python
class Transcript(BaseModel):
    segments: list[TranscriptSegment]

    @field_validator("segments")
    @classmethod
    def segments_sorted(cls, v):
        # This runs and sorts segments
        return sorted(v, key=lambda seg: seg.start)

    def model_post_init(self, __context):
        # This runs AFTER validators
        # Can safely assume segments are sorted
        if self.duration_seconds is None:
            self.duration_seconds = self.segments[-1].end
```

**Takeaway**: Design validators with execution order in mind. Use post-init for calculations that depend on validated data.

---

### 2. Post-Init Hooks for Computed Fields

**What We Learned**: `model_post_init` is perfect for auto-calculating optional fields.

**Pattern**:
```python
def model_post_init(self, __context) -> None:
    """Calculate optional fields after validation."""
    if self.word_count is None and self.segments:
        self.word_count = self.calculate_word_count()

    if self.duration_seconds is None and self.segments:
        self.duration_seconds = self.segments[-1].end
```

**Why Better Than Default Factory**:
- Default factory runs before validation
- Post-init runs after all data is validated
- Can access other validated fields safely

**Takeaway**: Use post-init for fields that derive from other fields.

---

### 3. Cross-Field Validation Needs `info` Parameter

**What We Learned**: To validate one field based on another, use `info.data`.

**Example**:
```python
@field_validator("transcript")
@classmethod
def transcript_required_if_success(cls, v: Optional[Transcript], info) -> Optional[Transcript]:
    if info.data.get("success") and v is None:
        raise ValueError("transcript is required when success is True")
    return v
```

**Why**: Without `info`, validators can only see their own field.

**Gotcha**: `info.data` may not have all fields if they failed validation.

**Takeaway**: Use `info.data.get()` with defaults, not direct access.

---

### 4. Properties Hide Implementation Details

**What We Learned**: Computed properties make models easier to use.

**Example**:
```python
@property
def full_text(self) -> str:
    """User doesn't need to know about segments."""
    return " ".join(seg.text for seg in self.segments)

@property
def is_free(self) -> bool:
    """User doesn't need to know source mapping."""
    return self.source in ("youtube", "cached")
```

**Why Better Than Methods**:
- More intuitive API (`transcript.full_text` vs `transcript.get_full_text()`)
- Feels like an attribute
- Can't accidentally pass arguments

**Takeaway**: Use properties for computed values that don't take parameters.

---

### 5. Test-to-Code Ratio of 1.7:1 is Healthy

**What We Observed**: 470 lines of tests for 280 lines of code.

**Why This is Good**:
- Tests document expected behavior
- Edge cases are covered
- Refactoring is safe
- Future contributors understand intent

**What Tests Caught**:
- Empty text validation
- Negative value rejection
- Segment sorting
- Cross-field validation rules

**Takeaway**: For data models, aim for 1.5-2:1 test ratio. Models are foundational.

---

## Patterns to Repeat

### 1. Validation with Clear Error Messages

**Pattern**:
```python
@field_validator("text")
@classmethod
def text_not_empty(cls, v: str) -> str:
    if not v or not v.strip():
        raise ValueError("Segment text cannot be empty")
    return v
```

**Why**: Users know exactly what's wrong.

---

### 2. Auto-Sorting Collections

**Pattern**:
```python
@field_validator("segments")
@classmethod
def segments_sorted(cls, v: list[TranscriptSegment]) -> list[TranscriptSegment]:
    if not v:
        return v
    # Check if sorted, sort if not
    for i in range(len(v) - 1):
        if v[i].start > v[i + 1].start:
            return sorted(v, key=lambda seg: seg.start)
    return v
```

**Why**: Users don't have to remember to sort. Models are defensive.

---

### 3. Rich Helper Methods

**Pattern**: Add methods that would be useful to callers

```python
def get_segment_at_time(self, time_seconds: float) -> Optional[TranscriptSegment]:
    """Find segment at specific time."""
    for segment in self.segments:
        if segment.contains_time(time_seconds):
            return segment
    return None
```

**Why**: Common operations are built-in, not repeated in calling code.

---

## Anti-Patterns to Avoid

### 1. Don't Use Mutable Defaults

**Bad**:
```python
segments: list[TranscriptSegment] = []  # ❌ Shared across instances!
```

**Good**:
```python
segments: list[TranscriptSegment] = Field(default_factory=list)  # ✅
```

---

### 2. Don't Make Everything a Property

**Bad**:
```python
@property
def calculate_statistics(self, min_length: int) -> dict:  # ❌ Takes parameter!
    ...
```

**Good**:
```python
def calculate_statistics(self, min_length: int) -> dict:  # ✅ Method
    ...
```

**Why**: Properties should be simple, fast, and parameter-free.

---

### 3. Don't Skip Field Descriptions

**Bad**:
```python
cost_usd: Optional[float] = None  # ❌ What does this mean?
```

**Good**:
```python
cost_usd: Optional[float] = Field(
    None,
    ge=0,
    description="Cost in USD for this transcription (if applicable)"
)  # ✅
```

---

## Technical Insights

### Pydantic v2 Performance

**Observation**: Models with many validators still fast (0.41s for 36 tests)

**Why**: Pydantic v2 uses Rust core (pydantic-core)

**Impact**: Can use validators freely without performance concerns

---

### Type Hints ≠ Runtime Validation

**Important**: Type hints are for IDEs/mypy. Pydantic adds runtime validation.

```python
# Type hint says float, but doesn't enforce
segments: list[TranscriptSegment]

# Pydantic validates at runtime
transcript = Transcript(segments="not a list")  # ❌ ValidationError
```

---

## Questions for Future

1. **Should we add more computed properties?** (e.g., `summary`, `topics`)
   - Wait until Phase 3 to see what LLM extraction needs

2. **Should segments have references back to parent Transcript?**
   - No - creates circular references, complicates serialization
   - Keep models simple

3. **Should we cache computed properties?** (e.g., `full_text`)
   - Not needed yet - concatenation is fast
   - Add caching if profiling shows it's slow

---

## Impact on Future Units

**Unit 3 (YouTube)**: These models made conversion trivial
```python
segments = [
    TranscriptSegment(**entry)  # Just unpack API response
    for entry in transcript_data
]
```

**Unit 5 (Gemini)**: Will benefit from same pattern

**Unit 7 (Manager)**: Can focus on orchestration, not data structure

---

## Recommended Reading

- [Pydantic Validators](https://docs.pydantic.dev/latest/concepts/validators/)
- [Pydantic Computed Fields](https://docs.pydantic.dev/latest/concepts/fields/)
- [Python Properties](https://docs.python.org/3/library/functions.html#property)

---

## Conclusion

Data models are the foundation. Investing time in Unit 2 to get them right pays off immediately in Unit 3 and beyond. The test coverage (36 tests) gives confidence to refactor if needed.

**Key principle**: Models should be smart enough to validate themselves, but simple enough to understand at a glance.
