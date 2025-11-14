# Pytest Async Testing Patterns - Research Documentation

**Date:** 2025-11-13
**Author:** Claude Code
**Status:** Complete
**Related Issues:** 19 test failures in async mocking and Pydantic model changes

## Executive Summary

Research into pytest-asyncio, unittest.mock.AsyncMock, and Pydantic V2 testing patterns to resolve 19 test failures in the Inkwell CLI project. The primary issues are:

1. **AsyncMock vs MagicMock confusion** - Using regular functions/lambdas instead of AsyncMock for async methods
2. **Pydantic V2 field changes** - Tests using deprecated field access patterns (`.content` instead of `.extracted_content.content`)
3. **Test fixture patterns** - Need for reusable async mock fixtures

## Environment Details

- **Python Version:** 3.13.1
- **pytest:** 8.4.2
- **pytest-asyncio:** 1.2.0 (supports async fixtures with scope)
- **Pydantic:** 2.12.4
- **Test Mode:** `asyncio_mode = "auto"` (configured in pyproject.toml)

## Problem Analysis

### Issue 1: "object MagicMock can't be used in 'await' expression"

**Root Cause:** Using regular Python functions or lambda functions for methods that will be awaited.

**Example from test_extraction_summary.py (line 302):**
```python
# WRONG - lambda returns a value, not a coroutine
engine.gemini_extractor.estimate_cost = lambda t, l: 0.01

# WRONG - regular function assigned, but extract() is awaited
async def mock_extract(template, transcript, metadata):
    return "Test output"
engine.gemini_extractor.extract = mock_extract  # Problem: direct assignment
```

**Why it fails:**
When you assign a coroutine function directly to a mock attribute, you're replacing the mock with the function object itself. When the code tries to call it, it gets a coroutine object, but the mock framework doesn't know how to handle it properly in all contexts.

### Issue 2: Pydantic Field Access Changes

**Root Cause:** ExtractionResult model changed structure. Old code accessed `.content` directly; new model has `.extracted_content.content`.

**Example from test_output_manager.py:**
```python
# OLD PATTERN (fails):
result.content  # AttributeError: 'ExtractionResult' object has no attribute 'content'

# NEW PATTERN (correct):
result.extracted_content.content  # Access through extracted_content field
```

**Model structure:**
```python
class ExtractionResult(BaseModel):
    episode_url: str
    template_name: str
    success: bool
    extracted_content: ExtractedContent | None  # Nested model
    # ... other fields

class ExtractedContent(BaseModel):
    template_name: str
    content: str | dict[str, Any]  # The actual content is here
    # ... other fields
```

### Issue 3: ValidationError from Old Dict Format

**Root Cause:** Tests creating ExtractedContent with old dictionary format that's missing required fields.

**Error from test_output_manager.py:**
```
ValidationError: 2 validation errors for ExtractedContent
template_name
  Field required [type=missing, input_value={'format': 'text', 'data'...}, input_type=dict]
content
  Field required [type=missing, input_value={'format': 'text', 'data'...}, input_type=dict]
```

## Official Documentation Findings

### 1. Python unittest.mock.AsyncMock Documentation

**Source:** https://docs.python.org/3/library/unittest.mock.html

#### Key Concepts

**AsyncMock Behavior:**
> "An asynchronous version of MagicMock. The AsyncMock object will behave so the object is recognized as an async function, and the result of a call is an awaitable."

**Critical Distinction:**
- Calling an AsyncMock returns a coroutine object
- The coroutine must be awaited to get the actual return value
- `return_value` and `side_effect` are evaluated AFTER the await

**Example from official docs:**
```python
mock = AsyncMock()
async def main():
    await mock()

asyncio.run(main())
mock.assert_awaited_once()
```

#### Return Values and Side Effects

**For AsyncMock:**
```python
# Setting return value
mock = AsyncMock(return_value='result')
result = await mock()  # Returns 'result'

# Using side_effect for sequence
mock = AsyncMock(side_effect=[1, 2, 3])
await mock()  # Returns 1
await mock()  # Returns 2
await mock()  # Returns 3

# Using side_effect as async function
async def side_effect_func(*args, **kwargs):
    return "computed_value"

mock = AsyncMock(side_effect=side_effect_func)
result = await mock()  # Returns "computed_value"
```

#### Common Pitfall: Calling vs Awaiting

**From official docs:**
```python
mock = AsyncMock()
async def main(coroutine_mock):
    await coroutine_mock

coroutine_mock = mock()
mock.called  # True - the mock was called
mock.assert_awaited()  # Raises AssertionError - NOT awaited yet
```

The mock tracks calls and awaits **separately**.

#### Assertion Methods for AsyncMock

AsyncMock provides await-specific assertions:
- `assert_awaited()` - Verify awaited at least once
- `assert_awaited_once()` - Verify exactly one await
- `assert_awaited_with()` - Verify last await with specific arguments
- `assert_awaited_once_with()` - Verify single await with arguments
- `assert_any_await()` - Verify awaited with given arguments at any point
- `assert_has_awaits()` - Verify specific sequence of awaits
- `assert_not_awaited()` - Verify never awaited

### 2. Pytest-Asyncio Best Practices

**Source:** https://tonybaloney.github.io/posts/async-test-patterns-for-pytest-and-unittest.html

#### Pattern 1: Async Test Functions

```python
import pytest

@pytest.mark.asyncio
async def test_an_async_function():
    result = await call_to_my_async_function()
    assert result == 'expected'
```

**Critical Warning from docs:**
> "If you just add `async` before your test methods without the marker, Pytest won't await them and they'll pass regardless!!"

#### Pattern 2: Async Fixtures

```python
from httpx import AsyncClient
import pytest

@pytest.fixture
async def async_app_client():
    async with AsyncClient(app=app, base_url='http://test') as client:
        yield client
```

This ensures proper resource cleanup after each test.

#### Pattern 3: Async Mocks

**The key pattern from the docs:**
```python
from unittest.mock import AsyncMock

@pytest.fixture
def mock_extractor():
    mock = AsyncMock()
    mock.extract = AsyncMock(return_value="fake_data")
    mock.estimate_cost = AsyncMock(return_value=0.01)
    return mock

@pytest.mark.asyncio
async def test_with_async_mock(mock_extractor):
    result = await mock_extractor.extract()
    assert result == "fake_data"
```

**Critical insight:** Even methods like `estimate_cost` that return simple values must be AsyncMock if they might be awaited.

### 3. Pytest-Asyncio 1.2.0 Modern Features

**Source:** https://articles.mergify.com/pytest-asyncio-2/

#### Async Fixture Scope (New in 0.23.0+)

Since pytest-asyncio 0.23.0, you can pass scope directly to the asyncio mark:

```python
@pytest.mark.asyncio(scope="module")
async def test_module_scoped():
    # Event loop persists for entire module
    pass
```

#### Cleanup Patterns

**Yield-based cleanup (recommended):**
```python
@pytest.fixture
async def async_resource():
    # Setup
    resource = await create_resource()

    yield resource

    # Cleanup - runs after test completes
    await resource.cleanup()
```

**Factory pattern with cleanup:**
```python
@pytest.fixture
def make_async_client(request):
    clients = []

    async def _make_client():
        client = AsyncClient()
        clients.append(client)
        return client

    yield _make_client

    # Cleanup all created clients
    for client in clients:
        request.addfinalizer(lambda: client.close())
```

### 4. Pydantic V2 Migration Patterns

**Source:** https://docs.pydantic.dev/latest/migration/

#### ValidationError Changes

**Key change in Pydantic V2:**
> "In Pydantic V2, when a TypeError is raised in a validator, it is no longer converted into a ValidationError."

Previously, calling functions with incorrect signatures in validators would produce user-facing ValidationErrors. Now, TypeErrors propagate naturally.

#### Required vs Optional Fields

**Major breaking change in Pydantic V2:**

```python
# Required fields
f1: str              # Required, cannot be None
f2: str | None       # Required, can be None (BREAKING CHANGE!)

# Optional fields (with defaults)
f3: str | None = None   # Optional, defaults to None
f4: str = 'default'     # Optional, cannot be None
```

**Critical insight from docs:**
> "A field annotated as `typing.Optional[T]` will be required, and will allow for a value of `None`. It does not mean that the field has a default value of `None`."

#### Testing Strategies for Model Changes

1. **Use TypeAdapter for validation testing:**
```python
from pydantic import TypeAdapter

adapter = TypeAdapter(MyModel)
result = adapter.validate_python(data_dict)
```

2. **Test both old and new field patterns during migration:**
```python
def test_model_accepts_new_format():
    # New format with nested structure
    result = ExtractionResult(
        episode_url="...",
        template_name="summary",
        success=True,
        extracted_content=ExtractedContent(
            template_name="summary",
            content="...",
        ),
    )
    assert result.extracted_content.content == "..."

def test_model_validation_catches_old_format():
    # Old format should raise ValidationError
    with pytest.raises(ValidationError):
        ExtractedContent(
            format="text",  # Old field
            data="...",      # Old field
            raw="...",       # Old field
        )
```

## Solutions for Specific Test Failures

### Solution 1: Fix AsyncMock in test_extraction_summary.py

**Problem:** Line 302 uses lambda for estimate_cost, line 296 assigns coroutine function directly

**Fix:**
```python
# BEFORE (line 296-302):
async def mock_extract(template, transcript, metadata):
    if template.expected_format == "json":
        return '{"quotes": []}'
    return "Test output"

engine.gemini_extractor.extract = mock_extract
engine.gemini_extractor.estimate_cost = lambda t, l: 0.01

# AFTER:
# Option A - Use AsyncMock with side_effect
async def mock_extract_side_effect(template, transcript, metadata):
    if template.expected_format == "json":
        return '{"quotes": []}'
    return "Test output"

engine.gemini_extractor.extract = AsyncMock(side_effect=mock_extract_side_effect)
engine.gemini_extractor.estimate_cost = Mock(return_value=0.01)  # Sync method

# Option B - Create properly configured AsyncMock
engine.gemini_extractor.extract = AsyncMock(return_value="Test output")
engine.gemini_extractor.estimate_cost = Mock(return_value=0.01)
```

**Why this works:**
- `AsyncMock(side_effect=...)` wraps the coroutine function properly
- `Mock(return_value=...)` is used for synchronous methods like `estimate_cost`
- The mock framework can now properly handle await expressions

### Solution 2: Fix Pydantic Field Access

**Problem:** Tests accessing `.content` directly on ExtractionResult

**Fix:**
```python
# BEFORE:
assert result.content == "expected"

# AFTER:
assert result.extracted_content.content == "expected"
```

**Locations to fix:**
- test_output_manager.py - Multiple assertions

### Solution 3: Create Reusable Async Mock Fixtures

**Add to conftest.py or test file:**
```python
@pytest.fixture
def mock_gemini_extractor():
    """Create properly configured mock Gemini extractor."""
    mock = MagicMock()
    # Async method - must be AsyncMock
    mock.extract = AsyncMock(return_value="Default output")
    # Sync method - use Mock or direct return
    mock.estimate_cost = Mock(return_value=0.01)
    return mock

@pytest.fixture
def mock_claude_extractor():
    """Create properly configured mock Claude extractor."""
    mock = MagicMock()
    mock.extract = AsyncMock(return_value="Default output")
    mock.estimate_cost = Mock(return_value=0.02)
    return mock

# Usage in tests:
@pytest.mark.asyncio
async def test_with_fixture(mock_gemini_extractor):
    # Override default return value if needed
    mock_gemini_extractor.extract.return_value = "Custom output"

    result = await mock_gemini_extractor.extract(template, transcript, metadata)
    assert result == "Custom output"
```

### Solution 4: Fix ExtractedContent Creation in Tests

**Problem:** Tests creating ExtractedContent with old dict format

**Fix:**
```python
# BEFORE (old format):
content = {
    'format': 'text',
    'data': 'Unicode ™',
    'raw': '...',
}
result = ExtractionResult(
    ...,
    extracted_content=content,  # Fails validation
)

# AFTER (new format):
content = ExtractedContent(
    template_name="summary",
    content="Unicode ™",  # Direct content, not wrapped in dict
    metadata={},
)
result = ExtractionResult(
    ...,
    extracted_content=content,
)
```

### Solution 5: Fix Cost Estimation Mock Issues

**Problem:** test_extraction_engine.py - estimate_cost returns MagicMock instead of number

**From test output:**
```
assert <MagicMock name='ClaudeExtractor().estimate_cost().__radd__()' id='4477742320'> == 0.02
```

**Fix:**
```python
# BEFORE:
engine.gemini_extractor.estimate_cost = Mock(return_value=0.01)
# ... but somewhere the mock is being called incorrectly

# AFTER - Ensure estimate_cost is a simple Mock, not AsyncMock:
with patch("inkwell.extraction.engine.ClaudeExtractor") as mock_claude_class:
    with patch("inkwell.extraction.engine.GeminiExtractor") as mock_gemini_class:
        # Create instances
        mock_claude = mock_claude_class.return_value
        mock_gemini = mock_gemini_class.return_value

        # Configure as regular functions (NOT async)
        mock_claude.estimate_cost = Mock(return_value=0.02)
        mock_gemini.estimate_cost = Mock(return_value=0.01)

        # Configure extract as AsyncMock
        mock_claude.extract = AsyncMock(return_value="output")
        mock_gemini.extract = AsyncMock(return_value="output")

        engine = ExtractionEngine()
        # Now engine.claude_extractor and engine.gemini_extractor are properly mocked
```

### Solution 6: Fix Version Test

**Problem:** test_cli.py::test_version_command expects '0.1.0' but gets 'v1.0.0'

**Fix:**
```python
# BEFORE:
assert '0.1.0' in result.stdout

# AFTER:
assert '1.0.0' in result.stdout
# or more flexible:
assert 'Inkwell CLI v1.0.0' in result.stdout
```

## Testing Patterns Summary

### Pattern 1: Mock Async Methods

```python
# For async methods that will be awaited:
mock.async_method = AsyncMock(return_value="value")

# For sync methods:
mock.sync_method = Mock(return_value="value")

# For methods with complex behavior:
async def side_effect_func(*args, **kwargs):
    # Custom logic here
    return computed_value

mock.async_method = AsyncMock(side_effect=side_effect_func)
```

### Pattern 2: Test Async Functions

```python
@pytest.mark.asyncio
async def test_something():
    result = await async_function()
    assert result == expected
```

### Pattern 3: Create Pydantic Models in Tests

```python
# Always use explicit model construction
content = ExtractedContent(
    template_name="summary",
    content="The actual content",  # str or dict
    metadata={},  # optional
)

result = ExtractionResult(
    episode_url="https://...",
    template_name="summary",
    success=True,
    extracted_content=content,
    cost_usd=0.01,
    provider="gemini",
)
```

### Pattern 4: Test Pydantic Validation

```python
def test_validation_error():
    with pytest.raises(ValidationError) as exc_info:
        ExtractedContent(
            # Missing required fields
            metadata={},
        )

    errors = exc_info.value.errors()
    assert len(errors) == 2  # template_name and content missing
    assert {e['loc'][0] for e in errors} == {'template_name', 'content'}
```

## Checklist for Fixing Tests

### AsyncMock Issues (13 failures)

- [ ] test_extraction_engine.py - Use AsyncMock for extract(), Mock for estimate_cost()
- [ ] test_extraction_summary.py::test_extract_all_returns_tuple - Fix lambda and function assignment
- [ ] test_extraction_summary.py::test_extract_all_tracks_cached_results - Same fix
- [ ] test_claude_extractor.py - Verify AsyncMock usage
- [ ] test_gemini_extractor.py - Verify AsyncMock usage
- [ ] test_markdown_generator.py - Check if uses async mocks
- [ ] test_output_manager.py - Check if uses async mocks

### Pydantic Field Changes (4 failures)

- [ ] test_output_manager.py::test_write_episode_overwrite_true_replaces - Change `.content` to `.extracted_content.content`
- [ ] test_output_manager.py::test_write_episode_unicode_content - Fix ExtractedContent creation
- [ ] test_output_manager.py::test_write_episode_calculates_cost - Check field access
- [ ] test_output_manager.py::test_get_statistics_with_episodes - Check field access

### Other Issues (2 failures)

- [ ] test_cli.py::test_version_command - Update version assertion
- [ ] test_interview/test_manager.py::test_create_manager_no_api_key_raises - Check API key validation

## Code Examples for Common Scenarios

### Example 1: Testing Extract Method with Different Templates

```python
@pytest.mark.asyncio
async def test_extract_handles_multiple_templates():
    with patch("inkwell.extraction.engine.ClaudeExtractor"), \
         patch("inkwell.extraction.engine.GeminiExtractor"):

        engine = ExtractionEngine()

        # Create side effect function for template-specific responses
        async def mock_extract_side_effect(template, transcript, metadata):
            if template.name == "summary":
                return "Episode summary text"
            elif template.name == "quotes":
                return '{"quotes": [{"text": "quote", "speaker": "John"}]}'
            else:
                return "Default response"

        # Configure mocks properly
        engine.gemini_extractor.extract = AsyncMock(
            side_effect=mock_extract_side_effect
        )
        engine.gemini_extractor.estimate_cost = Mock(return_value=0.01)

        # Test with summary template
        summary_result = await engine.extract(
            template=summary_template,
            transcript="test",
            metadata={},
        )

        assert summary_result.extracted_content.content == "Episode summary text"

        # Test with quotes template
        quotes_result = await engine.extract(
            template=quotes_template,
            transcript="test",
            metadata={},
        )

        assert quotes_result.extracted_content.content == {
            "quotes": [{"text": "quote", "speaker": "John"}]
        }
```

### Example 2: Testing Cache Behavior

```python
@pytest.mark.asyncio
async def test_cache_reduces_api_calls():
    with patch("inkwell.extraction.engine.GeminiExtractor") as mock_extractor_class:
        mock_extractor = mock_extractor_class.return_value

        # Use call_count to verify caching
        mock_extractor.extract = AsyncMock(return_value="Cached result")
        mock_extractor.estimate_cost = Mock(return_value=0.01)

        engine = ExtractionEngine(cache=temp_cache)

        # First call - should hit API
        result1 = await engine.extract(template, transcript, metadata)
        assert mock_extractor.extract.call_count == 1
        assert result1.from_cache is False

        # Second call - should use cache
        result2 = await engine.extract(template, transcript, metadata)
        assert mock_extractor.extract.call_count == 1  # Not called again!
        assert result2.from_cache is True
        assert result2.cost_usd == 0.0  # Cached results are free
```

### Example 3: Testing Error Handling

```python
@pytest.mark.asyncio
async def test_extract_handles_api_errors():
    with patch("inkwell.extraction.engine.GeminiExtractor") as mock_extractor_class:
        mock_extractor = mock_extractor_class.return_value

        # First call succeeds, second fails
        mock_extractor.extract = AsyncMock(
            side_effect=[
                "Success",
                Exception("API rate limit exceeded"),
            ]
        )
        mock_extractor.estimate_cost = Mock(return_value=0.01)

        engine = ExtractionEngine()

        # First extraction succeeds
        result1 = await engine.extract(template1, transcript, metadata)
        assert result1.success is True

        # Second extraction fails gracefully
        result2 = await engine.extract(template2, transcript, metadata)
        assert result2.success is False
        assert "API rate limit" in result2.error
```

## References

### Official Documentation

1. **Python unittest.mock**
   - Main docs: https://docs.python.org/3/library/unittest.mock.html
   - AsyncMock section: Search for "AsyncMock" in docs
   - Examples: https://docs.python.org/3/library/unittest.mock-examples.html

2. **pytest-asyncio**
   - PyPI: https://pypi.org/project/pytest-asyncio/
   - GitHub: https://github.com/pytest-dev/pytest-asyncio
   - Version 1.2.0 supports: async fixtures, configurable event loop scope

3. **Pydantic V2 Migration**
   - Official migration guide: https://docs.pydantic.dev/latest/migration/
   - ValidationError: https://docs.pydantic.dev/latest/errors/errors/
   - Field validators: https://docs.pydantic.dev/latest/concepts/validators/

### Community Resources

4. **Async Test Patterns for Pytest**
   - Author: Tony Baloney
   - URL: https://tonybaloney.github.io/posts/async-test-patterns-for-pytest-and-unittest.html
   - Excellent practical patterns for async testing

5. **BBC CloudFit - Unit Testing Python Asyncio Code**
   - URL: https://bbc.github.io/cloudfit-public-docs/asyncio/testing.html
   - Enterprise patterns for async testing

6. **Pytest with Eric - Pytest-Asyncio Guide**
   - URL: https://pytest-with-eric.com/pytest-advanced/pytest-asyncio/
   - Comprehensive tutorial with examples

### Package Versions (Current Project)

- Python: 3.13.1
- pytest: 8.4.2
- pytest-asyncio: 1.2.0
- pydantic: 2.12.4
- pydantic-core: 2.41.5

## Next Steps

1. **Create shared test fixtures** - Add async mock fixtures to conftest.py
2. **Fix AsyncMock issues systematically** - Start with test_extraction_engine.py
3. **Update Pydantic model access** - Use `.extracted_content.content` pattern
4. **Add regression tests** - Ensure AsyncMock patterns are preserved
5. **Document patterns in contributing guide** - Help future developers avoid these issues

## Lessons Learned

1. **AsyncMock is not optional** - Any method that might be awaited MUST be AsyncMock
2. **Lambda functions break async** - Never use lambda for methods that will be awaited
3. **Direct coroutine assignment fails** - Always wrap in AsyncMock
4. **Pydantic V2 breaks `.content` access** - Must access nested fields explicitly
5. **Mock configuration order matters** - Configure mocks before creating objects that use them
6. **pytest-asyncio auto mode helps** - `asyncio_mode = "auto"` reduces boilerplate
7. **Fixture scope matters for performance** - Use module scope for expensive setup

## Open Questions

1. Should we create a custom pytest plugin for common async mock patterns?
2. Should we add mypy strict mode to catch these issues at type-check time?
3. Should we refactor ExtractedContent to use discriminated unions (as noted in tech debt comment)?
4. Should we add pre-commit hook to check for lambda usage in test mocks?

---

**Document Status:** Complete and ready for implementation
**Reviewed By:** N/A
**Last Updated:** 2025-11-13
