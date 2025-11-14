---
status: done
priority: p2
issue_id: "039"
tags: [data-integrity, security, validation, config-manager]
dependencies: []
completed_at: 2025-11-14
---

# Add Validation for Decrypted Credentials

## Problem Statement

The ConfigManager decrypts feed credentials without validating that the decrypted values are valid strings or that decryption succeeded properly. Corrupted keyfiles or tampered credentials can cause runtime failures with cryptic error messages instead of clear validation errors.

**Severity**: IMPORTANT - Protects against keyfile corruption and provides better user experience.

## Findings

- Discovered during data integrity audit by data-integrity-guardian agent
- Location: `src/inkwell/config/manager.py:125-135`
- Issue: No validation that decrypted values are reasonable strings
- Risk: Cryptic runtime errors, poor user experience, time wasted debugging

**Error Scenario:**
1. User has 5 podcast feeds configured with encrypted credentials
2. `.keyfile` gets corrupted (disk error, bad backup restore, accidental edit)
3. User runs `inkwell fetch podcast-name`
4. ConfigManager loads feeds, decrypts credentials
5. Decryption returns garbage bytes: `b'\x89\xf3\x12\xab\x00\x00\xff...'` instead of "username"
6. Feed authentication fails with cryptic error: `TypeError: expected str, got bytes`
7. **Result:** User doesn't know keyfile is corrupted, wastes time debugging feed configuration instead of encryption

**Current Implementation:**
```python
# Decrypt credentials in feed configs
if "feeds" in data:
    for _feed_name, feed_data in data["feeds"].items():
        if "auth" in feed_data:
            auth = feed_data["auth"]
            if auth.get("username"):
                auth["username"] = self.encryptor.decrypt(auth["username"])
                # ⚠️ No validation that decrypted value is valid
            if auth.get("password"):
                auth["password"] = self.encryptor.decrypt(auth["password"])
                # ⚠️ No validation
            if auth.get("token"):
                auth["token"] = self.encryptor.decrypt(auth["token"])
                # ⚠️ No validation
```

**Why This Happens:**
- Fernet decryption doesn't validate plaintext format
- Corrupted keyfile can produce any bytes as output
- No sanity checks on decrypted values
- Generic exceptions don't help user understand root cause

**Real-World Corruption Scenarios:**
- Keyfile backed up as text, newlines added
- Keyfile manually edited (copy/paste error)
- Filesystem corruption (bad sector)
- Wrong keyfile restored from backup
- Keyfile from different installation

## Proposed Solutions

### Option 1: Validate Decrypted String Format (Recommended)

Add validation that decrypted values are reasonable strings:

```python
def load_feeds(self) -> Feeds:
    # ... load YAML

    # Decrypt credentials in feed configs
    if "feeds" in data:
        for feed_name, feed_data in data["feeds"].items():
            if "auth" in feed_data:
                auth = feed_data["auth"]

                try:
                    if auth.get("username"):
                        decrypted = self.encryptor.decrypt(auth["username"])
                        # Validate it's a reasonable string
                        if not decrypted or len(decrypted) > 255 or '\x00' in decrypted:
                            raise ValueError(f"Invalid username for feed '{feed_name}'")
                        auth["username"] = decrypted

                    if auth.get("password"):
                        decrypted = self.encryptor.decrypt(auth["password"])
                        if not decrypted or len(decrypted) > 255 or '\x00' in decrypted:
                            raise ValueError(f"Invalid password for feed '{feed_name}'")
                        auth["password"] = decrypted

                    if auth.get("token"):
                        decrypted = self.encryptor.decrypt(auth["token"])
                        if not decrypted or len(decrypted) > 1000 or '\x00' in decrypted:
                            raise ValueError(f"Invalid token for feed '{feed_name}'")
                        auth["token"] = decrypted

                except Exception as e:
                    raise InvalidConfigError(
                        f"Failed to decrypt credentials for feed '{feed_name}': {e}\n"
                        f"Your keyfile may be corrupted. Possible fixes:\n"
                        f"  1. Restore .keyfile from backup\n"
                        f"  2. Re-add the feed with correct credentials\n"
                        f"  3. Check keyfile permissions (should be 0600)"
                    ) from e

    # ... continue with Pydantic validation
```

**Validation Checks:**
- Not empty string
- Length reasonable (< 255 for username/password, < 1000 for tokens)
- No null bytes (indicates binary corruption)
- Printable ASCII/UTF-8 (credentials are typically ASCII)

**Pros**:
- Catches corrupted keyfiles early
- Provides clear, actionable error message
- Helps user identify root cause immediately
- Minimal performance overhead

**Cons**:
- Heuristic checks may reject valid edge cases
- Length limits need to be reasonable

**Effort**: Small (1 hour)
**Risk**: Low

### Option 2: Add Checksum to Encrypted Values

Store checksum with encrypted data to detect tampering:

```python
def _encrypt_with_checksum(self, value: str) -> str:
    import hashlib
    checksum = hashlib.sha256(value.encode()).hexdigest()[:8]
    payload = f"{checksum}:{value}"
    return self.encryptor.encrypt(payload)

def _decrypt_with_checksum(self, encrypted: str) -> str:
    decrypted = self.encryptor.decrypt(encrypted)
    if ":" not in decrypted:
        raise ValueError("Missing checksum in encrypted value")

    stored_checksum, value = decrypted.split(":", 1)
    calculated_checksum = hashlib.sha256(value.encode()).hexdigest()[:8]

    if stored_checksum != calculated_checksum:
        raise ValueError("Checksum mismatch - data corrupted")

    return value
```

**Pros**:
- Cryptographically verifies integrity
- Detects any corruption or tampering

**Cons**:
- Breaks existing encrypted credentials (requires re-encryption)
- More complex implementation
- Migration needed for existing users

**Effort**: Medium (2-3 hours)
**Risk**: Medium (requires migration)

### Option 3: Catch Specific Decryption Errors

Handle Fernet decryption errors specifically:

```python
from cryptography.fernet import InvalidToken

try:
    if auth.get("username"):
        auth["username"] = self.encryptor.decrypt(auth["username"])
except InvalidToken:
    raise InvalidConfigError(
        f"Failed to decrypt credentials for feed '{feed_name}'.\n"
        f"This usually means your .keyfile is corrupted or incorrect."
    )
```

**Pros**:
- Simple implementation
- Catches most common errors

**Cons**:
- Doesn't catch all corruption scenarios
- Doesn't validate output format
- Less comprehensive than Option 1

**Effort**: Small (30 minutes)
**Risk**: Low

## Recommended Action

**Implement Option 1: Validate Decrypted String Format**

This provides comprehensive protection with clear error messages. Option 3 can be combined as a first line of defense.

**Priority**: P2 IMPORTANT - Improves user experience and prevents time wasted debugging

## Technical Details

**Affected Files:**
- `src/inkwell/config/manager.py:125-135` (load_feeds method)
- `src/inkwell/config/crypto.py` (may need decrypt validation)
- `tests/unit/config/test_manager.py` (add corruption tests)

**Related Components:**
- `src/inkwell/config/crypto.py` (CredentialEncryptor)
- `src/inkwell/utils/errors.py` (InvalidConfigError)

**Database Changes**: No

**Validation Rules:**
```python
def _validate_decrypted_credential(value: str, field_name: str, max_length: int = 255) -> None:
    """Validate decrypted credential format."""
    if not value:
        raise ValueError(f"{field_name} is empty after decryption")

    if len(value) > max_length:
        raise ValueError(f"{field_name} exceeds maximum length ({max_length})")

    if '\x00' in value:
        raise ValueError(f"{field_name} contains null bytes (likely corruption)")

    # Optional: Check if printable
    if not value.isprintable():
        raise ValueError(f"{field_name} contains non-printable characters")
```

## Resources

- Original finding: DATA_INTEGRITY_REPORT.md (P2.2, lines 282-333)
- Fernet documentation: https://cryptography.io/en/latest/fernet/
- Related: CredentialEncryptor in crypto.py

## Acceptance Criteria

- [ ] Decrypted usernames validated (not empty, < 255 chars, no null bytes)
- [ ] Decrypted passwords validated (not empty, < 255 chars, no null bytes)
- [ ] Decrypted tokens validated (not empty, < 1000 chars, no null bytes)
- [ ] Clear error message when validation fails
- [ ] Error message suggests keyfile corruption as likely cause
- [ ] Error message provides recovery steps
- [ ] Test: Corrupted keyfile → clear InvalidConfigError
- [ ] Test: Valid credentials → decryption succeeds
- [ ] Test: Empty decrypted value → validation error
- [ ] Test: Null bytes in decrypted value → validation error
- [ ] All existing config tests still pass

## Work Log

### 2025-11-14 - Data Integrity Audit Discovery
**By:** Claude Code Review System (data-integrity-guardian agent)
**Actions:**
- Identified missing validation on decrypted credentials
- Analyzed corruption scenarios and error handling
- Classified as P2 IMPORTANT (user experience improvement)
- Recommended string format validation approach

**Learnings:**
- Decryption doesn't guarantee valid output format
- Corrupted keyfiles produce random bytes as output
- Clear error messages save users hours of debugging
- Early validation prevents cryptic downstream errors

### 2025-11-14 - Implementation Complete
**By:** Claude Code (resolution specialist)
**Actions:**
- Added `_validate_decrypted_credential()` helper method to ConfigManager
- Updated `load_feeds()` to validate all decrypted credentials
- Implemented validation checks: empty strings, null bytes, length limits
- Added clear error messages pointing to keyfile corruption
- Created comprehensive test suite (7 new tests)
- All tests passing (28/28 in test_config_manager.py)

**Changes Made:**
- `src/inkwell/config/manager.py`:
  - Added `_validate_decrypted_credential()` method (lines 150-175)
  - Updated `load_feeds()` with validation logic (lines 177-250)
  - Validates username/password (max 255 chars), tokens (max 1000 chars)
  - Checks for empty strings and null bytes
  - Wraps all decryption errors with helpful recovery steps
- `tests/unit/test_config_manager.py`:
  - Added 7 new tests for credential validation
  - Tests cover: empty values, null bytes, oversized values, corrupted keyfile
  - Tests verify error messages include recovery steps

**Validation Rules Implemented:**
- Username/password: not empty, max 255 chars, no null bytes
- Tokens: not empty, max 1000 chars, no null bytes
- Clear error messages with feed name and recovery steps
- Re-raise InvalidConfigError to preserve error context

**Test Coverage:**
- Empty decrypted username -> InvalidConfigError
- Null bytes in password -> InvalidConfigError with "null bytes" message
- Oversized token (>1000 chars) -> InvalidConfigError with "exceeds maximum length"
- Corrupted keyfile -> InvalidConfigError with recovery steps
- Valid credentials -> successful decryption
- Username length limit enforced (>255 chars rejected)
- Error messages include all recovery steps

**Status:** RESOLVED - All acceptance criteria met

## Notes

**Why This Matters:**
- Keyfile corruption is a realistic scenario (backups, manual edits, disk errors)
- Users expect clear error messages when something is wrong
- Current cryptic errors blame wrong component (feed auth vs keyfile)
- Better validation reduces support burden and user frustration

**Common Keyfile Corruption Scenarios:**
```
Good keyfile:
b'4K3mR9X_7Qp2WnV8BxY...'

Corrupted (newline added):
b'4K3mR9X_7Qp2WnV8BxY...\n'

Corrupted (truncated):
b'4K3mR9X_7Qp2W'

Wrong keyfile (different installation):
b'9ZaP3vN_1Lm5XbC7TyU...'
```

**Error Message Design:**
```
Before:
TypeError: expected str, got bytes

After:
InvalidConfigError: Failed to decrypt credentials for feed 'my-podcast': Invalid username for feed 'my-podcast'
Your keyfile may be corrupted. Possible fixes:
  1. Restore .keyfile from backup
  2. Re-add the feed with correct credentials
  3. Check keyfile permissions (should be 0600)
```

**Testing Strategy:**
```python
def test_load_feeds_with_corrupted_keyfile(tmp_path):
    """Verify clear error when keyfile is corrupted."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()

    # Create feeds.yaml with encrypted credentials
    # Corrupt the keyfile
    keyfile = config_dir / ".keyfile"
    keyfile.write_text("corrupted-keyfile-data")

    manager = ConfigManager(config_dir)

    with pytest.raises(InvalidConfigError) as exc_info:
        manager.load_feeds()

    assert "keyfile may be corrupted" in str(exc_info.value).lower()
    assert "Possible fixes" in str(exc_info.value)

def test_load_feeds_with_null_bytes_in_decrypted(mocker):
    """Verify validation catches null bytes."""
    manager = ConfigManager()

    # Mock decryptor to return garbage
    mocker.patch.object(
        manager.encryptor,
        'decrypt',
        return_value="username\x00\xff\xfe"
    )

    with pytest.raises(InvalidConfigError) as exc_info:
        manager.load_feeds()

    assert "null bytes" in str(exc_info.value).lower()
```

**Implementation Notes:**
- Use `str.isprintable()` for additional validation
- Length limits should be generous (avoid false positives)
- Log successful decryption at DEBUG level for troubleshooting
- Consider adding `--verify-keyfile` CLI command for diagnostics

Source: Triage session on 2025-11-14
