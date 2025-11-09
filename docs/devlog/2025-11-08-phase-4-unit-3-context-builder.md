# Phase 4 Unit 3: Interview Context Builder - Complete

**Date**: 2025-11-08
**Unit**: 3 of 9
**Status**: ✅ Complete
**Duration**: ~3 hours
**Related**: [Phase 4 Detailed Plan](./2025-11-08-phase-4-detailed-plan.md), [Unit 2 Data Models](./2025-11-08-phase-4-unit-2-data-models.md)

## Overview

Unit 3 implements the `InterviewContextBuilder`, which extracts content from Phase 3 output files and constructs rich context for interview question generation. The builder reads markdown files (summary, quotes, concepts, tools, etc.) and creates an `InterviewContext` object that provides structured information to the LLM.

## What Was Built

### Core Component

**InterviewContextBuilder** (`interview/context_builder.py`, 307 lines):
- Extracts content from `EpisodeOutput` objects
- Parses markdown files into structured data
- Builds `InterviewContext` for question generation
- Loads previous interview summaries (foundation)

### Extraction Methods (6)

**1. Summary Extraction** (`_extract_summary()`):
- Reads `summary.md` file
- Removes markdown headers (# Summary, ## Key Points, etc.)
- Preserves prose content
- Returns clean summary text

**2. Quote Extraction** (`_extract_quotes()`):
- Parses blockquote format:
  ```markdown
  > "Quote text"
  > — Speaker [timestamp]
  ```
- Extracts text, speaker, timestamp
- Handles quotes with/without timestamps
- Returns list of quote dictionaries

**3. Concept Extraction** (`_extract_concepts()`):
- Parses `key-concepts.md` file
- Supports bullet lists (-, *)
- Supports numbered lists (1. 2. etc.)
- Filters very short items (<=3 chars)
- Returns list of concept strings

**4. Additional Content Extraction** (`_extract_additional_content()`):
- Checks for 6 template types:
  - tools-mentioned
  - books-mentioned
  - people-mentioned
  - frameworks-mentioned
  - companies-mentioned
  - concepts-discussed
- Extracts list items from each
- Returns dictionary mapping template name → items

**5. List Item Extraction** (`_extract_list_items()`):
- General-purpose list parser
- Handles `-`, `*` bullet points
- Handles numbered lists (1. 2. 10. etc.)
- Filters empty items and headers
- Reusable across different file types

**6. Previous Interview Loading** (`load_previous_interviews()`):
- Finds `session-*.json` files in interview directory
- Sorts by modification time + name (stable ordering)
- Returns N most recent sessions
- TODO: Parse JSON and extract summaries (placeholder for now)

### Build Context Method

**`build_context(episode_output, guidelines, max_questions)`**:
- Takes `EpisodeOutput` from Phase 3
- Optionally accepts user `InterviewGuidelines`
- Calls all extraction methods
- Calculates duration in minutes
- Returns complete `InterviewContext` object

## Design Decisions

### 1. EpisodeOutput Integration

**Decision**: Work directly with Phase 3's `EpisodeOutput` model

**Rationale**:
- Already exists and is well-tested
- Provides `get_file(template_name)` method
- Contains all metadata (podcast, episode, duration)
- No need to reinvent the wheel

**Example**:
```python
summary_file = episode_output.get_file("summary")
if summary_file:
    content = summary_file.content  # Already parsed
```

### 2. Markdown Parsing Strategy

**Decision**: Simple string parsing instead of markdown library

**Rationale**:
- Phase 3 output has predictable structure
- Don't need full markdown AST
- String methods are faster and simpler
- Fewer dependencies
- Easy to debug and test

**Implementation**:
```python
# Remove headers
for line in lines:
    if not line.strip().startswith("#"):
        filtered_lines.append(line)
```

### 3. Quote Format Handling

**Decision**: Parse custom blockquote format with speaker/timestamp

**Rationale**:
- Phase 3 outputs specific format:
  ```
  > "Quote text"
  > — Speaker [timestamp]
  ```
- Need to extract all three components
- Handle optional timestamps
- Support various edge cases

**Challenge**: Initial parsing incorrectly used `lstrip("—")` which doesn't work as expected
- `lstrip()` removes characters, not substrings
- **Fix**: Use `split("—", 1)` to properly split on em dash

### 4. Concept Filtering

**Decision**: Filter concepts shorter than 4 characters

**Rationale**:
- Avoid extracting abbreviations like "AI", "ML"
- Focus on substantial concepts
- Prevent noise in context
- Threshold of 4 chosen empirically

**Implementation**:
```python
if concept and len(concept) > 3 and not concept.startswith("#"):
    concepts.append(concept)
```

### 5. Additional Content Templates

**Decision**: Support 6 common additional template types

**Rationale**:
- These are most useful for interview context
- Tools/frameworks → ask about practical applications
- Books/people → ask about influences
- Can easily extend to more templates
- Returns empty dict if none found (graceful)

### 6. Previous Interview Integration

**Decision**: Stub out previous interview loading for now

**Rationale**:
- Session persistence not implemented yet (Unit 5)
- Need foundation for future connection-making
- Can implement JSON parsing later
- For now, just discover files

**Implementation**:
```python
# Sort by mtime + name for stable ordering
session_files = sorted(
    interview_dir.glob("session-*.json"),
    key=lambda p: (p.stat().st_mtime, p.name)
)
```

### 7. Stable Sorting

**Decision**: Sort previous interviews by (mtime, name) tuple

**Rationale**:
- Files created at same time (tests) need predictable order
- Primary sort by modification time (most recent)
- Secondary sort by name (alphabetical)
- Makes behavior deterministic
- Tests don't flake

## Key Features

### Robust Parsing

**Handles Missing Files**:
- Returns empty string/list if file not found
- No exceptions thrown
- Graceful degradation
- Context still builds successfully

**Handles Empty Content**:
- Empty summary → ""
- No quotes → []
- No concepts → []
- Additional → {}

**Handles Various Formats**:
- Bullet points: `-` and `*`
- Numbered lists: `1.` `2.` `10.`
- Mixed content (prose + lists)
- Headers interspersed with content

### Content Filtering

**Summary**:
- Removes markdown headers
- Preserves paragraphs
- Strips whitespace

**Concepts**:
- Filters short items (<=3 chars)
- Removes headers
- Removes empty strings

**Lists**:
- Filters empty items
- Strips whitespace
- Handles indentation

### Integration with Models

**Uses Existing Models**:
- `EpisodeOutput` from `output.models`
- `OutputFile` for individual files
- `InterviewContext` from Unit 2
- `InterviewGuidelines` from Unit 2

**Returns Structured Data**:
- Summary: string
- Quotes: list[dict] with text/speaker/timestamp
- Concepts: list[str]
- Additional: dict[str, list[str]]

## Testing

### Test Suite Statistics

- **Total tests**: 19
- **Pass rate**: 100%
- **Coverage**: 100% on context builder logic
- **Test file**: `tests/unit/interview/test_context_builder.py` (~490 lines)

### Test Categories

**Basic Building (2)**:
- Build context from complete episode output
- Build context with user guidelines
- Verify metadata propagation

**Summary Extraction (2)**:
- Extract summary with headers removed
- Handle missing summary file

**Quote Extraction (2)**:
- Parse quotes with various formats (4 examples)
- Extract text, speaker, timestamp
- Handle missing timestamp
- Handle missing file

**Concept Extraction (3)**:
- Parse bullets and numbered lists
- Filter short concepts (<= 3 chars)
- Handle missing file

**Additional Content (3)**:
- Extract tools-mentioned
- Extract books-mentioned
- Handle no additional files

**Edge Cases (4)**:
- Empty episode (no files)
- No duration in metadata
- Prompt context formatting
- Mixed list formats

**Previous Interviews (3)**:
- Empty directory
- Nonexistent directory
- Multiple files with limit

### Edge Cases Tested

- Missing files (all types)
- Empty content
- No duration metadata
- Very short concepts filtered
- Mixed list formats (bullets + numbers)
- Files with same mtime (stable sorting)
- Headers interspersed with content

## Code Quality

### Linter Results

- ✅ All ruff checks pass
- ✅ Type hints throughout
- ✅ No unused imports
- ✅ Proper string handling

### Type Safety

- ✅ All methods have type hints
- ✅ Return types specified
- ✅ `dict[str, Any]` for flexible quote structure
- ✅ `list[str]` for concepts
- ✅ `Path` for filesystem operations

### Documentation

- ✅ Module docstring
- ✅ Class docstring with example
- ✅ Method docstrings with Args/Returns
- ✅ Inline comments for complex logic
- ✅ Test docstrings explain intent

## Statistics

**Production Code**:
- `context_builder.py`: 307 lines
- Updated `__init__.py`: +3 lines
- **Total**: ~310 lines

**Test Code**:
- `test_context_builder.py`: 490 lines
- **Test-to-code ratio**: 1.6:1

**Methods Implemented**: 6 extraction + 1 build
**Template Types Supported**: 6 additional content types
**Quote Components Extracted**: 3 (text, speaker, timestamp)

## Lessons Learned

### What Worked Well

1. **Simple String Parsing**
   - No markdown library needed
   - Fast and predictable
   - Easy to test
   - Clear logic

2. **EpisodeOutput Integration**
   - Reused existing, tested model
   - `get_file()` method very convenient
   - No new file I/O code needed
   - Clean separation of concerns

3. **Comprehensive Fixtures**
   - Created realistic test data
   - Fixtures reused across tests
   - Easy to add new test cases
   - Reflects real Phase 3 output

4. **Graceful Handling**
   - Missing files don't crash
   - Empty content returns defaults
   - No exceptions needed
   - Context always builds

### Challenges

1. **Quote Parsing Bug**
   - Issue: Used `lstrip("—")` to remove em dash
   - Problem: `lstrip()` removes characters, not substring
   - Result: "— Speaker" became "— Speaker" (unchanged)
   - **Fix**: Use `split("—", 1)` to properly split

2. **Test File Sorting**
   - Issue: Files created at same time have same mtime
   - Problem: Tests expected specific order
   - Result: Non-deterministic test failures
   - **Fix**: Sort by (mtime, name) tuple for stability

3. **Concept Filtering Threshold**
   - Issue: What length is too short?
   - Tried: 2, 3, 4, 5 characters
   - **Choice**: 4 (filters "AI", "ML" but keeps "REST")
   - Trade-off: Some useful abbreviations lost

4. **Additional Templates**
   - Issue: How many to support?
   - Could support all templates dynamically
   - **Choice**: Explicit list of 6 common ones
   - Rationale: More predictable, can extend later

### Surprises

1. **`lstrip()` Behavior**
   - Expected: Remove substring from left
   - Actual: Remove characters (like a character set)
   - Example: `"—Hello".lstrip("—")` → "Hello" ✓
   - Example: `"— Hello".lstrip("—")` → "— Hello" ✗ (space blocks it)
   - **Learning**: Use `split()` or `replace()` for substrings

2. **Path Sorting**
   - Can sort by tuple: `(p.stat().st_mtime, p.name)`
   - Python compares tuples element-by-element
   - Very elegant solution
   - Didn't know this pattern before

3. **Fixture Composition**
   - Can have fixtures depend on other fixtures
   - pytest handles dependency injection
   - Very powerful for building complex test data
   - `sample_episode_output` uses 5 other fixtures

4. **Test Coverage**
   - 19 tests felt like enough
   - High confidence in correctness
   - Found 2 bugs during test-writing
   - TDD approach paid off

## What's Next

### Unit 4: Claude Agent SDK Integration (Next)

**Immediate tasks**:
1. Implement `ClaudeAgent` wrapper class
2. Create interview template system (reflective, analytical, creative)
3. Implement streaming question generation
4. Add token usage tracking
5. Test with real context from Unit 3

**Why this order**:
- Have context ready for agent
- Agent is core of interview loop
- Templates define interview style
- Can test question generation end-to-end

### Future Enhancements

**Previous Interview Parsing**:
- Load session JSON files
- Extract key insights from previous interviews
- Build connection prompts
- Enable cross-episode reflection

**Dynamic Template Discovery**:
- Instead of hardcoded list of 6 templates
- Discover all available templates
- Extract from any template file
- More flexible for custom templates

**Caching**:
- Cache parsed contexts
- Avoid re-parsing same episode
- Store in session directory
- Invalidate on content changes

## Related Documentation

**From This Unit**:
- Context builder: `src/inkwell/interview/context_builder.py`
- Tests: `tests/unit/interview/test_context_builder.py`

**From Previous Units**:
- Unit 2: `InterviewContext` and `InterviewGuidelines` models
- Phase 3: `EpisodeOutput` and `OutputFile` models

**For Future Units**:
- Unit 4 will use `InterviewContext` for question generation
- Unit 5 will implement session persistence (previous interview loading)
- Unit 8 will integrate context builder into CLI flow

## Design Patterns Used

1. **Builder Pattern** - InterviewContextBuilder constructs complex InterviewContext
2. **Strategy Pattern** - Different extraction methods for different file types
3. **Null Object Pattern** - Return empty collections instead of exceptions
4. **Template Method** - `_extract_list_items()` reused by multiple extractors

## Key Decisions Summary

| Decision | Rationale | Impact |
|----------|-----------|--------|
| Use EpisodeOutput | Already exists, well-tested | Clean integration, no new I/O |
| Simple string parsing | Predictable structure | Fast, simple, testable |
| Split on em dash | Correct substring handling | Proper speaker extraction |
| Filter concepts <=3 chars | Avoid abbreviations | Focus on substantial concepts |
| Support 6 templates | Common use cases | Extensible later |
| Stable sorting (mtime, name) | Deterministic order | Tests don't flake |

## Implementation Highlights

### Quote Parsing
```python
# Extract quote text
if line.startswith(">") and '"' in line:
    quote_text = line.lstrip(">").strip().strip('"')
    current_quote = {"text": quote_text}

# Extract speaker and timestamp
elif line.startswith(">") and "—" in line:
    after_quote = line.lstrip(">").strip()
    _, attribution = after_quote.split("—", 1)

    if "[" in attribution:
        speaker, timestamp_part = attribution.split("[", 1)
        current_quote["speaker"] = speaker.strip()
        current_quote["timestamp"] = timestamp_part.rstrip("]").strip()
```

### List Extraction
```python
# Bullet points
if line.startswith("-") or line.startswith("*"):
    item = line.lstrip("-*").strip()
    if item and not item.startswith("#"):
        items.append(item)

# Numbered lists
elif line and line[0].isdigit() and "." in line:
    parts = line.split(".", 1)
    if len(parts) > 1:
        item = parts[1].strip()
        if item:
            items.append(item)
```

### Previous Interview Discovery
```python
# Sort by mtime + name for stable ordering
session_files = sorted(
    interview_dir.glob("session-*.json"),
    key=lambda p: (p.stat().st_mtime, p.name)
)

# Get most recent N
recent = session_files[-limit:] if len(session_files) > limit else session_files
```

## Success Criteria

**All Unit 3 objectives met**:
- ✅ InterviewContextBuilder implemented
- ✅ Summary, quotes, concepts extraction working
- ✅ Additional content extraction (6 types)
- ✅ Previous interview foundation
- ✅ 19 tests passing (100%)
- ✅ Handles missing files gracefully
- ✅ Linter clean
- ✅ Type hints throughout
- ✅ Documentation complete

## Files Created/Modified

**New Files** (2):
- `src/inkwell/interview/context_builder.py`
- `tests/unit/interview/test_context_builder.py`

**Modified Files** (1):
- `src/inkwell/interview/__init__.py` (added InterviewContextBuilder export)

---

**Unit 3 Status**: ✅ **Complete**

Ready to proceed to Unit 4: Claude Agent SDK Integration!

---

## Checklist

**Implementation**:
- [x] InterviewContextBuilder class
- [x] Summary extraction
- [x] Quote extraction (text, speaker, timestamp)
- [x] Concept extraction (bullets, numbers)
- [x] Additional content extraction (6 templates)
- [x] List item extraction helper
- [x] Previous interview loading (foundation)

**Testing**:
- [x] 19 comprehensive tests
- [x] 100% pass rate
- [x] Edge cases (missing files, empty content)
- [x] Quote parsing edge cases
- [x] List format variations
- [x] Stable sorting tests

**Quality**:
- [x] Linter passing
- [x] Type hints complete
- [x] Docstrings added
- [x] Code formatted

**Documentation**:
- [x] This devlog
- [x] Inline code documentation
- [x] Test documentation

**Next**:
- [ ] Unit 4: Implement Claude Agent SDK wrapper and templates
