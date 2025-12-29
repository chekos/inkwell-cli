# ADR-010: Transcript Caching Strategy

**Date**: 2025-11-07
**Status**: Accepted
**Context**: Phase 2 - Transcription Layer
**Related**: [Research: Caching Strategy](../research/transcript-caching-strategy.md), [ADR-009](./009-transcription-strategy.md)

---

## Context

Transcription is expensive (time and money):
- YouTube API: 1-3 seconds (free)
- Gemini transcription: 2-5 minutes + ~$0.60/hour

Common scenarios requiring repeat access:
- User re-processes with different extraction options (Phase 3)
- Failed LLM extraction requiring retry
- Testing and development
- Reviewing past episodes

Without caching, each operation requires full transcription, multiplying costs unnecessarily.

---

## Decision

Implement a **file-based JSON cache** with the following characteristics:

### Cache Storage
- **Location**: `~/.cache/inkwell/transcripts/` (XDG cache directory)
- **Format**: JSON files (one per episode)
- **Naming**: SHA256 hash of episode URL
- **Permissions**: 0o700 (owner-only access)

### Cache Key Strategy
```python
import hashlib

def generate_cache_key(episode_url: str) -> str:
    return hashlib.sha256(episode_url.encode()).hexdigest()

# Example:
# URL: "https://youtube.com/watch?v=abc123"
# Key: "a3f5b2c1d8e9f4a0b1c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7"
# File: ~/.cache/inkwell/transcripts/a3f5b2c1d8...d5e6f7.json
```

### Cache Entry Format
```json
{
  "segments": [
    {"text": "Hello world", "start": 0.0, "duration": 2.0},
    ...
  ],
  "source": "youtube",
  "language": "en",
  "episode_url": "https://...",
  "created_at": "2025-11-07T10:30:00Z",
  "duration_seconds": 3600.0,
  "word_count": 15000,
  "cost_usd": 0.60
}
```

### Time-To-Live (TTL)
- **Default**: 30 days
- **Rationale**: Balance between freshness and cost savings
- **Cleanup**: Automatic on startup (if > 24h since last cleanup)
- **Override**: User can manually clear cache anytime

### Cache Operations
- **get(url)**: Retrieve cached transcript (None if miss/expired)
- **set(url, transcript)**: Store transcript
- **invalidate(url)**: Remove specific entry
- **clear()**: Remove all cache
- **cleanup()**: Remove expired entries

---

## Alternatives Considered

### Alternative 1: SQLite Database

**Approach**: Store transcripts in SQLite database with indexing

**Pros**:
- Indexed queries for analytics
- ACID transactions
- Built-in (no external deps)

**Cons**:
- Overkill for key-value storage
- Less inspectable (need SQL client)
- Schema migrations needed
- More complexity

**Verdict**: ❌ Rejected - Too complex for our simple needs

---

### Alternative 2: No Persistent Cache (In-Memory Only)

**Approach**: Cache only during session, lost on exit

**Pros**:
- Simplest implementation
- Fastest (no I/O)

**Cons**:
- No cost savings across sessions
- User re-transcribes every run
- **Impact**: $0.60 per episode every time

**Verdict**: ❌ Rejected - Defeats purpose of caching

---

### Alternative 3: Redis/Memcached

**Approach**: External cache server

**Pros**:
- Optimized for caching
- Built-in TTL
- Very fast

**Cons**:
- External dependency (server must run)
- Overkill for single-user CLI
- Setup complexity
- Not suitable for occasional-use tool

**Verdict**: ❌ Rejected - Over-engineered for use case

---

### Alternative 4: Cache Transcripts in SQLite, Metadata in JSON

**Approach**: Hybrid system

**Pros**:
- Fast queries on metadata
- Efficient storage

**Cons**:
- Complexity of two systems
- Not worth the trade-off

**Verdict**: ❌ Rejected - Unnecessary complexity

---

## Rationale

### Why File-Based JSON?

1. **Simplicity**
   - No external dependencies
   - No schema migrations
   - Easy to understand

2. **Debuggability**
   - Users can inspect cached data: `cat ~/.cache/inkwell/transcripts/*.json`
   - Manual editing for testing
   - Transparent behavior

3. **XDG Compliance**
   - Standard cache location
   - Respects user's XDG environment variables
   - Plays well with system cache management

4. **Performance**
   - "Good enough" for expected scale
   - Typical: 10-100 cached episodes
   - File operations: < 10ms
   - Not a bottleneck

5. **Portability**
   - Easy backup/restore (copy directory)
   - Works across platforms
   - No database corruption issues

### Why SHA256 for Cache Keys?

1. **Deterministic**: Same URL → same key
2. **Collision-resistant**: Different URLs → different keys (256-bit space)
3. **Fixed length**: Manageable filenames (64 hex characters)
4. **Fast**: Negligible hashing overhead

### Why 30-Day TTL?

1. **Long enough**: Covers typical development iteration
2. **Short enough**: Prevents stale data accumulation
3. **Reasonable**: Podcast episodes don't change often
4. **User control**: Manual cache clearing available anytime

**Trade-off**: More aggressive TTL (7 days) → fresher data but less cost savings

---

## Consequences

### Positive

1. **Cost Savings**
   - First transcription: $0.60
   - Subsequent accesses: $0.00
   - **ROI**: Pays for itself on second access

2. **Performance**
   - First transcription: 2-5 minutes
   - Cache hit: < 100ms
   - **50-3000x speedup**

3. **User Experience**
   - Instant results for repeat operations
   - Can experiment with different settings without re-transcription
   - Predictable costs

4. **Development**
   - Fast iteration during testing
   - No API costs for development
   - Easy debugging (inspect cache files)

### Negative

1. **Disk Space**
   - ~500KB per cached episode
   - 100 episodes = ~50MB
   - 1000 episodes = ~500MB
   - **Mitigation**: TTL cleanup, user control

2. **Stale Data Risk**
   - Cached transcript may differ from current (if episode edited)
   - **Mitigation**: 30-day TTL, manual refresh with `--force`

3. **No Query Capabilities**
   - Can't easily query "all transcripts from podcast X"
   - **Acceptable**: Not a Phase 2 requirement

4. **Race Conditions**
   - Multiple processes could write same cache simultaneously
   - **Low risk**: CLI tool, typically single-user
   - **Future**: Add file locking if needed

### Risks & Mitigation

**Risk 1**: Corrupted cache files
**Mitigation**: Validate on load, delete if corrupted

**Risk 2**: Disk space exhaustion
**Mitigation**: TTL cleanup, manual clear, future LRU eviction

**Risk 3**: Cache poisoning (user manually edits incorrectly)
**Mitigation**: Pydantic validation on load

---

## Implementation Details

### Cache Class Interface

```python
class TranscriptCache:
    def __init__(self, cache_dir: Optional[Path] = None, ttl_days: int = 30):
        """Initialize cache with configurable location and TTL."""

    def get(self, episode_url: str) -> Optional[Transcript]:
        """Retrieve cached transcript. Returns None if miss/expired."""

    def set(self, episode_url: str, transcript: Transcript) -> None:
        """Cache transcript for episode."""

    def invalidate(self, episode_url: str) -> bool:
        """Remove cached transcript. Returns True if existed."""

    def clear_all(self) -> int:
        """Remove all cached transcripts. Returns count deleted."""

    def clear_expired(self) -> int:
        """Remove expired transcripts. Returns count deleted."""
```

### CLI Commands

```bash
# List cached transcripts
inkwell cache list

# Show cache statistics
inkwell cache stats

# Clear all cache
inkwell cache clear

# Clear expired only
inkwell cache cleanup

# Force refresh (skip cache)
inkwell transcribe URL --force
```

### Automatic Cleanup

```python
# On application startup
def startup_cleanup():
    """Clean expired cache if > 24h since last cleanup."""
    marker = get_cache_dir() / ".last_cleanup"

    if marker.exists():
        last_cleanup = datetime.fromtimestamp(marker.stat().st_mtime)
        if datetime.now() - last_cleanup < timedelta(hours=24):
            return  # Too soon

    # Perform cleanup
    cache = TranscriptCache()
    deleted = cache.clear_expired()

    if deleted > 0:
        logger.info(f"Cleaned up {deleted} expired cached transcripts")

    # Update marker
    marker.touch()
```

---

## Validation

### Cost Savings Analysis

**Scenario**: User processes 10 episodes, then re-processes with different options

- **Without cache**:
  - First: 10 × $0.60 = $6.00
  - Second: 10 × $0.60 = $6.00
  - **Total**: $12.00

- **With cache**:
  - First: 10 × $0.60 = $6.00
  - Second: 10 × $0.00 = $0.00 (cache hit)
  - **Total**: $6.00

**Savings**: 50% cost reduction for this workflow

### Performance Impact

**Cache hit times** (measured conceptually):
- File exists check: < 1ms
- Read file: ~1-5ms (500KB JSON)
- Parse JSON: ~1-3ms
- Pydantic validation: ~1-2ms
- **Total**: ~5-10ms

**vs. Gemini transcription**: 120,000-300,000ms (2-5 minutes)

**Speedup**: 12,000-60,000x faster

---

## Future Enhancements

### Phase 3+

1. **Compressed Cache** (v0.3+)
   - Gzip JSON files
   - ~80% size reduction
   - Negligible performance impact

2. **Cache Warming** (v0.4+)
   - Pre-cache episodes during off-hours
   - Background task for latest episodes

3. **Cache Analytics** (v0.5+)
   - Hit rate tracking
   - Cost savings dashboard
   - Per-podcast statistics

4. **LRU Eviction** (v0.6+)
   - Keep N most recent
   - Prevent unbounded growth

---

## References

- [Research: Transcript Caching Strategy](../research/transcript-caching-strategy.md)
- [ADR-009: Transcription Strategy](./009-transcription-strategy.md)
- [XDG Base Directory Specification](https://specifications.freedesktop.org/basedir-spec/basedir-spec-latest.html)

---

## Approval

**Status**: ✅ Accepted

**Date**: 2025-11-07

**Reviewers**: Claude (Phase 2 architect)

**Next steps**:
1. Implement TranscriptCache class (Unit 6)
2. Integrate with TranscriptionManager (Unit 7)
3. Add cache CLI commands (Unit 8)
4. Test caching behavior thoroughly (Unit 9)
