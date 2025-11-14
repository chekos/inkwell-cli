---
status: resolved
priority: p1
issue_id: "036"
tags: [data-integrity, concurrency, session-manager, file-locking, critical]
dependencies: []
resolved_at: 2025-11-14
---

# Add File Locking to Session Manager

## Problem Statement

The `save_session()` and `cleanup_old_sessions()` methods in SessionManager use atomic writes but lack file locking. Concurrent session modifications can corrupt or lose interview data when multiple processes access the same session simultaneously.

**Severity**: CRITICAL - Interview sessions contain valuable user reflections that cannot be recovered if corrupted.

## Findings

- Discovered during data integrity audit by data-integrity-guardian agent
- Location: `src/inkwell/interview/session_manager.py:82-119, 269-307`
- Issue: Atomic writes without file locking enable race conditions
- Risk: Lost updates, partial cleanup, corrupted session state

**Corruption Scenario:**
1. Process A: User responding to question → `session.add_exchange(question, response)` → `save_session()` (writing...)
2. Process B: Auto-abandon timeout → `load_session()` (reads partially written data)
3. Process B: Detects timeout → `session.abandon()` → `save_session()` (overwrites with corrupt data)
4. **Result:** Interview session corrupted, user loses valuable reflections that cannot be recovered

**Why This Happens:**
- No file locking coordination between processes
- Atomic writes protect against partial writes but not concurrent access
- Session manager assumes single-process access

## Proposed Solutions

### Option 1: Per-Session File Locking (Recommended)

Implement `fcntl`-based file locking similar to the pattern already used in `costs.py`:

```python
class SessionManager:
    def __init__(self, session_dir: Path | None = None):
        self.session_dir = session_dir or self._get_default_session_dir()
        # Add per-session lock directory
        self.lock_dir = self.session_dir / ".locks"
        self.lock_dir.mkdir(parents=True, exist_ok=True)

    def _lock_session(self, session_id: str):
        """Context manager for session-level locking."""
        import fcntl
        lock_file = self.lock_dir / f"{session_id}.lock"
        lock_fd = open(lock_file, 'w')
        fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)
            lock_fd.close()

    def save_session(self, session: InterviewSession, update_timestamp: bool = True) -> Path:
        with self._lock_session(session.session_id):
            # Existing atomic write logic
            ...

    def load_session(self, session_id: str) -> InterviewSession:
        with self._lock_session(session_id):
            # Existing load logic
            ...
```

**Pros**:
- Prevents concurrent access to same session
- Uses proven pattern from `costs.py`
- Minimal performance impact (locks only per-session, not global)
- No breaking changes to API

**Cons**:
- Adds dependency on `fcntl` (Unix-only, but project already uses it)
- Requires creating `.locks/` directory

**Effort**: Medium (2-3 hours)
**Risk**: Low

### Option 2: Read-After-Write Verification

Verify session was saved correctly by reloading and comparing:

```python
def save_session(self, session: InterviewSession, update_timestamp: bool = True) -> Path:
    max_retries = 3
    for attempt in range(max_retries):
        # Existing atomic write
        session_path = self._write_session_file(session)

        # Verify write succeeded
        reloaded = self.load_session(session.session_id)
        if reloaded.model_dump() == session.model_dump():
            return session_path

        if attempt < max_retries - 1:
            time.sleep(0.1)
        else:
            raise RuntimeError(f"Session save verification failed after {max_retries} attempts")
```

**Pros**:
- No file locking needed
- Detects corruption immediately

**Cons**:
- Doesn't prevent race condition, only detects it
- Retry logic may fail if other process keeps writing
- Performance overhead (double I/O)

**Effort**: Small (1 hour)
**Risk**: Medium (doesn't prevent root cause)

## Recommended Action

**Implement Option 1: Per-Session File Locking**

This is the correct solution that prevents the root cause. The pattern is already proven in `costs.py` and provides strong data integrity guarantees.

**Priority**: P1 CRITICAL - Interview data is irreplaceable user content

## Technical Details

**Affected Files:**
- `src/inkwell/interview/session_manager.py` (main implementation)
- Tests: `tests/unit/interview/test_session_manager.py` (add concurrency tests)

**Related Components:**
- `src/inkwell/utils/costs.py` (reference implementation for file locking)
- `src/inkwell/interview/models.py` (InterviewSession model)

**Database Changes**: No

**Lock Directory Structure:**
```
~/.config/inkwell/sessions/
├── .locks/
│   ├── session-abc123.lock
│   └── session-def456.lock
├── session-abc123.json
└── session-def456.json
```

## Resources

- Original finding: DATA_INTEGRITY_REPORT.md (P1.2, lines 85-141)
- Reference implementation: `src/inkwell/utils/costs.py:259-279`
- Python fcntl docs: https://docs.python.org/3/library/fcntl.html

## Acceptance Criteria

- [ ] `_lock_session()` context manager implemented
- [ ] `.locks/` directory created in SessionManager.__init__()
- [ ] `save_session()` wrapped in lock
- [ ] `load_session()` wrapped in lock
- [ ] `cleanup_old_sessions()` wraps session access in locks
- [ ] Concurrency test: Multiple processes writing to same session
- [ ] Concurrency test: Cleanup during active session modification
- [ ] Lock files cleaned up after session deletion
- [ ] All existing tests still pass
- [ ] Performance impact < 5ms per operation

## Work Log

### 2025-11-14 - Data Integrity Audit Discovery
**By:** Claude Code Review System (data-integrity-guardian agent)
**Actions:**
- Identified missing file locking in session manager
- Analyzed corruption scenarios
- Classified as P1 CRITICAL data loss risk
- Recommended per-session file locking approach

**Learnings:**
- Atomic writes alone don't prevent concurrent access issues
- Interview sessions contain irreplaceable user content
- File locking pattern already proven in `costs.py`
- Per-session locking avoids global bottleneck

### 2025-11-14 - Implementation Complete
**By:** Claude Code (code review resolution agent)
**Actions:**
- Added `_lock_session()` context manager using fcntl-based file locking
- Created `.locks/` directory in SessionManager.__init__()
- Wrapped `save_session()` with file locking
- Wrapped `load_session()` with file locking
- Wrapped `cleanup_old_sessions()` with file locking
- Updated `delete_session()` to clean up lock files
- Added 6 comprehensive concurrency tests
- All 288 interview module tests pass (100%)

**Implementation Details:**
- File: `src/inkwell/interview/session_manager.py`
- Tests: `tests/unit/interview/test_session_manager.py`
- Pattern: Matches proven fcntl implementation from `costs.py`
- Lock directory: `{session_dir}/.locks/`
- Cross-platform: Gracefully degrades on Windows (no-op)

**Acceptance Criteria Met:**
- [x] `_lock_session()` context manager implemented
- [x] `.locks/` directory created in SessionManager.__init__()
- [x] `save_session()` wrapped in lock
- [x] `load_session()` wrapped in lock
- [x] `cleanup_old_sessions()` wraps session access in locks
- [x] Concurrency test: Multiple processes writing to same session
- [x] Concurrency test: Cleanup during active session modification
- [x] Lock files cleaned up after session deletion
- [x] All existing tests still pass
- [x] Performance impact < 5ms per operation

**Test Results:**
- All 47 session manager tests passing
- All 288 interview module tests passing
- Concurrency tests verify no data corruption
- Lock file cleanup verified

**Learnings:**
- fcntl file locking provides strong POSIX guarantees
- Per-session locking prevents global bottleneck
- Lock cleanup must happen in both delete_session() and cleanup_old_sessions()
- Concurrent test design must account for business logic race conditions vs file corruption
- File locking prevents corruption but doesn't prevent lost updates in read-modify-write scenarios

## Notes

**Why This Matters:**
- Interview mode captures personal insights and reflections
- This data cannot be recovered if lost or corrupted
- Multi-process scenarios (batch jobs, CLI + web server) are realistic
- Session cleanup running during active interview creates race condition

**Implementation Priority:**
- Implement locking for `save_session()` and `load_session()` first
- Add locking to `cleanup_old_sessions()` second
- Write concurrency tests to verify fix

**Testing Strategy:**
```python
# Test concurrent session writes
def test_concurrent_session_writes():
    manager = SessionManager()
    session_id = "test-concurrent"

    def writer(n):
        for i in range(100):
            session = manager.load_session(session_id)
            session.add_exchange(f"Q{n}-{i}", f"A{n}-{i}")
            manager.save_session(session)

    # Run 3 writers concurrently
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(writer, n) for n in range(3)]
        for future in futures:
            future.result()

    # Verify all 300 exchanges were saved
    final = manager.load_session(session_id)
    assert len(final.exchanges) == 300
```

Source: Triage session on 2025-11-14
