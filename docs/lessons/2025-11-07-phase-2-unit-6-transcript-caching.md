# Lessons Learned: Phase 2 Unit 6 - Transcript Caching

**Date:** 2025-11-07
**Unit:** Phase 2, Unit 6
**Component:** File-based transcript caching system
**Duration:** ~1.5 hours
**Lines of Code:** ~240 implementation, ~370 tests (1.5:1 ratio)

---

## Summary

Implemented file-based transcript caching with SHA256 keys, 30-day TTL, and XDG compliance per ADR-010. Provides cache management operations (get, set, delete, clear, stats) with automatic expiration and corruption handling.

---

## Key Lessons Learned

### 1. Atomic Writes Prevent Partial Writes

**Pattern:**
```python
# Write to temp file first
temp_path = cache_path.with_suffix(".tmp")
with temp_path.open("w") as f:
    json.dump(data, f, indent=2)

# Then atomically rename
temp_path.rename(cache_path)
```

**Why This Matters:**
- System crash during write won't corrupt cache
- Rename is atomic on most filesystems
- Readers never see partial writes

**Lesson:** Always use temp-file-then-rename for critical data persistence.

---

### 2. Timezone-Aware Timestamps Are Essential

**Pattern:**
```python
# Always use UTC with timezone info
cached_at = datetime.now(timezone.utc)

# Later comparison also uses UTC
now = datetime.now(timezone.utc)
age = now - cached_at
```

**Why This Matters:**
- Avoids daylight saving time issues
- Portable across time zones
- Consistent comparison

**Anti-Pattern:**
```python
cached_at = datetime.now()  # BAD: No timezone, DST issues
```

---

### 3. Cache Keys Should Be Deterministic

**Pattern:**
```python
def _get_cache_key(self, episode_url: str) -> str:
    return hashlib.sha256(episode_url.encode("utf-8")).hexdigest()
```

**Benefits:**
- Same URL always produces same key
- No collisions (SHA256 is cryptographically secure)
- Fixed length keys (64 chars hex)
- URL-safe (no special characters)

**Lesson:** Use cryptographic hashes for cache keys when dealing with arbitrary strings.

---

### 4. Graceful Handling of Corrupted Data

**Pattern:**
```python
try:
    with cache_path.open("r") as f:
        data = json.load(f)
    # Process data
except (json.JSONDecodeError, KeyError, ValueError):
    # Corrupted - remove and return None
    cache_path.unlink(missing_ok=True)
    return None
```

**Why This Matters:**
- Corrupted cache doesn't crash app
- Self-healing (auto-deletes bad data)
- Returns None like cache miss

**Lesson:** Caches should degrade gracefully - never crash on corrupt data.

---

### 5. Statistics Need Defensive Programming

**Pattern:**
```python
for cache_file in self.cache_dir.glob("*.json"):
    try:
        total += 1
        # Process file
    except Exception:
        # Skip corrupted, continue counting
        continue
```

**Insight:** Count files even if processing fails. Corrupted files still exist and should be included in totals.

---

## Patterns to Repeat

### 1. XDG-Compliant Cache Directories
```python
from platformdirs import user_cache_dir

cache_dir = Path(user_cache_dir("inkwell", "inkwell")) / "transcripts"
```

### 2. TTL-Based Expiration
```python
def _is_expired(self, cached_at: datetime) -> bool:
    age = datetime.now(timezone.utc) - cached_at
    return age > timedelta(days=self.ttl_days)
```

### 3. Cache Miss Returns None
```python
def get(self, key: str) -> Value | None:
    if not exists or expired or corrupted:
        return None
    return value
```

---

## Anti-Patterns to Avoid

❌ **Don't use naive datetimes**
```python
cached_at = datetime.now()  # Missing timezone
```

✅ **Use timezone-aware UTC**
```python
cached_at = datetime.now(timezone.utc)
```

❌ **Don't crash on corrupt cache**
```python
data = json.load(f)  # Will crash on corrupt JSON
```

✅ **Handle gracefully**
```python
try:
    data = json.load(f)
except json.JSONDecodeError:
    cache_path.unlink()
    return None
```

---

## Technical Insights

### SHA256 Cache Keys

**Why SHA256:**
- Deterministic (same input → same output)
- No collisions in practice
- Fixed length (64 hex chars)
- Fast to compute

**Alternative Considered:**
- URL encoding: Too long, special characters
- MD5: Cryptographically broken (though fine for caching)
- Random IDs: Not deterministic

---

### JSON vs Pickle

**Why JSON:**
- Human-readable (debugging)
- Version-safe (Python version independent)
- Security (no code execution risk)
- Cross-language compatibility

**Trade-off:**
- Slightly slower than pickle
- Requires serialization logic (Pydantic handles this)

---

## Statistics

- **Implementation:** 240 lines of code
- **Tests:** 370 lines of code
- **Test-to-code ratio:** 1.5:1
- **Tests:** 25 total
- **Test execution time:** ~3 seconds
- **Pass rate:** 100%
- **Linter:** All checks passed

---

## References

- [ADR-010: Transcript Caching](/docs/adr/010-transcript-caching.md) - File-based JSON cache decision
- [Phase 2 Plan](/docs/devlog/2025-11-07-phase-2-detailed-plan.md) - Unit 6 objectives
