---
status: completed
priority: p2
issue_id: "038"
tags: [data-integrity, cache, concurrency, performance]
dependencies: []
completed_date: 2025-11-14
---

# Detect and Prevent Cache Corruption During Reads

## Problem Statement

The extraction cache reads JSON files without verifying they are complete or valid. If another process is writing to the cache file during a read, partial JSON can be loaded, causing silent corruption and forcing redundant expensive API calls.

**Severity**: IMPORTANT - Cache corruption causes wasted API costs and processing time.

## Findings

- Discovered during data integrity audit by data-integrity-guardian agent
- Location: `src/inkwell/extraction/cache.py:65-82`
- Issue: No verification that cache file is complete before reading
- Risk: Partial JSON reads, silent corruption, redundant API calls

**Corruption Scenario:**
1. Process A starts extracting Episode X → cache lookup for key `abc123`
2. Process B finishes extracting Episode X → writes cache file `abc123.json` (takes 50ms for atomic write)
3. Process A reads `abc123.json` **during** Process B's write → gets partial JSON `{"template": "sum...`
4. Process A's `json.loads()` fails with `JSONDecodeError`
5. Process A treats as cache miss → makes $0.10 API call to regenerate
6. **Result:** Cache corruption causes redundant API costs, wasted time (2-10 seconds), inconsistent results

**Current Implementation:**
```python
async def get(self, template_name: str, template_version: str, transcript: str) -> str | None:
    cache_file = self.cache_dir / f"{cache_key}.json"

    if not cache_file.exists():
        return None

    try:
        async with aiofiles.open(cache_file, "r") as f:
            content = await f.read()
            data = json.loads(content)  # ⚠️ May be mid-write from another process
            return data.get("content")
    except (json.JSONDecodeError, KeyError):
        return None  # ⚠️ Silent cache miss, no corruption cleanup
```

**Why This Happens:**
- Atomic writes use temp-file-rename pattern, but no coordination with readers
- Reader can open file during writer's atomic rename
- No integrity check that JSON is complete
- Corrupted cache entries never cleaned up

## Proposed Solutions

### Option 1: Check for Temp File + Content Validation (Recommended)

Detect active writes and validate JSON completeness:

```python
async def get(self, template_name: str, template_version: str, transcript: str) -> str | None:
    cache_file = self.cache_dir / f"{cache_key}.json"

    if not cache_file.exists():
        return None

    try:
        # Check for temp file existence (indicates active write)
        temp_file = cache_file.with_suffix(".tmp")
        if temp_file.exists():
            # Another process is writing, treat as cache miss
            logger.debug(f"Cache file {cache_file} is being written, treating as miss")
            return None

        async with aiofiles.open(cache_file, "r") as f:
            content = await f.read()

            # Verify JSON is complete (simple sanity check)
            if not content.strip().endswith("}"):
                # Partial write detected, remove corrupt file
                logger.warning(f"Detected partial write in cache file {cache_file}, removing")
                await self._delete_file(cache_file)
                return None

            data = json.loads(content)
            return data.get("content")

    except json.JSONDecodeError as e:
        # Corrupted JSON, delete and treat as miss
        logger.warning(f"Corrupted cache file {cache_file}: {e}, removing")
        await self._delete_file(cache_file)
        return None
    except KeyError:
        # Invalid structure, delete and treat as miss
        logger.warning(f"Invalid cache structure in {cache_file}, removing")
        await self._delete_file(cache_file)
        return None
```

**Pros**:
- Detects active writes (temp file check)
- Validates JSON completeness (endswith check)
- Cleans up corrupted cache entries
- Minimal performance overhead

**Cons**:
- Small race window between temp file deletion and final rename
- Endswith check is heuristic, not cryptographic

**Effort**: Small (1 hour)
**Risk**: Low

### Option 2: Add Checksum to Cache Entries

Store SHA-256 checksum with each cache entry:

```python
async def set(self, ...) -> None:
    import hashlib

    cache_data = {
        "template_name": template_name,
        "template_version": template_version,
        "content": content,
        "created_at": now_utc().isoformat(),
    }

    json_content = json.dumps(cache_data)
    checksum = hashlib.sha256(json_content.encode()).hexdigest()

    cache_data["checksum"] = checksum
    # Write with checksum included
    ...

async def get(self, ...) -> str | None:
    # ... read file
    stored_checksum = data.pop("checksum", None)
    if stored_checksum:
        calculated = hashlib.sha256(json.dumps(data).encode()).hexdigest()
        if calculated != stored_checksum:
            # Corruption detected
            await self._delete_file(cache_file)
            return None
```

**Pros**:
- Cryptographically verifies integrity
- Detects all types of corruption

**Cons**:
- Higher overhead (hashing on every read/write)
- More complex implementation
- Breaks existing cache entries

**Effort**: Medium (2 hours)
**Risk**: Medium (cache invalidation)

### Option 3: File Locking for Cache Access

Add read/write locks similar to costs.py:

```python
async def get(self, ...) -> str | None:
    with self._lock_cache_file(cache_key):
        # Existing read logic
        ...

async def set(self, ...) -> None:
    with self._lock_cache_file(cache_key):
        # Existing write logic
        ...
```

**Pros**:
- Prevents concurrent access entirely
- Most robust solution

**Cons**:
- Performance impact (serialized cache access)
- Adds complexity
- May not be needed if Option 1 sufficient

**Effort**: Medium (2-3 hours)
**Risk**: Low

## Recommended Action

**Implement Option 1: Temp File Check + Content Validation**

This provides good protection with minimal overhead. If corruption is still observed in production, upgrade to Option 2 (checksums) or Option 3 (file locking).

**Priority**: P2 IMPORTANT - Protects against redundant API costs

## Technical Details

**Affected Files:**
- `src/inkwell/extraction/cache.py:65-82` (get method)
- `src/inkwell/extraction/cache.py` (add _delete_file helper)
- `tests/unit/extraction/test_cache.py` (add corruption tests)

**Related Components:**
- `src/inkwell/extraction/engine.py` (cache consumer)
- Cost tracking (cache misses increase API costs)

**Database Changes**: No

**API Cost Impact:**
- Each cache miss costs $0.05-$0.10 (Gemini/Claude API call)
- Batch processing 100 episodes with 5% cache corruption: 5 × $0.10 = $0.50 wasted
- Over time: Adds up to significant unnecessary costs

## Resources

- Original finding: DATA_INTEGRITY_REPORT.md (P2.1, lines 227-276)
- Related: Atomic write implementation in cache.py
- Python JSON corruption handling: https://docs.python.org/3/library/json.html

## Acceptance Criteria

- [ ] Temp file check added to `get()` method
- [ ] JSON completeness validation (endswith check)
- [ ] Corrupted cache files deleted automatically
- [ ] Logging for cache corruption events
- [ ] Test: Read during concurrent write → cache miss (no error)
- [ ] Test: Partial JSON file → deleted and treated as miss
- [ ] Test: Invalid JSON → deleted and treated as miss
- [ ] Test: Valid cache hit → returns content correctly
- [ ] All existing cache tests still pass
- [ ] Monitor cache hit rate in production (should improve)

## Work Log

### 2025-11-14 - Data Integrity Audit Discovery
**By:** Claude Code Review System (data-integrity-guardian agent)
**Actions:**
- Identified missing corruption detection in cache reads
- Analyzed concurrent access scenarios
- Classified as P2 IMPORTANT (cost optimization)
- Recommended temp file check + validation approach

**Learnings:**
- Atomic writes protect writers but not readers
- Cache corruption causes expensive API call redundancy
- Simple validation (endswith) catches most corruption
- Automatic cleanup prevents corrupt entries from persisting

### 2025-11-14 - Implementation Complete
**By:** Claude Code (code-review-resolution-specialist)
**Actions:**
- Added logging import and logger setup to cache.py
- Implemented temp file check to detect active concurrent writes
- Added JSON completeness validation (endswith check)
- Improved exception handling with separate cases for JSONDecodeError, KeyError, and OSError
- Added detailed logging at WARNING level for all corruption events
- Created 5 new comprehensive tests for corruption detection scenarios
- All 26 cache tests passing (including 21 existing + 5 new)
- All 79 extraction-related tests passing

**Implementation Details:**
- Modified `get()` method in `/Users/sergio/projects/inkwell-cli/src/inkwell/extraction/cache.py` (lines 68-108)
- Added temp file check at line 68-72 (detects concurrent writes)
- Added JSON completeness check at line 80-85 (validates data integrity)
- Enhanced error handling at line 96-108 (separate logging for each corruption type)
- Test coverage in `/Users/sergio/projects/inkwell-cli/tests/unit/test_extraction_cache.py` (lines 292-365)

**Test Coverage:**
- test_cache_get_during_concurrent_write: Verifies temp file detection
- test_cache_get_partial_json_deleted: Validates incomplete JSON handling
- test_cache_get_invalid_json_deleted: Confirms malformed JSON cleanup
- test_cache_get_missing_required_field: Tests missing field detection
- test_cache_get_valid_after_corruption_check: Ensures valid data still works

**Acceptance Criteria Met:**
- [x] Temp file check added to `get()` method
- [x] JSON completeness validation (endswith check)
- [x] Corrupted cache files deleted automatically
- [x] Logging for cache corruption events
- [x] Test: Read during concurrent write -> cache miss (no error)
- [x] Test: Partial JSON file -> deleted and treated as miss
- [x] Test: Invalid JSON -> deleted and treated as miss
- [x] Test: Valid cache hit -> returns content correctly
- [x] All existing cache tests still pass
- [ ] Monitor cache hit rate in production (should improve)

**Learnings:**
- Sync `Path.exists()` is sufficient for temp file check (no async needed)
- Using `cache_file.name` in logs is clearer than full path
- Separate exception handlers provide better observability
- Test setup using `_make_key()` helper ensures correct file naming

## Notes

**Why This Matters:**
- Extraction cache prevents $0.05-$0.10 API calls per episode
- Cache hit rate directly impacts processing costs
- Batch jobs often run in parallel (multiple processes)
- Silent corruption wastes both time and money

**Cost Analysis:**
```
Scenario: Batch processing 1000 episodes with 3% cache corruption

Without fix:
- 30 episodes experience cache corruption
- 30 × $0.10 = $3.00 in redundant API calls
- 30 × 5 seconds = 2.5 minutes wasted processing time

With fix:
- Cache corruption detected and prevented
- $3.00 saved per batch
- Processing time reduced
```

**Implementation Notes:**
- Use `await aiofiles.os.path.exists()` for async temp file check
- Log corruption events at WARNING level for monitoring
- Consider adding cache corruption metric to cost tracking
- Helper method for file deletion:

```python
async def _delete_file(self, file_path: Path) -> None:
    """Delete file, ignoring if already gone."""
    try:
        await aiofiles.os.remove(file_path)
    except FileNotFoundError:
        pass  # Already deleted, ignore
```

**Testing Strategy:**
```python
async def test_cache_get_during_concurrent_write(tmp_path):
    """Verify cache read during write returns None (cache miss)."""
    cache = ExtractionCache(tmp_path)

    # Create temp file to simulate active write
    cache_key = cache._generate_key("template", "v1", "transcript")
    cache_file = tmp_path / f"{cache_key}.json"
    temp_file = cache_file.with_suffix(".tmp")
    temp_file.write_text('{"partial": ')

    # Should detect active write and return None
    result = await cache.get("template", "v1", "transcript")
    assert result is None

async def test_cache_get_partial_json_deleted(tmp_path):
    """Verify partial JSON is detected and deleted."""
    cache = ExtractionCache(tmp_path)

    cache_key = cache._generate_key("template", "v1", "transcript")
    cache_file = tmp_path / f"{cache_key}.json"
    cache_file.write_text('{"template": "summary", "content": "partial')

    # Should detect partial JSON and delete file
    result = await cache.get("template", "v1", "transcript")
    assert result is None
    assert not cache_file.exists()
```

Source: Triage session on 2025-11-14
