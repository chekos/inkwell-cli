# Architecture: Phase 2 Transcription System

**Last Updated:** 2025-11-07
**Status:** Implemented and Deployed
**Phase:** 2

---

## System Overview

The transcription system uses a multi-tier strategy to optimize for both cost and quality. It coordinates multiple components to transcribe podcast episodes, falling back to more expensive methods only when necessary.

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         CLI Layer                            │
│  ┌──────────────────┐           ┌──────────────────┐       │
│  │ transcribe       │           │ cache            │       │
│  │ command          │           │ command          │       │
│  └────────┬─────────┘           └────────┬─────────┘       │
└───────────┼──────────────────────────────┼─────────────────┘
            │                              │
            ▼                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   Orchestration Layer                        │
│  ┌─────────────────────────────────────────────────────┐   │
│  │         TranscriptionManager                         │   │
│  │  - Coordinates multi-tier strategy                  │   │
│  │  - Tracks attempts and costs                        │   │
│  │  - Manages fallback logic                           │   │
│  └──────────┬─────────┬───────────────┬────────────────┘   │
└─────────────┼─────────┼───────────────┼────────────────────┘
              │         │               │
              ▼         ▼               ▼
┌─────────────────────────────────────────────────────────────┐
│                   Transcription Tiers                        │
│  ┌──────────┐    ┌────────────┐    ┌──────────────┐       │
│  │  Cache   │    │  YouTube   │    │   Gemini     │       │
│  │  (Tier 0)│    │  (Tier 1)  │    │   (Tier 2)   │       │
│  │          │    │            │    │              │       │
│  │  Free    │    │  Free      │    │  Paid        │       │
│  │  Instant │    │  ~1-2s     │    │  ~variable   │       │
│  └──────────┘    └──────┬─────┘    └───────┬──────┘       │
└──────────────────────────┼──────────────────┼──────────────┘
                           │                  │
                           ▼                  ▼
                    ┌──────────────┐   ┌─────────────┐
                    │  YouTube API │   │  Audio      │
                    │              │   │  Downloader │
                    └──────────────┘   └──────┬──────┘
                                              │
                                              ▼
                                       ┌─────────────┐
                                       │  Gemini API │
                                       └─────────────┘
```

---

## Component Diagram

```
┌──────────────────────────────────────────────────────────────┐
│                    Data Models (Shared)                       │
│  ┌────────────┐  ┌───────────────┐  ┌──────────────────┐   │
│  │ Transcript │  │ Transcript    │  │ Transcription    │   │
│  │            │  │ Segment       │  │ Result           │   │
│  │ - segments │  │ - start       │  │ - success        │   │
│  │ - metadata │  │ - duration    │  │ - transcript     │   │
│  │ - source   │  │ - text        │  │ - error          │   │
│  │ - cost     │  └───────────────┘  │ - attempts       │   │
│  └────────────┘                     │ - cost           │   │
│                                      └──────────────────┘   │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│                    Core Components                            │
│                                                               │
│  TranscriptionManager                                        │
│  ├─ transcribe(url, use_cache, skip_youtube)                │
│  ├─ get_transcript(url)                                      │
│  ├─ force_refresh(url)                                       │
│  ├─ cache_stats()                                            │
│  └─ clear_cache()                                            │
│                                                               │
│  YouTubeTranscriber                                          │
│  ├─ can_transcribe(url) -> bool                             │
│  ├─ transcribe(url) -> Transcript                           │
│  ├─ extract_video_id(url) -> str                            │
│  └─ is_youtube_url(url) -> bool                             │
│                                                               │
│  GeminiTranscriber                                           │
│  ├─ can_transcribe(file_path) -> bool                       │
│  ├─ transcribe(file_path, url) -> Transcript                │
│  ├─ estimate_cost(file_path) -> CostEstimate                │
│  └─ confirm_cost(estimate) -> bool                          │
│                                                               │
│  AudioDownloader                                             │
│  ├─ download(url) -> Path                                   │
│  ├─ get_info(url) -> dict                                   │
│  └─ progress_callback: Callable                             │
│                                                               │
│  TranscriptCache                                             │
│  ├─ get(url) -> Transcript | None                           │
│  ├─ set(url, transcript)                                     │
│  ├─ delete(url)                                              │
│  ├─ clear() -> int                                           │
│  ├─ clear_expired() -> int                                   │
│  └─ stats() -> dict                                          │
└──────────────────────────────────────────────────────────────┘
```

---

## Sequence Diagrams

### Happy Path: YouTube Video (Free)

```
User          CLI         Manager      Cache      YouTube     Result
 │             │            │           │           │           │
 │──transcribe─>│            │           │           │           │
 │             │──transcribe()─>         │           │           │
 │             │            │──get()────>│           │           │
 │             │            │<─None──────│           │           │
 │             │            │                        │           │
 │             │            │──can_transcribe()─────>│           │
 │             │            │<────True───────────────│           │
 │             │            │                        │           │
 │             │            │──transcribe()─────────>│           │
 │             │            │                        │───API────>│
 │             │            │                        │<──data────│
 │             │            │<───Transcript──────────│           │
 │             │            │                        │           │
 │             │            │──set()────>│           │           │
 │             │            │<───OK──────│           │           │
 │             │            │                        │           │
 │             │<───Result──│                        │           │
 │<──output────│            │                        │           │
```

---

### Fallback Path: Non-YouTube URL (Paid)

```
User      CLI      Manager   Cache   YouTube  Downloader  Gemini   Result
 │         │         │        │        │          │          │        │
 │─transcribe>        │        │        │          │          │        │
 │         │─transcribe()>     │        │          │          │        │
 │         │         │─get()─>│        │          │          │        │
 │         │         │<─None──│        │          │          │        │
 │         │         │                 │          │          │        │
 │         │         │─can_transcribe()>          │          │        │
 │         │         │<──False────────│           │          │        │
 │         │         │                            │          │        │
 │         │         │─download()────────────────>│          │        │
 │         │         │                            │──yt-dlp─>│        │
 │         │         │<────audio.mp3──────────────│          │        │
 │         │         │                                       │        │
 │         │         │─estimate_cost()───────────────────────>        │
 │         │         │<────$0.0015────────────────────────────        │
 │         │                                                  │        │
 │<──confirm?────────────────────────────────────────────────────────>│
 │──Yes────────────────────────────────────────────────────>│         │
 │         │         │                                       │         │
 │         │         │─transcribe()──────────────────────────>        │
 │         │         │                                       │──API──>│
 │         │         │                                       │<─data──│
 │         │         │<────Transcript─────────────────────────        │
 │         │         │                            │          │        │
 │         │         │─set()─>│                   │          │        │
 │         │         │<─OK────│                   │          │        │
 │         │         │                            │          │        │
 │         │<─Result─│                            │          │        │
 │<─output─│         │                            │          │        │
```

---

### Cache Hit (Fastest Path)

```
User          CLI         Manager      Cache       Result
 │             │            │           │            │
 │──transcribe─>│            │           │            │
 │             │──transcribe()─>         │            │
 │             │            │──get()────>│            │
 │             │            │<─Transcript─           │
 │             │            │            │            │
 │             │<───Result──│            │            │
 │<──output────│            │            │            │
```

---

## Data Flow Diagram

### Transcription Data Flow

```
┌─────────────┐
│ Episode URL │
└──────┬──────┘
       │
       ▼
┌─────────────────┐
│ URL Hash        │──────────┐
│ (SHA-256)       │          │
└──────┬──────────┘          │
       │                     │
       ▼                     ▼
┌─────────────────┐   ┌──────────────┐
│ Cache Lookup    │   │ Cache Key    │
│ (JSON file)     │   │ abc123...    │
└──────┬──────────┘   └──────────────┘
       │
       ├─── Cache Hit ───> Return Transcript
       │
       └─── Cache Miss ──┐
                         │
                         ▼
              ┌──────────────────┐
              │ YouTube Check    │
              └────┬──────┬──────┘
                   │      │
        YouTube URL│      │Other URL
                   │      │
                   ▼      ▼
         ┌──────────┐  ┌─────────────┐
         │ YouTube  │  │ Download    │
         │ API      │  │ Audio       │
         └────┬─────┘  └──────┬──────┘
              │                │
              │                ▼
              │         ┌──────────────┐
              │         │ Estimate     │
              │         │ Cost         │
              │         └──────┬───────┘
              │                │
              │                ▼
              │         ┌──────────────┐
              │         │ User         │
              │         │ Confirms?    │
              │         └──────┬───────┘
              │                │
              │                ▼
              │         ┌──────────────┐
              │         │ Gemini API   │
              │         └──────┬───────┘
              │                │
              └────────┬───────┘
                       │
                       ▼
              ┌─────────────────┐
              │ Parse Segments  │
              └────────┬─────────┘
                       │
                       ▼
              ┌─────────────────┐
              │ Create          │
              │ Transcript      │
              └────────┬─────────┘
                       │
                       ▼
              ┌─────────────────┐
              │ Save to Cache   │
              └────────┬─────────┘
                       │
                       ▼
              ┌─────────────────┐
              │ Return Result   │
              └─────────────────┘
```

---

## Decision Trees

### Transcription Strategy Decision Tree

```
                    Episode URL
                        │
                        ▼
                  ┌──────────┐
                  │ Use      │──No──> Skip to YouTube check
                  │ cache?   │
                  └────┬─────┘
                       │ Yes
                       ▼
                  ┌──────────┐
                  │ Cached?  │──Yes──> Return from cache
                  └────┬─────┘
                       │ No
                       ▼
                  ┌──────────┐
                  │ YouTube  │──No──> Skip to audio download
                  │ URL?     │
                  └────┬─────┘
                       │ Yes
                       ▼
                  ┌──────────┐
                  │ Skip     │──Yes──> Skip to audio download
                  │ YouTube? │
                  └────┬─────┘
                       │ No
                       ▼
                  ┌──────────────┐
                  │ Transcript   │──Yes──> Parse & return
                  │ available?   │
                  └────┬─────────┘
                       │ No
                       ▼
                  ┌──────────────┐
                  │ Download     │
                  │ audio        │
                  └────┬─────────┘
                       │
                       ▼
                  ┌──────────────┐
                  │ Gemini       │──No──> Return error
                  │ configured?  │
                  └────┬─────────┘
                       │ Yes
                       ▼
                  ┌──────────────┐
                  │ Estimate     │
                  │ cost         │
                  └────┬─────────┘
                       │
                       ▼
                  ┌──────────────┐
                  │ User         │──No──> Return cancelled
                  │ confirms?    │
                  └────┬─────────┘
                       │ Yes
                       ▼
                  ┌──────────────┐
                  │ Transcribe   │
                  │ with Gemini  │
                  └────┬─────────┘
                       │
                       ▼
                  ┌──────────────┐
                  │ Cache &      │
                  │ return       │
                  └──────────────┘
```

---

## Storage Architecture

### File System Layout

```
~/.local/share/inkwell/
├── cache/
│   └── transcripts/
│       ├── 3a7bd3e5f9c2d1a6b8e4f2c1a9d7e5b3.json  # Cached transcript
│       ├── 7e5c9a3b1f4d6e8c2a5b7f9d3e1c6a4b.json
│       └── ...
│
├── audio/                              # Temp audio downloads
│   ├── episode_abc123.mp3             # Cleaned up after transcription
│   └── ...
│
└── logs/
    └── inkwell.log                     # Application logs

~/.config/inkwell/
├── config.yaml                         # Global configuration
├── feeds.yaml                          # Podcast feeds
└── .keyfile                            # Encryption key
```

### Cache File Format

```json
{
  "url": "https://youtube.com/watch?v=abc123",
  "segments": [
    {
      "start": 0.0,
      "duration": 5.2,
      "text": "Welcome to the podcast."
    },
    ...
  ],
  "language": "en",
  "source": "youtube",
  "duration_seconds": 3600.5,
  "word_count": 5234,
  "cost_usd": 0.0,
  "created_at": "2025-11-07T12:34:56Z"
}
```

---

## Error Handling Architecture

### Error Propagation Strategy

```
┌─────────────────────────────────────────────────────────┐
│                    Error Hierarchy                       │
│                                                          │
│  Exception (Python base)                                │
│      │                                                   │
│      ├─ TranscriptionError (Base)                       │
│      │    ├─ YouTubeError                               │
│      │    │    ├─ TranscriptsDisabled                   │
│      │    │    ├─ VideoUnavailable                      │
│      │    │    └─ NoTranscriptFound                     │
│      │    │                                              │
│      │    ├─ GeminiError                                │
│      │    │    ├─ APIKeyMissing                         │
│      │    │    ├─ CostRejected                          │
│      │    │    └─ TranscriptionFailed                   │
│      │    │                                              │
│      │    └─ CacheError                                 │
│      │         ├─ CacheCorrupted                        │
│      │         └─ CacheWriteFailed                      │
│      │                                                   │
│      └─ AudioDownloadError                              │
│           ├─ DownloadFailed                             │
│           └─ UnsupportedFormat                          │
└─────────────────────────────────────────────────────────┘
```

### Error Recovery Strategy

1. **Tier-level errors**: Try next tier
2. **Transient errors**: Retry with exponential backoff (future)
3. **Permanent errors**: Return clear error message
4. **All tiers failed**: Return comprehensive error with attempts list

---

## Performance Characteristics

### Latency by Tier

| Tier | Method | Typical Latency | P99 Latency |
|------|--------|-----------------|-------------|
| 0 | Cache | <10ms | 50ms |
| 1 | YouTube | 500ms - 2s | 5s |
| 2 | Gemini | 10s - 60s | 120s |

### Cost by Tier

| Tier | Method | Cost per Episode |
|------|--------|------------------|
| 0 | Cache | $0.00 |
| 1 | YouTube | $0.00 |
| 2 | Gemini | $0.001 - $0.005 |

### Throughput

- **Cache**: 100+ req/s (limited by disk I/O)
- **YouTube**: 10-20 req/s (API rate limits)
- **Gemini**: 1-5 req/s (upload + processing time)

---

## Security Considerations

### API Key Storage

```
┌──────────────────────────────────────┐
│  Environment Variables (Preferred)   │
│  - GEMINI_API_KEY                    │
│  - Loaded at runtime                 │
│  - Not stored in config              │
└──────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────┐
│  Config File (Fallback)              │
│  - config.yaml                       │
│  - Plain text (user responsible)     │
│  - File permissions: 600             │
└──────────────────────────────────────┘
```

### Cache Security

- Cache files: World-readable (contain public data)
- No sensitive data in cache
- URL hashing prevents path traversal

---

## Scalability Considerations

### Current Limits

- **Single-threaded**: One transcription at a time
- **Local cache**: Limited by disk space
- **API rate limits**: YouTube (10-20/s), Gemini (varies)

### Future Enhancements

1. **Parallel transcription**: Process multiple episodes concurrently
2. **Distributed cache**: Redis for shared cache across machines
3. **Queue system**: Celery for background processing
4. **Rate limiting**: Respect API limits with token bucket

---

## Monitoring & Observability

### Metrics to Track

```python
# Cost metrics
total_cost_usd: float
cost_by_source: dict[str, float]
cost_per_episode: float

# Performance metrics
transcription_duration: float
cache_hit_rate: float
tier_usage: dict[str, int]

# Error metrics
errors_by_type: dict[str, int]
failed_transcriptions: int
success_rate: float
```

### Logging Strategy

```
DEBUG: Detailed execution flow
INFO:  Normal operations (cache hits, API calls)
WARNING: Fallbacks, retries, non-critical issues
ERROR: Failures, exceptions, critical issues
```

---

## API Interfaces

### TranscriptionManager API

```python
class TranscriptionManager:
    async def transcribe(
        self,
        episode_url: str,
        use_cache: bool = True,
        skip_youtube: bool = False,
    ) -> TranscriptionResult:
        """
        Transcribe episode with multi-tier strategy.

        Returns:
            TranscriptionResult with transcript data or error
        """

    async def get_transcript(
        self,
        episode_url: str,
        force_refresh: bool = False,
    ) -> Transcript | None:
        """
        Get transcript, raising exception on error.

        Returns:
            Transcript if successful, None if not found
        Raises:
            TranscriptionError if transcription fails
        """

    def cache_stats(self) -> dict:
        """Get cache statistics."""

    def clear_cache(self) -> int:
        """Clear all cache entries."""
```

---

## Dependencies

### External APIs

- **YouTube Transcript API**: Free, rate-limited
- **Google Gemini API**: Paid ($0.00025/1K input tokens)
- **yt-dlp**: Local tool, free

### Python Libraries

- `youtube-transcript-api`: YouTube transcript extraction
- `google-generativeai`: Gemini API client
- `yt-dlp`: Media downloader
- `pydantic`: Data validation
- `httpx`: Async HTTP client

---

## Testing Strategy

### Unit Tests

- Each component tested in isolation
- Mock external APIs
- Test error paths
- Test edge cases

### Integration Tests

- Components working together
- Real cache operations
- CLI command execution
- End-to-end flows (mocked APIs)

### Manual Tests

- Real YouTube videos
- Real Gemini API calls
- Cost confirmation flow
- Cache behavior

---

## Future Architecture Enhancements

### Phase 3: LLM Extraction

```
Transcript
    │
    ▼
┌─────────────┐
│ LLM         │
│ Extractor   │
└─────┬───────┘
      │
      ├─> Summary
      ├─> Quotes
      ├─> Key Concepts
      ├─> Entities
      └─> Metadata
```

### Potential Improvements

1. **Webhook support**: Async transcription with callbacks
2. **Batch processing**: Transcribe multiple episodes in parallel
3. **Streaming**: Real-time transcription for live content
4. **Alternative APIs**: Whisper, AssemblyAI, Deepgram
5. **Quality scoring**: Rate transcript quality, retry if poor

---

## Conclusion

The Phase 2 transcription architecture successfully delivers:

- ✅ Multi-tier cost optimization
- ✅ Reliable fallback strategy
- ✅ Clean component separation
- ✅ Testable design
- ✅ Extensible for future enhancements

**Architecture Status:** Production-ready for Phase 3 integration.
