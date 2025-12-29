---
title: ADR 004 - Credential Encryption Implementation
adr:
  author: Claude
  created: 06-Nov-2025
  status: accepted
---

# ADR-004: Credential Encryption Implementation

**Status**: Accepted
**Date**: 2025-11-06
**Deciders**: Claude (implementation), User (approval)
**Related**: [Devlog Days 1-3](../devlog/2025-11-06-days-1-3-implementation.md), [ADR-002](./002-phase-1-architecture.md)

## Context

Inkwell needs to store podcast feed credentials (usernames, passwords, bearer tokens) for private/paid feeds. These credentials must be stored persistently in the user's config directory, but storing them in plaintext poses a security risk.

### Requirements

1. **Persistent Storage**: Credentials must survive restarts
2. **User Convenience**: No manual encryption/decryption steps
3. **Security**: Credentials protected from casual file browsing
4. **Simplicity**: Easy to implement and maintain
5. **Cross-Platform**: Works on Linux and macOS

### Threat Model

**What we're protecting against:**
- Casual browsing of config files (e.g., accidentally sharing ~/.config)
- Accidental credential leaks in screenshots or logs
- Credentials committed to git repositories

**What we're NOT protecting against:**
- Root/admin access to the system
- Memory dumps of running processes
- Sophisticated attackers with system access

This is an **internal tool** used by developers on their own machines, not a production service handling third-party secrets.

## Decision

**We chose Fernet symmetric encryption** from the `cryptography` library.

Implementation details:
- Encryption key generated automatically on first use
- Key stored in `~/.config/inkwell/.keyfile` with 600 permissions
- Credentials encrypted before writing to `feeds.yaml`
- Credentials decrypted when loading from `feeds.yaml`
- Permission validation rejects world-readable key files

## Rationale

### Why Fernet?

1. **Simple API**
   ```python
   cipher = Fernet(key)
   encrypted = cipher.encrypt(plaintext.encode())
   decrypted = cipher.decrypt(encrypted).decode()
   ```

2. **Industry Standard**
   - Used by Django, Twisted, and other major projects
   - Part of the `cryptography` library (CNCF graduated project)
   - Spec: https://github.com/fernet/spec/

3. **Appropriate Security**
   - AES-128-CBC with HMAC-SHA256
   - Authenticated encryption (detects tampering)
   - Built-in timestamp (for future key rotation)

4. **No External Dependencies**
   - Already using `cryptography` for HTTPS verification
   - No additional system requirements
   - Pure Python with C extensions for speed

### Implementation Design

**CredentialEncryptor Class**:
```python
class CredentialEncryptor:
    def __init__(self, key_path: Path):
        self.key_path = key_path

    def encrypt(self, plaintext: str) -> str:
        # Returns base64-encoded ciphertext

    def decrypt(self, ciphertext: str) -> str:
        # Returns plaintext string
```

**ConfigManager Integration**:
- `save_feeds()`: Encrypts before writing YAML
- `load_feeds()`: Decrypts after reading YAML
- Transparent to rest of codebase

**Security Features**:
- Key file created with `chmod 600` (owner read/write only)
- Permission validation on every access
- Clear error if permissions too open
- Empty string handling (returns empty, doesn't encrypt nothing)

## Alternatives Considered

### 1. System Keyring (macOS Keychain, Secret Service API)

**Pros:**
- More secure (hardware-backed on modern systems)
- OS manages key lifecycle
- Better protection against file-level attacks

**Cons:**
- Platform-specific code required
- Additional dependency (`keyring` library)
- Headless/CI environments more complex
- Overkill for single-user dev tool

**Decision**: Defer to v0.2+ if users request it. Can be added as optional enhancement.

### 2. Plaintext Storage

**Pros:**
- Simplest implementation
- No encryption overhead
- Clear error messages (can see credentials in file)

**Cons:**
- Security risk (accidental leaks)
- Credentials visible in file browsers
- Bad practice for a tool handling auth

**Decision**: Rejected. Not appropriate for 2025 security standards, even for dev tools.

### 3. Environment Variables

**Pros:**
- Common pattern (12-factor app)
- No file storage needed
- Slightly more secure than plaintext files

**Cons:**
- Doesn't scale (many feeds = many env vars)
- Not persistent across shells
- Visible in `ps aux` and process listings
- Worse UX (manual setup per feed)

**Decision**: Rejected. Poor UX for multi-feed management.

### 4. GPG Encryption

**Pros:**
- Very secure
- Public-key cryptography
- Well-known tool

**Cons:**
- Requires GPG installation and setup
- Complex key management
- Overkill for this use case
- Poor UX (passphrase prompts)

**Decision**: Rejected. Symmetric encryption sufficient for threat model.

### 5. AES-GCM Directly

**Pros:**
- More control over implementation
- Slightly faster than Fernet

**Cons:**
- Easy to implement incorrectly
- Need to handle nonce generation, authentication tags
- No time-based validity (Fernet includes timestamp)
- More code = more bugs

**Decision**: Rejected. Fernet provides battle-tested wrapper around AES-GCM.

## Consequences

### Positive
- ✅ Credentials never stored in plaintext
- ✅ Automatic encryption (transparent to users)
- ✅ Simple implementation (~150 lines of code)
- ✅ Good balance of security and usability
- ✅ Comprehensive test coverage (13 tests)
- ✅ Clear error messages for permission issues

### Negative
- ❌ Key stored on disk (mitigated by file permissions)
- ❌ Not hardware-backed (acceptable for dev tool)
- ❌ Single encryption key for all feeds (simplifies implementation)

### Neutral
- Can add system keyring support in future without breaking changes
- Key rotation not yet implemented (marked as TODO)

## Security Properties

### What's Protected

**At Rest:**
```yaml
# feeds.yaml (simplified)
feeds:
  private-podcast:
    url: https://...
    auth:
      type: basic
      username: gAAAAABl9X...  # Encrypted
      password: gAAAAABl9Y...  # Encrypted
```

**In Memory:**
- Credentials decrypted only when needed
- Not persisted in global state
- Cleared after use (Python GC handles this)

**Key Storage:**
```bash
$ ls -l ~/.config/inkwell/.keyfile
-rw------- 1 user user 44 Nov 06 12:00 .keyfile
```

### What's NOT Protected

- **Memory dumps**: Decrypted credentials visible in RAM
- **Root access**: Admin can read any file
- **Debugger**: Attached debugger can read memory
- **OS keylogger**: Can capture credentials in use

This is **acceptable** because:
- Target audience: developers on trusted machines
- Threat model: casual exposure, not sophisticated attacks
- Alternative (system keyring) can be added later if needed

## Implementation Validation

### Test Coverage

13 tests verify:
- Encryption/decryption roundtrips correctly
- Empty strings handled properly
- Unicode and long strings work
- Key generation happens automatically
- Key file created with 600 permissions
- Insecure permissions rejected with clear error
- Invalid ciphertext raises proper exception
- Different keys produce different ciphertexts
- Key file reused across instances

### Manual Verification

```bash
# Encrypted credentials not visible
$ cat ~/.config/inkwell/feeds.yaml
feeds:
  test:
    auth:
      username: gAAAAABl9XQP5xS...  # ✓ Encrypted

# Key file properly secured
$ ls -l ~/.config/inkwell/.keyfile
-rw------- 1 user user 44 Nov 06  # ✓ Owner-only

# Permissions enforced
$ chmod 644 ~/.config/inkwell/.keyfile
$ inkwell list
Error: Key file has insecure permissions (0o644)
Run: chmod 600 ~/.config/inkwell/.keyfile  # ✓ Clear error
```

## Future Enhancements

**v0.2+ Possible Improvements:**

1. **System Keyring Integration**
   - Optional: Use OS keyring if available
   - Fallback to Fernet if not
   - Config option: `use_system_keyring: true`

2. **Key Rotation**
   - Implement `rotate_key()` method (currently NotImplementedError)
   - Decrypt with old key, encrypt with new key
   - Automatic rotation after N days

3. **Per-Feed Keys**
   - Each feed encrypted with unique key
   - Better isolation (one compromise doesn't expose all)
   - More complex key management

4. **Hardware Security Module Support**
   - For enterprise users
   - Unlikely needed for dev tool

## Migration Path

If we switch to system keyring in future:

```python
class ConfigManager:
    def __init__(self, use_keyring: bool = False):
        if use_keyring:
            self.encryptor = KeyringEncryptor()
        else:
            self.encryptor = CredentialEncryptor(self.key_file)
```

Both encryptors implement same interface:
```python
class EncryptorInterface:
    def encrypt(self, plaintext: str) -> str: ...
    def decrypt(self, ciphertext: str) -> str: ...
```

No breaking changes needed for existing feeds.

## Lessons Learned

1. **Simple is Better**: Fernet is perfect for this use case. Didn't need GPG or system keyring.

2. **Permission Validation Matters**: Easy to mess up file permissions. Validate early with helpful errors.

3. **Transparency is Key**: ConfigManager handles encrypt/decrypt automatically. Rest of codebase never sees ciphertext.

4. **Test Edge Cases**: Empty strings, Unicode, long strings all have tests. Caught bugs early.

5. **Document the Threat Model**: Clear about what we protect against (and what we don't) prevents scope creep.

## References

- [Fernet Specification](https://github.com/fernet/spec/blob/master/Spec.md)
- [Cryptography Library Docs](https://cryptography.io/en/latest/fernet/)
- [OWASP: Cryptographic Storage Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Cryptographic_Storage_Cheat_Sheet.html)
- [Python `stat` module](https://docs.python.org/3/library/stat.html) (for permission checking)
