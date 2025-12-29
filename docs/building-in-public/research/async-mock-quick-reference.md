# Async Mock Quick Reference - Common Patterns

**Quick lookup for fixing the 19 test failures**

## The Golden Rules

1. **Methods that are awaited → AsyncMock**
2. **Methods that are not awaited → Mock**
3. **Never use lambda for async methods**
4. **Never assign coroutine functions directly**

## Quick Diagnostic

### Error: "object MagicMock can't be used in 'await' expression"

**You did this:**
```python
# WRONG - lambda for async method
mock.extract = lambda t, x, m: "result"

# WRONG - direct coroutine assignment
async def extract_fn(t, x, m):
    return "result"
mock.extract = extract_fn
```

**Do this instead:**
```python
# RIGHT - AsyncMock
mock.extract = AsyncMock(return_value="result")

# RIGHT - AsyncMock with side_effect
async def extract_fn(t, x, m):
    return "result"
mock.extract = AsyncMock(side_effect=extract_fn)
```

### Error: "AttributeError: 'ExtractionResult' object has no attribute 'content'"

**You did this:**
```python
# WRONG - old field structure
result.content
```

**Do this instead:**
```python
# RIGHT - new nested structure
result.extracted_content.content
```

### Error: "ValidationError: 2 validation errors for ExtractedContent"

**You did this:**
```python
# WRONG - old dict format
ExtractedContent({
    'format': 'text',
    'data': 'content',
})
```

**Do this instead:**
```python
# RIGHT - new model format
ExtractedContent(
    template_name="summary",
    content="content",
)
```

## Common Test Patterns

### Pattern 1: Mock an Extractor

```python
from unittest.mock import AsyncMock, Mock, patch

with patch("inkwell.extraction.engine.GeminiExtractor") as mock_class:
    mock_extractor = mock_class.return_value

    # Async method - use AsyncMock
    mock_extractor.extract = AsyncMock(return_value="output")

    # Sync method - use Mock
    mock_extractor.estimate_cost = Mock(return_value=0.01)

    engine = ExtractionEngine()
    result = await engine.extract(template, transcript, metadata)
```

### Pattern 2: Template-Specific Responses

```python
# Use side_effect with async function
async def mock_extract_side_effect(template, transcript, metadata):
    if template.name == "summary":
        return "Summary text"
    elif template.expected_format == "json":
        return '{"key": "value"}'
    return "Default"

mock.extract = AsyncMock(side_effect=mock_extract_side_effect)
mock.estimate_cost = Mock(return_value=0.01)
```

### Pattern 3: Create ExtractionResult

```python
from inkwell.extraction.models import ExtractedContent, ExtractionResult

# Create nested content model first
content = ExtractedContent(
    template_name="summary",
    content="The actual content",  # str or dict
    metadata={},
)

# Create result with nested content
result = ExtractionResult(
    episode_url="https://example.com/ep1",
    template_name="summary",
    success=True,
    extracted_content=content,  # Nested model
    cost_usd=0.01,
    provider="gemini",
)

# Access content
assert result.extracted_content.content == "The actual content"
```

### Pattern 4: Reusable Fixture

```python
# Add to conftest.py
@pytest.fixture
def mock_gemini_extractor():
    mock = MagicMock()
    mock.extract = AsyncMock(return_value="Default output")
    mock.estimate_cost = Mock(return_value=0.01)
    return mock

# Use in test
@pytest.mark.asyncio
async def test_something(mock_gemini_extractor):
    # Override if needed
    mock_gemini_extractor.extract.return_value = "Custom"

    result = await mock_gemini_extractor.extract(...)
    assert result == "Custom"
```

## Specific File Fixes

### test_extraction_summary.py (lines 296-302)

**BEFORE:**
```python
async def mock_extract(template, transcript, metadata):
    if template.expected_format == "json":
        return '{"quotes": []}'
    return "Test output"

engine.gemini_extractor.extract = mock_extract  # WRONG
engine.gemini_extractor.estimate_cost = lambda t, l: 0.01  # WRONG
```

**AFTER:**
```python
async def mock_extract(template, transcript, metadata):
    if template.expected_format == "json":
        return '{"quotes": []}'
    return "Test output"

engine.gemini_extractor.extract = AsyncMock(side_effect=mock_extract)  # RIGHT
engine.gemini_extractor.estimate_cost = Mock(return_value=0.01)  # RIGHT
```

### test_output_manager.py - Field Access

**BEFORE:**
```python
assert result.content == "expected"
```

**AFTER:**
```python
assert result.extracted_content.content == "expected"
```

### test_output_manager.py - ExtractedContent Creation

**BEFORE:**
```python
ExtractionResult(
    ...,
    extracted_content={
        'format': 'text',
        'data': 'content',
    },
)
```

**AFTER:**
```python
ExtractionResult(
    ...,
    extracted_content=ExtractedContent(
        template_name="summary",
        content="content",
    ),
)
```

## Import Checklist

```python
# For async tests
import pytest
from unittest.mock import AsyncMock, Mock, MagicMock, patch

# For Pydantic models
from inkwell.extraction.models import (
    ExtractedContent,
    ExtractionResult,
    ExtractionTemplate,
)
from pydantic import ValidationError  # For testing validation

# Async test decorator
@pytest.mark.asyncio
async def test_something():
    ...
```

## Verification Commands

```bash
# Run single failing test with full output
uv run pytest tests/unit/test_extraction_summary.py::TestExtractionEngineWithSummary::test_extract_all_returns_tuple -v

# Run all extraction engine tests
uv run pytest tests/unit/test_extraction_engine.py -v

# Run all tests with AsyncMock issues
uv run pytest tests/unit/test_extraction*.py -v

# Check for remaining failures
uv run pytest tests/ -v --tb=no | grep FAILED
```

## Common Mistakes Summary

| Mistake | Symptom | Fix |
|---------|---------|-----|
| `mock.method = lambda: x` | "can't be used in 'await'" | `mock.method = AsyncMock(return_value=x)` |
| `mock.method = async_fn` | "can't be used in 'await'" | `mock.method = AsyncMock(side_effect=async_fn)` |
| `result.content` | "has no attribute 'content'" | `result.extracted_content.content` |
| `ExtractedContent({...})` | "ValidationError" | `ExtractedContent(template_name=..., content=...)` |
| `Mock()` for async method | "can't be used in 'await'" | `AsyncMock()` for async methods |
| Version check `'0.1.0'` | "assert '0.1.0' in ..." | Update to `'1.0.0'` |

## Testing AsyncMock Behavior

```python
# Verify AsyncMock is configured correctly
mock = AsyncMock(return_value="test")
assert inspect.iscoroutinefunction(mock)  # Should be True

# Verify it can be awaited
result = await mock()
assert result == "test"

# Verify call tracking
mock.assert_awaited_once()

# Verify arguments
mock.assert_awaited_with()
```

## Related Files

- **Full research doc:** `/Users/sergio/projects/inkwell-cli/docs/research/pytest-async-testing-patterns.md`
- **Test conftest:** `/Users/sergio/projects/inkwell-cli/tests/conftest.py`
- **Extraction models:** `/Users/sergio/projects/inkwell-cli/src/inkwell/extraction/models.py`
