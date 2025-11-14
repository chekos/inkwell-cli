---
status: completed
priority: p2
issue_id: "041"
tags: [data-integrity, atomicity, session-manager, cleanup]
dependencies: []
---

# Add Transaction Boundary to Session Cleanup

## Problem Statement

The `cleanup_old_sessions()` method in SessionManager deletes session files one-by-one without transaction boundaries. If the process crashes mid-cleanup, some sessions are deleted while others remain, creating an inconsistent state and orphaned sessions that require repeated cleanup cycles.

**Severity**: IMPORTANT - Prevents orphaned sessions and cleanup inconsistencies.

## Findings

- Discovered during data integrity audit by data-integrity-guardian agent
- Location: `src/inkwell/interview/session_manager.py:269-307`
- Issue: Incremental deletion without atomicity guarantees
- Risk: Partial cleanup, orphaned sessions, non-deterministic behavior

**Partial Cleanup Scenario:**
1. SessionManager runs cleanup at 2 AM: 20 abandoned sessions identified for deletion
2. Sessions 1-8 deleted successfully (✓ deleted)
3. **Process crashes** during deletion of session 9 (SIGKILL, OOM, power loss, Ctrl+C)
4. Sessions 9-20 remain on disk (still marked as old)
5. Next cleanup run (3 AM): Sessions 9-20 identified **again** for deletion
6. **Result:** Cleanup is non-deterministic and must be re-run multiple times. If crashes keep happening at different points, orphaned sessions accumulate indefinitely.

**Current Implementation:**
```python
def cleanup_old_sessions(self, days: int = 30) -> int:
    """Delete sessions older than specified days."""
    cutoff_date = now_utc() - timedelta(days=days)
    deleted = 0

    for session_file in self.session_dir.glob("session-*.json"):
        try:
            with session_file.open("r") as f:
                session_data = json.load(f)

            status = session_data.get("status")
            if status not in ["completed", "abandoned"]:
                continue

            updated_at_str = session_data.get("updated_at")
            if updated_at_str:
                updated_at = datetime.fromisoformat(updated_at_str.replace("Z", "+00:00"))
                if updated_at < cutoff_date:
                    session_file.unlink()  # ⚠️ DELETE - no rollback, no transaction
                    deleted += 1

        except (json.JSONDecodeError, ValueError, KeyError):
            continue  # ⚠️ Skip error, but already deleted some sessions

    return deleted
```

**Why This Happens:**
- No transaction boundary around entire cleanup operation
- Each deletion is committed immediately (cannot rollback)
- Process crash leaves partial cleanup state
- No way to detect or recover from partial cleanup

**Real-World Crash Scenarios:**
- SIGKILL (kill -9, OOM killer)
- User hits Ctrl+C mid-cleanup
- Power loss or system shutdown
- Disk I/O errors mid-operation
- Process reaches time/memory limits

## Proposed Solutions

### Option 1: Two-Phase Cleanup with Markers (Recommended)

Implement multi-phase cleanup with crash recovery:

```python
def cleanup_old_sessions(self, days: int = 30) -> int:
    """Delete old sessions with crash recovery support."""
    cutoff_date = now_utc() - timedelta(days=days)

    # Phase 1: Identify sessions to delete (read-only, no side effects)
    sessions_to_delete = []
    for session_file in self.session_dir.glob("session-*.json"):
        try:
            with session_file.open("r") as f:
                session_data = json.load(f)

            status = session_data.get("status")
            if status not in ["completed", "abandoned"]:
                continue

            updated_at_str = session_data.get("updated_at")
            if updated_at_str:
                updated_at = datetime.fromisoformat(updated_at_str.replace("Z", "+00:00"))
                if updated_at < cutoff_date:
                    sessions_to_delete.append(session_file)

        except (json.JSONDecodeError, ValueError, KeyError):
            logger.debug(f"Skipping invalid session file: {session_file}")
            continue

    logger.info(f"Identified {len(sessions_to_delete)} sessions for cleanup")

    # Phase 2: Mark for deletion (creates .deleting marker files)
    marked = []
    for session_file in sessions_to_delete:
        marker = session_file.with_suffix(".deleting")
        try:
            marker.touch()
            marked.append((session_file, marker))
            logger.debug(f"Marked for deletion: {session_file.name}")
        except Exception as e:
            logger.warning(f"Failed to mark {session_file} for deletion: {e}")
            continue

    # Phase 3: Actual deletion (crash-safe, markers enable recovery)
    deleted = 0
    for session_file, marker in marked:
        try:
            session_file.unlink()
            marker.unlink(missing_ok=True)
            deleted += 1
            logger.debug(f"Deleted session: {session_file.name}")
        except Exception as e:
            logger.warning(f"Failed to delete {session_file}: {e}")
            # ✅ Leave marker for next cleanup to retry
            continue

    # Phase 4: Recovery - cleanup any orphaned markers from previous crashes
    self._recover_failed_cleanup()

    logger.info(f"Cleanup complete: {deleted} sessions deleted")
    return deleted

def _recover_failed_cleanup(self) -> int:
    """Recover from previous cleanup crashes by processing orphaned markers."""
    recovered = 0

    for marker in self.session_dir.glob("*.deleting"):
        session_file = marker.with_suffix(".json")

        if session_file.exists():
            # Session still exists, retry deletion
            try:
                session_file.unlink()
                marker.unlink(missing_ok=True)
                recovered += 1
                logger.info(f"Recovered and deleted: {session_file.name}")
            except Exception as e:
                logger.warning(f"Failed to recover {session_file}: {e}")
        else:
            # Session already deleted, just remove marker
            marker.unlink(missing_ok=True)
            logger.debug(f"Removed orphaned marker: {marker.name}")

    if recovered > 0:
        logger.info(f"Recovered {recovered} sessions from previous failed cleanup")

    return recovered
```

**Marker File Structure:**
```
~/.config/inkwell/sessions/
├── session-abc123.json
├── session-abc123.deleting       ← Marker indicates deletion in progress
├── session-def456.json
└── session-def456.deleting       ← If process crashes, markers remain for recovery
```

**Pros**:
- Crash-safe with automatic recovery
- Markers enable retry of failed deletions
- Read-only phase 1 has no side effects
- Clear audit trail of what's being deleted
- Next cleanup run recovers automatically

**Cons**:
- Slightly more complex implementation
- Creates temporary marker files

**Effort**: Medium (2 hours)
**Risk**: Low

### Option 2: Write-Ahead Log (WAL)

Log deletions before executing:

```python
def cleanup_old_sessions(self, days: int = 30) -> int:
    wal_file = self.session_dir / ".cleanup.wal"

    # Write deletion plan to WAL
    sessions_to_delete = self._identify_old_sessions(days)
    wal_data = {
        "timestamp": now_utc().isoformat(),
        "sessions": [str(s) for s in sessions_to_delete]
    }
    wal_file.write_text(json.dumps(wal_data))

    # Execute deletions
    deleted = 0
    for session_file in sessions_to_delete:
        try:
            session_file.unlink()
            deleted += 1
        except Exception:
            continue

    # Success - remove WAL
    wal_file.unlink(missing_ok=True)
    return deleted

def recover_cleanup(self):
    """Recover from crashed cleanup using WAL."""
    wal_file = self.session_dir / ".cleanup.wal"
    if not wal_file.exists():
        return

    # Replay deletions from WAL
    wal_data = json.loads(wal_file.read_text())
    for session_path in wal_data["sessions"]:
        Path(session_path).unlink(missing_ok=True)

    wal_file.unlink()
```

**Pros**:
- Single WAL file (simpler than markers)
- Clear recovery mechanism

**Cons**:
- WAL file can become stale if not cleaned up
- Harder to debug than per-file markers
- More centralized failure point

**Effort**: Medium (2-3 hours)
**Risk**: Low

### Option 3: Dry-Run + Confirm Pattern

Separate identification from deletion:

```python
def identify_old_sessions(self, days: int = 30) -> list[Path]:
    """Phase 1: Identify sessions (read-only)."""
    # ... return list of sessions

def delete_sessions(self, session_files: list[Path]) -> int:
    """Phase 2: Delete sessions (destructive)."""
    # ... delete all or none
```

**Pros**:
- Clear separation of concerns
- Testable phases

**Cons**:
- Requires API change (breaking)
- Doesn't solve crash recovery
- Users must call both methods

**Effort**: Small (1 hour)
**Risk**: Medium (API change)

## Recommended Action

**Implement Option 1: Two-Phase Cleanup with Markers**

This provides automatic crash recovery without requiring API changes or centralized WAL management. Markers are easy to debug and understand.

**Priority**: P2 IMPORTANT - Prevents orphaned sessions and cleanup inconsistencies

## Technical Details

**Affected Files:**
- `src/inkwell/interview/session_manager.py:269-307` (cleanup_old_sessions method)
- `src/inkwell/interview/session_manager.py` (add _recover_failed_cleanup method)
- `tests/unit/interview/test_session_manager.py` (add crash recovery tests)

**Related Components:**
- Session files in `~/.config/inkwell/sessions/`
- Marker files: `*.deleting`

**Database Changes**: No

**Marker File Lifecycle:**
1. **Created**: When session identified for deletion (Phase 2)
2. **Removed**: After successful session deletion (Phase 3)
3. **Orphaned**: If process crashes between marker creation and deletion
4. **Recovered**: Next cleanup run processes orphaned markers

## Resources

- Original finding: DATA_INTEGRITY_REPORT.md (P2.4, lines 401-476)
- WAL pattern: https://en.wikipedia.org/wiki/Write-ahead_logging
- Two-phase commit: https://en.wikipedia.org/wiki/Two-phase_commit_protocol

## Acceptance Criteria

- [x] Phase 1: Identify sessions (read-only)
- [x] Phase 2: Mark sessions with `.deleting` files
- [x] Phase 3: Delete sessions and remove markers
- [x] Phase 4: Recover orphaned markers from crashes
- [x] `_recover_failed_cleanup()` method implemented
- [x] Recovery runs automatically at start of cleanup
- [x] Logging for all phases (identify, mark, delete, recover)
- [x] Test: Cleanup completes successfully → no markers remain
- [x] Test: Crash during deletion → markers remain for recovery
- [x] Test: Recovery processes orphaned markers correctly
- [x] Test: Multiple cleanup runs are idempotent
- [x] All existing session manager tests still pass

## Work Log

### 2025-11-14 - Data Integrity Audit Discovery
**By:** Claude Code Review System (data-integrity-guardian agent)
**Actions:**
- Identified lack of transaction boundaries in session cleanup
- Analyzed partial cleanup scenarios
- Classified as P2 IMPORTANT (cleanup reliability)
- Recommended two-phase cleanup with marker files

**Learnings:**
- Incremental operations without atomicity risk partial state
- Crash recovery requires audit trail (markers or WAL)
- Two-phase approach enables safe retry on failure
- Idempotent cleanup allows safe re-runs

### 2025-11-14 - Implementation Complete
**By:** Claude Code (code-review-resolution-specialist)
**Actions:**
- Added logging import and logger setup to session_manager.py
- Implemented `_recover_failed_cleanup()` method with file locking
- Refactored `cleanup_old_sessions()` to use four-phase approach:
  - Phase 0: Recovery - process orphaned markers from previous crashes
  - Phase 1: Identify - read-only identification of old sessions
  - Phase 2: Mark - create `.deleting` marker files
  - Phase 3: Delete - remove sessions and markers atomically
- Added comprehensive logging for debugging and monitoring
- Created 7 new tests covering crash recovery scenarios:
  - test_cleanup_recovers_from_crash
  - test_cleanup_is_idempotent
  - test_recover_failed_cleanup_with_existing_session
  - test_recover_failed_cleanup_with_missing_session
  - test_cleanup_no_markers_remain_on_success
  - test_cleanup_leaves_markers_on_deletion_failure
  - test_cleanup_handles_multiple_crashes
- All 54 tests passing (47 existing + 7 new)

**Technical Details:**
- Marker files use `.deleting` extension
- Recovery runs automatically at start of each cleanup
- File locking prevents race conditions during recovery
- Markers enable idempotent retry on failure
- Logging provides clear audit trail of cleanup operations

**Learnings:**
- Marker files provide simple and effective crash recovery
- Per-file markers easier to debug than centralized WAL
- File locking ensures safe concurrent access
- Idempotent operations enable safe retries
- Mock testing requires careful handling of state in closures

## Notes

**Why This Matters:**
- Session cleanup may run unattended (cron jobs, background tasks)
- Process crashes are realistic (OOM, signals, power loss)
- Orphaned sessions waste disk space over time
- Non-deterministic cleanup is hard to debug and trust

**Cleanup Scenarios:**
```
Scenario 1: Successful Cleanup
1. Identify 10 sessions → []
2. Mark 10 sessions → [.deleting files created]
3. Delete 10 sessions → [sessions deleted, markers removed]
4. Recover → [no orphaned markers]
Result: ✅ 10 deleted, 0 markers remaining

Scenario 2: Crash During Deletion
1. Identify 10 sessions → []
2. Mark 10 sessions → [.deleting files created]
3. Delete 5 sessions → [CRASH]
   Result: 5 sessions deleted, 5 sessions + 5 markers remain
4. Next cleanup run:
   a. Recover → [processes 5 orphaned markers]
   b. Delete remaining 5 → [markers removed]
Result: ✅ All 10 eventually deleted, 0 markers remaining

Scenario 3: Repeated Crashes (worst case)
Run 1: Delete 3, crash → 7 remain with markers
Run 2: Recover 7, delete 2, crash → 5 remain with markers
Run 3: Recover 5, delete all → 0 remain
Result: ✅ Eventually consistent, automatic recovery
```

**Implementation Notes:**
- Call `_recover_failed_cleanup()` at start of every cleanup
- Use `Path.unlink(missing_ok=True)` to avoid race conditions
- Log all recovery actions for debugging
- Consider adding `--dry-run` flag for testing

**Testing Strategy:**
```python
def test_cleanup_recovers_from_crash(session_manager, tmp_path):
    """Verify cleanup recovers from mid-deletion crash."""
    # Create 10 old sessions
    sessions = [create_old_session(session_manager, i) for i in range(10)]

    # Mock unlink to fail after 5 deletions (simulate crash)
    delete_count = 0
    original_unlink = Path.unlink

    def failing_unlink(self, missing_ok=False):
        nonlocal delete_count
        if self.suffix == ".json":
            delete_count += 1
            if delete_count > 5:
                raise OSError("Simulated crash")
        original_unlink(self, missing_ok=missing_ok)

    with patch.object(Path, 'unlink', failing_unlink):
        with pytest.raises(OSError):
            session_manager.cleanup_old_sessions(days=0)

    # Verify partial cleanup
    remaining = list(tmp_path.glob("session-*.json"))
    markers = list(tmp_path.glob("*.deleting"))
    assert len(remaining) == 5  # 5 sessions remain
    assert len(markers) == 5    # 5 markers remain

    # Run cleanup again - should recover
    deleted = session_manager.cleanup_old_sessions(days=0)

    # Verify complete recovery
    assert deleted == 5  # Deleted remaining 5
    assert len(list(tmp_path.glob("session-*.json"))) == 0
    assert len(list(tmp_path.glob("*.deleting"))) == 0

def test_cleanup_is_idempotent(session_manager):
    """Verify multiple cleanup runs are safe."""
    create_old_session(session_manager, 1)

    # Run cleanup 3 times
    count1 = session_manager.cleanup_old_sessions(days=0)
    count2 = session_manager.cleanup_old_sessions(days=0)
    count3 = session_manager.cleanup_old_sessions(days=0)

    assert count1 == 1  # First run deletes
    assert count2 == 0  # Second run finds nothing
    assert count3 == 0  # Third run finds nothing
```

**Monitoring and Debugging:**
```python
# Add metrics to cleanup
logger.info(
    f"Cleanup summary: identified={len(sessions_to_delete)}, "
    f"marked={len(marked)}, deleted={deleted}, recovered={recovered_count}"
)

# Add --debug flag to show markers
if logger.isEnabledFor(logging.DEBUG):
    markers = list(self.session_dir.glob("*.deleting"))
    if markers:
        logger.debug(f"Orphaned markers: {[m.name for m in markers]}")
```

Source: Triage session on 2025-11-14
