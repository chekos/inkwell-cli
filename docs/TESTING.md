# Testing Guide

Comprehensive testing documentation for Inkwell CLI.

## Table of Contents

1. [Overview](#overview)
2. [Running Tests](#running-tests)
3. [Test Organization](#test-organization)
4. [Writing Tests](#writing-tests)
5. [Test Coverage](#test-coverage)
6. [CI/CD Integration](#cicd-integration)

## Overview

Inkwell uses a comprehensive testing strategy with 150+ tests across unit and integration levels.

### Test Pyramid

```
         /\
        /E2\     E2E Tests (CLI integration)
       /────\
      / INT  \   Integration Tests (component boundaries)
     /────────\
    /   UNIT   \ Unit Tests (individual components)
   /────────────\
```

### Testing Principles

1. **Fast feedback:** All tests run in seconds
2. **High coverage:** >90% line coverage for critical paths
3. **Integration focus:** Real component instances with mocked externals
4. **Maintainability:** Clear, focused, well-documented tests

## Running Tests

### Prerequisites

Install dev dependencies:
```bash
uv sync --dev
```

### All Tests

Run the complete test suite:
```bash
uv run pytest
```

### Specific Test File

```bash
uv run pytest tests/unit/test_extraction_engine.py
```

### Specific Test

```bash
uv run pytest tests/unit/test_extraction_engine.py::test_extract_all_processes_multiple_templates
```

### With Coverage

```bash
uv run pytest --cov=src/inkwell --cov-report=html
```

Open `htmlcov/index.html` to view coverage report.

### Watch Mode

For TDD workflow:
```bash
uv run pytest-watch
```

### Verbose Output

```bash
uv run pytest -v --tb=short
```

### Fast Fail

Stop on first failure:
```bash
uv run pytest -x
```

## Test Organization

```
tests/
├── conftest.py              # Shared fixtures
├── fixtures/                # Test data
│   └── sample_transcript.txt
├── unit/                    # Component tests
│   ├── test_config_*.py     # Configuration (Phase 1)
│   ├── test_feeds_*.py      # Feed management (Phase 1)
│   ├── transcription/       # Transcription (Phase 2)
│   │   ├── test_youtube.py
│   │   ├── test_gemini.py
│   │   └── test_manager.py
│   ├── test_extraction_*.py # Extraction (Phase 3)
│   └── test_output_*.py     # Output (Phase 3)
└── integration/             # Cross-component tests
    ├── test_cli.py          # CLI commands
    └── test_e2e_extraction.py # Pipeline integration
```

## Writing Tests

### Test Structure

Follow the Arrange-Act-Assert pattern:

```python
def test_extraction_caches_result(tmp_path):
    # Arrange
    cache = ExtractionCache(cache_dir=tmp_path)
    template = ExtractionTemplate(name="test", version=1, ...)
    transcript = "Sample transcript"

    # Act
    cache.set("test", 1, transcript, "output")
    result = cache.get("test", 1, transcript)

    # Assert
    assert result == "output"
```

### Naming Conventions

- **Test files:** `test_<module>.py`
- **Test classes:** `Test<Component>`
- **Test functions:** `test_<behavior>`

Examples:
```python
# Good
def test_cache_hit_returns_cached_result()
def test_invalid_json_raises_parse_error()

# Bad
def test_cache()  # Too vague
def test_1()      # Not descriptive
```

### Fixtures

Use pytest fixtures for reusable test data:

```python
@pytest.fixture
def sample_transcript():
    """Sample podcast transcript."""
    return "Welcome to the show..."

@pytest.fixture
def temp_output_dir(tmp_path):
    """Temporary output directory."""
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    return output_dir
```

### Async Tests

Use `pytest-asyncio` for async code:

```python
@pytest.mark.asyncio
async def test_concurrent_extraction():
    """Test async extraction."""
    extractor = GeminiExtractor(api_key="test")
    result = await extractor.extract(template, transcript, metadata)
    assert result is not None
```

### Mocking

#### Mock External APIs

```python
from unittest.mock import AsyncMock, Mock, patch

@pytest.mark.asyncio
async def test_claude_extraction():
    with patch("anthropic.AsyncAnthropic") as mock_client:
        mock_message = Mock(
            content=[Mock(text='{"result": "test"}')],
            usage=Mock(input_tokens=100, output_tokens=50)
        )
        mock_client.return_value.messages.create = AsyncMock(
            return_value=mock_message
        )

        extractor = ClaudeExtractor(api_key="test")
        result = await extractor.extract(template, transcript, metadata)
        assert result == '{"result": "test"}'
```

#### Use Real Components

Prefer real instances over mocks for internal components:

```python
# Good - real components, mocked externals
def test_output_manager_writes_files(tmp_path):
    manager = OutputManager(base_output_dir=tmp_path)  # Real
    generator = MarkdownGenerator()  # Real
    # ... test real integration

# Avoid - mocking internal components
def test_output_manager_calls_generator():
    manager = Mock()  # Don't mock internal components
```

### Error Testing

Test error scenarios comprehensively:

```python
@pytest.mark.asyncio
async def test_api_rate_limit_error():
    """Test handling of rate limit errors."""
    with patch("google.generativeai.GenerativeModel") as mock_model:
        mock_model.return_value.generate_content_async = AsyncMock(
            side_effect=Exception("429: Rate limit exceeded")
        )

        extractor = GeminiExtractor(api_key="test")
        with pytest.raises(ProviderError) as exc_info:
            await extractor.extract(template, transcript, metadata)

        assert "rate limit" in str(exc_info.value).lower()
```

### Parametrized Tests

Test multiple scenarios efficiently:

```python
@pytest.mark.parametrize("category,expected_templates", [
    ("tech", ["summary", "tools-mentioned"]),
    ("interview", ["summary", "quotes"]),
    ("general", ["summary", "key-concepts"]),
])
def test_template_selection_by_category(category, expected_templates):
    """Test template selection for different categories."""
    selector = TemplateSelector(loader)
    templates = selector.select_templates(category=category)
    template_names = [t.name for t in templates]

    for expected in expected_templates:
        assert expected in template_names
```

## Test Coverage

### Current Coverage

Phase 3 extraction pipeline:

| Component | Tests | Line Coverage | Branch Coverage |
|-----------|-------|---------------|-----------------|
| Extractors | 40 | 95% | 90% |
| Engine | 52 | 98% | 95% |
| Templates | 25 | 92% | 85% |
| Output | 72 | 96% | 92% |
| Cache | 18 | 100% | 100% |

### Coverage Goals

- **Critical paths:** 95%+ line coverage
- **Business logic:** 90%+ branch coverage
- **Error handling:** 85%+ coverage
- **Happy paths:** 100% coverage

### Generate Coverage Report

```bash
uv run pytest --cov=src/inkwell --cov-report=html --cov-report=term
```

View report:
```bash
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
```

### Coverage by Component

```bash
# Extraction pipeline only
uv run pytest --cov=src/inkwell/extraction tests/unit/test_extraction_*

# Output system only
uv run pytest --cov=src/inkwell/output tests/unit/test_output_*
```

## Test Categories

### Unit Tests

**Purpose:** Test individual components in isolation

**Location:** `tests/unit/`

**Characteristics:**
- Fast (<5s total)
- Isolated (no shared state)
- Mocked externals (APIs, file I/O)
- Focused (one component per test)

**Example:**
```python
def test_cache_hit():
    """Cache returns stored value."""
    cache = ExtractionCache(cache_dir=tmp_path)
    cache.set("key", "value")
    assert cache.get("key") == "value"
```

### Integration Tests

**Purpose:** Test component interactions

**Location:** `tests/integration/`

**Characteristics:**
- Real components
- Mocked external dependencies
- Test data flow
- Validate error propagation

**Example:**
```python
async def test_engine_uses_cache():
    """Engine checks cache before calling extractor."""
    engine = ExtractionEngine(extractors=[extractor], cache=cache)
    # First call - should hit extractor
    await engine.extract(template, transcript, metadata)
    # Second call - should hit cache
    result = await engine.extract(template, transcript, metadata)
    assert result.provider == "cache"
```

### E2E Tests

**Purpose:** Test complete user workflows

**Location:** `tests/integration/test_cli.py`

**Characteristics:**
- CLI command execution
- Real file I/O (temp dirs)
- User-facing scenarios
- End-to-end flows

**Example:**
```python
def test_fetch_command_creates_output():
    """Fetch command creates markdown output."""
    result = runner.invoke(app, [
        "fetch", "https://youtube.com/watch?v=test",
        "--output", str(tmp_path)
    ])
    assert result.exit_code == 0
    assert (tmp_path / "episode-name").exists()
```

## CI/CD Integration

### Pre-commit Hooks

Install hooks:
```bash
pre-commit install
```

Hooks run:
- Linter (ruff)
- Type checker (mypy)
- Tests (pytest)

### GitHub Actions (Future)

```yaml
name: Test

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          pip install uv
          uv sync --dev
      - name: Run tests
        run: uv run pytest --cov --cov-report=xml
      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

## Debugging Tests

### Print Debug Info

```python
def test_extraction(caplog):
    """Test with logging output."""
    with caplog.at_level(logging.DEBUG):
        extractor.extract(...)

    print(caplog.text)  # View logs
```

### Interactive Debugging

```python
def test_something():
    # ... test code
    import pdb; pdb.set_trace()  # Breakpoint
    # ... continue
```

### Verbose Failures

```bash
uv run pytest -vv --tb=long
```

### Keep Test Files

```bash
uv run pytest --basetemp=./test-output
```

## Best Practices

### Do's

✅ **Test behavior, not implementation**
```python
# Good - tests behavior
def test_extraction_returns_valid_markdown():
    result = extract(...)
    assert "# Summary" in result

# Bad - tests implementation
def test_extraction_calls_api():
    assert mock_api.called
```

✅ **Use descriptive test names**
```python
# Good
def test_cache_invalidated_when_template_version_changes()

# Bad
def test_cache_2()
```

✅ **One assertion concept per test**
```python
# Good
def test_cache_hit_returns_value():
    assert cache.get("key") == "value"

def test_cache_miss_returns_none():
    assert cache.get("missing") is None

# Avoid
def test_cache():
    assert cache.get("key") == "value"
    assert cache.get("missing") is None
    assert cache.get("other") == "other_value"
```

✅ **Use fixtures for setup**
```python
@pytest.fixture
def configured_engine():
    return ExtractionEngine(extractors=[], cache_dir=tmp_path)

def test_engine(configured_engine):
    # Use fixture instead of setup in test
```

### Don'ts

❌ **Don't test framework code**
```python
# Bad - tests pytest fixture
def test_tmp_path_exists(tmp_path):
    assert tmp_path.exists()
```

❌ **Don't use real API keys**
```python
# Bad - uses real API
extractor = ClaudeExtractor(api_key=os.getenv("ANTHROPIC_API_KEY"))

# Good - uses mock
with patch("anthropic.AsyncAnthropic"):
    extractor = ClaudeExtractor(api_key="test-key")
```

❌ **Don't share state between tests**
```python
# Bad - shared state
cache = Cache()

def test_1():
    cache.set("key", "value")

def test_2():
    assert cache.get("key") is None  # Fails if test_1 ran first

# Good - isolated
@pytest.fixture
def cache():
    return Cache()
```

## Troubleshooting

### Tests Pass Locally, Fail in CI

**Cause:** Environment differences

**Solution:**
- Check Python version consistency
- Verify dependency versions
- Check for file path assumptions
- Ensure temp directories used

### Slow Tests

**Cause:** Real API calls or I/O

**Solution:**
- Mock external dependencies
- Use in-memory storage
- Parallelize with pytest-xdist

### Flaky Tests

**Cause:** Race conditions or timing

**Solution:**
- Avoid sleep() in tests
- Use proper async/await
- Eliminate shared state

### Import Errors

**Cause:** Package not installed in editable mode

**Solution:**
```bash
uv pip install -e .
```

## Resources

- [pytest documentation](https://docs.pytest.org/)
- [pytest-asyncio](https://pytest-asyncio.readthedocs.io/)
- [Testing best practices](https://docs.python-guide.org/writing/tests/)
- [Coverage.py](https://coverage.readthedocs.io/)

## References

- Unit tests: `tests/unit/`
- Integration tests: `tests/integration/`
- Test fixtures: `tests/conftest.py`
- Testing strategy: `docs/devlog/2025-11-07-phase-3-unit-9-testing-strategy.md`

---

**Last updated:** 2025-11-07
