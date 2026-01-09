# ADR-017: Extraction Caching Strategy

**Date**: 2025-11-07
**Status**: Accepted
**Context**: Phase 3 Unit 5 - Extraction Engine

---

## Context

LLM API calls are:
- **Expensive**: $0.003-$0.135 per extraction
- **Slow**: 3-8 seconds per extraction
- **Rate-limited**: Providers limit requests per minute

For the same transcript with the same template, the result should be identical (deterministic). Re-extracting wastes time and money.

We need a caching strategy that:
1. Avoids redundant API calls
2. Invalidates when templates change
3. Expires stale entries
4. Is simple and reliable

## Decision

**We will implement file-based caching with template version in the cache key.**

Cache entries:
- Stored in `~/.cache/inkwell/extractions/` (XDG compliant)
- One JSON file per extraction
- Cache key = SHA-256(template_name + template_version + transcript)
- TTL = 30 days (configurable)
- Automatic cleanup of expired entries

## Rationale

### Why File-Based Cache?

**Alternatives considered:**
1. In-memory cache (dict)
2. SQLite database
3. Redis/memcached
4. File-based cache

**Decision: File-based cache**

**Pros:**
- ✅ Persists across CLI invocations
- ✅ No external dependencies (no Redis setup)
- ✅ Easy to inspect/debug (JSON files)
- ✅ Easy to clear (`rm -rf ~/.cache/inkwell`)
- ✅ XDG compliant
- ✅ Works offline

**Cons:**
- ❌ Slower than in-memory (negligible vs API latency)
- ❌ No atomic transactions (not critical for our use case)
- ❌ File system overhead

**Verdict:** Benefits outweigh drawbacks. File-based is simplest and most reliable.

### Why Include Template Version in Key?

**Problem:** If a template changes, cached results become stale.

**Solution:** Include `template.version` in cache key.

**Example:**
```
Cache key = SHA-256("summary:1.0:transcript_text")
```

When template is updated to v1.1:
```
Cache key = SHA-256("summary:1.1:transcript_text")
```

Different key → cache miss → fresh extraction with new template.

**Benefits:**
- Automatic invalidation when template changes
- No manual cache clearing needed
- Version bumps invalidate affected entries only

### Why 30-Day TTL?

**Reasoning:**
- Podcast transcripts don't change
- Template versions change infrequently
- 30 days balances freshness vs cache hits
- User can clear cache manually if needed

**Configurable:** Can be changed per use case.

### Why SHA-256 for Cache Keys?

**Alternatives:**
- MD5 (faster, less secure)
- SHA-1 (deprecated)
- SHA-256 (standard, secure)

**Decision: SHA-256**

**Reasoning:**
- Standard, well-supported
- Collision-resistant (important for correctness)
- Fast enough (< 1ms)
- Security not critical here, but good practice

## Implementation

### Cache Structure

```
~/.cache/inkwell/extractions/
├── abc123...def.json  # summary v1.0, transcript A
├── 456789...xyz.json  # quotes v1.0, transcript A
└── fedcba...321.json  # summary v1.0, transcript B
```

### Cache File Format

```json
{
  "timestamp": 1699305600.0,
  "template_name": "summary",
  "template_version": "1.0",
  "result": "Extracted summary text..."
}
```

### Cache Key Generation

```python
def _make_key(template_name: str, template_version: str, transcript: str) -> str:
    content = f"{template_name}:{template_version}:{transcript}"
    return hashlib.sha256(content.encode()).hexdigest()
```

### Cache Lookup Flow

```
1. Compute cache key
2. Check if file exists
3. If exists:
   a. Read JSON
   b. Check TTL
   c. If expired: delete file, return None
   d. If valid: return result
4. If not exists: return None
```

### Cache Write Flow

```
1. Compute cache key
2. Create cache entry dict
3. Write JSON to file
4. Handle write errors gracefully (continue without caching)
```

## Usage

### Basic Usage

```python
from inkwell.extraction import ExtractionCache, ExtractionEngine

# Create engine with default cache
engine = ExtractionEngine()

# Extraction automatically uses cache
result = await engine.extract(template, transcript, metadata)
```

### Custom Cache Directory

```python
from pathlib import Path

cache = ExtractionCache(cache_dir=Path("/tmp/my-cache"))
engine = ExtractionEngine(cache=cache)
```

### Bypass Cache

```python
# Force fresh extraction
result = await engine.extract(
    template, transcript, metadata,
    use_cache=False
)
```

### Clear Cache

```python
cache = ExtractionCache()

# Clear all entries
cache.clear()

# Clear expired entries only
cache.clear_expired()

# Get statistics
stats = cache.get_stats()
print(f"Cached: {stats['total_entries']} entries, {stats['total_size_mb']} MB")
```

## Performance

### Cache Hit Performance

| Operation | Latency |
|-----------|---------|
| Cache miss → API call | 3-8 seconds |
| Cache hit → File read | 1-5 ms |

**Speedup: 600-8000x faster with cache hit**

### Disk Usage

Typical cache sizes:
- 10 episodes, 3 templates each: ~30 entries
- Average entry size: 2-10 KB
- Total: 60-300 KB

**Negligible disk usage** for most users.

### Cache Hit Rate

Expected hit rates:
- Development (same episodes): ~80%
- Production (unique episodes): ~10-20% (repeat extractions)

Even 20% hit rate saves significant time and money.

## Cache Invalidation Strategy

**Cache invalidation happens when:**

1. **Template version changes** → Automatic (different cache key)
2. **TTL expires (30 days)** → Automatic (deleted on access)
3. **User clears cache** → Manual (`cache.clear()`)

**Cache is NOT invalidated when:**
- Transcript unchanged (good - same input → same output)
- Template name unchanged (version must change)
- Metadata changes (not part of cache key - acceptable trade-off)

### Why Metadata Not in Cache Key?

**Problem:** Including metadata (podcast name, episode title) in cache key means:
- Different metadata → different key
- But result might be identical

**Decision:** Exclude metadata from cache key

**Rationale:**
- Most templates don't use metadata
- For those that do, metadata rarely affects output significantly
- Simplifies cache key
- Higher cache hit rate

**Trade-off:** If metadata significantly affects output, cache may return stale results. **Mitigation:** Include metadata in template version bump if critical.

## Error Handling

### Corrupted Cache Files

```python
try:
    with cache_file.open("r") as f:
        data = json.load(f)
except (json.JSONDecodeError, KeyError, OSError):
    # Corrupted file, delete it
    cache_file.unlink(missing_ok=True)
    return None
```

**Strategy:** Delete corrupted files, continue gracefully.

### Write Failures

```python
try:
    with cache_file.open("w") as f:
        json.dump(data, f)
except OSError:
    # Failed to write cache, just continue
    pass
```

**Strategy:** Cache is optional. If write fails, continue without caching.

### Concurrent Access

**Scenario:** Two processes access cache simultaneously.

**Handling:**
- Reads are safe (no modification)
- Writes may race (last write wins)
- No locking needed (worst case: redundant extraction)

**Verdict:** Safe enough for CLI tool (not a web service).

## Testing Strategy

**Unit tests:**
- Cache hit/miss
- TTL expiration
- Version invalidation
- Corrupted file handling
- Stats calculation
- Concurrent access

**Integration tests:**
- Real extraction with caching
- Multiple templates
- Cache persistence

## Future Enhancements

### 1. Compression

For large transcripts, compress cache files:

```python
import gzip

with gzip.open(cache_file, "wt") as f:
    json.dump(data, f)
```

**Trade-off:** CPU time vs disk space (not worth it for typical sizes).

### 2. Cache Warming

Pre-populate cache for common extractions:

```bash
inkwell cache warm --episodes episodes.txt --templates summary,quotes
```

### 3. Shared Cache

Allow multiple users to share cache (e.g., team working on same podcasts):

```python
cache = ExtractionCache(cache_dir=Path("/shared/cache"))
```

### 4. Cache Analytics

Track cache hit rate:

```python
class CacheAnalytics:
    def __init__(self):
        self.hits = 0
        self.misses = 0

    def record_hit(self):
        self.hits += 1

    def record_miss(self):
        self.misses += 1

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0
```

### 5. Remote Cache

Cache in cloud storage (S3, GCS) for distributed teams:

```python
class S3Cache(ExtractionCache):
    def __init__(self, bucket: str):
        self.s3 = boto3.client("s3")
        self.bucket = bucket

    def get(self, ...):
        # Download from S3
        ...
```

## Consequences

### Positive

✅ Dramatic speedup for repeat extractions (600-8000x)
✅ Cost savings (cached results free)
✅ Automatic invalidation on template changes
✅ Simple, reliable implementation
✅ Easy to inspect and debug
✅ XDG compliant

### Negative

❌ Disk space usage (negligible)
❌ Cache can become stale if metadata affects output
❌ No garbage collection (relies on TTL)

### Neutral

- File-based (not in-memory or database)
- 30-day TTL (configurable)
- Metadata not in cache key

## Related

- [ADR-015: Extraction Caching](./015-extraction-caching.md) - Initial decision (Phase 3 Unit 1)
- [Unit 5 Devlog](../devlog/2025-11-07-phase-3-unit-5-extraction-engine.md) - Implementation details

---

## Revision History

- 2025-11-07: Initial ADR (Phase 3 Unit 5)
