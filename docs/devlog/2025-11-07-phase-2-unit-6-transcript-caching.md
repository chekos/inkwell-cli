# Devlog: Phase 2 Unit 6 - Transcript Caching

**Date:** 2025-11-07
**Unit:** Phase 2, Unit 6
**Status:** ✅ Complete
**Duration:** ~1.5 hours

---

## Objectives

Implement file-based transcript caching per ADR-010 to avoid redundant API calls.

### Goals
- [x] SHA256-based cache keys from episode URLs
- [x] 30-day TTL with automatic expiration
- [x] XDG-compliant cache directory
- [x] Atomic writes (temp file + rename)
- [x] Cache management operations
- [x] Cost metadata preservation

---

## Implementation Summary

**File:** `src/inkwell/transcription/cache.py` (240 lines)

### TranscriptCache Class

```python
class TranscriptCache:
    def __init__(self, cache_dir: Path | None = None, ttl_days: int = 30):
        # Uses platformdirs for XDG compliance

    def get(self, episode_url: str) -> Transcript | None:
        # Returns None if missing, expired, or corrupted

    def set(self, episode_url: str, transcript: Transcript) -> None:
        # Atomic write with temp file

    def delete(self, episode_url: str) -> bool:
        # Remove single entry

    def clear(self) -> int:
        # Remove all entries

    def clear_expired(self) -> int:
        # Remove expired only

    def stats(self) -> dict[str, Any]:
        # Get cache statistics
```

---

## Key Features

### 1. SHA256 Cache Keys
```python
def _get_cache_key(self, episode_url: str) -> str:
    return hashlib.sha256(episode_url.encode("utf-8")).hexdigest()
```
- Deterministic (same URL → same key)
- No collisions
- 64-character hex strings

### 2. TTL-Based Expiration
```python
def _is_expired(self, cached_at: datetime) -> bool:
    now = datetime.now(timezone.utc)
    age = now - cached_at
    return age > timedelta(days=self.ttl_days)
```
- Default: 30 days
- Automatic expiration on retrieval
- Timezone-aware (UTC)

### 3. Atomic Writes
```python
temp_path = cache_path.with_suffix(".tmp")
with temp_path.open("w") as f:
    json.dump(data, f, indent=2)
temp_path.rename(cache_path)  # Atomic
```
- Prevents partial writes
- System crash safe

### 4. Corruption Handling
```python
try:
    data = json.load(f)
except (json.JSONDecodeError, KeyError, ValueError):
    cache_path.unlink(missing_ok=True)
    return None
```
- Auto-deletes corrupted files
- Returns None (cache miss)

---

## Testing Strategy

**Test Coverage:** 25 tests

- Initialization (default, custom, XDG)
- Cache key generation
- Expiration logic (fresh, old, boundary)
- Set/get operations
- Missing entries
- Expired entries
- Corrupted files
- Delete operations
- Clear operations (all, expired only)
- Statistics
- Atomic writes
- Cost metadata preservation
- Different TTL values

**Execution:** All tests pass in ~3s

---

## Design Decisions

### 1. File-Based vs In-Memory

**Decision:** File-based cache

**Rationale:**
- Persists across runs
- Shared between processes
- No memory pressure
- ADR-010 decision

### 2. JSON vs Pickle

**Decision:** JSON storage

**Rationale:**
- Human-readable
- Version-safe
- Secure (no code execution)
- Pydantic provides serialization

### 3. SHA256 vs Other Hashing

**Decision:** SHA256 for cache keys

**Rationale:**
- Cryptographically secure (no collisions)
- Deterministic
- Fixed length
- Fast enough

### 4. Automatic Expiration on Read

**Decision:** Check expiration on get(), auto-delete

**Rationale:**
- Lazy expiration (no background jobs)
- Simple implementation
- Self-healing cache

---

## Integration Points

### With YouTube/Gemini Transcribers
```python
cache = TranscriptCache()

# Try cache first
cached = cache.get(episode_url)
if cached:
    return cached

# Cache miss - transcribe
transcript = await transcriber.transcribe(...)

# Save to cache
cache.set(episode_url, transcript)
```

### Future Orchestrator (Unit 7)
```python
# Check cache before trying transcription tiers
if cached := cache.get(url):
    return TranscriptionResult(
        success=True,
        transcript=cached,
        from_cache=True
    )
```

---

## Code Statistics

- **Implementation:** 240 lines
- **Tests:** 370 lines
- **Test-to-code ratio:** 1.5:1
- **Tests:** 25
- **Pass rate:** 100%
- **Execution time:** ~3s

---

## What Went Well ✅

1. **Atomic writes** - No corruption risk
2. **TTL design** - Simple and effective
3. **Corruption handling** - Self-healing
4. **Test coverage** - All edge cases covered
5. **XDG compliance** - Proper system integration

---

## Next Steps

### Immediate (Unit 7)
- Implement transcription orchestrator
- Integrate cache with transcribers
- Multi-tier fallback logic

---

## References

- [ADR-010: Transcript Caching](/docs/adr/010-transcript-caching.md)
- [platformdirs Documentation](https://github.com/platformdirs/platformdirs)
