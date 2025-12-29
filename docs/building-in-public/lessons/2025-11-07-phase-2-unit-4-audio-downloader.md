# Lessons Learned: Phase 2 Unit 4 - Audio Downloader

**Date:** 2025-11-07
**Unit:** Phase 2, Unit 4
**Component:** Audio downloader with yt-dlp
**Duration:** ~1.5 hours
**Lines of Code:** ~230 implementation, ~410 tests (1.8:1 ratio)

---

## Summary

Implemented audio downloading using yt-dlp with comprehensive error handling, progress tracking, and authentication support. This unit builds on ADR-011's format selection decisions and provides the foundation for audio transcription when YouTube transcripts are unavailable.

---

## Key Lessons Learned

### 1. Mocking Context Managers Requires Specific Setup

**What Happened:**
Initial test failures with `replace() argument 2 must be str, not MagicMock` occurred because YoutubeDL is a context manager and our mocks weren't properly configured.

**The Pattern:**
```python
# Wrong - doesn't handle context manager
mock_ydl = MagicMock()
with patch("module.YoutubeDL", return_value=mock_ydl):
    # This fails - mock_ydl isn't a context manager

# Right - explicitly configure context manager
mock_ydl_instance = MagicMock()  # The actual object returned by __enter__
mock_ydl_class = MagicMock()
mock_ydl_class.return_value.__enter__.return_value = mock_ydl_instance
mock_ydl_class.return_value.__exit__.return_value = None
with patch("module.YoutubeDL", mock_ydl_class):
    # This works - mock_ydl_instance is what's used inside the context
```

**Impact:**
All future mocking of context managers will use this pattern. This is essential for testing file operations, database connections, and third-party libraries.

---

### 2. Thread Pool Execution for Blocking Libraries

**What Happened:**
yt-dlp is synchronous and blocking. In an async application, blocking calls would freeze the event loop.

**The Solution:**
```python
async def download(self, url: str) -> Path:
    loop = asyncio.get_event_loop()
    output_path = await loop.run_in_executor(
        None,  # Use default thread pool
        self._download_sync,  # Synchronous method
        url,
        ydl_opts,
        output_template
    )
    return output_path
```

**Why This Matters:**
- Maintains async interface consistency (all transcriber methods are async)
- Doesn't block the event loop
- Allows concurrent operations (e.g., download audio while extracting YouTube transcript)
- Minimal overhead for I/O-bound operations

**Trade-off:**
Adds slight complexity to testing (need `pytest.mark.asyncio`) but worth it for interface consistency.

---

### 3. Progress Hooks Need Defensive Programming

**What Happened:**
yt-dlp's progress hooks provide inconsistent data. Sometimes `total_bytes` is present, sometimes only `total_bytes_estimate`, sometimes neither.

**The Solution:**
```python
def _progress_hook(self, progress_dict: dict[str, Any]) -> None:
    if not self.progress_callback:
        return  # Exit early if no callback

    total_bytes = progress_dict.get("total_bytes") or progress_dict.get(
        "total_bytes_estimate"
    )

    progress = DownloadProgress(
        status=progress_dict.get("status", "unknown"),  # Default fallback
        downloaded_bytes=progress_dict.get("downloaded_bytes", 0),  # Safe default
        total_bytes=total_bytes,  # May be None - that's OK
        speed=progress_dict.get("speed"),
        eta=progress_dict.get("eta"),
    )
```

**Key Patterns:**
- Always check if callback exists before using it
- Use `.get()` with sensible defaults
- Handle None gracefully (Pydantic `Optional` fields)
- Fallback chains for similar fields (`total_bytes` → `total_bytes_estimate`)

---

### 4. Error Messages Should Guide Users Through the System

**What Happened:**
When audio download fails, users need to understand:
1. What went wrong
2. Why it might have happened
3. What happens next (fallback to Gemini)

**The Pattern:**
```python
raise AudioDownloadError(
    f"Failed to download audio from {url}. "
    f"This may be due to network issues, invalid URL, or unsupported source. "
    f"Error: {e}"
)
```

**Better Than:**
```python
raise AudioDownloadError(f"Download failed: {e}")  # Too terse
```

**Impact:**
This pattern from Unit 3 (YouTube transcriber) is now established as the project standard. Every error message should:
- Explain what failed
- Suggest possible causes
- Indicate next steps (if applicable)

---

### 5. Pydantic Computed Properties for User-Friendly APIs

**What Happened:**
Progress percentage is useful for UIs but shouldn't be stored (it's derived from `downloaded_bytes / total_bytes`).

**The Pattern:**
```python
class DownloadProgress(BaseModel):
    downloaded_bytes: int
    total_bytes: int | None

    @property
    def percentage(self) -> float | None:
        """Calculate download percentage if total is known."""
        if self.total_bytes and self.total_bytes > 0:
            return (self.downloaded_bytes / self.total_bytes) * 100
        return None
```

**Benefits:**
- No data duplication
- Always consistent (can't get out of sync)
- Type-safe (returns `float | None`)
- User-friendly API (`progress.percentage` instead of manual calculation)

**Pattern from Unit 2:**
This reinforces the lesson from data models - use properties for computed values.

---

### 6. Fixture Composition in Pytest

**What Happened:**
We needed `mock_ydl_instance` for the actual mock and `mock_ydl_class` for the context manager. Instead of duplicating setup, we composed fixtures.

**The Pattern:**
```python
@pytest.fixture
def mock_ydl_instance(self) -> Mock:
    """Create mock YoutubeDL instance."""
    mock = MagicMock()
    mock.extract_info.return_value = {...}
    return mock

@pytest.fixture
def mock_ydl_class(self, mock_ydl_instance: Mock) -> Mock:
    """Create mock YoutubeDL class that works as context manager."""
    mock_class = MagicMock()
    mock_class.return_value.__enter__.return_value = mock_ydl_instance
    mock_class.return_value.__exit__.return_value = None
    return mock_class
```

**Benefits:**
- DRY (Don't Repeat Yourself)
- Clear separation of concerns
- Easy to test both the instance and the context manager behavior
- Can use either fixture depending on test needs

---

## Patterns to Repeat

### 1. Async Wrapper for Sync Libraries
When integrating synchronous third-party libraries into async codebase:
```python
async def async_method(self, ...):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, self._sync_method, ...)

def _sync_method(self, ...):
    # Synchronous implementation
```

### 2. Progress Callback Pattern
For long-running operations:
```python
class Downloader:
    def __init__(self, progress_callback: Callable[[Progress], None] | None = None):
        self.progress_callback = progress_callback

    def _progress_hook(self, data: dict):
        if not self.progress_callback:
            return
        self.progress_callback(Progress(...))
```

### 3. Comprehensive Error Context
Every exception should include:
```python
raise CustomError(
    f"What failed: {specifics}. "
    f"Possible causes: {reasons}. "
    f"Next steps: {guidance}. "
    f"Error: {original_error}"
)
```

---

## Anti-Patterns to Avoid

### 1. **Don't Mock Without Understanding the API**
❌ Wrong:
```python
mock = MagicMock()  # Hope it works
with patch("module.YoutubeDL", return_value=mock):
    ...
```

✅ Right:
```python
# Read the docs, understand YoutubeDL is a context manager
mock_instance = MagicMock()  # The actual object
mock_class = MagicMock()
mock_class.return_value.__enter__.return_value = mock_instance
```

**Lesson:** Read the library documentation to understand how objects are used (context managers, iterators, etc.) before mocking.

---

### 2. **Don't Block the Event Loop**
❌ Wrong:
```python
async def download(self, url: str):
    # This blocks!
    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url)  # Synchronous call
```

✅ Right:
```python
async def download(self, url: str):
    loop = asyncio.get_event_loop()
    info = await loop.run_in_executor(None, self._sync_download, url)
```

---

### 3. **Don't Assume Dictionary Keys Exist**
❌ Wrong:
```python
total = progress_dict["total_bytes"]  # KeyError if missing
```

✅ Right:
```python
total = progress_dict.get("total_bytes") or progress_dict.get("total_bytes_estimate")
```

---

## Technical Insights

### yt-dlp Architecture Understanding

**Discovered:**
- yt-dlp uses postprocessors for format conversion (FFmpegExtractAudio)
- Progress hooks are called with varying data depending on download stage
- Output template supports placeholders (`%(title)s`, `%(id)s`, `%(ext)s`)
- Context manager handles cleanup automatically

**Configuration for Our Use Case (ADR-011):**
```python
ydl_opts = {
    "format": "bestaudio/best",  # Get best quality audio
    "postprocessors": [{
        "key": "FFmpegExtractAudio",
        "preferredcodec": "m4a",      # M4A container
        "preferredquality": "128",     # 128kbps AAC
    }],
}
```

---

### Testing Philosophy Reinforced

**Test-to-Code Ratio:** 1.8:1 (410 test lines / 230 implementation lines)

**Coverage:**
- 22 tests across 2 test classes
- All happy paths tested
- All error conditions tested
- Edge cases covered (missing data, None values, etc.)

**Speed:**
0.57-0.61 seconds for full test suite due to:
- All external dependencies mocked
- No network calls
- No file I/O (using temp directories)

---

## Impact on Future Units

### Unit 5: Gemini Transcription
- Can reuse async wrapper pattern for Google AI SDK
- Progress tracking pattern applies to transcription progress
- Error message pattern continues

### Unit 6: Transcript Caching
- Downloaded audio files need cache keys (URL-based)
- File path handling patterns established

### Unit 7: Transcription Orchestrator
- Async interface makes coordination easier
- Error messages guide fallback logic
- Progress callbacks can be aggregated

### Unit 8: CLI Integration
- Progress callbacks can drive rich progress bars
- Error messages are user-friendly (ready for CLI display)

---

## Statistics

- **Implementation:** 230 lines of code
- **Tests:** 410 lines of code
- **Test-to-code ratio:** 1.8:1
- **Tests:** 22 total (5 DownloadProgress, 17 AudioDownloader)
- **Test execution time:** 0.57-0.61 seconds
- **Pass rate:** 100%
- **Linter:** All checks passed
- **Dependencies added:** yt-dlp>=2025.10.22

---

## References

- [ADR-011: Audio Format Selection](/docs/adr/011-audio-format-selection.md) - M4A/AAC 128kbps decision
- [Research: yt-dlp Audio Extraction](/docs/research/yt-dlp-audio-extraction.md) - yt-dlp best practices
- [Phase 2 Plan](/docs/devlog/2025-11-07-phase-2-detailed-plan.md) - Unit 4 objectives
