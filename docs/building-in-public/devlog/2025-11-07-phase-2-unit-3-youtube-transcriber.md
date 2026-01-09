# Devlog: Phase 2 Unit 3 - YouTube Transcript Extractor

**Date**: 2025-11-07
**Phase**: 2 (Transcription Layer)
**Unit**: 3 of 9
**Status**: ✅ Complete
**Duration**: ~1 hour

---

## Overview

Unit 3 implemented the YouTube transcript extractor, which serves as Tier 1 (primary method) in our multi-tier transcription strategy. This component attempts to fetch existing transcripts from YouTube videos, providing free and instant transcription when available.

**Key outcome**: Complete YouTube transcription implementation with 28 passing tests and comprehensive error handling.

---

## What We Built

### YouTubeTranscriber Class

**Location**: `src/inkwell/transcription/youtube.py` (~200 lines)

**Key Features**:
1. **URL Detection** - Identifies YouTube URLs across multiple formats
2. **Video ID Extraction** - Parses video IDs from various URL patterns
3. **Transcript Fetching** - Retrieves transcripts via youtube-transcript-api
4. **Language Preferences** - Tries languages in order of preference
5. **Error Handling** - Graceful handling of 6+ error scenarios
6. **Model Integration** - Converts API response to our Transcript model

---

## Implementation Details

### 1. URL Detection

**Supported formats**:
```python
# All of these work:
"https://www.youtube.com/watch?v=VIDEO_ID"
"https://youtu.be/VIDEO_ID"
"https://youtube.com/embed/VIDEO_ID"
"https://m.youtube.com/watch?v=VIDEO_ID"
```

**Implementation**:
```python
def _is_youtube_url(self, url: str) -> bool:
    patterns = [
        r"youtube\.com/watch",
        r"youtu\.be/",
        r"youtube\.com/embed/",
        r"m\.youtube\.com/watch",
    ]
    return any(re.search(pattern, url, re.IGNORECASE) for pattern in patterns)
```

**Why case-insensitive**: Users may provide URLs like `YouTube.com` or `YOUTU.BE`

---

### 2. Video ID Extraction

**Challenges**: YouTube has multiple URL formats with different structures

**Solution**: Parse each format specifically

```python
def _extract_video_id(self, url: str) -> Optional[str]:
    parsed = urlparse(url)

    # youtube.com/watch?v=VIDEO_ID
    if "youtube.com" in parsed.netloc and "/watch" in parsed.path:
        query = parse_qs(parsed.query)
        if "v" in query:
            return query["v"][0]

    # youtu.be/VIDEO_ID
    if "youtu.be" in parsed.netloc:
        return parsed.path.strip("/")

    # youtube.com/embed/VIDEO_ID
    embed_match = re.search(r"youtube\.com/embed/([^/?]+)", url)
    if embed_match:
        return embed_match.group(1)

    return None
```

**Edge cases handled**:
- URLs with query parameters (`?t=30s&list=PLxyz`)
- URLs with fragments (`#comments`)
- URLs with trailing slashes

---

### 3. Language Preference System

**Goal**: Try languages in order until one succeeds

**Implementation**:
```python
# Try each preferred language
for lang in self.preferred_languages:
    try:
        transcript = transcript_list.find_transcript([lang])
        break
    except NoTranscriptFound:
        continue

# Fallback to auto-generated
if transcript is None:
    transcript = transcript_list.find_generated_transcript(self.preferred_languages)
```

**Why this matters**:
- Multi-language podcast support
- Some videos only have auto-generated English
- User can specify preference order

---

### 4. Error Handling

**Six error scenarios handled**:

#### 1. Invalid URL → `TranscriptionError`
```
Could not extract video ID from URL
```

#### 2. Transcripts Disabled → `TranscriptionError`
```
Transcripts are disabled for this video
```

#### 3. Video Unavailable → `TranscriptionError`
```
Video is unavailable (private, deleted, or restricted)
```

#### 4. Network/403 Errors → `TranscriptionError`
```
Failed to retrieve transcript (rate limiting or access restrictions)
Will fall back to Gemini transcription
```

#### 5. No Transcript in Preferred Language → `TranscriptionError`
```
No transcript found in languages: en
Available languages: fr, de
```

#### 6. Unexpected Errors → `TranscriptionError`
```
Unexpected error while fetching transcript: [error details]
```

**Why clear errors matter**: Each error suggests what went wrong and what happens next (fallback)

---

### 5. Conversion to Our Model

**YouTube API response**:
```python
[
    {"text": "Hello world", "start": 0.0, "duration": 2.0},
    {"text": "Next segment", "start": 2.0, "duration": 3.0},
]
```

**Our Transcript model**:
```python
Transcript(
    segments=[
        TranscriptSegment(text="Hello world", start=0.0, duration=2.0),
        TranscriptSegment(text="Next segment", start=2.0, duration=3.0),
    ],
    source="youtube",
    language="en",
    episode_url=url,
)
```

**Benefits of conversion**:
- Type safety with Pydantic validation
- Consistent interface for all transcription sources
- Helper methods (full_text, get_segment_at_time, etc.)

---

## Test Coverage

### Test Suite Statistics

**Total tests**: 28
**Pass rate**: 100%
**Execution time**: 0.33s
**Coverage**: 100% of youtube.py

### Test Breakdown

**URL Detection** (6 tests):
- Standard youtube.com/watch URLs
- Short youtu.be URLs
- Embed URLs
- Mobile URLs
- Non-YouTube URLs (rejection)
- Case-insensitive detection

**Video ID Extraction** (6 tests):
- Watch URLs with/without parameters
- Short URLs with/without parameters
- Embed URLs
- Invalid URLs (return None)
- Edge cases (trailing slash, fragments)

**Transcript Fetching** (9 tests):
- Successful fetching (mocked)
- Fallback to auto-generated
- Language preference order
- Invalid URL handling
- Transcripts disabled error
- Video unavailable error
- Network/403 errors
- No transcript in any language
- Unexpected errors

**Cost Estimation** (1 test):
- Always returns $0 (YouTube is free)

**Language Preferences** (3 tests):
- Default is English
- Custom preferences
- Empty list defaults to English

**Edge Cases** (3 tests):
- Trailing slashes
- URL fragments
- Empty transcript data

---

## Design Decisions

### 1. Async Methods Even Though Not Truly Async

**Decision**: Methods are `async def` even though youtube-transcript-api is synchronous

**Why**:
- **Interface consistency**: Gemini transcriber (Unit 5) will be async
- **Future-proofing**: May add async HTTP calls later
- **Minimal overhead**: async/await overhead negligible

**Trade-off**: Slightly more complex testing (need `pytest.mark.asyncio`)

---

### 2. Comprehensive Error Messages

**Decision**: Every error includes context and next steps

**Example**:
```
Failed to retrieve transcript from YouTube.
This may be due to network issues, rate limiting, or access restrictions.
Will fall back to audio download + Gemini transcription.
```

**Why**:
- Users understand what happened
- Users know what happens next (fallback)
- Reduces support questions

---

### 3. Language Fallback Chain

**Decision**: Try preferred languages, then auto-generated

**Chain**:
1. Try each language in `preferred_languages` list
2. If all fail, try auto-generated transcript
3. If that fails, raise error with available languages

**Why**: Maximizes success rate while respecting user preferences

---

### 4. Mocked Tests

**Decision**: All tests mock youtube-transcript-api

**Why**:
- Unit tests should be fast (0.33s total)
- No network dependencies
- No reliance on YouTube API availability
- Unit 1 research showed 403 errors in this environment

**Trade-off**: Would benefit from integration test with real video (deferred to manual testing)

---

## What Went Well ✅

### 1. Test-Driven Development

**Approach**: Wrote tests while implementing

**Benefits**:
- Caught edge cases early (URL formats, error paths)
- 100% coverage achieved naturally
- Confidence in error handling

**Example**: Test for empty transcript data revealed we handle it correctly

---

### 2. Clear Error Hierarchy

**Approach**: All errors raise `TranscriptionError` with clear messages

**Benefits**:
- Calling code knows what to catch
- Error messages guide user/developer
- Easy to test error scenarios

---

### 3. URL Parsing Robustness

**Approach**: Handle multiple YouTube URL formats

**Result**: Works with any URL users might provide

**Formats tested**:
- youtube.com/watch?v=...
- youtu.be/...
- youtube.com/embed/...
- m.youtube.com/watch?v=...
- With parameters, fragments, trailing slashes

---

## Lessons Learned

### 1. Mock API Constructors Correctly

**Challenge**: First test of `CouldNotRetrieveTranscript` failed

**Issue**: Wrong number of constructor arguments

**Fix**: Checked actual exception class, used `CouldNotRetrieveTranscript("video_id")`

**Lesson**: When mocking exceptions, verify constructor signatures

---

### 2. Language Preference Requires Iteration

**Observation**: Can't pass multiple languages to `find_transcript()`

**Solution**: Iterate and try each language individually

```python
for lang in self.preferred_languages:
    try:
        transcript = transcript_list.find_transcript([lang])
        break
    except NoTranscriptFound:
        continue
```

**Lesson**: API doesn't always match your mental model, adapt accordingly

---

### 3. Error Context is Critical

**Observation**: YouTube errors can be cryptic

**Solution**: Wrap all exceptions with contextual `TranscriptionError`

**Impact**: Users know exactly what failed and why

**Example**:
```python
except VideoUnavailable as e:
    raise TranscriptionError(
        "Video is unavailable. It may be private, deleted, or region-restricted."
    ) from e
```

---

## Integration with Phase 2 Architecture

### How Unit 3 Fits

**Multi-tier strategy**:
```
Episode URL
    ↓
YouTubeTranscriber.can_transcribe() → True?
    ↓ Yes
YouTubeTranscriber.transcribe()
    ↓ Success
Return Transcript ✅

    ↓ Failure (403, unavailable, etc.)
Fall back to Tier 2 (Gemini) → Unit 5
```

**Key insight**: Unit 3 is designed to fail gracefully. Errors trigger fallback, not user-facing failures.

---

### Ready for Unit 7 Integration

**Unit 7 (TranscriptionManager) will use**:
```python
transcriber = YouTubeTranscriber()

if await transcriber.can_transcribe(url):
    try:
        transcript = await transcriber.transcribe(url)
        return TranscriptionResult(success=True, transcript=transcript)
    except TranscriptionError:
        # Fall back to Gemini
        pass
```

**Clean interface**: Manager doesn't need to know about YouTube specifics

---

## Next Steps

### Unit 4: Audio Downloader (Immediate)

Implement audio download with yt-dlp:
- Download audio from any podcast source
- Convert to M4A/AAC 128kbps
- Handle authentication for private feeds
- File size validation
- Progress indicators

### Units 5-7: Remaining Tier 2

1. **Unit 5**: GeminiTranscriber (AI transcription)
2. **Unit 6**: TranscriptCache (avoid redundant work)
3. **Unit 7**: TranscriptionManager (orchestrate Tier 1 → Tier 2)

---

## Metrics

**Code written**:
- Production: ~200 lines (youtube.py)
- Tests: ~350 lines (test_youtube.py)
- Ratio: 1.75:1 (test:prod)

**Time breakdown**:
- Implementation: 30 minutes
- Test writing: 20 minutes
- Test debugging: 5 minutes
- Documentation: 5 minutes

**Test statistics**:
- Total tests: 28
- Error scenarios: 6
- URL formats: 4
- Edge cases: 3+

---

## Files Created/Modified

**New files** (2):
- `src/inkwell/transcription/youtube.py`
- `tests/unit/transcription/test_youtube.py`

**Modified files** (1):
- `src/inkwell/transcription/__init__.py` (exports)

---

## References

- [Phase 2 Implementation Plan](./2025-11-07-phase-2-detailed-plan.md)
- [ADR-009: Transcription Strategy](../adr/009-transcription-strategy.md)
- [Unit 1 Research: Transcription APIs](../research/transcription-apis-comparison.md)
- [youtube-transcript-api Documentation](https://github.com/jdepoix/youtube-transcript-api)

---

## Sign-Off

**Unit 3 Status**: ✅ **COMPLETE**

**Quality Gates Passed**:
- ✅ YouTubeTranscriber fully implemented
- ✅ 28 tests written and passing (100% coverage)
- ✅ All URL formats supported
- ✅ Comprehensive error handling (6 scenarios)
- ✅ Language preference system working
- ✅ Integration with Transcript models
- ✅ Documentation complete

**Ready to proceed**: Unit 4 (Audio Downloader)

**Date**: 2025-11-07
**Time spent**: 1 hour
**Tests**: 28/28 passing (0.33s)

---

## Personal Reflection

Unit 3 was all about **graceful degradation**. The YouTube API is unreliable (as Unit 1 research showed), so this implementation is designed to fail gracefully and trigger the Gemini fallback.

The comprehensive error handling isn't defensive programming—it's architectural. Each error scenario maps to a specific user experience:
- Invalid URL → User mistake, clear message
- Transcripts disabled → Expected scenario, use fallback
- 403 Forbidden → Environment issue, use fallback
- No English transcript → Try other languages or fallback

The test-to-code ratio of 1.75:1 reflects the importance of error paths. In a multi-tier system, **error handling is the architecture**.

28 tests in 0.33 seconds means rapid iteration. When implementation changes (and it will), tests provide instant feedback.

**Phase 2 is 3/9 complete. Momentum strong!** 🚀
