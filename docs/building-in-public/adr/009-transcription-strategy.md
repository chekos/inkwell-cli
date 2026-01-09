# ADR-009: Multi-Tier Transcription Strategy

**Date**: 2025-11-07
**Status**: Accepted
**Context**: Phase 2 - Transcription Layer
**Related**: [Research: Transcription APIs](../research/transcription-apis-comparison.md)

---

## Context

Phase 2 requires transcribing podcast audio to text. We need a strategy that balances cost, quality, reliability, and universal compatibility across different podcast sources.

Key constraints:
- Cost sensitivity (users processing many episodes)
- Variable availability (not all podcasts on YouTube)
- Quality requirements (accurate transcription for LLM extraction)
- Reliability (tool must work consistently)

---

## Decision

We will implement a **multi-tier transcription strategy** with automatic fallback:

### Tier 1: YouTube Transcript API (Primary)
- **When**: Episode URL is from YouTube
- **Method**: Use `youtube-transcript-api` to fetch existing transcripts
- **Cost**: FREE
- **Speed**: 1-3 seconds
- **Fallback trigger**: Transcript unavailable, API errors (403, 404, etc.)

### Tier 2: Gemini Transcription (Fallback)
- **When**: Tier 1 fails OR non-YouTube source
- **Method**: Download audio with `yt-dlp`, transcribe with Gemini API
- **Cost**: ~$0.01/minute (~$0.60/hour)
- **Speed**: 2-5 minutes
- **Fallback trigger**: None (terminal fallback)

### Architecture Flow
```
Episode URL
    │
    ├─► Is YouTube URL?
    │     ├─► Yes → Try YouTubeTranscriber
    │     │           ├─► Success → Cache → Return ✅
    │     │           └─► Failed (403/404/unavailable)
    │     │                     ↓
    │     └─► No → Skip to Tier 2
    │
    └─► Tier 2: AudioDownloader + GeminiTranscriber
              ├─► Download audio (yt-dlp)
              ├─► Transcribe (Gemini)
              └─► Cache → Return ✅
```

---

## Alternatives Considered

### Alternative 1: Gemini-Only (No YouTube Fallback)
**Approach**: Always download audio and transcribe with Gemini

**Pros**:
- Simpler architecture (one code path)
- Consistent quality
- Universal (works for all sources)

**Cons**:
- Higher cost (~3-4x more expensive)
- Slower (always 2-5 minutes)
- Wastes free YouTube transcripts
- **Cost estimate**: $0.60/episode vs $0.18/episode with multi-tier

**Verdict**: ❌ Rejected - Unnecessarily expensive

---

### Alternative 2: Whisper Local (No Cloud APIs)
**Approach**: Run OpenAI Whisper model locally

**Pros**:
- No API costs after setup
- Privacy (all local processing)
- Offline capability
- High quality transcription

**Cons**:
- Hardware requirements (GPU for reasonable speed)
- Slow on CPU (10-30x realtime)
- Setup complexity (model download, dependencies)
- Resource intensive (RAM, disk)
- User maintenance burden

**Verdict**: ❌ Rejected for Phase 2 - Consider as opt-in feature in v0.4+

---

### Alternative 3: Third-Party Services (AssemblyAI, Deepgram)
**Approach**: Use specialized transcription APIs

**Pros**:
- Purpose-built for transcription
- Features (speaker diarization, punctuation)
- Enterprise SLAs

**Cons**:
- Higher cost ($0.015-0.025/minute vs $0.01/minute)
- Privacy concerns (third-party audio processing)
- Vendor lock-in
- Additional account setup

**Verdict**: ❌ Rejected - Gemini provides sufficient quality at lower cost

---

### Alternative 4: YouTube-Only (No Fallback)
**Approach**: Only support YouTube-hosted podcasts

**Pros**:
- FREE (no transcription costs)
- Fast (instant)
- Simple implementation

**Cons**:
- Limited scope (only YouTube)
- Excludes private feeds (Substack, Patreon, etc.)
- Availability issues (observed 403 errors)
- Unreliable (depends on YouTube infrastructure)

**Verdict**: ❌ Rejected - Too limiting, unreliable as sole method

---

## Rationale

The multi-tier strategy provides the best balance:

### 1. Cost Optimization
**Scenario**: 100 episodes, 70% on YouTube with transcripts available

- **Tier 1 success (70 episodes)**: FREE
- **Tier 2 fallback (30 episodes, avg 45 min)**: 30 × 45 × $0.01 = **$13.50**
- **Total**: **$13.50** for 100 episodes

vs. Gemini-only: 100 × 45 × $0.01 = **$45.00**

**Savings**: 70% cost reduction

### 2. Universal Compatibility
- YouTube podcasts: Tier 1 → Tier 2 fallback
- Non-YouTube (Substack, direct RSS, etc.): Tier 2 works
- Private feeds: Tier 2 with authentication

**Coverage**: 100% of sources

### 3. Reliability Through Redundancy
- YouTube API blocked? → Gemini fallback
- Transcript unavailable? → Gemini fallback
- Non-YouTube source? → Gemini handles it

**Failure modes**: Gracefully handled at each tier

### 4. Quality
- YouTube transcripts: Often high quality (manual or refined auto-gen)
- Gemini transcription: State-of-the-art AI quality
- **Both sources**: Sufficient for LLM extraction in Phase 3

### 5. User Experience
- Fast when possible (YouTube instant)
- Universal when needed (Gemini fallback)
- Cost-transparent (show estimates)
- Always works (no "unsupported source" errors)

---

## Consequences

### Positive

1. **Cost-effective**: 70% savings vs single-tier Gemini
2. **Fast**: Instant when YouTube works
3. **Universal**: All podcast sources supported
4. **Reliable**: Multiple fallback options
5. **Scalable**: Can add more tiers in future (e.g., Whisper local)

### Negative

1. **Complexity**: Two code paths to maintain
2. **Testing**: Need to test both tiers thoroughly
3. **Error handling**: More failure modes to consider
4. **Documentation**: Users need to understand multi-tier behavior

### Mitigation

- **Complexity**: Abstract behind `TranscriptionManager` interface
- **Testing**: Comprehensive unit + integration tests
- **Error handling**: Clear error messages, attempt tracking
- **Documentation**: User guide explains strategy benefits

---

## Implementation Notes

### Phase 2 Implementation

```python
class TranscriptionManager:
    async def transcribe(
        self,
        episode_url: str,
        force_refresh: bool = False
    ) -> TranscriptionResult:
        # Check cache first
        if cached := self.cache.get(episode_url):
            return cached

        attempts = []

        # Tier 1: YouTube (if applicable)
        if await self.youtube_transcriber.can_transcribe(episode_url):
            try:
                transcript = await self.youtube_transcriber.transcribe(episode_url)
                attempts.append("youtube")
                self.cache.set(episode_url, transcript)
                return TranscriptionResult(success=True, transcript=transcript)
            except TranscriptionError as e:
                attempts.append("youtube_failed")
                logger.warning(f"YouTube failed: {e}, falling back to Gemini")

        # Tier 2: Gemini (always fallback)
        audio_path = await self.audio_downloader.download(episode_url)
        transcript = await self.gemini_transcriber.transcribe(episode_url, audio_path)
        attempts.append("gemini")

        self.cache.set(episode_url, transcript)
        return TranscriptionResult(success=True, transcript=transcript, attempts=attempts)
```

### Future Tiers (v0.4+)

Could add:
- **Tier 0**: Check for pre-existing transcript file (user-provided)
- **Tier 3**: Whisper local (opt-in, for users with GPUs)
- **Tier 4**: Manual upload (user transcribes, pastes text)

---

## Validation

### Observed Evidence

**During research (2025-11-07)**:
- YouTube transcript API returned 403 errors for test videos
- Demonstrates real-world unreliability
- Validates need for fallback strategy

**Expected in production**:
- ~30-70% YouTube transcript availability (varies by podcast type)
- Some YouTube videos blocked/rate-limited
- Non-YouTube sources require Tier 2

### Success Metrics

**Phase 2 goals**:
- ✅ 70%+ cost savings vs Gemini-only
- ✅ 100% source compatibility
- ✅ < 10 second transcription time when YouTube works
- ✅ Graceful fallback in all failure scenarios

---

## References

- [Research: Transcription APIs Comparison](../research/transcription-apis-comparison.md)
- [Phase 2 Implementation Plan](../devlog/2025-11-07-phase-2-detailed-plan.md)
- [youtube-transcript-api Documentation](https://github.com/jdepoix/youtube-transcript-api)
- [Google Gemini API Pricing](https://ai.google.dev/pricing)

---

## Approval

**Status**: ✅ Accepted

**Date**: 2025-11-07

**Reviewers**: Claude (Phase 2 architect)

**Next steps**:
1. Implement YouTubeTranscriber (Unit 3)
2. Implement AudioDownloader (Unit 4)
3. Implement GeminiTranscriber (Unit 5)
4. Implement TranscriptionManager orchestration (Unit 7)
