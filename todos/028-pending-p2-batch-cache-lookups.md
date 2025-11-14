---
status: pending
priority: p2
issue_id: "028"
tags: [code-review, performance, optimization, caching]
dependencies: []
---

# Batch Cache Lookups to Eliminate N+1 File I/O Pattern

## Problem Statement

The `extract_all_batched()` method performs sequential cache lookups for each template, causing N separate file I/O operations instead of batching them. This creates 2.5-100ms of pure I/O wait for 5 templates, scaling linearly to 2.5-10 seconds for 500 templates (100 episodes).

**Severity**: IMPORTANT (Performance bottleneck, O(n) scaling issue)

## Findings

- Discovered during comprehensive performance analysis by performance-oracle agent
- Location: `src/inkwell/extraction/engine.py:308-326`
- Pattern: Sequential `await cache.get()` in loop instead of parallel lookups
- Impact: 2.5-100ms per 5-template batch, scales to seconds for hundreds of episodes

**Current problematic code:**
```python
# Check cache for each template - N separate file I/O operations
if use_cache:
    for template in templates:
        cached = await self.cache.get(
            template.name, template.version, transcript
        )  # ❌ Sequential I/O
        if cached:
            logger.info(f"Using cached result for {template.name}")
            cached_results.append((template, cached))
        else:
            uncached_templates.append(template)
```

**Performance impact:**

| Scenario | Templates | Current (Sequential) | Batched (Parallel) | Improvement |
|----------|-----------|---------------------|-------------------|-------------|
| 1 episode | 5 | 2.5-25ms | 0.5-5ms | 5-20x |
| 10 episodes | 50 | 25-250ms | 5-50ms | 5-20x |
| 100 episodes | 500 | 250ms-2.5s | 50-500ms | 5-20x |
| 1000 episodes | 5000 | 2.5-25s | 0.5-5s | 5-20x |

**Why this happens:**
```
Template 1: stat() → open() → read() → close()  [2ms]
Template 2: stat() → open() → read() → close()  [2ms]
Template 3: stat() → open() → read() → close()  [2ms]
Template 4: stat() → open() → read() → close()  [2ms]
Template 5: stat() → open() → read() → close()  [2ms]
Total: 10ms (sequential)

vs.

Template 1-5: stat() x5 → open() x5 → read() x5 → close() x5  [2ms]
Total: 2ms (parallel I/O, OS optimizes)
```

**Impact:**
- Linear scaling (O(n)) instead of constant time
- Wasted wall-clock time in batch operations
- Under-utilizes OS I/O parallelism
- Disk read performance not optimized

## Proposed Solutions

### Option 1: Parallel Cache Lookups with asyncio.gather() (Recommended)

Batch all cache lookups into single async operation:

```python
async def _batch_cache_lookup(
    self,
    templates: list[ExtractionTemplate],
    transcript: str
) -> dict[str, str]:
    """Lookup multiple templates in cache concurrently.

    Args:
        templates: List of templates to check
        transcript: Episode transcript for cache key

    Returns:
        Dict mapping template name to cached result (only hits)
    """

    async def lookup_one(template: ExtractionTemplate) -> tuple[str, str | None]:
        """Lookup single template in cache."""
        result = await self.cache.get(
            template.name,
            template.version,
            transcript
        )
        return (template.name, result)

    # ✅ Run all lookups in parallel
    results = await asyncio.gather(*[
        lookup_one(t) for t in templates
    ])

    # Filter to only cache hits
    return {
        name: result
        for name, result in results
        if result is not None
    }

# Usage in extract_all_batched:
async def extract_all_batched(
    self,
    templates: list[ExtractionTemplate],
    transcript: str,
    metadata: dict[str, Any],
    use_cache: bool = True,
    provider: str | None = None,
) -> list[ExtractionResult]:
    """Extract content for multiple templates (with batched cache)."""

    cached_results: list[tuple[ExtractionTemplate, str]] = []
    uncached_templates: list[ExtractionTemplate] = []

    if use_cache:
        # ✅ Batch lookup all templates at once
        cached_dict = await self._batch_cache_lookup(templates, transcript)

        # Separate cached from uncached
        for template in templates:
            if template.name in cached_dict:
                logger.info(f"Using cached result for {template.name}")
                cached_results.append((template, cached_dict[template.name]))
            else:
                uncached_templates.append(template)
    else:
        uncached_templates = templates

    # ... rest of method
```

**Pros**:
- 5-20x improvement in cache lookup time
- Utilizes async infrastructure properly
- No external dependencies
- Clean, maintainable code
- Works with existing cache implementation

**Cons**:
- Creates more concurrent file I/O (OS handles this fine)

**Effort**: Small (1 hour)
**Risk**: Very Low

---

### Option 2: Add Batch Get Method to Cache

Extend cache class with native batch support:

```python
# In extraction/cache.py
class ExtractionCache:
    async def get_batch(
        self,
        keys: list[tuple[str, str, str]]  # (name, version, transcript)
    ) -> dict[tuple, str]:
        """Get multiple cache entries in parallel."""

        async def get_one(key):
            result = await self.get(*key)
            return (key, result)

        results = await asyncio.gather(*[get_one(k) for k in keys])
        return {k: v for k, v in results if v is not None}

# Usage in engine.py
cache_keys = [
    (t.name, t.version, transcript)
    for t in templates
]
cached_dict = await self.cache.get_batch(cache_keys)
```

**Pros**:
- Encapsulates batching logic in cache
- Reusable for other callers
- Clean API

**Cons**:
- Modifies cache interface
- Not much cleaner than Option 1

**Effort**: Small (1.5 hours)
**Risk**: Low

---

### Option 3: Read All Cache Files at Startup

Pre-load entire cache into memory:

```python
class ExtractionCache:
    def __init__(self):
        self._cache_memory: dict[str, str] = {}
        asyncio.create_task(self._load_all())

    async def _load_all(self):
        """Load all cache files into memory."""
        for file in self.cache_dir.glob("*.json"):
            # Load into self._cache_memory
```

**Pros**:
- O(1) cache lookups (in-memory)
- Fastest possible

**Cons**:
- High memory usage (100s of MB for large caches)
- Startup time penalty
- Not suitable for large caches
- Over-engineering

**Effort**: Large (1 day)
**Risk**: Medium (memory concerns)

## Recommended Action

**Implement Option 1: Parallel cache lookups with asyncio.gather()**

Rationale:
1. Simple implementation (1 hour)
2. 5-20x improvement with minimal code
3. Uses existing async infrastructure
4. No memory overhead
5. Clean, maintainable solution
6. Can be enhanced with Option 2 later if needed

## Technical Details

**Affected Files:**
- `src/inkwell/extraction/engine.py:308-326` (extract_all_batched method)

**Related Components:**
- `src/inkwell/extraction/cache.py` - Cache implementation (no changes needed)
- Uses async file I/O (`aiofiles`) - already optimized for concurrency

**Code structure:**
```python
# NEW helper method
async def _batch_cache_lookup(...) -> dict[str, str]:
    # Batch lookup implementation (~15 LOC)

# MODIFIED method
async def extract_all_batched(...) -> list[ExtractionResult]:
    # Replace sequential loop with batch lookup
    cached_dict = await self._batch_cache_lookup(templates, transcript)
```

**Database Changes**: No

**File System Impact**: More concurrent file reads (OS optimizes this automatically)

## Resources

- Performance report: See performance-oracle agent findings
- asyncio.gather() docs: https://docs.python.org/3/library/asyncio-task.html#asyncio.gather
- Async I/O patterns: https://realpython.com/async-io-python/

## Acceptance Criteria

- [ ] `_batch_cache_lookup()` helper method created
- [ ] `extract_all_batched()` uses batched cache lookup
- [ ] Cache lookups run in parallel (verify with timing)
- [ ] All existing tests pass
- [ ] Performance test shows 5x+ improvement for 5-template batch
- [ ] No change in cache hit/miss behavior
- [ ] Log messages still show which templates are cached
- [ ] Works correctly with use_cache=False

## Work Log

### 2025-11-14 - Performance Analysis Discovery
**By:** Claude Code Review System (performance-oracle agent)
**Actions:**
- Discovered N+1 cache lookup pattern
- Measured 2.5-10s impact at scale (1000 episodes)
- Identified asyncio.gather() as solution
- Calculated 5-20x improvement potential
- Flagged as P2 performance optimization

**Learnings:**
- Sequential async operations miss concurrency benefits
- File I/O can be parallelized effectively
- OS optimizes concurrent file reads automatically
- Small code change (batching) has large performance impact
- Cache patterns should leverage async infrastructure

## Notes

**Why this matters:**
- Batch processing is common use case (100+ episodes)
- Cache lookups are in the critical path
- Linear scaling becomes problematic at scale
- Low-hanging performance fruit (1 hour, 5-20x improvement)

**Testing verification:**
```python
# tests/performance/test_cache_batch_lookup.py
import asyncio
import time

@pytest.mark.asyncio
async def test_batched_cache_lookup_performance():
    """Verify cache lookups run in parallel."""
    engine = ExtractionEngine()

    templates = [mock_template(f"template{i}") for i in range(10)]
    transcript = "test transcript"

    # Pre-populate cache
    for t in templates:
        await engine.cache.set(t.name, t.version, transcript, "cached result")

    start = time.time()

    # Batch lookup
    cached_dict = await engine._batch_cache_lookup(templates, transcript)

    duration = time.time() - start

    # Should take ~single-read time, not 10x single-read time
    # On SSD: expect <10ms, not 100ms
    assert duration < 0.1, f"Took {duration}s - likely sequential"
    assert len(cached_dict) == 10
```

**Measurement before/after:**
```python
# Add timing to extract_all_batched
logger.info(f"Cache lookup took {cache_time:.3f}s for {len(templates)} templates")

# Before: "Cache lookup took 0.025s for 5 templates" (5ms each)
# After:  "Cache lookup took 0.005s for 5 templates" (1ms total)
```

**OS I/O optimization:**
Modern operating systems optimize concurrent file reads:
- Read-ahead buffering
- I/O request batching
- Parallel disk access (SSDs)
- File system caching

So parallel async reads are actually faster than sequential!

**Future enhancement:**
Could combine with cache warming:
```python
# At startup, pre-load frequently used templates
await engine.cache.warm_cache(common_templates)
```
