---
status: resolved
priority: p1
issue_id: "005"
tags: [code-review, data-integrity, concurrency, critical]
dependencies: []
---

# Add File Locking to Cost Tracking

## Problem Statement

Cost tracking uses non-atomic read-modify-write operations on `costs.json`. When multiple processes run `inkwell` concurrently, the last writer wins and cost data from concurrent operations is permanently lost.

**Severity**: CRITICAL (Financial Data Loss)

## Findings

- Discovered during data integrity review by data-integrity-guardian agent
- Location: `src/inkwell/utils/costs.py:201-205`
- Race condition in cost tracking persistence
- No locking mechanism prevents concurrent writes
- Financial data loss in multi-user or automated scenarios

**Race Condition Scenario**:
```
Time  Process A                    Process B
----  -------------------------    -------------------------
T0    Read costs.json (10 entries)
T1                                 Read costs.json (10 entries)
T2    Add entry 11
T3                                 Add entry 12
T4    Write costs.json (11 entries)
T5                                 Write costs.json (11 entries) ← Entry 11 LOST
```

**Impact**:
- Lost financial tracking data
- Incorrect billing reports
- GDPR compliance issues (data not accurate)
- User trust erosion

## Proposed Solutions

### Option 1: File-Based Locking with Atomic Write (Recommended)
**Pros**:
- Simple and reliable
- Works across processes
- No external dependencies
- Backward compatible with existing JSON format

**Cons**:
- Slightly more complex than current implementation

**Effort**: Small (2 hours)
**Risk**: Low

**Implementation**:

```python
# src/inkwell/utils/costs.py

import fcntl
import tempfile
from pathlib import Path

class CostTracker:
    def __init__(self, costs_file: Path | None = None):
        self.costs_file = costs_file or self._get_default_costs_file()
        self.costs_file.parent.mkdir(parents=True, exist_ok=True)
        self.usage_history: list[APIUsage] = []
        if self.costs_file.exists():
            self._load()

    def _load(self) -> None:
        """Load costs from disk."""
        try:
            with open(self.costs_file, 'r') as f:
                # Acquire shared lock for reading
                fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                try:
                    data = json.load(f)
                    self.usage_history = [APIUsage.model_validate(item) for item in data]
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        except (json.JSONDecodeError, ValueError) as e:
            # Corrupt file - try backup
            self._load_from_backup()

    def _load_from_backup(self) -> None:
        """Load from backup file if main file is corrupt."""
        backup_file = self.costs_file.with_suffix('.json.bak')
        if backup_file.exists():
            try:
                with open(backup_file, 'r') as f:
                    data = json.load(f)
                    self.usage_history = [APIUsage.model_validate(item) for item in data]
                logger.warning(f"Loaded costs from backup: {backup_file}")
                return
            except Exception:
                pass

        # Both failed - archive corrupt file
        if self.costs_file.exists():
            corrupt_backup = self.costs_file.with_suffix(f'.json.corrupt.{int(time.time())}')
            self.costs_file.rename(corrupt_backup)
            logger.error(f"Archived corrupt cost file to {corrupt_backup}")

        self.usage_history = []

    def _save(self) -> None:
        """Save costs to disk with file locking."""
        # Create backup first
        if self.costs_file.exists():
            backup_file = self.costs_file.with_suffix('.json.bak')
            try:
                shutil.copy2(self.costs_file, backup_file)
            except Exception as e:
                logger.warning(f"Failed to create backup: {e}")

        # Atomic write with exclusive lock
        temp_fd, temp_path = tempfile.mkstemp(
            dir=self.costs_file.parent,
            prefix=".tmp_costs_",
            suffix=".json"
        )

        try:
            # Open main file for locking
            with open(self.costs_file, 'a+') as lock_file:
                # Acquire exclusive lock
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)

                try:
                    # Re-read to get latest data (another process might have written)
                    lock_file.seek(0)
                    try:
                        existing_data = json.load(lock_file)
                        existing = [APIUsage.model_validate(item) for item in existing_data]
                    except (json.JSONDecodeError, ValueError):
                        existing = []

                    # Merge: add entries not already present (by timestamp + operation)
                    existing_keys = {(u.timestamp.isoformat(), u.operation, u.provider) for u in existing}
                    new_entries = [
                        u for u in self.usage_history
                        if (u.timestamp.isoformat(), u.operation, u.provider) not in existing_keys
                    ]
                    combined = existing + new_entries

                    # Write to temp file
                    with open(temp_fd, 'w') as f:
                        data = [usage.model_dump(mode="json") for usage in combined]
                        json.dump(data, f, indent=2, default=str)
                        f.flush()
                        os.fsync(f.fileno())

                    # Atomic replace
                    Path(temp_path).replace(self.costs_file)

                    # Update in-memory state
                    self.usage_history = combined

                finally:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

        except Exception:
            # Clean up temp file
            Path(temp_path).unlink(missing_ok=True)
            raise

    def track(self, usage: APIUsage) -> None:
        """Track an API usage operation."""
        self.usage_history.append(usage)
        self._save()  # Save immediately with locking
```

**Key Improvements**:
1. **Exclusive lock** during write prevents concurrent modifications
2. **Re-read after lock** ensures we have latest data
3. **Merge strategy** combines existing + new entries (deduplicates by timestamp)
4. **Backup creation** before overwrite for data recovery
5. **Atomic write** with fsync ensures durability

### Option 2: SQLite Database (Future Enhancement)
**Pros**:
- ACID guarantees built-in
- Better performance at scale
- Query capabilities

**Cons**:
- Requires migration
- More complex setup
- Breaking change

**Effort**: Medium (4-6 hours)
**Risk**: Medium

## Recommended Action

Implement Option 1 immediately to fix data loss issue. Consider Option 2 (SQLite) for v1.1 or v2.0.

## Technical Details

**Affected Files**:
- `src/inkwell/utils/costs.py:186-205` (_load and _save methods)

**Related Components**:
- All LLM operations that track costs
- CLI commands that read costs (`inkwell costs`)

**Database Changes**: No (still JSON, just with locking)

## Resources

- File Locking Best Practices: https://docs.python.org/3/library/fcntl.html
- Atomic File Operations: https://stackoverflow.com/questions/2333872/

## Acceptance Criteria

- [ ] File locking implemented with fcntl (POSIX) or msvcrt (Windows)
- [ ] Exclusive lock acquired before write
- [ ] Shared lock acquired for read
- [ ] Re-read after lock to merge concurrent changes
- [ ] Merge strategy deduplicates entries
- [ ] Backup created before overwrite
- [ ] Corrupt file handling with backup fallback
- [ ] fsync added for durability
- [ ] Unit tests for concurrent writes (multiprocessing)
- [ ] Unit tests for corrupt file recovery
- [ ] Documentation updated
- [ ] All existing tests pass
- [ ] Windows compatibility tested (use msvcrt for locking)

## Work Log

### 2025-11-13 - Code Review Discovery
**By:** Claude Code Review System
**Actions:**
- Discovered during data integrity review
- Analyzed by data-integrity-guardian agent
- Created race condition scenario
- Confirmed financial data loss risk
- Categorized as CRITICAL priority

**Learnings**:
- Read-modify-write without locking = race condition
- Financial data requires ACID guarantees
- File locking is simple and effective for single-machine scenarios
- Must re-read after acquiring lock (TOCTTOU)
- Merge strategy better than last-write-wins

## Notes

**Why File Locking**:
- Simple and effective for local file systems
- No external dependencies
- Works across processes
- Minimal performance overhead

**Merge Strategy**:
Instead of overwriting, we merge:
1. Acquire exclusive lock
2. Re-read file (might have changed)
3. Identify new entries (not in existing)
4. Combine existing + new
5. Write combined data
6. Release lock

This prevents data loss from concurrent operations.

**Cross-Platform Support**:
```python
import sys
if sys.platform == 'win32':
    import msvcrt
    # Use msvcrt.locking() on Windows
else:
    import fcntl
    # Use fcntl.flock() on POSIX
```

**Testing Concurrent Writes**:
```python
def test_concurrent_cost_tracking():
    """Test that concurrent cost tracking doesn't lose data."""
    import multiprocessing

    def track_cost(i):
        tracker = CostTracker(costs_file=shared_file)
        tracker.track(APIUsage(operation=f"test_{i}", ...))

    # Run 10 concurrent processes
    processes = [multiprocessing.Process(target=track_cost, args=(i,)) for i in range(10)]
    for p in processes:
        p.start()
    for p in processes:
        p.join()

    # Verify all 10 entries present
    tracker = CostTracker(costs_file=shared_file)
    assert len(tracker.usage_history) == 10
```

**Source**: Code review performed on 2025-11-13
**Review command**: /review #9
