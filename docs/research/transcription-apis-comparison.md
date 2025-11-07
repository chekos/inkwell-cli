# Research: Transcription APIs Comparison

**Date**: 2025-11-07
**Author**: Claude (Phase 2 Research)
**Status**: Complete

## Overview

This document compares different approaches for transcribing podcast audio to inform Phase 2 architecture decisions.

---

## Options Evaluated

### 1. YouTube Transcript API (via youtube-transcript-api)

**Description**: Extract existing transcripts from YouTube-hosted videos using the `youtube-transcript-api` Python library.

#### Pros
- ✅ **Free** - No API costs
- ✅ **Fast** - Transcripts already generated, just fetching
- ✅ **High quality** - Many channels have manual or refined transcripts
- ✅ **Timestamps included** - Precise segment timing
- ✅ **Multiple languages** - Support for non-English content
- ✅ **Well-maintained library** - Active development, good documentation

#### Cons
- ❌ **Availability** - Not all videos have transcripts
- ❌ **Rate limiting** - YouTube can block requests (observed 403 errors)
- ❌ **YouTube-only** - Only works for YouTube-hosted content
- ❌ **Network dependent** - Requires internet, can be blocked
- ❌ **No control** - Dependent on YouTube's infrastructure

#### Cost
**FREE**

#### Observed Behavior
During testing (2025-11-07):
- Encountered 403 Forbidden errors for multiple podcast videos
- Likely due to environment restrictions or YouTube rate limiting
- Demonstrates need for robust fallback strategy

#### API Example
```python
from youtube_transcript_api import YouTubeTranscriptApi

api = YouTubeTranscriptApi()
transcript_list = api.list(video_id)
transcript = transcript_list.find_transcript(['en'])
data = transcript.fetch()

# Returns:
# [
#   {"text": "Hello", "start": 0.0, "duration": 1.5},
#   {"text": "world", "start": 1.5, "duration": 1.0},
#   ...
# ]
```

---

### 2. Google Gemini API (gemini-2.0-flash-exp)

**Description**: Upload audio files to Gemini and request transcription via prompting.

#### Pros
- ✅ **Universal** - Works with any audio source
- ✅ **High quality** - State-of-the-art AI transcription
- ✅ **Flexible** - Can handle various audio formats
- ✅ **Timestamping** - Can be prompted to add timestamps
- ✅ **Google infrastructure** - Reliable, scalable
- ✅ **Multimodal** - Can add context from video if needed

#### Cons
- ❌ **Costs money** - ~$0.01 per minute of audio
- ❌ **Slower** - Upload + processing time
- ❌ **File size limits** - Large episodes may need splitting
- ❌ **Requires preprocessing** - Need to download audio first
- ❌ **API quotas** - Rate limits and daily quotas

#### Cost
**~$0.01 per minute** (as of 2025)
- 30-minute podcast: ~$0.30
- 60-minute podcast: ~$0.60
- Average with 70% YouTube coverage: ~$0.18/episode

#### API Flow
```python
import google.generativeai as genai

# Upload audio
audio_file = genai.upload_file(path="episode.m4a")

# Wait for processing
while audio_file.state.name == "PROCESSING":
    await asyncio.sleep(1)
    audio_file = genai.get_file(audio_file.name)

# Request transcription
model = genai.GenerativeModel("gemini-2.0-flash-exp")
response = model.generate_content([
    audio_file,
    "Transcribe this audio with timestamps every 30 seconds..."
])
```

---

### 3. OpenAI Whisper (Local)

**Description**: Run Whisper model locally for transcription.

#### Pros
- ✅ **No API costs** - One-time model download
- ✅ **Privacy** - All processing local
- ✅ **High quality** - State-of-the-art accuracy
- ✅ **Offline** - No internet required after setup

#### Cons
- ❌ **Hardware requirements** - GPU recommended for reasonable speed
- ❌ **Slow on CPU** - 10-30x realtime without GPU
- ❌ **Setup complexity** - Need to install models, dependencies
- ❌ **Resource intensive** - RAM and disk space
- ❌ **Maintenance** - User responsible for updates

#### Cost
**FREE** (after initial setup)

#### Decision
**Not chosen for Phase 2** - Adds significant complexity and hardware requirements. May revisit in v0.4+ as an opt-in feature.

---

### 4. Third-Party Services (AssemblyAI, Deepgram, etc.)

**Description**: Commercial transcription APIs.

#### Pros
- ✅ **Specialized** - Purpose-built for transcription
- ✅ **Features** - Speaker diarization, punctuation, etc.
- ✅ **Reliable** - Enterprise-grade SLAs

#### Cons
- ❌ **Cost** - $0.015-0.025 per minute
- ❌ **Privacy** - Audio sent to third party
- ❌ **Vendor lock-in** - API changes, pricing changes
- ❌ **Additional account** - Need API keys, billing setup

#### Decision
**Not chosen for Phase 2** - Higher cost than Gemini, less integrated with our stack. Gemini provides good enough quality at lower cost.

---

## Recommended Strategy: Multi-Tier Fallback

### Tier 1: YouTube Transcript API (Primary)
**When**: Episode URL is a YouTube video
**Why**: Free, fast, usually high quality
**Fallback trigger**: Transcript unavailable, API errors (403, 404, etc.)

### Tier 2: Gemini Transcription (Fallback)
**When**: YouTube fails or URL is non-YouTube source
**Why**: Universal, high quality, reasonable cost
**Cost mitigation**: Caching (never transcribe twice), user confirmation for expensive operations

### Architecture
```
Episode URL
    │
    ├─► Is YouTube? → Try YouTube Transcript API
    │     ├─► Success → Cache → Done ✅
    │     └─► Failed → Fall through to Tier 2
    │
    └─► Tier 2: Download audio → Gemini → Cache → Done ✅
```

---

## Cost Analysis

### Scenario 1: High YouTube Coverage (70%)
- 100 episodes processed
- 70 from YouTube (FREE)
- 30 from Gemini (avg 45 min each)
- Cost: 30 * 45 * $0.01/min = **$13.50**

### Scenario 2: Low YouTube Coverage (30%)
- 100 episodes processed
- 30 from YouTube (FREE)
- 70 from Gemini (avg 45 min each)
- Cost: 70 * 45 * $0.01/min = **$31.50**

### With Caching
- Repeat episodes: **$0** (cache hit)
- New episodes: Cost as above
- **Cache hit rate determines actual costs**

---

## Quality Comparison

| Aspect | YouTube | Gemini | Whisper Local |
|--------|---------|---------|---------------|
| Accuracy | High (manual) / Medium (auto) | High | Very High |
| Speed | Instant | 2-5 minutes | 10-30x realtime (CPU) |
| Cost | FREE | ~$0.60/hr | FREE |
| Availability | 30-70% of videos | 100% | 100% |
| Timestamps | Native | Prompted | Native |
| Setup | pip install | API key | Model download + GPU |

---

## Risks & Mitigation

### Risk 1: YouTube API Blocking
**Evidence**: Observed 403 errors during testing
**Impact**: Primary tier unavailable
**Mitigation**:
- Graceful fallback to Gemini
- Retry logic with exponential backoff
- Clear error messages to user

### Risk 2: Gemini Costs Higher Than Expected
**Impact**: User surprise at API bills
**Mitigation**:
- Show cost estimate before transcribing
- Require confirmation for transcriptions > $1.00
- Aggressive caching to minimize redundant work
- Consider monthly budget tracking (future feature)

### Risk 3: Transcript Quality Issues
**Impact**: Poor LLM extraction in Phase 3
**Mitigation**:
- Manual review of sample transcripts
- Prompt engineering for Gemini
- Quality validation (word count, duration checks)

---

## Recommendations

### For Phase 2 (v0.2)
1. ✅ Implement YouTube transcript extraction as primary
2. ✅ Implement Gemini transcription as fallback
3. ✅ Aggressive caching (never transcribe twice)
4. ✅ Cost tracking and user warnings
5. ✅ Graceful error handling at each tier

### For Future Versions
- **v0.3+**: Add transcript quality metrics
- **v0.4+**: Optional Whisper local (for privacy-conscious users)
- **v0.5+**: Speaker diarization (if Gemini adds support)
- **v0.6+**: Budget tracking and usage reports

---

## References

- [youtube-transcript-api Documentation](https://github.com/jdepoix/youtube-transcript-api)
- [Google Gemini API Pricing](https://ai.google.dev/pricing)
- [OpenAI Whisper](https://github.com/openai/whisper)
- [Phase 2 Implementation Plan](../devlog/2025-11-07-phase-2-detailed-plan.md)

---

## Conclusion

The multi-tier strategy (YouTube → Gemini) provides the best balance of:
- **Cost optimization** (free when possible)
- **Reliability** (fallback when YouTube unavailable)
- **Quality** (both sources produce good transcripts)
- **User experience** (fast when YouTube works, universal coverage)

The 403 errors observed during testing actually **validate this architecture** - relying solely on YouTube would leave users stranded when the API is blocked or unavailable. The Gemini fallback ensures the tool always works, regardless of source or availability.

**Decision**: Proceed with multi-tier implementation as designed. ✅
