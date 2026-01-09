# Lessons Learned: Phase 2 Unit 7 - Transcription Manager

**Date:** 2025-11-07
**Unit:** Phase 2, Unit 7
**Component:** Transcription orchestrator/manager
**Duration:** ~2 hours
**Lines of Code:** ~215 implementation, ~370 tests (1.7:1 ratio)

---

## Summary

Implemented TranscriptionManager orchestrator that ties together cache, YouTube transcriber, audio downloader, and Gemini transcriber into a unified multi-tier transcription system per ADR-009.

---

## Key Lessons Learned

### 1. Exception Type Consolidation Matters

**What Happened:**
Both youtube.py and gemini.py defined their own `TranscriptionError` classes, causing import confusion in tests.

**The Problem:**
```python
# In manager.py
from inkwell.transcription.youtube import TranscriptionError

# In test (WRONG)
from inkwell.transcription.gemini import TranscriptionError  # Different class!
```

**Impact:** Tests failed because exception catching didn't work across modules.

**Lesson:** Consolidate common exceptions in a single module (e.g., models.py or exceptions.py) to avoid type mismatches.

---

### 2. Graceful Degradation for Optional Components

**Pattern:**
```python
def __init__(self, gemini_transcriber=None, gemini_api_key=None):
    if gemini_transcriber:
        self.gemini_transcriber = gemini_transcriber
    elif gemini_api_key:
        self.gemini_transcriber = GeminiTranscriber(api_key=gemini_api_key)
    else:
        try:
            self.gemini_transcriber = GeminiTranscriber()  # Try env var
        except ValueError:
            self.gemini_transcriber = None  # Disable Gemini tier
```

**Benefits:**
- System works without Gemini API key (YouTube-only)
- Explicit error messages when tier unavailable
- Flexible deployment options

**Lesson:** Design systems to work with partial configuration, not all-or-nothing.

---

### 3. Attempt Tracking Provides Debugging Visibility

**Pattern:**
```python
attempts: list[str] = []

if use_cache:
    attempts.append("cache")
    # Try cache...

if not skip_youtube:
    attempts.append("youtube")
    # Try YouTube...

attempts.append("gemini")
# Try Gemini...

return TranscriptionResult(..., attempts=attempts)
```

**Benefits:**
- Clear audit trail of what was tried
- Debugging information ("Why did this cost money?")
- Performance analysis ("How often does cache work?")

**Lesson:** Track execution paths through complex systems for observability.

---

### 4. Cost Accumulation Across Tiers

**Pattern:**
```python
total_cost = 0.0

# YouTube tier
cost_usd=0.0  # Free

# Gemini tier
if transcript.cost_usd:
    total_cost += transcript.cost_usd

return TranscriptionResult(..., cost_usd=total_cost)
```

**Why This Matters:**
- Users see total cost regardless of tier used
- Can track spending over time
- Cost per episode visible

**Lesson:** Aggregate costs at orchestration level, not just component level.

---

### 5. Convenience Methods Improve UX

**Pattern:**
```python
# Low-level: Full control
result = await manager.transcribe(url, use_cache=True, skip_youtube=False)
if result.success:
    transcript = result.transcript

# High-level: Simple
transcript = await manager.get_transcript(url)
```

**Benefits:**
- Simple cases are simple
- Complex cases still possible
- Reduces boilerplate in calling code

**Lesson:** Provide both high-level convenience and low-level control.

---

## Patterns to Repeat

### 1. Multi-Tier Fallback
```python
# Try each tier in order
for tier in [tier1, tier2, tier3]:
    try:
        result = await tier.process()
        return success(result)
    except TierError:
        continue  # Try next tier

return failure("All tiers failed")
```

### 2. Metadata Aggregation
```python
start_time = datetime.now(timezone.utc)
attempts = []
total_cost = 0.0

# Execute logic, track everything
attempts.append("tier_name")
total_cost += tier_cost

duration = (datetime.now(timezone.utc) - start_time).total_seconds()
return Result(attempts=attempts, cost=total_cost, duration=duration)
```

### 3. Component Injection with Defaults
```python
def __init__(self, component=None, other_component=None):
    self.component = component or DefaultComponent()
    self.other_component = other_component or DefaultOtherComponent()
```

---

## Anti-Patterns to Avoid

❌ **Don't define same exception in multiple modules**
```python
# youtube.py
class TranscriptionError(Exception): pass

# gemini.py
class TranscriptionError(Exception): pass  # BAD: Name collision
```

✅ **Consolidate in one place**
```python
# exceptions.py
class TranscriptionError(Exception): pass

# Import everywhere else
from inkwell.transcription.exceptions import TranscriptionError
```

---

## Technical Insights

### Orchestration Complexity

**Before (Direct Usage):**
```python
# Caller must handle all logic
cache = TranscriptCache()
youtube = YouTubeTranscriber()
downloader = AudioDownloader()
gemini = GeminiTranscriber()

cached = cache.get(url)
if cached:
    return cached

try:
    if youtube.can_transcribe(url):
        transcript = await youtube.transcribe(url)
        cache.set(url, transcript)
        return transcript
except:
    pass

audio = await downloader.download(url)
transcript = await gemini.transcribe(audio)
cache.set(url, transcript)
return transcript
```

**After (Orchestrator):**
```python
# Orchestrator handles all logic
manager = TranscriptionManager()
transcript = await manager.get_transcript(url)
```

**Reduction:** ~20 lines → 2 lines for common case

---

## Statistics

- **Implementation:** 215 lines of code
- **Tests:** 370 lines of code
- **Test-to-code ratio:** 1.7:1
- **Tests:** 16 total
- **Test execution time:** ~3 seconds
- **Pass rate:** 100%
- **Linter:** All checks passed

---

## References

- [ADR-009: Transcription Strategy](/docs/adr/009-transcription-strategy.md) - Multi-tier approach
- [Unit 3: YouTube Transcriber](/docs/devlog/2025-11-07-phase-2-unit-3-youtube-transcriber.md)
- [Unit 4: Audio Downloader](/docs/devlog/2025-11-07-phase-2-unit-4-audio-downloader.md)
- [Unit 5: Gemini Transcriber](/docs/devlog/2025-11-07-phase-2-unit-5-gemini-transcription.md)
- [Unit 6: Transcript Cache](/docs/devlog/2025-11-07-phase-2-unit-6-transcript-caching.md)
