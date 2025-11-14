# Pytest Testing Best Practices: Achieving 100% Pass Rate

**Research Date:** 2025-11-13
**Focus Areas:** Async testing, Pydantic models, test maintenance, isolation, and regression prevention

## Executive Summary

This research synthesizes best practices from official Python/pytest documentation, industry experts, and successful open-source projects. The focus is on creating maintainable, reliable test suites that consistently achieve 100% pass rates through proper async handling, test isolation, and systematic regression prevention.

---

## 1. Python Testing Best Practices

### 1.1 Pytest Fixtures and Mocking for Async Code

#### Essential Setup

**Install pytest-asyncio** (required for async test support):
```bash
uv add --dev pytest-asyncio
```

**Configure pytest-asyncio** in `pyproject.toml`:
```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"  # Automatically detect and run async tests
```

#### Async Test Pattern

```python
import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_async_function():
    """IMPORTANT: Must use @pytest.mark.asyncio marker for async tests."""
    result = await some_async_function()
    assert result == expected_value
```

**Critical Warning:** If you add `async` before test methods without the `@pytest.mark.asyncio` marker, pytest won't await them and they'll pass regardless of their actual behavior!

#### Async Fixtures

```python
import pytest
import pytest_asyncio

@pytest_asyncio.fixture
async def async_client():
    """Use pytest_asyncio.fixture for async fixtures."""
    client = AsyncClient()
    await client.connect()
    yield client  # Setup before yield, teardown after
    await client.disconnect()

@pytest.mark.asyncio
async def test_with_async_fixture(async_client):
    result = await async_client.fetch_data()
    assert result is not None
```

**Best Practice:** Use `yield` fixtures for proper setup/teardown. Code before `yield` is setup, code after `yield` is teardown.

#### AsyncMock vs Mock: Critical Differences

**When to Use AsyncMock (Python 3.8+):**

```python
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
@patch("app.api.client.fetch_data", new_callable=AsyncMock)
async def test_async_api_call(mock_fetch):
    """Use new_callable=AsyncMock for patching async functions."""
    mock_fetch.return_value = {"status": "success"}

    result = await fetch_data()

    assert result["status"] == "success"
    mock_fetch.assert_called_once()
```

**Common Pitfall #1: Using Mock Instead of AsyncMock**

```python
# WRONG - Will fail or behave unexpectedly
@patch("app.api.client.fetch_data", return_value={"data": "test"})
async def test_async_call(mock_fetch):
    result = await fetch_data()  # TypeError: object dict can't be used in 'await'
```

```python
# CORRECT - Use AsyncMock
@patch("app.api.client.fetch_data", new_callable=AsyncMock)
async def test_async_call(mock_fetch):
    mock_fetch.return_value = {"data": "test"}
    result = await fetch_data()
    assert result["data"] == "test"
```

**Common Pitfall #2: Not Awaiting AsyncMock**

```python
# WRONG
mock = AsyncMock(return_value="result")
result = mock()  # This returns a coroutine object, not "result"

# CORRECT
mock = AsyncMock(return_value="result")
result = await mock()  # Now result == "result"
```

#### Mocking Async Context Managers

```python
from unittest.mock import AsyncMock, MagicMock

@pytest_asyncio.fixture
async def mock_async_context_manager():
    """Pattern for mocking async context managers."""
    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_data)
    mock_cm.__aexit__ = AsyncMock(return_value=None)
    return mock_cm

@pytest.mark.asyncio
async def test_with_async_context_manager(mock_async_context_manager):
    async with mock_async_context_manager as data:
        assert data == mock_data
```

#### Async Extractor Pattern (Common in LLM/API Code)

```python
from unittest.mock import AsyncMock, patch

class TestAsyncExtractor:
    @pytest.mark.asyncio
    @patch("app.extractors.base.AsyncClient", new_callable=AsyncMock)
    async def test_extract_content(self, mock_client):
        """Pattern for testing async extractors."""
        # Setup mock response
        mock_response = AsyncMock()
        mock_response.json = AsyncMock(return_value={"extracted": "data"})
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(
            return_value=mock_response
        )

        # Test
        extractor = AsyncExtractor()
        result = await extractor.extract("test input")

        # Verify
        assert result["extracted"] == "data"
        mock_client.return_value.__aenter__.return_value.post.assert_called_once()
```

### 1.2 Test Organization and Naming Conventions

#### Directory Structure

```
project/
├── src/
│   └── myapp/
│       ├── __init__.py
│       ├── models.py
│       └── services.py
├── tests/
│   ├── __init__.py          # Optional but recommended for namespace isolation
│   ├── conftest.py          # Shared fixtures
│   ├── test_models.py       # Test files prefixed with test_
│   └── test_services.py
└── pyproject.toml
```

**Best Practice:** Use `__init__.py` in test folders to avoid name collisions when two tests have the same name by giving each test a unique namespace.

#### Naming Conventions (Official Pytest Standards)

**Files:**
- Prefix: `test_*.py` (preferred)
- Suffix: `*_test.py` (also supported but less common)

**Functions:**
```python
# GOOD - Descriptive, explains what and why
def test_login_with_valid_credentials_returns_true():
    pass

def test_login_with_invalid_password_raises_auth_error():
    pass

# BAD - Not descriptive enough
def test_login():
    pass

def test1():
    pass
```

**Classes:**
```python
# GOOD
class TestUserAuthentication:
    def test_valid_credentials_succeed(self):
        pass

    def test_invalid_credentials_fail(self):
        pass

# BAD - Missing Test prefix
class UserTests:  # Won't be auto-discovered
    pass
```

**Naming Pattern:** `test_<what>_<condition>_<expected_result>`

Examples:
- `test_parse_feed_with_empty_url_raises_value_error`
- `test_transcribe_audio_returns_transcript_object`
- `test_extract_quotes_with_no_content_returns_empty_list`

#### Test Organization Anti-Patterns

**Avoid:**
1. **Inconsistent naming** - Wastes time and creates confusion
2. **Flaky tests** - Tests that sometimes pass/fail erode confidence
3. **Monolithic tests** - Tests doing too much are hard to debug
4. **Order dependencies** - Tests should run independently in any order

### 1.3 Handling Async/Await in Tests with AsyncMock

#### Pattern: Testing Async Functions with Side Effects

```python
@pytest.mark.asyncio
@patch("app.services.send_notification", new_callable=AsyncMock)
async def test_process_with_side_effects(mock_notify):
    """Test async function that has side effects."""
    mock_notify.side_effect = None  # No exception

    await process_data()

    mock_notify.assert_called_once_with(expected_arg)
```

#### Pattern: Testing Async Functions that Raise Exceptions

```python
@pytest.mark.asyncio
@patch("app.services.fetch_external_data", new_callable=AsyncMock)
async def test_handles_api_timeout(mock_fetch):
    """Test that async exceptions are handled correctly."""
    mock_fetch.side_effect = TimeoutError("API timeout")

    with pytest.raises(TimeoutError):
        await fetch_and_process()
```

#### Pattern: Verifying Async Call Arguments

```python
@pytest.mark.asyncio
@patch("app.services.save_to_database", new_callable=AsyncMock)
async def test_saves_correct_data(mock_save):
    """Verify async function called with correct arguments."""
    mock_save.return_value = True

    await process_and_save({"key": "value"})

    # Verify called with exact arguments
    mock_save.assert_called_once_with({"key": "value"})

    # Or verify with partial matching
    call_args = mock_save.call_args[0][0]
    assert call_args["key"] == "value"
```

### 1.4 Pydantic Model Validation Testing

#### What to Test vs What Not to Test

**Don't Test Pydantic Itself:**
```python
# BAD - This just tests Pydantic, not your code
def test_user_model_has_email():
    user = User(email="test@example.com", name="Test")
    assert user.email == "test@example.com"  # Useless test
```

**Do Test Custom Validators:**
```python
from pydantic import BaseModel, field_validator, ValidationError

class Episode(BaseModel):
    title: str
    duration: int

    @field_validator("duration")
    @classmethod
    def validate_duration(cls, v):
        if v < 0:
            raise ValueError("Duration must be positive")
        return v

# GOOD - Tests your custom validation logic
def test_episode_rejects_negative_duration():
    """Test custom validator rejects invalid data."""
    with pytest.raises(ValidationError) as exc_info:
        Episode(title="Test", duration=-10)

    assert "Duration must be positive" in str(exc_info.value)

def test_episode_accepts_valid_duration():
    """Test custom validator accepts valid data."""
    episode = Episode(title="Test", duration=3600)
    assert episode.duration == 3600
```

#### Testing Model Field Migrations

**Pattern: Test Required vs Optional Field Changes**

```python
from pydantic import BaseModel, Field
from typing import Optional

class PodcastMetadataV1(BaseModel):
    title: str
    description: str
    # Old version - author was required
    author: str

class PodcastMetadataV2(BaseModel):
    title: str
    description: str
    # New version - author is optional with default
    author: Optional[str] = None

def test_metadata_migration_backwards_compatible():
    """Test that new model accepts old data format."""
    # Old data format with author
    old_data = {
        "title": "My Podcast",
        "description": "A great show",
        "author": "John Doe"
    }

    # Should work with new model
    metadata = PodcastMetadataV2(**old_data)
    assert metadata.author == "John Doe"

def test_metadata_migration_handles_missing_author():
    """Test that new model handles missing optional field."""
    # New data format without author
    new_data = {
        "title": "My Podcast",
        "description": "A great show"
    }

    # Should work with new model
    metadata = PodcastMetadataV2(**new_data)
    assert metadata.author is None
```

#### Pydantic V2 Migration Patterns

**V1 to V2 Validator Changes:**

```python
# OLD (Pydantic V1) - DEPRECATED
from pydantic import BaseModel, validator

class OldModel(BaseModel):
    email: str

    @validator("email")
    def validate_email(cls, v):
        if "@" not in v:
            raise ValueError("Invalid email")
        return v

# NEW (Pydantic V2) - CURRENT
from pydantic import BaseModel, field_validator

class NewModel(BaseModel):
    email: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, v):
        if "@" not in v:
            raise ValueError("Invalid email")
        return v

# Test for both during migration
def test_email_validation_works_in_new_model():
    """Verify validators work after V2 migration."""
    with pytest.raises(ValidationError) as exc_info:
        NewModel(email="invalid")

    assert "Invalid email" in str(exc_info.value)
```

---

## 2. Test Maintenance Strategies

### 2.1 Preventing Test Regression After API Changes

#### Strategy 1: Use pytest-regressions for Output Testing

```bash
uv add --dev pytest-regressions
```

```python
def test_extract_quotes_output(data_regression):
    """Regression test for quote extraction output format."""
    result = extract_quotes(sample_transcript)

    # First run: saves result to data file
    # Subsequent runs: compares against saved data
    data_regression.check(result)

# Regenerate all regression files after intentional API change
# pytest --regen-all
```

**Best Practice:** When you intentionally change API output, run `pytest --regen-all` to update baseline files, then commit them.

#### Strategy 2: Bug-Specific Regression Tests

```python
def test_regression_issue_123_duplicate_quotes():
    """
    Regression test for Issue #123.

    Bug: extract_quotes() was returning duplicate quotes when
    the same quote appeared in multiple segments.

    Fix: Added deduplication logic in extract_quotes().
    """
    transcript_with_duplicates = [
        {"text": "This is important"},
        {"text": "Some other text"},
        {"text": "This is important"},  # Duplicate
    ]

    quotes = extract_quotes(transcript_with_duplicates)

    # Verify no duplicates
    assert len(quotes) == 1
    assert quotes[0] == "This is important"
```

**Best Practice:** When fixing a bug, write a test that captures the exact failure scenario. Name it clearly with the issue number.

#### Strategy 3: Contract Testing for API Changes

```python
import pytest
from pydantic import BaseModel

class QuoteOutput(BaseModel):
    """Contract: defines expected output structure."""
    text: str
    timestamp: float
    speaker: Optional[str] = None

def test_extract_quotes_respects_contract():
    """Verify extract_quotes() output matches defined contract."""
    quotes = extract_quotes(sample_transcript)

    # This will fail if API changes break the contract
    for quote in quotes:
        validated = QuoteOutput(**quote)
        assert validated.text
        assert validated.timestamp >= 0
```

**Best Practice:** Use Pydantic models to define API contracts. Tests will fail if changes break contracts.

### 2.2 Handling Model Field Migrations in Tests

#### Migration Strategy: Add New Optional Field

```python
# Step 1: Add field as optional
class EpisodeV2(BaseModel):
    title: str
    description: str
    new_field: Optional[str] = None  # New field, optional

# Step 2: Test backwards compatibility
def test_old_data_works_with_new_model():
    old_data = {"title": "Test", "description": "Test desc"}
    episode = EpisodeV2(**old_data)
    assert episode.new_field is None

# Step 3: After migration complete, make required (if needed)
class EpisodeV3(BaseModel):
    title: str
    description: str
    new_field: str  # Now required

# Step 4: Update tests
def test_new_field_now_required():
    with pytest.raises(ValidationError):
        EpisodeV3(title="Test", description="Test desc")
```

#### Migration Strategy: Rename Field with Alias

```python
from pydantic import BaseModel, Field

class EpisodeMigrated(BaseModel):
    title: str
    # Support both old and new field names during transition
    episode_description: str = Field(alias="description")

def test_supports_old_field_name():
    """Test backward compatibility with old field name."""
    old_data = {"title": "Test", "description": "Old name"}
    episode = EpisodeMigrated(**old_data)
    assert episode.episode_description == "Old name"

def test_supports_new_field_name():
    """Test new field name works."""
    new_data = {"title": "Test", "episode_description": "New name"}
    episode = EpisodeMigrated(**new_data)
    assert episode.episode_description == "New name"
```

### 2.3 Test Isolation and Independence

#### Problem: Global State Pollution

```python
# BAD - Tests affect each other
class TestPodcastProcessor:
    processor = PodcastProcessor()  # Shared instance!

    def test_first(self):
        self.processor.add_feed("feed1")
        assert len(self.processor.feeds) == 1

    def test_second(self):
        # FAILS if test_first ran first!
        assert len(self.processor.feeds) == 0
```

```python
# GOOD - Tests are isolated
class TestPodcastProcessor:
    @pytest.fixture
    def processor(self):
        """Each test gets fresh instance."""
        return PodcastProcessor()

    def test_first(self, processor):
        processor.add_feed("feed1")
        assert len(processor.feeds) == 1

    def test_second(self, processor):
        # Always passes - fresh instance
        assert len(processor.feeds) == 0
```

#### Testing for Isolation Problems

```bash
# Install pytest-randomly to detect order dependencies
uv add --dev pytest-randomly

# Run tests in random order
pytest --randomly-seed=auto
```

**Best Practice:** Run tests with `pytest-randomly` in CI to catch hidden dependencies on execution order.

#### Fixture Scope for Proper Isolation

```python
@pytest.fixture(scope="function")  # Default - new instance per test
def function_scoped():
    return Database()

@pytest.fixture(scope="class")  # Shared across test class
def class_scoped():
    return ExpensiveResource()

@pytest.fixture(scope="module")  # Shared across test file
def module_scoped():
    return SharedConfig()

@pytest.fixture(scope="session")  # Shared across entire test session
def session_scoped():
    return TestDatabase()
```

**Best Practice:** Use `scope="function"` (default) unless you have expensive setup. Document why you use broader scopes.

#### Teardown with Yield Fixtures

```python
@pytest.fixture
def database():
    """Proper setup and teardown pattern."""
    # Setup
    db = Database()
    db.connect()

    yield db  # Test runs here

    # Teardown (always runs, even if test fails)
    db.disconnect()
    db.cleanup()

@pytest_asyncio.fixture
async def async_resource():
    """Async setup and teardown."""
    # Setup
    resource = await AsyncResource.create()

    yield resource

    # Teardown
    await resource.cleanup()
```

### 2.4 Datetime Handling in Tests (Timezone-Aware)

#### Install freezegun

```bash
uv add --dev freezegun
```

#### Pattern: Freeze Time for Consistent Tests

```python
from freezegun import freeze_time
from datetime import datetime, timezone

@freeze_time("2024-01-15 10:00:00")
def test_timestamp_generation():
    """Test with frozen time for deterministic results."""
    timestamp = generate_timestamp()
    assert timestamp == datetime(2024, 1, 15, 10, 0, 0)

@freeze_time("2024-01-15 10:00:00", tz_offset=0)  # UTC
def test_utc_timestamp():
    """Test with explicit UTC timezone."""
    timestamp = generate_utc_timestamp()
    expected = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
    assert timestamp == expected
```

#### Pattern: Test Across Timezones

```python
import pytest
from datetime import datetime
from zoneinfo import ZoneInfo
from freezegun import freeze_time

@pytest.mark.parametrize("timezone,expected_hour", [
    ("UTC", 10),
    ("America/New_York", 5),   # UTC-5 in winter
    ("Europe/London", 10),      # UTC+0 in winter
    ("Asia/Tokyo", 19),         # UTC+9
])
@freeze_time("2024-01-15 10:00:00", tz_offset=0)
def test_timezone_conversion(timezone, expected_hour):
    """Test timestamp conversion across timezones."""
    utc_time = datetime(2024, 1, 15, 10, 0, 0, tzinfo=ZoneInfo("UTC"))
    local_time = utc_time.astimezone(ZoneInfo(timezone))
    assert local_time.hour == expected_hour
```

#### Best Practices for Datetime Testing

1. **Always use timezone-aware datetimes:**
```python
# GOOD
from datetime import datetime, timezone
dt = datetime.now(timezone.utc)

# BAD
dt = datetime.now()  # Naive datetime
```

2. **Store times in UTC, display in local:**
```python
def test_episode_timestamp_storage():
    """Test that timestamps are stored in UTC."""
    episode = create_episode(title="Test")

    # Verify stored in UTC
    assert episode.created_at.tzinfo == timezone.utc

    # Convert for display
    local_time = episode.created_at.astimezone(local_tz)
```

3. **Use freezegun fixture for multiple tests:**
```python
@pytest.fixture
def frozen_time():
    """Reusable frozen time fixture."""
    with freeze_time("2024-01-15 10:00:00"):
        yield

def test_with_frozen_time(frozen_time):
    """Test uses frozen time from fixture."""
    timestamp = generate_timestamp()
    assert timestamp.day == 15
```

---

## 3. Mock Best Practices

### 3.1 When to Use Mock vs AsyncMock

#### Decision Tree

```
Is the function/method async (defined with 'async def')?
├─ YES → Use AsyncMock
│   └─ from unittest.mock import AsyncMock
│       mock = AsyncMock(return_value=result)
│       result = await mock()
│
└─ NO → Use Mock or MagicMock
    └─ from unittest.mock import Mock, MagicMock
        mock = Mock(return_value=result)
        result = mock()
```

#### Quick Reference

```python
from unittest.mock import Mock, AsyncMock, MagicMock

# Sync function
def sync_function():
    return "result"

mock_sync = Mock(return_value="result")
assert mock_sync() == "result"

# Async function
async def async_function():
    return "result"

mock_async = AsyncMock(return_value="result")
assert await mock_async() == "result"

# When you need magic methods (__len__, __iter__, etc.)
mock_with_magic = MagicMock()
mock_with_magic.__len__.return_value = 5
assert len(mock_with_magic) == 5
```

### 3.2 Common Pitfalls with MagicMock and Async

#### Pitfall 1: MagicMock Doesn't Work with Async

```python
# WRONG - MagicMock won't work with async functions
@patch("app.services.fetch_data")
async def test_async_function(mock_fetch):
    mock_fetch.return_value = "data"
    result = await fetch_data()  # TypeError!

# CORRECT - Use AsyncMock
@patch("app.services.fetch_data", new_callable=AsyncMock)
async def test_async_function(mock_fetch):
    mock_fetch.return_value = "data"
    result = await fetch_data()
    assert result == "data"
```

#### Pitfall 2: Over-Mocking

```python
# BAD - Mocking too much, tests nothing real
@patch("app.services.validate_input")
@patch("app.services.process_data")
@patch("app.services.format_output")
def test_entire_pipeline_mocked(mock_format, mock_process, mock_validate):
    """This test is useless - mocks everything."""
    mock_validate.return_value = True
    mock_process.return_value = {"data": "test"}
    mock_format.return_value = "formatted"

    result = run_pipeline()  # Only tests mocks, not real code
    assert result == "formatted"

# GOOD - Mock only external dependencies
@patch("app.services.external_api_call", new_callable=AsyncMock)
async def test_pipeline_with_real_logic(mock_api):
    """Tests real code, mocks only external dependency."""
    mock_api.return_value = {"external": "data"}

    # validate_input, process_data, format_output run for real
    result = await run_pipeline()

    # Test real business logic
    assert result["processed"] is True
    assert result["formatted_correctly"] is True
```

**Rule of Thumb:** Mock external systems (APIs, databases, file system), test your own logic.

#### Pitfall 3: Not Configuring Nested Mocks

```python
# BAD - Nested async calls not properly mocked
@patch("app.client.APIClient")
async def test_nested_calls(mock_client):
    client = APIClient()
    result = await client.fetch()  # TypeError!

# GOOD - Properly configure nested async mocks
@patch("app.client.APIClient")
async def test_nested_calls(mock_client):
    mock_instance = AsyncMock()
    mock_instance.fetch = AsyncMock(return_value={"data": "test"})
    mock_client.return_value = mock_instance

    client = APIClient()
    result = await client.fetch()
    assert result["data"] == "test"
```

### 3.3 Proper Async Extractor Mocking Patterns

#### Pattern 1: Mock LLM API Client

```python
import pytest
from unittest.mock import AsyncMock, patch

class TestQuoteExtractor:
    @pytest.mark.asyncio
    @patch("app.extractors.quotes.AnthropicClient")
    async def test_extract_quotes(self, mock_client_class):
        """Pattern for mocking LLM client in extractor."""
        # Setup mock instance
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client

        # Setup mock response
        mock_response = AsyncMock()
        mock_response.content = [
            AsyncMock(text='{"quotes": ["Quote 1", "Quote 2"]}')
        ]
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        # Test extractor
        extractor = QuoteExtractor(api_key="test")
        quotes = await extractor.extract(transcript="Test transcript")

        # Verify
        assert len(quotes) == 2
        assert "Quote 1" in quotes
        mock_client.messages.create.assert_called_once()
```

#### Pattern 2: Mock with Fixture

```python
@pytest_asyncio.fixture
async def mock_llm_client():
    """Reusable LLM client mock."""
    with patch("app.extractors.base.AnthropicClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client

        # Default response
        mock_response = AsyncMock()
        mock_response.content = [AsyncMock(text='{"result": "default"}')]
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        yield mock_client

@pytest.mark.asyncio
async def test_with_llm_fixture(mock_llm_client):
    """Test using reusable LLM mock fixture."""
    # Override response for this test
    mock_llm_client.messages.create.return_value.content[0].text = \
        '{"quotes": ["Test"]}'

    extractor = QuoteExtractor(api_key="test")
    result = await extractor.extract("transcript")
    assert "Test" in result
```

#### Pattern 3: Test Error Handling

```python
@pytest.mark.asyncio
@patch("app.extractors.quotes.AnthropicClient")
async def test_extractor_handles_api_error(mock_client_class):
    """Test extractor handles API errors gracefully."""
    mock_client = AsyncMock()
    mock_client_class.return_value = mock_client

    # Simulate API error
    mock_client.messages.create = AsyncMock(
        side_effect=Exception("API rate limit exceeded")
    )

    extractor = QuoteExtractor(api_key="test")

    with pytest.raises(Exception) as exc_info:
        await extractor.extract("transcript")

    assert "rate limit" in str(exc_info.value).lower()
```

---

## 4. Pydantic-Specific Testing

### 4.1 Testing Model Validation Changes

#### Pattern: Test Validation Rules

```python
from pydantic import BaseModel, field_validator, ValidationError
import pytest

class Episode(BaseModel):
    title: str
    duration_seconds: int

    @field_validator("title")
    @classmethod
    def title_not_empty(cls, v):
        if not v.strip():
            raise ValueError("Title cannot be empty")
        return v.strip()

    @field_validator("duration_seconds")
    @classmethod
    def duration_positive(cls, v):
        if v <= 0:
            raise ValueError("Duration must be positive")
        return v

class TestEpisodeValidation:
    def test_valid_episode(self):
        """Test that valid data passes validation."""
        episode = Episode(title="Test Episode", duration_seconds=3600)
        assert episode.title == "Test Episode"
        assert episode.duration_seconds == 3600

    def test_empty_title_raises_error(self):
        """Test that empty title is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            Episode(title="   ", duration_seconds=3600)

        errors = exc_info.value.errors()
        assert any("Title cannot be empty" in str(e) for e in errors)

    def test_negative_duration_raises_error(self):
        """Test that negative duration is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            Episode(title="Test", duration_seconds=-100)

        errors = exc_info.value.errors()
        assert any("Duration must be positive" in str(e) for e in errors)

    def test_title_whitespace_stripped(self):
        """Test that title whitespace is trimmed."""
        episode = Episode(title="  Test Episode  ", duration_seconds=3600)
        assert episode.title == "Test Episode"
```

### 4.2 Field Requirement Migrations

#### Pattern: Optional to Required Migration

```python
# Phase 1: Field is optional
class PodcastV1(BaseModel):
    title: str
    author: Optional[str] = None

# Phase 2: Field is optional with deprecation warning
class PodcastV2(BaseModel):
    title: str
    author: Optional[str] = None

    @model_validator(mode="after")
    def warn_missing_author(self):
        if self.author is None:
            import warnings
            warnings.warn(
                "author field will be required in next version",
                DeprecationWarning
            )
        return self

# Phase 3: Field is required
class PodcastV3(BaseModel):
    title: str
    author: str

# Tests for migration
class TestPodcastMigration:
    def test_v1_accepts_missing_author(self):
        """V1: author is optional."""
        podcast = PodcastV1(title="Test")
        assert podcast.author is None

    def test_v2_warns_about_missing_author(self):
        """V2: warns when author missing."""
        with pytest.warns(DeprecationWarning, match="author field will be required"):
            podcast = PodcastV2(title="Test")

    def test_v3_requires_author(self):
        """V3: author is required."""
        with pytest.raises(ValidationError) as exc_info:
            PodcastV3(title="Test")

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("author",) for e in errors)
```

### 4.3 Migration Strategies for Model Updates

#### Strategy 1: Versioned Models

```python
# Keep old version for backwards compatibility
class EpisodeV1(BaseModel):
    title: str
    description: str

# New version with additional fields
class EpisodeV2(BaseModel):
    title: str
    description: str
    tags: List[str] = []

    @classmethod
    def from_v1(cls, v1: EpisodeV1) -> "EpisodeV2":
        """Migration helper from V1 to V2."""
        return cls(
            title=v1.title,
            description=v1.description,
            tags=[]
        )

def test_v1_to_v2_migration():
    """Test migration from V1 to V2."""
    v1 = EpisodeV1(title="Test", description="Desc")
    v2 = EpisodeV2.from_v1(v1)

    assert v2.title == v1.title
    assert v2.description == v1.description
    assert v2.tags == []
```

#### Strategy 2: Field Aliases for Renaming

```python
from pydantic import BaseModel, Field

class EpisodeRenamed(BaseModel):
    title: str
    # New field name, accepts old name via alias
    summary: str = Field(alias="description")

    model_config = {"populate_by_name": True}  # Accept both names

def test_accepts_old_field_name():
    """Test backwards compatibility with old field name."""
    data = {"title": "Test", "description": "Old name"}
    episode = EpisodeRenamed(**data)
    assert episode.summary == "Old name"

def test_accepts_new_field_name():
    """Test new field name works."""
    data = {"title": "Test", "summary": "New name"}
    episode = EpisodeRenamed(**data)
    assert episode.summary == "New name"
```

#### Strategy 3: Default Values for New Fields

```python
class EpisodeWithDefaults(BaseModel):
    title: str
    description: str
    # New fields with sensible defaults
    published: bool = False
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

def test_old_data_gets_defaults():
    """Test that old data gets default values for new fields."""
    old_data = {"title": "Test", "description": "Desc"}
    episode = EpisodeWithDefaults(**old_data)

    assert episode.published is False
    assert episode.tags == []
    assert episode.metadata == {}
```

---

## 5. Conftest.py Organization

### 5.1 Shared Fixtures Structure

```python
# tests/conftest.py
"""Shared fixtures for all tests."""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch
from pathlib import Path

# ============================================================================
# Configuration Fixtures
# ============================================================================

@pytest.fixture(scope="session")
def test_data_dir():
    """Path to test data directory."""
    return Path(__file__).parent / "data"

@pytest.fixture
def sample_transcript(test_data_dir):
    """Load sample transcript for testing."""
    with open(test_data_dir / "sample_transcript.json") as f:
        return json.load(f)

# ============================================================================
# Mock Fixtures
# ============================================================================

@pytest_asyncio.fixture
async def mock_anthropic_client():
    """Mock Anthropic API client."""
    with patch("anthropic.AsyncAnthropic") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client

        # Default response
        mock_response = AsyncMock()
        mock_response.content = [AsyncMock(text='{"result": "test"}')]
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        yield mock_client

@pytest.fixture
def mock_feedparser():
    """Mock feedparser for RSS tests."""
    with patch("feedparser.parse") as mock_parse:
        mock_parse.return_value = {
            "feed": {"title": "Test Podcast"},
            "entries": []
        }
        yield mock_parse

# ============================================================================
# Async Setup Fixtures
# ============================================================================

@pytest_asyncio.fixture
async def async_database():
    """Async database fixture with setup/teardown."""
    db = await AsyncDatabase.create()
    await db.initialize()

    yield db

    await db.cleanup()
    await db.close()

# ============================================================================
# Pytest Configuration
# ============================================================================

def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
```

### 5.2 Nested conftest.py for Scoped Fixtures

```
tests/
├── conftest.py                 # Global fixtures
├── test_models.py
├── integration/
│   ├── conftest.py            # Integration test fixtures
│   └── test_api_integration.py
└── unit/
    ├── conftest.py            # Unit test fixtures
    └── test_extractors.py
```

```python
# tests/integration/conftest.py
"""Fixtures specific to integration tests."""

import pytest

@pytest.fixture(scope="module")
def test_server():
    """Start test server for integration tests."""
    server = TestServer()
    server.start()

    yield server

    server.stop()

@pytest.fixture
def api_client(test_server):
    """HTTP client connected to test server."""
    return APIClient(base_url=test_server.url)
```

---

## 6. Advanced Patterns

### 6.1 Parametrize for Comprehensive Testing

```python
import pytest

@pytest.mark.parametrize("input_text,expected_quotes", [
    ("Simple quote", ["Simple quote"]),
    ("Quote 1. Quote 2.", ["Quote 1", "Quote 2"]),
    ("", []),
    ("   ", []),
])
def test_extract_quotes_variations(input_text, expected_quotes):
    """Test quote extraction with various inputs."""
    result = extract_quotes(input_text)
    assert result == expected_quotes

@pytest.mark.parametrize("duration,expected_valid", [
    (3600, True),      # Normal duration
    (0, False),        # Zero
    (-100, False),     # Negative
    (86400, True),     # Long episode
])
def test_duration_validation(duration, expected_valid):
    """Test duration validation with parametrize."""
    if expected_valid:
        episode = Episode(title="Test", duration_seconds=duration)
        assert episode.duration_seconds == duration
    else:
        with pytest.raises(ValidationError):
            Episode(title="Test", duration_seconds=duration)
```

### 6.2 Using pytest.mark for Organization

```python
# Mark tests by category
@pytest.mark.slow
def test_large_file_processing():
    """Slow test marked for selective running."""
    pass

@pytest.mark.integration
@pytest.mark.asyncio
async def test_full_pipeline():
    """Integration test."""
    pass

# Run only specific tests
# pytest -m "not slow"                    # Skip slow tests
# pytest -m "integration"                 # Only integration tests
# pytest -m "asyncio and not integration" # Async unit tests
```

### 6.3 Custom Assertions for Better Error Messages

```python
def assert_valid_episode(episode):
    """Custom assertion with detailed error messages."""
    assert episode.title, "Episode must have a title"
    assert episode.duration_seconds > 0, \
        f"Duration must be positive, got {episode.duration_seconds}"
    assert episode.published_date <= datetime.now(timezone.utc), \
        "Published date cannot be in the future"

def test_episode_creation():
    episode = create_episode()
    assert_valid_episode(episode)
```

---

## 7. CI/CD Integration

### 7.1 GitHub Actions Configuration

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
    - uses: actions/checkout@v4

    - name: Install uv
      uses: astral-sh/setup-uv@v2

    - name: Set up Python
      uses: actions/setup-python@v5
      with:
        python-version: "3.11"

    - name: Install dependencies
      run: uv sync --dev

    - name: Run tests with coverage
      run: |
        uv run pytest \
          --cov=src \
          --cov-report=xml \
          --cov-report=term \
          -v

    - name: Run tests in random order (detect order dependencies)
      run: uv run pytest --randomly-seed=auto

    - name: Upload coverage
      uses: codecov/codecov-action@v3
```

### 7.2 Pre-commit Hooks for Tests

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: pytest-fast
        name: Run fast tests
        entry: uv run pytest -m "not slow"
        language: system
        pass_filenames: false
        always_run: true
```

---

## 8. Summary: Achieving 100% Pass Rate

### Checklist for Maintainable Tests

- [ ] **Async tests use `@pytest.mark.asyncio` marker**
- [ ] **Async functions mocked with `AsyncMock`, not `Mock`**
- [ ] **Tests are isolated - no shared state between tests**
- [ ] **Fixtures use `yield` for proper setup/teardown**
- [ ] **Test names are descriptive: `test_what_condition_expected`**
- [ ] **Each test tests one thing - no monolithic tests**
- [ ] **Datetime tests use `freezegun` for determinism**
- [ ] **All datetimes are timezone-aware (UTC)**
- [ ] **Pydantic validators have explicit tests**
- [ ] **Model migrations tested for backwards compatibility**
- [ ] **External dependencies mocked, internal logic tested**
- [ ] **Regression tests created for fixed bugs**
- [ ] **Tests run in random order without failures**
- [ ] **Coverage is measured and reviewed**
- [ ] **Slow tests marked with `@pytest.mark.slow`**

### Common Failure Patterns to Avoid

1. **Missing `@pytest.mark.asyncio`** → Async tests pass without running
2. **Using `Mock` for async functions** → TypeError when awaiting
3. **Shared test state** → Tests pass/fail depending on order
4. **Naive datetimes** → Tests fail in different timezones
5. **Testing Pydantic instead of your code** → Useless tests
6. **Over-mocking** → Tests pass but code is broken
7. **Flaky tests from time.now()** → Use freezegun
8. **No regression tests** → Same bugs keep coming back

### Key Metrics for Test Health

```bash
# Run tests with coverage
uv run pytest --cov=src --cov-report=term-missing

# Check for slow tests
uv run pytest --durations=10

# Test in random order
uv run pytest --randomly-seed=auto

# Run specific markers
uv run pytest -m "not slow and not integration"
```

---

## 9. References

### Official Documentation
- [Pytest Documentation](https://docs.pytest.org/)
- [pytest-asyncio](https://pytest-asyncio.readthedocs.io/)
- [unittest.mock](https://docs.python.org/3/library/unittest.mock.html)
- [Pydantic Validation](https://docs.pydantic.dev/)
- [freezegun](https://github.com/spulec/freezegun)

### Authoritative Guides
- [Tony Baloney: Async Test Patterns](https://tonybaloney.github.io/posts/async-test-patterns-for-pytest-and-unittest.html)
- [Pytest with Eric: Best Practices](https://pytest-with-eric.com/)
- [Real Python: Effective Testing with pytest](https://realpython.com/pytest-python-testing/)
- [BBC: Testing Asyncio Code](https://bbc.github.io/cloudfit-public-docs/asyncio/testing.html)

### Tools and Plugins
- `pytest` - Core testing framework
- `pytest-asyncio` - Async test support
- `pytest-cov` - Coverage reporting
- `pytest-randomly` - Detect order dependencies
- `pytest-regressions` - Regression testing
- `freezegun` - Datetime mocking
- `pytest-mock` - pytest-friendly mocking

---

**Document Version:** 1.0
**Last Updated:** 2025-11-13
**Status:** Complete
