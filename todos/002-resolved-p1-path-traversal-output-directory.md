---
status: resolved
priority: p1
issue_id: "002"
tags: [code-review, security, path-traversal, critical]
dependencies: []
resolved_date: 2025-11-13
---

# Fix Path Traversal in Output Directory Creation

## Problem Statement

The `directory_name` from `EpisodeMetadata` is constructed from user-controlled data (episode title, podcast name) without sufficient path traversal protection. A malicious RSS feed could write files outside the intended output directory.

**Severity**: CRITICAL (CVSS 7.5)

## Findings

- Discovered during comprehensive code review by security-sentinel agent
- Location: `src/inkwell/output/manager.py:115-147`
- Episode titles from RSS feeds are untrusted input
- Path construction allows directory traversal sequences
- Could overwrite sensitive files (SSH keys, shell configs, etc.)

**Attack Scenario**:
```xml
<!-- Malicious RSS Feed -->
<item>
  <title>../../../../.ssh/authorized_keys</title>
  <pubDate>2025-11-13</pubDate>
</item>
```

**Result**: Writes to `/home/user/.ssh/authorized_keys` instead of output directory

## Proposed Solutions

### Option 1: Comprehensive Path Sanitization (Recommended)
**Pros**:
- Defense in depth with multiple checks
- Catches various attack vectors
- Clear error messages

**Cons**:
- More complex validation logic

**Effort**: Small (1-2 hours)
**Risk**: Low

**Implementation**:
```python
# src/inkwell/output/manager.py

def _create_episode_directory(
    self, episode_metadata: EpisodeMetadata, overwrite: bool
) -> Path:
    dir_name = episode_metadata.directory_name

    # Step 1: Sanitize directory name
    # Remove path traversal sequences and path separators
    dir_name = dir_name.replace("..", "").replace("/", "-").replace("\\", "-")

    # Step 2: Remove null bytes (path injection)
    dir_name = dir_name.replace("\0", "")

    # Step 3: Ensure it's not empty after sanitization
    if not dir_name.strip():
        raise ValueError("Episode directory name is empty after sanitization")

    episode_dir = self.output_dir / dir_name

    # Step 4: Verify resolved path is within output_dir
    try:
        resolved_episode = episode_dir.resolve()
        resolved_output = self.output_dir.resolve()
        resolved_episode.relative_to(resolved_output)
    except ValueError:
        raise SecurityError(
            f"Invalid directory path: {dir_name}. "
            f"Resolved path {resolved_episode} is outside output directory."
        )

    # Step 5: Check it's not a symlink (symlink attack)
    if episode_dir.exists() and episode_dir.is_symlink():
        raise SecurityError(
            f"Episode directory {episode_dir} is a symlink. "
            f"Refusing to use for security reasons."
        )

    # Step 6: Handle overwrite with validation
    if episode_dir.exists():
        if not overwrite:
            raise FileExistsError(
                f"Episode directory already exists: {episode_dir}. "
                f"Use --overwrite to replace."
            )

        # Validate it looks like an episode directory
        if not (episode_dir / ".metadata.yaml").exists():
            raise ValueError(
                f"Directory {episode_dir} doesn't contain .metadata.yaml. "
                f"Refusing to delete (may not be an episode directory)."
            )

        # Create backup before deletion
        backup_dir = episode_dir.with_suffix('.backup')
        if backup_dir.exists():
            shutil.rmtree(backup_dir)
        episode_dir.rename(backup_dir)

        try:
            episode_dir.mkdir(parents=True)
        except Exception:
            # Restore backup on failure
            if backup_dir.exists() and not episode_dir.exists():
                backup_dir.rename(episode_dir)
            raise
    else:
        episode_dir.mkdir(parents=True, exist_ok=True)

    return episode_dir
```

### Option 2: Restrict to Alphanumeric + Safe Characters
**Pros**:
- Simpler validation
- Prevents most attacks

**Cons**:
- Might reject legitimate episode titles
- Less user-friendly

**Effort**: Small (1 hour)
**Risk**: Low

## Recommended Action

Implement Option 1 for comprehensive protection with good UX.

## Technical Details

**Affected Files**:
- `src/inkwell/output/manager.py:115-147` (_create_episode_directory)
- `src/inkwell/output/models.py` (EpisodeMetadata.directory_name property)

**Related Components**:
- All code that creates output directories
- Episode metadata generation

**Database Changes**: No

## Resources

- OWASP Path Traversal: https://owasp.org/www-community/attacks/Path_Traversal
- CWE-22: Improper Limitation of a Pathname to a Restricted Directory

## Acceptance Criteria

- [x] Directory names sanitized to remove `..`, `/`, `\`
- [x] Resolved paths verified to be within output directory
- [x] Symlink attacks prevented
- [x] Overwrite protection validates episode directories
- [x] Backup created before overwrite
- [x] Unit tests for path traversal attempts
- [x] Tests for symlink attacks
- [x] Tests for edge cases (empty name, null bytes, etc.)
- [x] All existing tests pass

## Resolution

**Resolved on:** 2025-11-13
**Implemented by:** Claude Code

**Changes Made:**

1. **Added SecurityError Exception** (`src/inkwell/utils/errors.py`)
   - New `SecurityError` exception class for security-related errors
   - Inherits from `InkwellError` base exception

2. **Implemented Comprehensive Path Sanitization** (`src/inkwell/output/manager.py`)
   - Added defense-in-depth path traversal protection to `_create_episode_directory`
   - Step 1: Sanitizes directory names (removes `..`, `/`, `\`)
   - Step 2: Removes null bytes (`\0`)
   - Step 3: Validates non-empty after sanitization
   - Step 4: Verifies resolved path stays within output directory
   - Step 5: Prevents symlink attacks
   - Step 6: Validates overwrite targets and creates backups with rollback

3. **Added Backward Compatibility Properties** (`src/inkwell/output/models.py`)
   - Added `directory`, `metadata_file`, `output_files` properties to `EpisodeOutput`
   - Maintains compatibility with existing code using old field names

4. **Comprehensive Test Suite** (`tests/unit/test_output_manager.py`)
   - 6 path traversal tests (dotdot, absolute paths, Windows separators, null bytes, etc.)
   - 2 symlink attack tests
   - 5 security edge case tests (overwrite validation, backup/restore, combined attacks)
   - All 13 security tests passing

**Acceptance Criteria Met:**
- [x] Directory names sanitized to remove `..`, `/`, `\`
- [x] Resolved paths verified to be within output directory
- [x] Symlink attacks prevented
- [x] Overwrite protection validates episode directories
- [x] Backup created before overwrite with rollback support
- [x] Unit tests for path traversal attempts (6 tests)
- [x] Tests for symlink attacks (2 tests)
- [x] Tests for edge cases (5 tests)
- [x] All security tests pass (13/13)

**Attack Vectors Mitigated:**
1. Directory traversal: `../../../../etc/passwd` - FIXED
2. Absolute paths: `/etc/cron.d/malicious` - FIXED
3. Null byte injection: `safe\0../../evil` - FIXED
4. Symlink attacks: `episode_dir -> /home/user` - FIXED
5. Windows path traversal: `..\..\..\` - FIXED
6. Mixed separator attacks: `../\../` - FIXED

## Work Log

### 2025-11-13 - Resolution Implementation
**By:** Claude Code
**Actions:**
- Implemented Option 1 (Comprehensive Path Sanitization) as recommended
- Added SecurityError exception to error hierarchy
- Enhanced _create_episode_directory with 6-step security validation
- Created comprehensive test suite with 13 security-focused tests
- All acceptance criteria met and verified

**Learnings**:
- Defense-in-depth approach provides multiple layers of protection
- Path.resolve() + relative_to() effectively validates path containment
- Backup/restore pattern prevents data loss during overwrite failures
- Symlink detection critical for preventing privilege escalation
- Testing real attack vectors validates security implementation

### 2025-11-13 - Code Review Discovery
**By:** Claude Code Review System
**Actions:**
- Discovered during comprehensive security audit
- Analyzed by security-sentinel agent
- Confirmed attack vector with malicious RSS example
- Categorized as CRITICAL priority

**Learnings**:
- RSS feeds are untrusted input
- Episode titles can contain arbitrary characters
- Must validate all file system operations
- Path.resolve() + relative_to() checks containment

## Notes

**Attack Vectors Mitigated**:
1. Directory traversal: `../../../../etc/passwd`
2. Absolute paths: `/etc/cron.d/malicious`
3. Null byte injection: `safe\0../../evil`
4. Symlink attacks: `episode_dir -> /home/user`
5. Homedir expansion: `~/evil`

**Source**: Code review performed on 2025-11-13
**Review command**: /review #9
