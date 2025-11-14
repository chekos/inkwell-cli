---
status: pending
priority: p2
issue_id: "044"
tags: [data-integrity, disaster-recovery, encryption, key-management]
dependencies: []
---

# Add Automatic Backup for Encryption Keyfile

## Problem Statement

The encryption keyfile (`.keyfile`) used to encrypt/decrypt feed credentials is generated once but never backed up. If the keyfile is deleted or corrupted, all encrypted feed credentials are permanently lost and cannot be recovered.

**Severity**: IMPORTANT - Data loss prevention for encrypted credentials.

## Findings

- Discovered during data integrity audit by data-integrity-guardian agent
- Location: `src/inkwell/config/crypto.py:40-52`
- Issue: Keyfile generated without backup
- Risk: Permanent loss of all encrypted feed credentials

**Catastrophic Loss Scenario:**
1. User configures 15 podcast feeds with authentication (private/paid feeds with complex credentials)
2. Each feed requires: username, password, possibly 2FA tokens
3. All credentials encrypted using `.keyfile` and stored in `feeds.yaml`
4. Keyfile stored at `~/.config/inkwell/.keyfile`
5. **User accidentally runs:** `rm -rf ~/.config/inkwell/` (cleaning up, thinks they can regenerate)
   OR: Restores config from backup that doesn't include `.keyfile`
   OR: Keyfile corrupted by disk error
6. User tries to fetch episodes: `DecryptionError: Invalid key`
7. **Result:** All 15 feed credentials permanently lost and unrecoverable
8. User must manually:
   - Find credentials for all 15 feeds (possibly lost)
   - Re-add each feed one by one
   - Re-enter complex passwords and auth tokens
   - **Hours of work** to recreate what was lost in seconds

**Current Implementation:**
```python
class CredentialEncryptor:
    def _ensure_key(self) -> bytes:
        """Ensure encryption key exists, creating if necessary."""
        if self.key_path.exists():
            self._validate_key_permissions()
            return self.key_path.read_bytes()

        # Generate new key
        key = Fernet.generate_key()

        # Ensure parent directory exists
        self.key_path.parent.mkdir(parents=True, exist_ok=True)

        # Write key file
        self.key_path.write_bytes(key)
        self.key_path.chmod(0o600)
        # ⚠️ No backup created
        # ⚠️ No recovery instructions
        # ⚠️ No warning about importance

        return key
```

**Why This Happens:**
- Keyfile is critical but users don't realize it
- No automatic backup mechanism
- No recovery documentation
- Easy to accidentally delete with parent directory
- Not included in typical backup routines

**Real-World Key Loss Scenarios:**
- Accidental directory deletion (`rm -rf ~/.config/inkwell/`)
- Config restore from backup without keyfile
- Filesystem corruption (bad disk sector)
- Migration to new machine without copying keyfile
- Cloud sync service conflict (overwrites with old version)
- User cleanup of "hidden files" (`.keyfile` looks expendable)

## Proposed Solutions

### Option 1: Automatic Backup + Recovery Instructions (Recommended)

Create backup keyfile and recovery documentation automatically:

```python
class CredentialEncryptor:
    def _ensure_key(self) -> bytes:
        """Ensure encryption key exists, creating if necessary."""
        if self.key_path.exists():
            self._validate_key_permissions()
            return self.key_path.read_bytes()

        # Generate new key
        key = Fernet.generate_key()

        # Ensure parent directory exists
        self.key_path.parent.mkdir(parents=True, exist_ok=True)

        # Write primary key file
        self.key_path.write_bytes(key)
        self.key_path.chmod(0o600)

        # ✅ Create backup with same permissions
        backup_path = self.key_path.parent / ".keyfile.backup"
        backup_path.write_bytes(key)
        backup_path.chmod(0o600)

        # ✅ Create recovery instructions
        recovery_doc = self.key_path.parent / "KEYFILE_RECOVERY.txt"
        recovery_doc.write_text(
            f"ENCRYPTION KEY BACKUP\n"
            f"====================\n\n"
            f"Your encryption key is stored at:\n"
            f"  Primary: {self.key_path}\n"
            f"  Backup:  {backup_path}\n\n"
            f"IMPORTANT: If you lose both files, all encrypted feed credentials\n"
            f"will be permanently unrecoverable. Back up these files securely!\n\n"
            f"To restore from backup:\n"
            f"  cp {backup_path} {self.key_path}\n"
            f"  chmod 600 {self.key_path}\n\n"
            f"To back up to external location:\n"
            f"  cp {self.key_path} /path/to/secure/backup/location/\n\n"
            f"Security Notes:\n"
            f"  - Keep backups secure (encrypted USB, password manager, etc.)\n"
            f"  - Never commit keyfile to git\n"
            f"  - Never share keyfile (it decrypts all your credentials)\n"
            f"  - If compromised, regenerate and re-add all feeds\n\n"
            f"Generated: {datetime.now().isoformat()}\n"
        )
        recovery_doc.chmod(0o600)

        # ✅ Warn user about critical files
        logger.warning(
            f"Created new encryption key at {self.key_path}\n"
            f"IMPORTANT: A backup has been created at {backup_path}\n"
            f"See {recovery_doc} for recovery instructions.\n"
            f"Losing both files will result in permanent data loss!"
        )

        return key

    def verify_backup_exists(self) -> bool:
        """Check if backup keyfile exists and matches primary."""
        backup_path = self.key_path.parent / ".keyfile.backup"

        if not backup_path.exists():
            return False

        # Verify backup matches primary
        if self.key_path.exists():
            primary_key = self.key_path.read_bytes()
            backup_key = backup_path.read_bytes()
            return primary_key == backup_key

        return True

    def restore_from_backup(self) -> bool:
        """Restore primary keyfile from backup."""
        backup_path = self.key_path.parent / ".keyfile.backup"

        if not backup_path.exists():
            logger.error("Backup keyfile not found")
            return False

        backup_key = backup_path.read_bytes()
        self.key_path.write_bytes(backup_key)
        self.key_path.chmod(0o600)

        logger.info(f"Restored keyfile from backup: {backup_path}")
        return True
```

**File Structure:**
```
~/.config/inkwell/
├── config.yaml
├── feeds.yaml
├── .keyfile              ← Primary encryption key
├── .keyfile.backup       ← Automatic backup
└── KEYFILE_RECOVERY.txt  ← Recovery instructions
```

**Pros**:
- Automatic backup on key creation
- Clear recovery instructions
- No user action required
- Protects against accidental deletion of primary
- Warns user about importance

**Cons**:
- Backup in same directory (not offsite)
- Both files could be deleted together

**Effort**: Small (1 hour)
**Risk**: Low

### Option 2: Multiple Backup Locations

Create backups in multiple locations:

```python
def _ensure_key(self) -> bytes:
    # ... generate key

    # Backup 1: Same directory
    backup1 = self.key_path.parent / ".keyfile.backup"
    backup1.write_bytes(key)

    # Backup 2: Home directory
    backup2 = Path.home() / ".inkwell-keyfile-backup"
    backup2.write_bytes(key)

    # Backup 3: Temp directory (for current session)
    import tempfile
    backup3 = Path(tempfile.gettempdir()) / "inkwell-keyfile-backup"
    backup3.write_bytes(key)
```

**Pros**:
- Multiple backup locations increase safety
- Home directory backup survives config deletion

**Cons**:
- Security risk (keys in multiple locations)
- Harder to manage
- May confuse users

**Effort**: Small (1 hour)
**Risk**: Medium (security)

### Option 3: Cloud Backup Integration

Offer to upload encrypted keyfile to cloud storage:

```python
def _offer_cloud_backup(self, key: bytes):
    """Offer to backup keyfile to user's cloud storage."""
    print("Would you like to backup your encryption key to cloud storage? [y/N]")
    if input().lower() == 'y':
        # Guide user through cloud backup
        ...
```

**Pros**:
- Offsite backup
- Protected against local disasters

**Cons**:
- Complex implementation
- Security concerns (cloud exposure)
- Requires user interaction

**Effort**: Large (4+ hours)
**Risk**: High (security, complexity)

## Recommended Action

**Implement Option 1: Automatic Backup + Recovery Instructions**

This provides immediate protection without complexity or security risks. Users get automatic backup and clear recovery instructions.

**Priority**: P2 IMPORTANT - Data loss prevention

## Technical Details

**Affected Files:**
- `src/inkwell/config/crypto.py:40-52` (_ensure_key method)
- `src/inkwell/config/crypto.py` (add verify_backup_exists, restore_from_backup)
- `src/inkwell/cli.py` (add `inkwell config verify-keyfile` command)
- `tests/unit/config/test_crypto.py` (test backup creation)

**Related Components:**
- `~/.config/inkwell/.keyfile` (primary key)
- `~/.config/inkwell/.keyfile.backup` (new backup)
- `~/.config/inkwell/KEYFILE_RECOVERY.txt` (new recovery docs)

**Database Changes**: No

**Security Considerations:**
- Both primary and backup must have 0600 permissions
- Recovery doc should also be 0600 (contains file paths)
- Warn users to create offsite backup manually
- Document keyfile in .gitignore

## Resources

- Original finding: DATA_INTEGRITY_REPORT.md (P2.7, lines 585-647)
- Fernet encryption: https://cryptography.io/en/latest/fernet/
- Key management best practices: https://www.owasp.org/index.php/Key_Management_Cheat_Sheet

## Acceptance Criteria

- [ ] Backup keyfile created automatically on key generation
- [ ] Backup location: `.keyfile.backup` in same directory
- [ ] Backup has 0600 permissions
- [ ] Recovery instructions created: `KEYFILE_RECOVERY.txt`
- [ ] Warning logged when key generated (mentions backup)
- [ ] `verify_backup_exists()` method checks backup matches primary
- [ ] `restore_from_backup()` method restores primary from backup
- [ ] CLI command: `inkwell config verify-keyfile` checks backup
- [ ] CLI command: `inkwell config restore-keyfile` restores from backup
- [ ] Test: New key generation creates backup ✓
- [ ] Test: Backup matches primary key ✓
- [ ] Test: Restore from backup works ✓
- [ ] Test: Missing backup detected by verify ✓
- [ ] All existing crypto tests still pass

## Work Log

### 2025-11-14 - Data Integrity Audit Discovery
**By:** Claude Code Review System (data-integrity-guardian agent)
**Actions:**
- Identified missing backup for encryption keyfile
- Analyzed catastrophic loss scenarios
- Classified as P2 IMPORTANT (data loss prevention)
- Recommended automatic backup with recovery docs

**Learnings:**
- Keyfile loss means permanent credential loss
- Users don't understand criticality until too late
- Automatic backup provides safety net
- Recovery documentation guides users through restoration

## Notes

**Why This Matters:**
- Encryption keyfile is single point of failure
- Loss of keyfile = loss of all encrypted credentials
- Feed credentials may be hard to recover (paid podcasts, complex auth)
- Users don't realize importance until disaster strikes
- Prevention is far better than recovery

**Impact of Keyfile Loss:**
```
Scenario: User has 15 authenticated feeds
Average time per feed: 5-10 minutes to find credentials and re-add
Total recovery time: 75-150 minutes (1.25-2.5 hours)

With backup: Recovery time < 1 minute
Savings: 1-2 hours of frustration
```

**User Education:**
```
When keyfile is created, show:

⚠️  IMPORTANT: Encryption Key Created

Your feed credentials are encrypted using a key stored at:
  ~/.config/inkwell/.keyfile

A backup has been created at:
  ~/.config/inkwell/.keyfile.backup

If you lose both files, your credentials cannot be recovered!

Recommended: Create an offsite backup now
  cp ~/.config/inkwell/.keyfile /path/to/secure/backup/
```

**Testing Strategy:**
```python
def test_keyfile_backup_created_on_generation(tmp_path):
    """Verify backup keyfile created with primary."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()

    encryptor = CredentialEncryptor(config_dir)

    # Trigger key generation
    _ = encryptor.encrypt("test")

    # Verify backup exists
    primary = config_dir / ".keyfile"
    backup = config_dir / ".keyfile.backup"
    recovery_doc = config_dir / "KEYFILE_RECOVERY.txt"

    assert primary.exists()
    assert backup.exists()
    assert recovery_doc.exists()

    # Verify backup matches primary
    assert primary.read_bytes() == backup.read_bytes()

    # Verify permissions
    assert oct(primary.stat().st_mode)[-3:] == "600"
    assert oct(backup.stat().st_mode)[-3:] == "600"

def test_restore_keyfile_from_backup(tmp_path):
    """Verify keyfile can be restored from backup."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()

    encryptor = CredentialEncryptor(config_dir)

    # Generate key and backup
    original_encrypted = encryptor.encrypt("test")

    # Delete primary keyfile (simulate loss)
    primary = config_dir / ".keyfile"
    primary.unlink()

    # Restore from backup
    assert encryptor.restore_from_backup()
    assert primary.exists()

    # Verify restored key works
    decrypted = encryptor.decrypt(original_encrypted)
    assert decrypted == "test"

def test_verify_backup_detects_mismatch(tmp_path):
    """Verify backup verification detects corrupted backup."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()

    encryptor = CredentialEncryptor(config_dir)
    _ = encryptor.encrypt("test")

    # Corrupt backup
    backup = config_dir / ".keyfile.backup"
    backup.write_bytes(b"corrupted-key-data")

    # Verify should detect mismatch
    assert not encryptor.verify_backup_exists()
```

**CLI Commands:**
```bash
# Check if backup exists and matches
$ inkwell config verify-keyfile
✅ Keyfile backup exists and matches primary
  Primary: ~/.config/inkwell/.keyfile
  Backup:  ~/.config/inkwell/.keyfile.backup

# Restore from backup
$ inkwell config restore-keyfile
⚠️  This will overwrite your current keyfile with the backup.
Continue? [y/N] y
✅ Keyfile restored from backup

# Show recovery instructions
$ cat ~/.config/inkwell/KEYFILE_RECOVERY.txt
[Recovery instructions displayed]
```

**Best Practices for Users:**
1. **Immediately after setup**: Create offsite backup
2. **Regular backups**: Include `.keyfile` in backup routine
3. **Cloud sync**: Add to Dropbox/iCloud (but encrypt separately)
4. **Password manager**: Some support file storage (1Password, etc.)
5. **USB backup**: Keep encrypted copy on USB drive

**Future Enhancements:**
- Add `--backup-keyfile` flag to CLI for manual backup
- Periodic backup verification in background
- Warn if backup is missing/mismatched
- Export/import keyfile with password protection

Source: Triage session on 2025-11-14
