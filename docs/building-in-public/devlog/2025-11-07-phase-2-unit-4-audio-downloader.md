# Devlog: Phase 2 Unit 4 - Audio Downloader

**Date:** 2025-11-07
**Unit:** Phase 2, Unit 4
**Status:** ✅ Complete
**Duration:** ~1.5 hours

---

## Objectives

Implement audio downloading capability using yt-dlp to support transcription when YouTube transcripts are unavailable.

### Goals
- [x] Download audio from YouTube and other sources
- [x] Use M4A/AAC 128kbps format per ADR-011
- [x] Provide progress tracking for long downloads
- [x] Support authentication for private feeds
- [x] Comprehensive error handling
- [x] Async interface for consistency

---

## Implementation Summary

### Components Created

1. **`src/inkwell/audio/__init__.py`**
   - Module exports: `AudioDownloader`, `AudioDownloadError`, `DownloadProgress`

2. **`src/inkwell/audio/downloader.py`** (230 lines)
   - `AudioDownloadError`: Custom exception for download failures
   - `DownloadProgress`: Pydantic model for progress tracking
   - `AudioDownloader`: Main downloader class

3. **`tests/unit/audio/test_downloader.py`** (410 lines)
   - 22 comprehensive tests
   - 100% pass rate
   - All external dependencies mocked

---

## Key Features

### 1. AudioDownloader Class

```python
class AudioDownloader:
    def __init__(
        self,
        output_dir: Path | None = None,
        progress_callback: Callable[[DownloadProgress], None] | None = None,
    ):
        ...

    async def download(
        self,
        url: str,
        output_filename: str | None = None,
        username: str | None = None,
        password: str | None = None,
    ) -> Path:
        ...

    async def get_info(self, url: str) -> dict[str, Any]:
        ...
```

**Features:**
- Downloads from YouTube, direct URLs, and other yt-dlp supported sources
- Converts to M4A/AAC 128kbps (per ADR-011)
- Optional progress callbacks
- Optional authentication
- Optional custom filenames
- Info extraction without downloading

---

### 2. Progress Tracking

```python
class DownloadProgress(BaseModel):
    status: str
    downloaded_bytes: int
    total_bytes: int | None
    speed: float | None
    eta: int | None

    @property
    def percentage(self) -> float | None:
        """Calculate download percentage if total is known."""
        if self.total_bytes and self.total_bytes > 0:
            return (self.downloaded_bytes / self.total_bytes) * 100
        return None
```

**Usage:**
```python
def progress_callback(progress: DownloadProgress):
    print(f"Download: {progress.percentage:.1f}% at {progress.speed/1024:.1f} KB/s")

downloader = AudioDownloader(progress_callback=progress_callback)
```

---

### 3. Format Configuration (ADR-011)

```python
ydl_opts = {
    "format": "bestaudio/best",
    "postprocessors": [{
        "key": "FFmpegExtractAudio",
        "preferredcodec": "m4a",      # M4A container
        "preferredquality": "128",     # 128kbps AAC
    }],
    "outtmpl": output_template,
    "progress_hooks": [self._progress_hook],
    "quiet": True,
}
```

---

### 4. Async Interface with Thread Pool

**Challenge:** yt-dlp is synchronous and would block the event loop.

**Solution:** Run synchronous operations in thread pool executor:

```python
async def download(self, url: str, ...) -> Path:
    loop = asyncio.get_event_loop()
    output_path = await loop.run_in_executor(
        None,  # Default thread pool
        self._download_sync,
        url,
        ydl_opts,
        output_template
    )
    return output_path

def _download_sync(self, url: str, ydl_opts: dict, ...) -> Path:
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        # ... determine output path
        return output_path
```

**Benefits:**
- Maintains async interface consistency
- Doesn't block event loop
- Allows concurrent operations

---

### 5. Error Handling

Three exception types caught and wrapped:

1. **`DownloadError`** - Network issues, invalid URLs
   ```python
   raise AudioDownloadError(
       f"Failed to download audio from {url}. "
       f"This may be due to network issues, invalid URL, or unsupported source. "
       f"Error: {e}"
   )
   ```

2. **`ExtractorError`** - Invalid content, access restrictions
   ```python
   raise AudioDownloadError(
       f"Failed to extract audio information from {url}. "
       f"The URL may be invalid or the content may not be accessible. "
       f"Error: {e}"
   )
   ```

3. **Generic exceptions** - Unexpected failures
   ```python
   raise AudioDownloadError(
       f"Unexpected error downloading audio from {url}: {e}"
   )
   ```

All errors provide clear messages explaining what happened and why.

---

## Testing Strategy

### Test Coverage (22 tests)

**DownloadProgress Tests (5):**
- ✅ Basic progress creation
- ✅ Percentage calculation
- ✅ Percentage with unknown total
- ✅ Percentage with zero total
- ✅ Validation (negative bytes rejected)

**AudioDownloader Tests (17):**
- ✅ Initialization (default dir, custom dir, auto-create)
- ✅ Successful download
- ✅ Download with custom filename
- ✅ Download with authentication
- ✅ Format configuration (verify ADR-011)
- ✅ Progress callback invocation
- ✅ Error handling (DownloadError)
- ✅ Error handling (ExtractorError)
- ✅ Error handling (generic exceptions)
- ✅ Missing output file error
- ✅ Info extraction success
- ✅ Info extraction error
- ✅ Info extraction with no result
- ✅ Progress hook without callback
- ✅ Progress hook with total_bytes_estimate

**Test Execution:**
```
22 passed in 0.57-0.61s
```

---

### Mocking Strategy

**Challenge:** YoutubeDL is a context manager.

**Solution:** Explicit context manager mocking:

```python
@pytest.fixture
def mock_ydl_instance(self) -> Mock:
    """The actual YoutubeDL object returned by __enter__"""
    mock = MagicMock()
    mock.extract_info.return_value = {
        "title": "Test Video",
        "id": "test123",
        "duration": 300,
    }
    return mock

@pytest.fixture
def mock_ydl_class(self, mock_ydl_instance: Mock) -> Mock:
    """The YoutubeDL class with context manager support"""
    mock_class = MagicMock()
    mock_class.return_value.__enter__.return_value = mock_ydl_instance
    mock_class.return_value.__exit__.return_value = None
    return mock_class
```

**Usage in tests:**
```python
with patch("inkwell.audio.downloader.YoutubeDL", mock_ydl_class):
    result = await downloader.download("https://youtube.com/watch?v=test123")
```

---

## Design Decisions

### 1. Async Methods Even Though yt-dlp is Sync

**Decision:** Use `async def` for all public methods

**Rationale:**
- Interface consistency with YouTubeTranscriber (Unit 3)
- Future-proofing for async operations
- Thread pool execution prevents blocking

**Trade-off:** Slightly more complex testing (`pytest.mark.asyncio`)

---

### 2. Optional Progress Callback

**Decision:** Progress callback is optional, not required

**Rationale:**
- Not all use cases need progress (e.g., background jobs)
- CLI will use it, but library code might not
- Defensive check (`if not self.progress_callback: return`) prevents errors

---

### 3. Separate `get_info()` Method

**Decision:** Provide method to extract info without downloading

**Rationale:**
- Useful for validation before download
- Can check file size, duration, etc.
- Follows yt-dlp's own API design

---

### 4. Custom Filename Support

**Decision:** Allow optional custom filename

**Rationale:**
- Some callers want predictable filenames
- Default template uses title+ID (good for exploration)
- Custom filename good for automation

**Default:** `"%(title)s-%(id)s.%(ext)s"` → `"My Video-abc123.m4a"`
**Custom:** `"custom-name"` → `"custom-name.m4a"`

---

## Challenges & Solutions

### Challenge 1: Mocking Context Managers

**Problem:** Initial tests failed with `replace() argument 2 must be str, not MagicMock`

**Root Cause:** YoutubeDL is used as `with YoutubeDL(...) as ydl:`, but our mock wasn't configured as a context manager.

**Solution:**
```python
mock_ydl_class.return_value.__enter__.return_value = mock_ydl_instance
mock_ydl_class.return_value.__exit__.return_value = None
```

**Impact:** Established pattern for mocking context managers in this project.

---

### Challenge 2: Inconsistent Progress Data

**Problem:** yt-dlp provides inconsistent progress data (sometimes `total_bytes`, sometimes `total_bytes_estimate`, sometimes neither)

**Solution:** Defensive programming with fallbacks
```python
total_bytes = progress_dict.get("total_bytes") or progress_dict.get(
    "total_bytes_estimate"
)
```

**Impact:** Progress tracking works even when data is incomplete. `percentage` returns `None` when total is unknown (acceptable UX).

---

### Challenge 3: Output Path Detection

**Problem:** yt-dlp creates the file, but we need to know the exact path for the return value.

**Solution:** Use output template to predict filename
```python
output_template = str(self.output_dir / "%(title)s-%(id)s.%(ext)s")

# After download, replace placeholders with actual values
output_path = Path(
    output_template.replace("%(ext)s", "m4a")
                   .replace("%(title)s", info.get("title", "audio"))
                   .replace("%(id)s", info.get("id", "unknown"))
)

if not output_path.exists():
    raise AudioDownloadError("File not found at expected location")
```

---

## What Went Well ✅

1. **Async wrapper pattern** - Clean separation between async interface and sync implementation
2. **Fixture composition** - Reusable mock fixtures reduced test boilerplate
3. **Comprehensive error handling** - All yt-dlp exceptions caught and wrapped with context
4. **Progress tracking** - Flexible callback system works for CLI and library use
5. **Test coverage** - 22 tests cover all paths including edge cases
6. **Linter compliance** - All checks passed on first run after fixes

---

## What Could Be Improved 🔄

1. **No integration tests** - All tests use mocks. Would benefit from one real download test (manual testing recommended)
2. **Limited format options** - Hardcoded to M4A/AAC 128kbps. Could add format parameter if needed later.
3. **No retry logic** - Network failures cause immediate error. Could add exponential backoff.
4. **Output path prediction** - Current approach works but is fragile. yt-dlp doesn't provide the final path directly.

---

## Dependencies Added

```toml
[project]
dependencies = [
    # ... existing
    "yt-dlp>=2025.10.22",
]
```

**Why yt-dlp:**
- Most comprehensive downloader (supports 1000+ sites)
- Active development
- Excellent format selection
- Built-in ffmpeg integration for conversion
- Better than youtube-dl (more maintained)

---

## Integration Points

### With YouTube Transcriber (Unit 3)
```python
# Try YouTube transcript first
if await youtube_transcriber.can_transcribe(url):
    try:
        transcript = await youtube_transcriber.transcribe(url)
    except TranscriptionError:
        # YouTube failed - download audio for Gemini
        audio_path = await audio_downloader.download(url)
```

### With Future Gemini Transcriber (Unit 5)
```python
# If YouTube transcript unavailable, use audio
audio_path = await audio_downloader.download(url)
transcript = await gemini_transcriber.transcribe(audio_path)
```

---

## Code Statistics

- **Implementation:** 230 lines
- **Tests:** 410 lines
- **Test-to-code ratio:** 1.8:1
- **Test classes:** 2
- **Test methods:** 22
- **Pass rate:** 100%
- **Execution time:** 0.57-0.61s

---

## Next Steps

### Immediate (Unit 5)
- Implement Gemini transcription API integration
- Use downloaded audio files from this unit
- Maintain async interface pattern

### Future Enhancements (If Needed)
- Add retry logic for network failures
- Support multiple audio formats (beyond M4A)
- Add file size limits/warnings
- Integration tests with real downloads

---

## References

- [ADR-011: Audio Format Selection](/docs/adr/011-audio-format-selection.md)
- [Research: yt-dlp Audio Extraction](/docs/research/yt-dlp-audio-extraction.md)
- [Unit 3: YouTube Transcriber](/docs/devlog/2025-11-07-phase-2-unit-3-youtube-transcriber.md)
- [Phase 2 Plan](/docs/devlog/2025-11-07-phase-2-detailed-plan.md)
- [yt-dlp Documentation](https://github.com/yt-dlp/yt-dlp)
