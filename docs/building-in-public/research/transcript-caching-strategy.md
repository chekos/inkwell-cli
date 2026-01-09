# Research: Transcript Caching Strategy

**Date**: 2025-11-07
**Author**: Claude (Phase 2 Research)
**Status**: Complete

## Overview

Research on caching strategies for podcast transcripts to minimize API costs and improve user experience.

---

## Why Caching Matters

### Cost Optimization
- **Gemini transcription**: ~$0.60 per hour
- **Repeat processing**: Common scenarios:
  - User re-runs processing with different options
  - Testing and development
  - Failed extraction requiring retry
- **Impact**: Without caching, costs multiply unnecessarily

### Performance Optimization
- **YouTube API**: 1-3 seconds
- **Gemini transcription**: 2-5 minutes
- **Cache hit**: < 100ms

### Use Case
User processes "Episode 123", then decides to re-process with different extraction templates.
- **Without cache**: $0.60 + 3 minutes
- **With cache**: FREE + instant

---

## Caching Approaches Evaluated

### Option 1: File-Based JSON Cache

**Description**: Store transcripts as JSON files in `~/.cache/inkwell/transcripts/`

#### Pros
- ✅ **Simple** - No database dependencies
- ✅ **Inspectable** - Users can view cached data
- ✅ **XDG compliant** - Standard cache location
- ✅ **Portable** - Easy to backup/restore
- ✅ **Debuggable** - Can manually edit for testing

#### Cons
- ❌ **No indexing** - Linear search for queries
- ❌ **No transactions** - Race conditions possible
- ❌ **Manual cleanup** - Need explicit TTL management

#### Implementation
```python
# Cache structure
~/.cache/inkwell/transcripts/
├── a3f5b2c1d8e9f4a0.json  # SHA256 hash of episode URL
├── b4c6d3e2f9a1b5c7.json
└── ...

# File format
{
  "segments": [...],
  "source": "youtube",
  "language": "en",
  "episode_url": "https://...",
  "created_at": "2025-11-07T10:30:00Z",
  "duration_seconds": 3600.0,
  "word_count": 15000,
  "cost_usd": 0.60
}
```

---

### Option 2: SQLite Database

**Description**: Use SQLite to store transcripts with indexing

#### Pros
- ✅ **Indexed queries** - Fast lookups
- ✅ **Transactions** - ACID guarantees
- ✅ **Rich queries** - SQL for analytics
- ✅ **Built-in** - No external dependencies

#### Cons
- ❌ **Complexity** - Schema, migrations
- ❌ **Less inspectable** - Need SQL client
- ❌ **Overkill** - For simple key-value storage

---

### Option 3: In-Memory Cache (No Persistence)

**Description**: Cache only during session, no disk storage

#### Pros
- ✅ **Fastest** - No I/O
- ✅ **Simple** - Just a Python dict

#### Cons
- ❌ **Session-only** - Lost on exit
- ❌ **No cost savings** - Re-transcribe every run
- ❌ **Not suitable** - For our use case

---

### Option 4: Redis/Memcached

**Description**: External cache server

#### Pros
- ✅ **Fast** - Optimized caching
- ✅ **TTL built-in** - Automatic expiration

#### Cons
- ❌ **External dependency** - Need server running
- ❌ **Overkill** - For single-user CLI tool
- ❌ **Complexity** - Setup, maintenance

---

## Recommendation: File-Based JSON Cache

**Rationale**:
1. **Simplicity**: No external dependencies, easy to understand
2. **Debuggability**: Users can inspect cached data
3. **XDG Compliance**: Standard location for cache data
4. **Good enough**: Performance is fine for expected cache size

**Trade-offs**:
- Not optimized for thousands of entries (but we won't have that)
- No built-in TTL (but we can implement manually)
- No query capabilities (but we only need key-value lookups)

---

## Cache Key Generation

### Requirements
- **Deterministic**: Same URL always → same key
- **Unique**: Different URLs → different keys
- **Short**: Reasonable filename length
- **Safe**: Valid filesystem characters

### Strategy: SHA256 Hash

```python
import hashlib

def generate_cache_key(episode_url: str) -> str:
    """Generate deterministic cache key from URL."""
    return hashlib.sha256(episode_url.encode()).hexdigest()
```

**Example**:
- URL: `https://youtube.com/watch?v=abc123`
- Key: `a3f5b2c1d8e9f4a0b1c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7`
- File: `a3f5b2c1d8e9f4a0b1c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7.json`

### Alternative: URL Normalization + Hash

For even better deduplication:

```python
from urllib.parse import urlparse, parse_qs, urlencode

def normalize_url(url: str) -> str:
    """Normalize URL to canonical form."""
    parsed = urlparse(url)

    # Sort query parameters
    query = parse_qs(parsed.query)
    sorted_query = urlencode(sorted(query.items()))

    # Rebuild normalized URL
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}?{sorted_query}"

def generate_cache_key(episode_url: str) -> str:
    normalized = normalize_url(episode_url)
    return hashlib.sha256(normalized.encode()).hexdigest()
```

**Decision**: Start with simple hash, add normalization if deduplication issues arise.

---

## Time-To-Live (TTL) Strategy

### Options

#### 1. No Expiration (Cache Forever)
**Pros**: Max cost savings
**Cons**: Stale data, disk space growth
**Verdict**: ❌ Not suitable

#### 2. Fixed TTL (e.g., 30 days)
**Pros**: Predictable, balances freshness and cost
**Cons**: Arbitrary number
**Verdict**: ✅ Recommended

#### 3. User-Configurable TTL
**Pros**: Flexibility
**Cons**: More complexity
**Verdict**: Consider for v0.3+

#### 4. Never Expire, Manual Invalidation
**Pros**: User control
**Cons**: Requires active management
**Verdict**: Partial (offer clear command)

### Recommendation: 30-Day TTL + Manual Invalidation

**Rationale**:
- **30 days**: Long enough for development iteration
- **Short enough**: Prevents stale data issues
- **Manual option**: `inkwell cache clear` for full control

```python
from datetime import datetime, timedelta

def is_cache_valid(created_at: datetime, ttl_days: int = 30) -> bool:
    age = datetime.utcnow() - created_at
    return age < timedelta(days=ttl_days)
```

---

## Cache Invalidation Strategies

### Automatic Invalidation

**Triggers**:
1. **Age**: Older than TTL (30 days)
2. **Corruption**: JSON parse fails
3. **Schema change**: Missing required fields

**Implementation**:
```python
def get_cached_transcript(episode_url: str) -> Optional[Transcript]:
    cache_path = get_cache_path(episode_url)

    if not cache_path.exists():
        return None

    try:
        data = json.loads(cache_path.read_text())
        transcript = Transcript(**data)  # Pydantic validation

        # Check TTL
        if not is_cache_valid(transcript.created_at):
            cache_path.unlink()  # Delete expired
            return None

        return transcript

    except (json.JSONDecodeError, ValidationError):
        # Corrupted cache, delete
        cache_path.unlink()
        return None
```

### Manual Invalidation

**CLI Commands**:

```bash
# Clear all cache
inkwell cache clear

# Clear specific episode
inkwell cache invalidate "https://episode-url"

# Clear expired only
inkwell cache cleanup
```

---

## Cache Management

### Storage Limits

**Expected size**:
- Average transcript: ~500KB (JSON)
- 100 episodes cached: ~50MB
- 1000 episodes: ~500MB

**Limit**: No hard limit for Phase 2
- Users unlikely to hit 1000 episodes
- If needed in future, implement LRU eviction

### Periodic Cleanup

**Strategy**: Check for expired cache on startup

```python
def cleanup_expired_cache(ttl_days: int = 30) -> int:
    """Remove expired cache entries. Returns count deleted."""
    cache_dir = get_cache_dir() / "transcripts"
    deleted = 0

    for cache_file in cache_dir.glob("*.json"):
        try:
            data = json.loads(cache_file.read_text())
            created_at = datetime.fromisoformat(data["created_at"])

            if not is_cache_valid(created_at, ttl_days):
                cache_file.unlink()
                deleted += 1
        except Exception:
            # Delete corrupted files
            cache_file.unlink()
            deleted += 1

    return deleted
```

**When to run**: On `inkwell` startup (if > 24h since last cleanup)

---

## Cache Statistics

### Useful Metrics

**Track**:
- Total cached episodes
- Total cache size (MB)
- Cache hit rate (session)
- Cost saved (estimated)
- Oldest cache entry

**CLI Command**:
```bash
$ inkwell cache stats

Cache Statistics
================
Location: ~/.cache/inkwell/transcripts/
Total episodes: 47
Cache size: 23.5 MB
Oldest entry: 2025-10-15 (23 days ago)
Estimated cost saved: $28.20
```

**Implementation**:
```python
def get_cache_stats() -> dict:
    cache_dir = get_cache_dir() / "transcripts"

    total_files = 0
    total_size = 0
    oldest_date = None
    total_cost_saved = 0.0

    for cache_file in cache_dir.glob("*.json"):
        total_files += 1
        total_size += cache_file.stat().st_size

        try:
            data = json.loads(cache_file.read_text())
            created_at = datetime.fromisoformat(data["created_at"])
            cost = data.get("cost_usd", 0.0)

            if oldest_date is None or created_at < oldest_date:
                oldest_date = created_at

            total_cost_saved += cost
        except Exception:
            pass

    return {
        "total_episodes": total_files,
        "total_size_mb": total_size / (1024 * 1024),
        "oldest_date": oldest_date,
        "cost_saved_usd": total_cost_saved,
    }
```

---

## Cache Warming (Future Feature)

**Concept**: Pre-cache common episodes during off-hours

**Use Case**:
- User subscribes to a podcast
- System caches latest 10 episodes overnight
- User wakes up to instant processing

**Implementation**: Post-v0.3, requires:
- Background task scheduling
- Batch processing
- Cost limits

---

## Security & Privacy

### Concerns

**Cache contains**:
- Full transcript text
- Episode URLs
- Timestamps

**Risks**:
- Sensitive/private podcast content exposed
- Cache readable by other users (wrong permissions)

### Mitigations

**1. Correct Permissions**
```python
cache_dir.mkdir(parents=True, exist_ok=True, mode=0o700)  # Owner only
```

**2. No PII in Cache Keys**
- Use hash, not descriptive names
- Cache files are opaque

**3. User Control**
- Clear documentation of what's cached
- Easy cache clearing
- TTL prevents indefinite storage

---

## Testing Strategy

### Unit Tests
- Cache hit/miss logic
- TTL expiration
- Corrupted cache handling
- Key generation consistency

### Integration Tests
- End-to-end caching flow
- Manual invalidation
- Stats calculation
- Cleanup on startup

### Manual Tests
- Verify disk usage
- Inspect cached files
- Test cache across sessions
- Verify TTL enforcement

---

## Recommendations

### For Phase 2 (v0.2)
1. ✅ File-based JSON cache
2. ✅ SHA256 URL hashing for keys
3. ✅ 30-day TTL
4. ✅ Manual invalidation commands
5. ✅ Startup cleanup of expired entries

### For Future Versions
- **v0.3+**: Cache statistics dashboard
- **v0.4+**: Configurable TTL per feed
- **v0.5+**: Cache warming/pre-fetching
- **v0.6+**: Compressed cache storage

---

## References

- [XDG Base Directory Specification](https://specifications.freedesktop.org/basedir-spec/basedir-spec-latest.html)
- [Python pathlib Documentation](https://docs.python.org/3/library/pathlib.html)
- [Phase 2 Implementation Plan](../devlog/2025-11-07-phase-2-detailed-plan.md)

---

## Conclusion

A simple file-based JSON cache with SHA256 URL hashing and 30-day TTL provides the right balance for Phase 2:

- **Simple**: No external dependencies
- **Effective**: Eliminates redundant transcription costs
- **Manageable**: Clear commands for user control
- **Appropriate**: Scales to expected usage

The strategy significantly reduces costs while maintaining simplicity and user control.

**Decision**: Proceed with file-based JSON cache as designed. ✅
