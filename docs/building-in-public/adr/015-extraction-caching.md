# ADR-015: Extraction Caching Strategy

**Date**: 2025-11-07
**Status**: Accepted
**Deciders**: Phase 3 Team
**Related**: [ADR-013](013-llm-provider-abstraction.md), [Phase 3 Plan](../devlog/2025-11-07-phase-3-detailed-plan.md)

## Context

Content extraction using LLMs is expensive in both cost and time:
- **Cost**: $0.15-0.40 per episode with Claude, $0.01-0.03 with Gemini
- **Latency**: 3-8 seconds per template extraction
- **Rate limits**: API calls limited per minute/day

Common scenarios where caching helps:
1. **Re-generating output**: User wants different markdown format
2. **Template updates**: Non-extraction template changes (output format)
3. **Experimentation**: Testing different template configurations
4. **Bulk operations**: Processing archive of previously-extracted episodes
5. **Development**: Testing and debugging

Without caching, users pay and wait for identical extractions repeatedly.

We need to decide:
- **What to cache?** (Transcript? Extraction? Both?)
- **Where to cache?** (Memory? Disk? Database?)
- **How long to cache?** (Forever? TTL? Manual invalidation?)
- **Cache key strategy?** (Episode URL? Content hash? Template version?)

## Decision

**We will implement per-template extraction caching with file-based storage, SHA-256 cache keys, and 30-day TTL.**

### Architecture

```python
class ExtractionCache:
    """Cache extracted content per template"""

    def __init__(self, cache_dir: Path, ttl_days: int = 30):
        self.cache_dir = cache_dir  # ~/.cache/inkwell/extractions/
        self.ttl_days = ttl_days

    def get(
        self,
        episode_url: str,
        template_name: str,
        template_version: str,
    ) -> Optional[ExtractedContent]:
        """Get cached extraction if fresh"""
        cache_key = self._generate_key(episode_url, template_name, template_version)
        cache_path = self.cache_dir / f"{cache_key}.json"

        if not cache_path.exists():
            return None

        # Check TTL
        cached_at = self._get_cached_time(cache_path)
        if datetime.utcnow() - cached_at > timedelta(days=self.ttl_days):
            cache_path.unlink()  # Expired
            return None

        # Load and return
        return ExtractedContent.parse_file(cache_path)

    def set(
        self,
        episode_url: str,
        template_name: str,
        template_version: str,
        content: ExtractedContent,
    ) -> None:
        """Cache extraction result"""
        cache_key = self._generate_key(episode_url, template_name, template_version)
        cache_path = self.cache_dir / f"{cache_key}.json"

        data = {
            "cached_at": datetime.utcnow().isoformat(),
            "episode_url": episode_url,
            "template_name": template_name,
            "template_version": template_version,
            "content": content.model_dump(),
        }

        cache_path.write_text(json.dumps(data, indent=2))

    def _generate_key(self, episode_url: str, template_name: str, version: str) -> str:
        """Generate cache key from inputs"""
        key_data = f"{episode_url}:{template_name}:{version}"
        return hashlib.sha256(key_data.encode()).hexdigest()
```

### Cache Key Structure

```
Cache Key = SHA256(episode_url + template_name + template_version)

Example:
  Episode: https://example.com/ep123.mp3
  Template: quotes
  Version: 1.0
  Key: sha256("https://example.com/ep123.mp3:quotes:1.0")
     = "a7f8e9..."
  File: ~/.cache/inkwell/extractions/a7f8e9....json
```

### Cache Invalidation

**Automatic:**
- TTL expiration (30 days default)
- Template version change
- Corrupted cache file

**Manual:**
```bash
# Clear all cache
inkwell cache clear --extractions

# Clear specific episode
inkwell cache clear --episode "https://example.com/ep123.mp3"

# Clear specific template
inkwell cache clear --template quotes

# Clear expired only
inkwell cache clear --expired
```

### Cache Configuration

```yaml
# ~/.config/inkwell/config.yaml
extraction_cache:
  enabled: true
  ttl_days: 30
  max_size_mb: 500  # Auto-cleanup when exceeded

# Per-template override
templates:
  quotes:
    cache_enabled: true  # Can disable per template
  experimental:
    cache_enabled: false  # Don't cache experiments
```

## Alternatives Considered

### Alternative 1: No Caching

**Pros:**
- Simplest implementation
- Always fresh data
- No cache management

**Cons:**
- Expensive repeated extractions
- Poor developer experience
- Slow iteration cycles
- Wastes API quota

**Rejected because**: Cost and time savings are critical

### Alternative 2: Transcript-Level Caching Only

**Cache transcripts, re-extract every time**

**Pros:**
- Simpler (already done in Phase 2)
- Smaller cache size
- Always reflects latest template

**Cons:**
- Doesn't save on extraction costs
- Still slow for multiple templates
- Wastes LLM API calls

**Rejected because**: Doesn't solve the extraction cost problem

### Alternative 3: Episode-Level Caching

**Cache all extractions for an episode together**

```json
{
  "episode_url": "...",
  "extractions": {
    "summary": {...},
    "quotes": {...},
    "concepts": {...}
  }
}
```

**Pros:**
- One file per episode
- Easy to manage
- Atomic updates

**Cons:**
- Must re-extract all templates if one changes
- Can't cache individual template updates
- Invalidation too coarse-grained
- Large cache files

**Rejected because**: Template-level granularity needed

### Alternative 4: Content-Hash Caching

**Cache key based on transcript content hash**

```
Key = SHA256(transcript_content + template_name + template_version)
```

**Pros:**
- Deduplicate identical transcripts
- More cache hits

**Cons:**
- Transcript not always available at cache check
- More complex cache key generation
- Harder to invalidate by episode
- Doesn't map to user's mental model

**Rejected because**: Episode URL is more intuitive

### Alternative 5: Database Caching (SQLite)

**Store cache in SQLite database**

**Pros:**
- Queryable (list by episode, template, date)
- Transactional
- Structured data
- Easy statistics

**Cons:**
- More complex than files
- Requires database migrations
- Locks and concurrency issues
- Overkill for simple cache

**Rejected because**: Files are sufficient and simpler

### Alternative 6: In-Memory Only

**Cache only during process lifetime**

**Pros:**
- Fastest access
- No disk I/O
- Auto-cleanup on exit

**Cons:**
- Doesn't persist across runs
- High memory usage
- No benefit for CLI usage pattern
- Lost on crash

**Rejected because**: CLI tools need persistent cache

### Alternative 7: No TTL (Infinite Cache)

**Cache forever unless manually cleared**

**Pros:**
- Maximum cache hits
- Simplest logic
- No time checks

**Cons:**
- Stale extractions
- Unbounded cache growth
- Old template versions persist
- No cleanup mechanism

**Rejected because**: Some invalidation strategy needed

## Rationale

### Why Per-Template File-Based Caching?

1. **Granular Invalidation**
   - Update one template without losing others
   - Clear specific template caches
   - Template versioning works naturally

2. **Simple Implementation**
   - Files are easy to inspect
   - No database needed
   - Atomic writes (rename)
   - XDG-compliant cache directory

3. **Transparent to Users**
   - Can view cache files manually
   - Easy to debug issues
   - Clear what's cached
   - Simple to delete

4. **Efficient Storage**
   - JSON is compact and readable
   - Only cache successful extractions
   - Compress if needed (future)

### Why 30-Day TTL?

**Reasoning:**
- Podcast content doesn't change
- Template improvements may happen
- Balance between cache hits and freshness
- User can override if needed

**Alternatives considered:**
- 7 days: Too aggressive, low cache hit rate
- 60 days: Stale templates persist too long
- 90 days: Unbounded growth risk
- Forever: Never gets fresh extractions

### Why Template Version in Cache Key?

**Critical for correctness:**
```yaml
# Version 1.0
name: quotes
user_prompt: "Extract 5 quotes"

# Version 1.1 (change prompt)
name: quotes
user_prompt: "Extract 10 quotes with context"
```

If we don't include version:
- ❌ V1.0 extraction cached
- ❌ Update to V1.1
- ❌ Still returns 5 quotes (wrong!)

With version:
- ✅ V1.0 extraction cached with key `...quotes:1.0`
- ✅ Update to V1.1
- ✅ New key `...quotes:1.1` → cache miss → fresh extraction

## Consequences

### Positive

✅ **Cost Savings**: Avoid redundant API calls
✅ **Speed**: Instant cache hits (vs 3-8s extraction)
✅ **Developer Experience**: Fast iteration
✅ **Offline Work**: Re-generate output without API
✅ **Graceful Degradation**: Falls back to extraction on miss

### Negative

❌ **Storage**: Cache uses disk space (~5-50KB per extraction)
❌ **Stale Data**: Old extractions may persist
❌ **Complexity**: More code to maintain
❌ **Debugging**: Cache issues can be confusing
❌ **Invalidation**: Need to handle properly

### Mitigations

1. **Storage Management**
   ```bash
   # Auto-cleanup when cache exceeds limit
   if cache_size > max_size_mb:
       clear_oldest_entries()

   # User can clear anytime
   inkwell cache clear --extractions
   ```

2. **Cache Statistics**
   ```bash
   inkwell cache stats

   # Output:
   # Extraction Cache:
   #   Size: 45.2 MB
   #   Entries: 237
   #   Hit rate: 73%
   #   Oldest: 28 days
   ```

3. **Clear Error Messages**
   ```python
   if cache_load_error:
       logger.warning(f"Cache corrupted for {episode}, re-extracting")
       cache.invalidate(episode, template)
   ```

4. **Force Refresh Flag**
   ```bash
   # Skip cache, force fresh extraction
   inkwell fetch "podcast" --latest --force-refresh
   ```

## Implementation Plan

### Phase 1: Basic Cache (Unit 5)

```python
class ExtractionCache:
    def get(self, episode_url, template_name, template_version) -> Optional[ExtractedContent]
    def set(self, episode_url, template_name, template_version, content) -> None
    def invalidate(self, episode_url, template_name) -> bool
    def clear_all(self) -> int
```

### Phase 2: Management Commands (Unit 5)

```bash
inkwell cache stats
inkwell cache clear [--extractions] [--episode URL] [--template NAME]
inkwell cache inspect <cache-key>
```

### Phase 3: Auto-Cleanup (Unit 5)

```python
# Periodic cleanup
def cleanup_expired(cache: ExtractionCache):
    """Remove entries older than TTL"""
    removed = cache.clear_expired()
    logger.info(f"Cleaned up {removed} expired cache entries")

# Size-based cleanup
def enforce_size_limit(cache: ExtractionCache, max_mb: int):
    """Remove oldest entries when size exceeded"""
    if cache.size_mb > max_mb:
        cache.clear_oldest(n=cache.count // 10)  # Remove 10%
```

### Phase 4: Monitoring (Unit 9)

```python
# Track cache performance
cache_stats = {
    "hits": 0,
    "misses": 0,
    "hit_rate": 0.0,
    "total_cost_saved": 0.0,
}

# Log at end of extraction
logger.info(f"Cache hit rate: {cache_stats['hit_rate']:.1%}")
logger.info(f"Cost saved: ${cache_stats['total_cost_saved']:.2f}")
```

## Validation

### Success Criteria

✅ Cache hit returns instantly (<100ms)
✅ Cache miss falls back to extraction
✅ Template version change invalidates cache
✅ TTL expiration works correctly
✅ Cache statistics accurate
✅ Clear commands work as expected
✅ Cache survives process restarts

### Testing Strategy

```python
def test_cache_hit():
    cache.set(episode, template, version, content)
    result = cache.get(episode, template, version)
    assert result == content

def test_cache_miss():
    result = cache.get(episode, template, version)
    assert result is None

def test_ttl_expiration(mock_time):
    cache.set(episode, template, version, content)
    mock_time.advance(days=31)  # Beyond TTL
    result = cache.get(episode, template, version)
    assert result is None  # Expired

def test_version_isolation():
    cache.set(episode, template, "1.0", content_v1)
    cache.set(episode, template, "1.1", content_v2)
    assert cache.get(episode, template, "1.0") == content_v1
    assert cache.get(episode, template, "1.1") == content_v2
```

## Related Decisions

- [ADR-013: LLM Provider Abstraction](013-llm-provider-abstraction.md) - Provider costs influence caching importance
- [ADR-014: Template Format](014-template-format.md) - Template versioning enables cache invalidation

## References

- [HTTP Caching (RFC 7234)](https://tools.ietf.org/html/rfc7234)
- [Cache Invalidation](https://martinfowler.com/bliki/TwoHardThings.html)
- [XDG Base Directory Spec](https://specifications.freedesktop.org/basedir-spec/basedir-spec-latest.html)

## Revision History

- 2025-11-07: Initial decision (Phase 3 Unit 1)
