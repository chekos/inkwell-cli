---
status: resolved
priority: p3
issue_id: "015"
tags: [code-review, performance, optimization, async]
dependencies: []
---

# Add Async File I/O Operations

## Problem Statement

All file operations (cache reads/writes) are synchronous despite being in async functions. This blocks the event loop and wastes time waiting for I/O. Using async file operations would improve cache performance by 15-25%.

**Severity**: LOW (Performance Optimization)

## Findings

- Discovered during performance analysis by performance-oracle agent
- All cache operations use synchronous I/O
- Blocks event loop during file operations
- Each cache operation: ~5-20ms penalty
- Compounds with multiple templates (4 templates = 40-80ms wasted)

**Affected Locations**:
- `src/inkwell/extraction/cache.py:64-78` (get method)
- `src/inkwell/extraction/cache.py:80-100` (set method)
- `src/inkwell/transcription/cache.py` (similar pattern)
- `src/inkwell/utils/costs.py` (JSON file operations)

**Current Pattern**:
```python
async def extract(...):
    # ... async operations ...

    if use_cache:
        cached = self.cache.get(...)  # ← BLOCKING I/O!
        if cached:
            return cached

    # ... more async operations ...

    self.cache.set(...)  # ← BLOCKING I/O!
```

**Performance Impact**:
- Cache hit: ~10ms blocked
- Cache miss + write: ~15ms blocked
- 4 templates: 40-60ms blocked per episode
- No parallelization benefit during I/O

## Proposed Solutions

### Option 1: Use aiofiles Library (Recommended)
**Pros**:
- Simple to implement
- True async I/O
- No blocking
- Works with existing code structure

**Cons**:
- New dependency

**Effort**: Small (1-2 hours)
**Risk**: Low

**Implementation**:

```python
# Add to pyproject.toml
dependencies = [
    # ... existing ...
    "aiofiles>=23.2.0",
]


# src/inkwell/extraction/cache.py

import aiofiles
import json
from pathlib import Path

class ExtractionCache:
    """Async cache for extraction results."""

    def __init__(self, cache_dir: Path, ttl_seconds: int = 2592000):
        self.cache_dir = cache_dir
        self.ttl_seconds = ttl_seconds
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    async def get(
        self,
        template_name: str,
        template_version: str,
        transcript: str
    ) -> str | None:
        """Get cached extraction result (async).

        Args:
            template_name: Name of extraction template
            template_version: Version of template
            transcript: Episode transcript

        Returns:
            Cached result if valid, None otherwise

        Example:
            >>> cache = ExtractionCache(Path("cache"))
            >>> result = await cache.get("summary", "1.0", "transcript...")
        """
        cache_file = self._get_cache_path(template_name, template_version, transcript)

        if not cache_file.exists():
            return None

        try:
            # Async file read
            async with aiofiles.open(cache_file, 'r') as f:
                content = await f.read()
                data = json.loads(content)

            # Check TTL
            timestamp = data.get("timestamp", 0)
            if time.time() - timestamp > self.ttl_seconds:
                # Expired - delete asynchronously
                await self._delete_file(cache_file)
                return None

            return data.get("result")

        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Invalid cache file {cache_file}: {e}")
            await self._delete_file(cache_file)
            return None

    async def set(
        self,
        template_name: str,
        template_version: str,
        transcript: str,
        result: str
    ) -> None:
        """Store extraction result in cache (async).

        Args:
            template_name: Name of extraction template
            template_version: Version of template
            transcript: Episode transcript
            result: Extraction result to cache

        Example:
            >>> await cache.set("summary", "1.0", "transcript...", "Summary text")
        """
        cache_file = self._get_cache_path(template_name, template_version, transcript)

        data = {
            "timestamp": time.time(),
            "template_name": template_name,
            "template_version": template_version,
            "result": result
        }

        # Async file write with atomic replace
        temp_file = cache_file.with_suffix('.tmp')

        try:
            # Write to temp file
            async with aiofiles.open(temp_file, 'w') as f:
                await f.write(json.dumps(data))

            # Atomic rename (still sync, but fast)
            temp_file.replace(cache_file)

        except Exception as e:
            logger.error(f"Failed to write cache file: {e}")
            if temp_file.exists():
                temp_file.unlink()
            raise

    async def _delete_file(self, path: Path) -> None:
        """Delete file asynchronously."""
        try:
            # aiofiles doesn't have unlink, use thread pool
            await asyncio.to_thread(path.unlink, missing_ok=True)
        except Exception as e:
            logger.warning(f"Failed to delete cache file {path}: {e}")

    async def clear(self) -> None:
        """Clear all cache files (async)."""
        cache_files = list(self.cache_dir.glob("*.json"))

        # Delete files in parallel
        await asyncio.gather(*[
            self._delete_file(f) for f in cache_files
        ], return_exceptions=True)

        logger.info(f"Cleared {len(cache_files)} cache files")

    async def get_stats(self) -> dict:
        """Get cache statistics (async)."""
        cache_files = list(self.cache_dir.glob("*.json"))

        # Read file sizes in parallel
        async def get_size(path: Path) -> int:
            return await asyncio.to_thread(path.stat().st_size)

        sizes = await asyncio.gather(*[
            get_size(f) for f in cache_files
        ])

        total_size = sum(sizes)

        return {
            "file_count": len(cache_files),
            "total_size_bytes": total_size,
            "total_size_mb": total_size / (1024 * 1024)
        }


# Update extraction engine to use async cache:
# src/inkwell/extraction/engine.py

class ExtractionEngine:
    async def extract(
        self,
        template: ExtractionTemplate,
        transcript: str,
        metadata: dict[str, Any],
        use_cache: bool = True
    ) -> ExtractionResult:
        """Extract information using template (now fully async)."""

        # Check cache (now async)
        if use_cache:
            cached = await self.cache.get(
                template.name,
                template.version,
                transcript
            )
            if cached:
                logger.info(f"Cache hit for {template.name}")
                return ExtractionResult(success=True, content=cached)

        # ... extraction logic ...

        # Save to cache (now async)
        if use_cache and result.success:
            await self.cache.set(
                template.name,
                template.version,
                transcript,
                result.content
            )

        return result
```

### Option 2: Bulk Cache Operations
**Pros**:
- Even faster (parallel I/O)
- Reduces cache calls

**Cons**:
- More complex API
- Requires refactoring

**Effort**: Medium (3-4 hours)
**Risk**: Medium

**Implementation**:
```python
class ExtractionCache:
    async def get_many(
        self,
        requests: list[tuple[str, str, str]]
    ) -> dict[str, str | None]:
        """Get multiple cache entries in parallel."""
        tasks = [
            self.get(template_name, version, transcript)
            for template_name, version, transcript in requests
        ]
        results = await asyncio.gather(*tasks)
        return dict(zip([r[0] for r in requests], results))

    async def set_many(
        self,
        items: list[tuple[str, str, str, str]]
    ) -> None:
        """Set multiple cache entries in parallel."""
        tasks = [
            self.set(template_name, version, transcript, result)
            for template_name, version, transcript, result in items
        ]
        await asyncio.gather(*tasks)
```

## Recommended Action

Implement Option 1 for v1.1. Adds async I/O with minimal changes.

## Technical Details

**Affected Files**:
- `src/inkwell/extraction/cache.py` (get and set methods)
- `src/inkwell/transcription/cache.py` (similar updates)
- `src/inkwell/utils/costs.py` (optional: async JSON operations)

**New Dependencies**:
- `aiofiles>=23.2.0`

**Related Components**:
- All cache operations
- Extraction engine
- Transcription manager

**Database Changes**: No

## Resources

- aiofiles Documentation: https://pypi.org/project/aiofiles/
- Async I/O in Python: https://realpython.com/async-io-python/
- asyncio Best Practices: https://docs.python.org/3/library/asyncio-task.html

## Acceptance Criteria

- [ ] aiofiles dependency added
- [ ] ExtractionCache.get() converted to async
- [ ] ExtractionCache.set() converted to async
- [ ] ExtractionCache.clear() converted to async
- [ ] TranscriptionCache updated similarly
- [ ] All callers updated to await cache operations
- [ ] Unit tests for async cache operations
- [ ] Performance benchmarks showing improvement
- [ ] No event loop blocking during I/O
- [ ] Documentation updated
- [ ] All existing tests pass

## Work Log

### 2025-11-13 - Code Review Discovery
**By:** Claude Code Review System
**Actions:**
- Discovered during performance analysis
- Analyzed by performance-oracle agent
- Measured I/O blocking overhead
- Categorized as LOW priority (optimization)

**Learnings**:
- Sync I/O in async context blocks event loop
- aiofiles provides true async I/O
- 15-25% improvement possible
- Parallel I/O possible with async

## Notes

**Why Async I/O Matters**:

Synchronous I/O in async context:
```python
async def process():
    data = cache.get(...)  # ← Blocks event loop for 10ms
    # Nothing else can run during this time
    result = await api_call()  # ← Now async operations can run
```

Async I/O:
```python
async def process():
    data = await cache.get(...)  # ← Event loop free during I/O
    # Other tasks can run while waiting for disk
    result = await api_call()
```

**Performance Comparison**:

Synchronous (current):
```
Task A: Read cache (10ms blocked)
Task B: ← waiting
Task C: ← waiting

Total time: 30ms (sequential)
```

Asynchronous (proposed):
```
Task A: Read cache (10ms, non-blocking)
Task B: Read cache (10ms, concurrent)
Task C: Read cache (10ms, concurrent)

Total time: 10ms (parallel)
```

**Migration Example**:

```python
# BEFORE (sync in async context)
class ExtractionCache:
    def get(self, key: str) -> str | None:
        with open(cache_file) as f:  # Blocks event loop
            return json.load(f)

# AFTER (async)
class ExtractionCache:
    async def get(self, key: str) -> str | None:
        async with aiofiles.open(cache_file) as f:  # Non-blocking
            content = await f.read()
            return json.loads(content)

# Usage changes from:
result = cache.get(key)

# To:
result = await cache.get(key)
```

**Testing**:
```python
@pytest.mark.asyncio
async def test_async_cache():
    """Test async cache operations."""
    cache = ExtractionCache(tmp_path)

    # Set value
    await cache.set("template", "1.0", "transcript", "result")

    # Get value
    result = await cache.get("template", "1.0", "transcript")
    assert result == "result"


@pytest.mark.asyncio
async def test_cache_parallelism():
    """Test that cache operations can run in parallel."""
    cache = ExtractionCache(tmp_path)

    # Prepare multiple cache entries
    for i in range(10):
        await cache.set(f"template{i}", "1.0", f"transcript{i}", f"result{i}")

    # Read all in parallel
    start = time.time()
    results = await asyncio.gather(*[
        cache.get(f"template{i}", "1.0", f"transcript{i}")
        for i in range(10)
    ])
    elapsed = time.time() - start

    # Should take ~10ms (parallel), not ~100ms (sequential)
    assert len(results) == 10
    assert elapsed < 0.05  # 50ms max (generous)
```

**Common Pitfalls**:

1. **Forgetting await**:
```python
# ❌ WRONG - returns coroutine, not result
result = cache.get(key)

# ✅ CORRECT
result = await cache.get(key)
```

2. **Mixing sync and async**:
```python
# ❌ WRONG - sync method in async class
class Cache:
    async def get(self): ...
    def set(self): ...  # Should also be async

# ✅ CORRECT - all async
class Cache:
    async def get(self): ...
    async def set(self): ...
```

3. **Not handling errors**:
```python
# ❌ WRONG - errors can hang event loop
async def get(self):
    async with aiofiles.open(file) as f:
        return await f.read()  # What if file doesn't exist?

# ✅ CORRECT - handle errors
async def get(self):
    try:
        async with aiofiles.open(file) as f:
            return await f.read()
    except FileNotFoundError:
        return None
```

**Source**: Code review performed on 2025-11-13
**Review command**: /review #9
