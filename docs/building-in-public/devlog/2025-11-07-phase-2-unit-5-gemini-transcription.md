# Devlog: Phase 2 Unit 5 - Gemini Transcription

**Date:** 2025-11-07
**Unit:** Phase 2, Unit 5
**Status:** ✅ Complete
**Duration:** ~2 hours

---

## Objectives

Implement Gemini API integration for audio transcription as Tier 2 fallback when YouTube transcripts are unavailable.

### Goals
- [x] Integrate Google Generative AI SDK (Gemini 1.5 Flash)
- [x] Implement cost estimation and confirmation per ADR-012
- [x] Support multiple audio formats (MP3, M4A, WAV, AAC, OGG, FLAC)
- [x] Parse timestamps from Gemini responses (optional enhancement)
- [x] Async interface consistent with other transcribers
- [x] Comprehensive error handling

---

## Implementation Summary

### Components Created

1. **`src/inkwell/transcription/gemini.py`** (376 lines)
   - `TranscriptionError`: Custom exception
   - `CostEstimate`: Pydantic model for cost tracking
   - `GeminiTranscriber`: Main transcriber class
   - `GeminiTranscriberWithSegments`: Enhanced version with timestamp parsing

2. **`tests/unit/transcription/test_gemini.py`** (475 lines)
   - 26 comprehensive tests
   - 100% pass rate
   - All Google AI SDK calls mocked

---

## Key Features

### 1. GeminiTranscriber Class

```python
class GeminiTranscriber:
    def __init__(
        self,
        api_key: str | None = None,
        model_name: str = "gemini-1.5-flash",
        cost_threshold_usd: float = 1.0,
        cost_confirmation_callback: Callable[[CostEstimate], bool] | None = None,
    ):
        ...

    async def can_transcribe(self, audio_path: Path) -> bool:
        ...

    async def transcribe(self, audio_path: Path, episode_url: str | None = None) -> Transcript:
        ...
```

**Features:**
- API key from parameter or environment variable
- Cost estimation before transcription
- Optional cost confirmation callback
- Thread pool execution for blocking SDK
- Support for 6 audio formats

---

### 2. Cost Estimation & Confirmation

```python
class CostEstimate(BaseModel):
    file_size_mb: float
    estimated_cost_usd: float
    rate_per_mb: float = 0.000125

    @property
    def formatted_cost(self) -> str:
        """Format cost for user display."""
        if self.estimated_cost_usd < 0.01:
            return f"${self.estimated_cost_usd:.4f}"
        return f"${self.estimated_cost_usd:.2f}"
```

**Flow:**
1. Estimate cost based on file size (~$0.000125/MB)
2. Auto-approve if below threshold (default $1.00)
3. Call confirmation callback if above threshold
4. Proceed or cancel based on approval

---

### 3. Timestamp Parsing (Enhanced Version)

```python
class GeminiTranscriberWithSegments(GeminiTranscriber):
    def _parse_timestamps(self, text: str) -> list[TranscriptSegment]:
        """Parse [HH:MM:SS] or [MM:SS] markers from transcript."""
        ...
```

**Supported Formats:**
- `[00:00:00] Speaker: Text` - HH:MM:SS
- `[0:00] Text` - MM:SS
- Multiline segments
- Speaker prefix removal

**Fallback:**
If no timestamps found, returns single segment with full text.

---

## Design Decisions

### 1. Two-Class Design (Base + Enhanced)

**Decision:** Provide `GeminiTranscriber` (basic) and `GeminiTranscriberWithSegments` (enhanced)

**Rationale:**
- Basic version always works (single segment)
- Enhanced version attempts timestamp parsing
- Users choose based on needs
- Both share core transcription logic

---

### 2. Cost Threshold with Callback

**Decision:** Threshold + optional callback instead of always requiring confirmation

**Rationale:**
- Small files auto-approve (< $1.00)
- Large files trigger callback
- CLI can implement interactive prompt
- Library can implement custom logic

**Example Usage:**
```python
# CLI mode: prompt user
def confirm_cost(estimate: CostEstimate) -> bool:
    return typer.confirm(f"Transcribe for {estimate.formatted_cost}?")

transcriber = GeminiTranscriber(
    cost_threshold_usd=0.5,
    cost_confirmation_callback=confirm_cost
)
```

---

### 3. Async Interface with Thread Pool

**Decision:** Use `async def` with thread pool executor

**Rationale:**
- Google AI SDK is synchronous
- Consistent interface with YouTubeTranscriber
- Allows concurrent operations
- Non-blocking for event loop

**Implementation:**
```python
async def transcribe(self, audio_path: Path, ...) -> Transcript:
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(
        None,
        self._transcribe_sync,
        audio_path
    )
    ...
```

---

### 4. Environment Variable API Key

**Decision:** Support both parameter and environment variable

**Rationale:**
- Development: Pass directly
- Production: Use env vars (12-factor)
- Security: Avoid hardcoding keys
- Testing: Mock easily

---

## Testing Strategy

### Test Coverage (26 tests)

**CostEstimate Tests (4):**
- ✅ Basic estimate creation
- ✅ Formatted cost (small amounts)
- ✅ Formatted cost (large amounts)
- ✅ Validation (negative costs rejected)

**GeminiTranscriber Tests (18):**
- ✅ Initialization (API key, env var, error)
- ✅ Custom parameters (model, threshold, callback)
- ✅ can_transcribe (supported/unsupported/missing)
- ✅ Cost estimation accuracy
- ✅ Cost confirmation (below/above threshold, rejection)
- ✅ Successful transcription
- ✅ Episode URL metadata
- ✅ Error handling (missing file, unsupported format, API error, empty response)

**GeminiTranscriberWithSegments Tests (4):**
- ✅ Parse HH:MM:SS timestamps
- ✅ Parse MM:SS timestamps
- ✅ Fallback when no timestamps
- ✅ Multiline segments

**Execution:** All tests pass in ~3 seconds

---

## Challenges & Solutions

### Challenge 1: Timestamp Parsing Bug

**Problem:** Initial logic checked `if secs > 0` to determine format, failing for `[00:01:00]`

**Root Cause:**
```python
secs = int(match.group(3)) if match.group(3) else 0
if secs > 0:  # BUG: [00:01:00] has secs=0
```

**Solution:**
```python
secs = int(match.group(3)) if match.group(3) is not None else None
if secs is not None:  # Check presence, not value
```

**Impact:** Always check `is not None` for optional regex groups

---

### Challenge 2: Google AI SDK is Synchronous

**Problem:** SDK has no async support, would block event loop

**Solution:** Thread pool executor
```python
loop = asyncio.get_event_loop()
result = await loop.run_in_executor(None, self._sync_method, ...)
```

**Impact:** Established pattern for wrapping synchronous APIs (used in Unit 4 too)

---

### Challenge 3: Unpredictable Response Format

**Problem:** Gemini sometimes includes timestamps, sometimes doesn't

**Solution:** Graceful fallback
```python
segments = self._parse_timestamps(text)
if not segments:  # Parsing failed
    segments = [TranscriptSegment(text=text, start=0.0, duration=0.0)]
```

**Impact:** Always returns valid Transcript, degrades gracefully

---

## What Went Well ✅

1. **Two-class design** - Base + enhanced allows flexibility
2. **Cost management** - Threshold + callback pattern is elegant
3. **Timestamp parsing** - Handles multiple formats with graceful fallback
4. **Test coverage** - 26 tests cover all paths including edge cases
5. **Consistent patterns** - Reused async wrapper from Unit 4
6. **Clear error messages** - All errors explain what/why/next

---

## What Could Be Improved 🔄

1. **No actual API integration test** - All mocked (manual testing recommended)
2. **Cost estimation is approximate** - Based on file size, actual costs may vary
3. **Limited language detection** - Defaults to English, no auto-detect
4. **Timestamp parsing is heuristic** - May fail on unusual formats
5. **No retry logic** - Network failures cause immediate error

---

## Integration Points

### With Audio Downloader (Unit 4)
```python
# Download audio if YouTube transcript unavailable
audio_path = await audio_downloader.download(url)

# Transcribe with Gemini
transcript = await gemini_transcriber.transcribe(audio_path, episode_url=url)
```

### With YouTube Transcriber (Unit 3)
```python
# Try YouTube first (Tier 1)
try:
    transcript = await youtube_transcriber.transcribe(url)
except TranscriptionError:
    # Fallback to Gemini (Tier 2)
    audio_path = await audio_downloader.download(url)
    transcript = await gemini_transcriber.transcribe(audio_path)
```

---

## Code Statistics

- **Implementation:** 376 lines
- **Tests:** 475 lines
- **Test-to-code ratio:** 1.3:1
- **Test classes:** 3
- **Test methods:** 26
- **Pass rate:** 100%
- **Execution time:** ~3s

---

## Dependencies Added

```toml
[project]
dependencies = [
    # ... existing
    "google-generativeai>=0.8.5",
]
```

**Transitive Dependencies (19):**
- google-ai-generativelanguage
- google-api-core
- google-api-python-client
- google-auth, google-auth-httplib2
- googleapis-common-protos
- grpcio, grpcio-status
- httplib2, proto-plus, protobuf
- pyasn1, pyasn1-modules
- pyparsing, rsa
- tqdm, uritemplate, cachetools

---

## Next Steps

### Immediate (Unit 6)
- Implement transcript caching system
- Cache both YouTube and Gemini transcripts
- Preserve cost metadata in cache

### Future Enhancements
- Language auto-detection
- Retry logic with exponential backoff
- Integration tests with real API
- Support for more timestamp formats

---

## References

- [ADR-009: Transcription Strategy](/docs/adr/009-transcription-strategy.md)
- [ADR-012: Gemini Cost Management](/docs/adr/012-gemini-cost-management.md)
- [Unit 4: Audio Downloader](/docs/devlog/2025-11-07-phase-2-unit-4-audio-downloader.md)
- [Google AI Documentation](https://ai.google.dev/gemini-api/docs)
