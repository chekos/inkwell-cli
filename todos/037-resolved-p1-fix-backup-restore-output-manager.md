---
status: resolved
priority: p1
issue_id: "037"
tags: [data-integrity, backup-recovery, output-manager, critical]
dependencies: []
resolved_at: 2025-11-14
---

# Fix Backup Restore in Output Manager Write Operations

## Problem Statement

The `write_episode()` method in OutputManager creates a backup directory before overwriting existing episodes, but fails to restore the backup if subsequent file writes fail after the initial directory creation succeeds. This results in complete data loss - users lose both the original episode and get an incomplete new episode.

**Severity**: CRITICAL - User data loss during overwrites is unacceptable.

## Findings

- Discovered during data integrity audit by data-integrity-guardian agent
- Location: `src/inkwell/output/manager.py:194-205`
- Issue: Backup restoration only happens if `mkdir()` fails, not if subsequent writes fail
- Risk: Orphaned backup directories, incomplete episodes, permanent data loss

**Data Loss Scenario:**
1. User runs `inkwell fetch podcast --overwrite` on existing episode
2. Backup created: `episode-2025-11-14-title.backup/` (original moved here)
3. New directory created: `episode-2025-11-14-title/` ✓
4. First markdown file written: `summary.md` ✓
5. Second markdown write fails: **disk full / permissions / quota exceeded**
6. Exception raised, user sees error
7. **Result:** Backup remains as `.backup/`, new episode is incomplete, user has lost access to complete original episode

**Current Implementation Problem:**
```python
# Create backup before deletion
backup_dir = episode_dir.with_suffix('.backup')
if backup_dir.exists():
    shutil.rmtree(backup_dir)  # Deletes old backup
episode_dir.rename(backup_dir)    # Moves current to backup

try:
    episode_dir.mkdir(parents=True)
except Exception:
    # ⚠️ ONLY restores if mkdir() fails
    if backup_dir.exists() and not episode_dir.exists():
        backup_dir.rename(episode_dir)
    raise

# ⚠️ NO PROTECTION: If any of these fail, backup is never restored
for result in extraction_results:
    output_file = episode_dir / f"{result.template_name}.md"
    self._write_file_atomic(output_file, result.content)
```

## Proposed Solutions

### Option 1: Wrap Entire Write Operation in Try/Except (Recommended)

Move exception handling to cover ALL write operations, not just mkdir:

```python
def write_episode(
    self,
    episode_metadata: EpisodeMetadata,
    extraction_results: list[ExtractionResult],
    overwrite: bool = False,
) -> EpisodeOutput:
    episode_dir = None
    backup_dir = None

    try:
        # Create episode directory (handles backup internally)
        episode_dir = self._create_episode_directory(episode_metadata, overwrite)
        backup_dir = episode_dir.with_suffix('.backup') if overwrite else None

        # Write markdown files
        output_files = []
        total_cost = 0.0

        for result in extraction_results:
            output_file = episode_dir / f"{result.template_name}.md"
            self._write_file_atomic(output_file, result.content)
            output_files.append(output_file)
            total_cost += result.cost

        # Write metadata file
        metadata_file = episode_dir / ".metadata.yaml"
        self._write_metadata(metadata_file, episode_metadata)

        # ✅ SUCCESS - remove backup
        if backup_dir and backup_dir.exists():
            shutil.rmtree(backup_dir)

        return EpisodeOutput(
            episode_dir=episode_dir,
            output_files=output_files,
            total_cost=total_cost,
        )

    except Exception:
        # ✅ RESTORE backup on ANY failure
        if backup_dir and backup_dir.exists() and episode_dir:
            if episode_dir.exists():
                shutil.rmtree(episode_dir)
            backup_dir.rename(episode_dir)
        raise
```

**Pros**:
- Guarantees backup restoration on any failure
- Clean rollback to known good state
- No partial episodes left on disk
- Users never lose original data

**Cons**:
- None (this is the correct approach)

**Effort**: Small (1-2 hours)
**Risk**: Low

### Option 2: Two-Phase Commit Pattern

Write to temporary directory first, only move to final location after all writes succeed:

```python
def write_episode(...) -> EpisodeOutput:
    temp_dir = self.output_dir / f".tmp-{uuid4()}"
    episode_dir = self._get_episode_directory(episode_metadata)
    backup_dir = episode_dir.with_suffix('.backup') if overwrite else None

    try:
        # Phase 1: Write everything to temp directory
        temp_dir.mkdir(parents=True)

        for result in extraction_results:
            output_file = temp_dir / f"{result.template_name}.md"
            self._write_file_atomic(output_file, result.content)

        # Phase 2: Atomic swap
        if overwrite and episode_dir.exists():
            episode_dir.rename(backup_dir)

        temp_dir.rename(episode_dir)

        # Success - remove backup
        if backup_dir and backup_dir.exists():
            shutil.rmtree(backup_dir)

    except Exception:
        # Cleanup temp directory
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        # Restore backup if needed
        if backup_dir and backup_dir.exists():
            backup_dir.rename(episode_dir)
        raise
```

**Pros**:
- Never touches original until all writes succeed
- True atomic swap
- Even safer than Option 1

**Cons**:
- More complex implementation
- Extra disk space needed (temp + backup)
- Requires more changes to existing code

**Effort**: Medium (3-4 hours)
**Risk**: Low

## Recommended Action

**Implement Option 1: Wrap Entire Write Operation**

This is the minimal fix that solves the problem completely. Option 2 is slightly safer but requires more refactoring. Option 1 provides adequate protection with minimal code changes.

**Priority**: P1 CRITICAL - Data loss during overwrites is unacceptable

## Technical Details

**Affected Files:**
- `src/inkwell/output/manager.py:194-205` (main fix)
- `tests/unit/output/test_manager.py` (add failure tests)

**Related Components:**
- `src/inkwell/output/models.py` (EpisodeOutput)
- `src/inkwell/cli.py` (calls write_episode with --overwrite flag)

**Database Changes**: No

**Failure Scenarios to Test:**
1. Disk full during markdown write
2. Permission denied during metadata write
3. Process killed mid-write (SIGKILL)
4. Filesystem errors (I/O error, read-only)

## Resources

- Original finding: DATA_INTEGRITY_REPORT.md (P1.3, lines 143-222)
- Related: Atomic write implementation in `_write_file_atomic()`
- Python shutil docs: https://docs.python.org/3/library/shutil.html

## Acceptance Criteria

- [x] Try/except wraps entire write operation (all file writes)
- [x] Backup restored on ANY exception during write
- [x] Partial episode directories cleaned up on failure
- [x] Backup removed only after ALL writes succeed
- [x] Test: Disk full scenario - backup restored
- [x] Test: Permission error - backup restored
- [x] Test: Metadata write failure - backup restored
- [x] Test: Successful overwrite - backup removed
- [x] All existing tests still pass (52/52 passing)
- [x] No orphaned `.backup/` directories after failures

## Work Log

### 2025-11-14 - Data Integrity Audit Discovery
**By:** Claude Code Review System (data-integrity-guardian agent)
**Actions:**
- Identified incomplete backup restoration logic
- Analyzed data loss scenarios
- Classified as P1 CRITICAL data integrity issue
- Recommended comprehensive exception handling

**Learnings:**
- Backup creation alone doesn't guarantee data safety
- Exception handling must cover entire operation, not just setup
- Partial operations are worse than failed operations
- Users expect rollback on failure, especially with --overwrite flag

### 2025-11-14 - Implementation Complete
**By:** Claude Code (code-review-resolver agent)
**Actions:**
- Wrapped entire write_episode() operation in try/except
- Pre-calculate episode directory path for backup tracking
- Added _get_episode_directory_path() helper method
- Backup restored on ANY exception (mkdir, file write, metadata write)
- Backup removed only after successful completion
- Added 4 comprehensive tests covering all failure scenarios
- All 52 existing tests still pass

**Implementation Details:**
- Lines 74-143: Refactored write_episode() with comprehensive backup restoration
- Lines 145-167: Added _get_episode_directory_path() helper
- Lines 224-226: Simplified _create_episode_directory() (removed duplicate handling)
- Tests 865-1000: Added mkdir failure, file write failure, metadata failure, and success tests

**Test Results:**
```
tests/unit/test_output_manager.py::test_overwrite_restores_backup_on_mkdir_failure PASSED
tests/unit/test_output_manager.py::test_overwrite_restores_backup_on_file_write_failure PASSED
tests/unit/test_output_manager.py::test_overwrite_restores_backup_on_metadata_write_failure PASSED
tests/unit/test_output_manager.py::test_overwrite_removes_backup_on_success PASSED
52 total tests passing (100%)
```

**Key Design Decisions:**
- Pre-calculate directory path before any operations for reliable backup tracking
- Exception handler works even if mkdir fails (episode_dir pre-calculated)
- Backup cleaned up only after ALL writes succeed
- No orphaned .backup directories left behind on failures
- Logging added for debugging backup operations

**Files Modified:**
- /Users/sergio/projects/inkwell-cli/src/inkwell/output/manager.py
- /Users/sergio/projects/inkwell-cli/tests/unit/test_output_manager.py

## Notes

**Why This Matters:**
- Users trust `--overwrite` to safely replace episodes
- Podcast episode data can take hours to process
- Original transcripts may no longer be available
- Data loss violates user expectations of tool reliability

**Real-World Failure Scenarios:**
- Disk quota exceeded mid-write (common in CI environments)
- Network filesystem becoming read-only
- Process killed by OOM killer
- Antivirus temporarily locking files

**Testing Strategy:**
```python
def test_write_episode_restores_backup_on_failure(tmp_path, mocker):
    """Verify backup restored when file write fails."""
    # Create original episode
    manager = OutputManager(tmp_path)
    original = create_test_episode()
    manager.write_episode(original, [], overwrite=False)

    # Mock file write to fail on 2nd file
    write_count = 0
    original_write = manager._write_file_atomic

    def failing_write(path, content):
        nonlocal write_count
        write_count += 1
        if write_count == 2:
            raise OSError("Disk full")
        original_write(path, content)

    mocker.patch.object(manager, '_write_file_atomic', failing_write)

    # Attempt overwrite - should fail and restore backup
    with pytest.raises(OSError):
        manager.write_episode(original, results, overwrite=True)

    # Verify: original episode still exists and is complete
    episode_dir = manager._get_episode_directory(original)
    assert episode_dir.exists()
    assert (episode_dir / "summary.md").exists()
    assert not (episode_dir.with_suffix('.backup')).exists()
```

**Implementation Notes:**
- Keep backup cleanup as last step before return
- Use `shutil.rmtree()` for cleanup, handle ENOENT gracefully
- Log backup restoration for debugging
- Consider adding backup expiry cleanup (remove .backup dirs > 7 days)

Source: Triage session on 2025-11-14
