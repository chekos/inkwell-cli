# Data Integrity Report: Inkwell CLI

**Date:** 2025-11-14
**Reviewer:** Data Integrity Guardian
**Scope:** Configuration, feeds, caches, sessions, output files, metadata, cost tracking

---

## Executive Summary

The Inkwell CLI demonstrates **strong foundational data integrity practices** with comprehensive atomic write operations, file locking, backup mechanisms, and timezone-aware datetime handling. However, there are **critical data loss risks** in concurrent access scenarios and several important areas requiring improvement.

**Overall Risk Level:** MEDIUM
**Critical Issues:** 3 (P1)
**Important Issues:** 8 (P2)
**Best Practices:** 6 (P3)

---

## Critical Data Integrity Risks (P1)

### P1.1: Race Condition in Config/Feed Updates

**Location:** `/Users/sergio/projects/inkwell-cli/src/inkwell/config/manager.py`
**Lines:** 187-203, 205-221, 223-238

**Risk:** Read-modify-write race condition causing data loss during concurrent operations.

**Issue:**
```python
def add_feed(self, name: str, feed_config: FeedConfig) -> None:
    feeds = self.load_feeds()  # Read

    if name in feeds.feeds:
        raise DuplicateFeedError(...)

    feeds.feeds[name] = feed_config  # Modify
    self.save_feeds(feeds)  # Write
```

**Scenario for Data Loss:**
1. Process A calls `add_feed("feed1", config1)` → loads current feeds
2. Process B calls `add_feed("feed2", config2)` → loads current feeds
3. Process A writes feed1
4. Process B writes feed2, **overwriting feed1** (last-write-wins)

**Impact:** Loss of feed configurations in multi-process environments (e.g., parallel episode processing).

**Remediation:**
```python
# Option 1: File locking (similar to costs.py approach)
def add_feed(self, name: str, feed_config: FeedConfig) -> None:
    with self._lock_feeds_file():
        feeds = self.load_feeds()
        if name in feeds.feeds:
            raise DuplicateFeedError(...)
        feeds.feeds[name] = feed_config
        self._save_feeds_unlocked(feeds)

# Option 2: Read-after-write verification
def add_feed(self, name: str, feed_config: FeedConfig) -> None:
    max_retries = 3
    for attempt in range(max_retries):
        feeds = self.load_feeds()
        if name in feeds.feeds:
            raise DuplicateFeedError(...)
        feeds.feeds[name] = feed_config
        self.save_feeds(feeds)

        # Verify write succeeded
        reloaded = self.load_feeds()
        if name in reloaded.feeds:
            return

        if attempt < max_retries - 1:
            time.sleep(0.1)
        else:
            raise RuntimeError(f"Failed to add feed after {max_retries} attempts")
```

**Priority:** CRITICAL - This affects the core configuration system.

---

### P1.2: Missing File Locking in Session Manager

**Location:** `/Users/sergio/projects/inkwell-cli/src/inkwell/interview/session_manager.py`
**Lines:** 82-119, 269-307

**Risk:** Concurrent session modifications can corrupt or lose interview data.

**Issue:**
The `save_session()` and `cleanup_old_sessions()` methods use atomic writes but lack file locking. This can cause:

1. **Lost updates:** Two processes modifying same session simultaneously
2. **Partial cleanup:** Cleanup deleting sessions being actively modified
3. **Corrupted state:** Race between status updates

**Example Corruption Scenario:**
```python
# Process A: User responding to question
session.add_exchange(question, response)
manager.save_session(session)  # Writing...

# Process B: Auto-abandon timeout
for session_file in self.session_dir.glob("session-*.json"):
    session = load_session(...)  # Reads partially written data
    if self.detect_timeout(session):
        session.abandon()
        self.save_session(session)  # Overwrites with corrupt data
```

**Remediation:**
```python
class SessionManager:
    def __init__(self, session_dir: Path | None = None):
        # Add per-session lock directory
        self.session_dir = session_dir or self._get_default_session_dir()
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
```

**Priority:** CRITICAL - Interview sessions contain valuable user reflections that cannot be recovered if lost.

---

### P1.3: No Recovery Mechanism for Failed Atomic Writes

**Location:** `/Users/sergio/projects/inkwell-cli/src/inkwell/output/manager.py`
**Lines:** 194-205

**Risk:** Directory backup not restored on write failure, causing data loss.

**Issue:**
```python
# Create backup before deletion
backup_dir = episode_dir.with_suffix('.backup')
if backup_dir.exists():
    shutil.rmtree(backup_dir)  # Deletes old backup
episode_dir.rename(backup_dir)    # Moves current to backup

try:
    episode_dir.mkdir(parents=True)
except Exception:
    # Restore backup on failure
    if backup_dir.exists() and not episode_dir.exists():
        backup_dir.rename(episode_dir)
    raise
```

**Problem:** If `episode_dir.mkdir()` succeeds but subsequent file writes fail, the backup is never restored and remains orphaned.

**Corruption Scenario:**
1. User runs `--overwrite` on existing episode
2. Backup created: `episode-2025-11-14-title.backup`
3. New directory created successfully
4. First markdown write fails (disk full, permissions, etc.)
5. Exception raised, user sees error
6. **Result:** Backup exists but not restored, original data still lost

**Remediation:**
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
            # ... write files
            pass

        # Write metadata file
        metadata_file = episode_dir / ".metadata.yaml"
        self._write_metadata(metadata_file, episode_metadata)

        # Success - remove backup
        if backup_dir and backup_dir.exists():
            shutil.rmtree(backup_dir)

        return EpisodeOutput(...)

    except Exception:
        # Restore backup on ANY failure
        if backup_dir and backup_dir.exists() and episode_dir:
            if episode_dir.exists():
                shutil.rmtree(episode_dir)
            backup_dir.rename(episode_dir)
        raise
```

**Priority:** CRITICAL - User data loss during overwrites is unacceptable.

---

## Important Improvements (P2)

### P2.1: Cache Corruption Not Detected During Reads

**Location:** `/Users/sergio/projects/inkwell-cli/src/inkwell/extraction/cache.py`
**Lines:** 65-82

**Risk:** Silent data corruption if cache file written by another process during read.

**Issue:**
```python
async def get(self, template_name: str, template_version: str, transcript: str) -> str | None:
    cache_file = self.cache_dir / f"{cache_key}.json"

    if not cache_file.exists():
        return None

    try:
        async with aiofiles.open(cache_file, "r") as f:
            content = await f.read()
            data = json.loads(content)  # May be mid-write from another process
```

**Issue:** No verification that the entire file was written before reading. If another process is writing, partial JSON is read.

**Remediation:**
```python
async def get(self, template_name: str, template_version: str, transcript: str) -> str | None:
    cache_file = self.cache_dir / f"{cache_key}.json"

    if not cache_file.exists():
        return None

    try:
        # Check for temp file existence (indicates active write)
        temp_file = cache_file.with_suffix(".tmp")
        if temp_file.exists():
            # Another process is writing, treat as cache miss
            return None

        async with aiofiles.open(cache_file, "r") as f:
            content = await f.read()

            # Verify JSON is complete (simple sanity check)
            if not content.strip().endswith("}"):
                # Partial write detected
                await self._delete_file(cache_file)
                return None

            data = json.loads(content)
```

**Priority:** IMPORTANT - Cache corruption leads to redundant API calls and wasted costs.

---

### P2.2: Missing Data Validation on Deserialization

**Location:** `/Users/sergio/projects/inkwell-cli/src/inkwell/config/manager.py`
**Lines:** 125-135

**Risk:** Encrypted credentials may be corrupted or tampered with, causing runtime failures.

**Issue:**
```python
# Decrypt credentials in feed configs
if "feeds" in data:
    for _feed_name, feed_data in data["feeds"].items():
        if "auth" in feed_data:
            auth = feed_data["auth"]
            if auth.get("username"):
                auth["username"] = self.encryptor.decrypt(auth["username"])
            # ... decrypt password, token
```

**Problem:** No validation that decrypted values are valid strings or that decryption succeeded properly.

**Remediation:**
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

                except Exception as e:
                    raise InvalidConfigError(
                        f"Failed to decrypt credentials for feed '{feed_name}': {e}\n"
                        f"Your keyfile may be corrupted. Consider re-adding the feed."
                    ) from e
```

**Priority:** IMPORTANT - Protects against keyfile corruption and credential tampering.

---

### P2.3: Metadata YAML Lacks Schema Versioning

**Location:** `/Users/sergio/projects/inkwell-cli/src/inkwell/output/manager.py`
**Lines:** 273-286

**Risk:** Future schema changes will break ability to read old episode metadata.

**Issue:**
```python
def _write_metadata(self, metadata_file: Path, episode_metadata: EpisodeMetadata) -> None:
    metadata_dict = episode_metadata.model_dump()
    content = yaml.dump(metadata_dict, default_flow_style=False, sort_keys=False)
    self._write_file_atomic(metadata_file, content)
```

**Problem:** No version field in metadata. If `EpisodeMetadata` schema changes (add/remove fields, rename), old files become unreadable.

**Remediation:**
```python
# In output/models.py
class EpisodeMetadata(BaseModel):
    # Add schema version
    schema_version: int = Field(
        default=1,
        description="Metadata schema version for migration support"
    )

    # Existing fields...
    podcast_name: str = Field(...)
    episode_title: str = Field(...)
    # ...

# In output/manager.py
def load_episode_metadata(self, episode_dir: Path) -> EpisodeMetadata:
    metadata_file = episode_dir / ".metadata.yaml"

    if not metadata_file.exists():
        raise FileNotFoundError(f"Metadata file not found: {metadata_file}")

    with metadata_file.open("r") as f:
        data = yaml.safe_load(f)

    # Handle schema migrations
    schema_version = data.get("schema_version", 0)

    if schema_version == 0:
        # Migrate v0 -> v1
        data = self._migrate_metadata_v0_to_v1(data)

    if schema_version > 1:
        logger.warning(
            f"Metadata schema version {schema_version} is newer than supported (1). "
            f"Some fields may be missing."
        )

    return EpisodeMetadata(**data)
```

**Priority:** IMPORTANT - Essential for long-term data migration and backward compatibility.

---

### P2.4: Session Cleanup Lacks Transaction Boundary

**Location:** `/Users/sergio/projects/inkwell-cli/src/inkwell/interview/session_manager.py`
**Lines:** 269-307

**Risk:** Partial cleanup leaves inconsistent state if process crashes mid-cleanup.

**Issue:**
```python
def cleanup_old_sessions(self, days: int = 30) -> int:
    cutoff_date = now_utc() - timedelta(days=days)
    deleted = 0

    for session_file in self.session_dir.glob("session-*.json"):
        try:
            # ... load and check
            if updated_at < cutoff_date:
                session_file.unlink()  # DELETE - no rollback
                deleted += 1
        except:
            continue  # Skip, but already deleted some

    return deleted
```

**Problem:** If process crashes after deleting 5 of 10 sessions, the remaining 5 are orphaned in next cleanup cycle.

**Remediation:**
```python
def cleanup_old_sessions(self, days: int = 30) -> int:
    cutoff_date = now_utc() - timedelta(days=days)

    # Phase 1: Identify sessions to delete (read-only)
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
            continue

    # Phase 2: Mark for deletion (create .deleting marker)
    marked = []
    for session_file in sessions_to_delete:
        marker = session_file.with_suffix(".deleting")
        try:
            marker.touch()
            marked.append((session_file, marker))
        except Exception:
            continue

    # Phase 3: Actual deletion
    deleted = 0
    for session_file, marker in marked:
        try:
            session_file.unlink()
            marker.unlink(missing_ok=True)
            deleted += 1
        except Exception as e:
            logger.warning(f"Failed to delete {session_file}: {e}")
            # Leave marker for next cleanup

    return deleted
```

**Priority:** IMPORTANT - Prevents orphaned sessions and cleanup inconsistencies.

---

### P2.5: No Integrity Checks for YAML Files

**Location:** All YAML write operations (config, feeds, metadata)

**Risk:** Silent YAML corruption from filesystem errors, improper encoding, or bugs.

**Issue:** YAML files written with no checksum or integrity verification.

**Remediation:**
```python
# Add to output/manager.py and config/manager.py
import hashlib

def _write_yaml_with_checksum(self, file_path: Path, data: dict) -> None:
    """Write YAML with embedded checksum for integrity verification."""
    # Generate YAML content
    yaml_content = yaml.dump(data, default_flow_style=False, sort_keys=False)

    # Calculate checksum
    checksum = hashlib.sha256(yaml_content.encode('utf-8')).hexdigest()

    # Add checksum as comment at end
    final_content = f"{yaml_content}\n# checksum: {checksum}\n"

    # Write atomically
    self._write_file_atomic(file_path, final_content)

def _read_yaml_with_verification(self, file_path: Path) -> dict:
    """Read YAML and verify checksum."""
    content = file_path.read_text(encoding='utf-8')

    # Extract checksum
    if "# checksum: " in content:
        main_content, checksum_line = content.rsplit("# checksum: ", 1)
        expected_checksum = checksum_line.strip()

        # Recalculate checksum
        actual_checksum = hashlib.sha256(main_content.encode('utf-8')).hexdigest()

        if actual_checksum != expected_checksum:
            raise ValueError(
                f"YAML file {file_path} failed integrity check. "
                f"File may be corrupted."
            )

        content = main_content

    return yaml.safe_load(content)
```

**Priority:** IMPORTANT - Detects corruption early before it causes data loss.

---

### P2.6: Missing Transaction Log for Config Changes

**Location:** `/Users/sergio/projects/inkwell-cli/src/inkwell/config/manager.py`

**Risk:** No audit trail for configuration changes; impossible to debug who/what/when a feed was added/removed.

**Issue:** Config changes are immediate with no history.

**Remediation:**
```python
# Add to config/manager.py
class ConfigManager:
    def __init__(self, config_dir: Path | None = None) -> None:
        # ... existing init
        self.audit_log = self.config_dir / "audit.log"

    def _log_change(self, operation: str, details: dict) -> None:
        """Append change to audit log."""
        log_entry = {
            "timestamp": now_utc().isoformat(),
            "operation": operation,
            "details": details,
            "user": os.getenv("USER", "unknown"),
            "pid": os.getpid(),
        }

        with open(self.audit_log, "a") as f:
            f.write(json.dumps(log_entry) + "\n")

    def add_feed(self, name: str, feed_config: FeedConfig) -> None:
        feeds = self.load_feeds()

        if name in feeds.feeds:
            raise DuplicateFeedError(...)

        feeds.feeds[name] = feed_config
        self.save_feeds(feeds)

        # Log the change
        self._log_change("add_feed", {
            "feed_name": name,
            "url": str(feed_config.url),
            "auth_type": feed_config.auth.type,
        })
```

**Priority:** IMPORTANT - Essential for troubleshooting and compliance.

---

### P2.7: Encryption Key Not Backed Up

**Location:** `/Users/sergio/projects/inkwell-cli/src/inkwell/config/crypto.py`
**Lines:** 40-52

**Risk:** Loss of keyfile means permanent loss of all encrypted credentials.

**Issue:**
```python
# Generate new key
key = Fernet.generate_key()
self.key_path.write_bytes(key)
self.key_path.chmod(0o600)
```

**Problem:** No backup or recovery mechanism. If `.keyfile` is deleted, all feed credentials are permanently lost.

**Remediation:**
```python
class CredentialEncryptor:
    def _ensure_key(self) -> bytes:
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

        # Create backup with additional security warning
        backup_path = self.key_path.parent / ".keyfile.backup"
        backup_path.write_bytes(key)
        backup_path.chmod(0o600)

        # Create recovery instructions
        recovery_doc = self.key_path.parent / "KEYFILE_RECOVERY.txt"
        recovery_doc.write_text(
            f"ENCRYPTION KEY BACKUP\n"
            f"====================\n\n"
            f"Your encryption key is stored at:\n"
            f"  Primary: {self.key_path}\n"
            f"  Backup:  {backup_path}\n\n"
            f"IMPORTANT: If you lose both files, all encrypted feed credentials\n"
            f"will be permanently unrecoverable. Back up these files securely!\n\n"
            f"To restore:\n"
            f"  cp {backup_path} {self.key_path}\n"
            f"  chmod 600 {self.key_path}\n"
        )
        recovery_doc.chmod(0o600)

        logger.warning(
            f"Created new encryption key at {self.key_path}. "
            f"A backup has been created. See {recovery_doc} for recovery instructions."
        )

        return key
```

**Priority:** IMPORTANT - Data loss prevention for encrypted credentials.

---

### P2.8: Cost Tracker Merge Logic May Lose Precision

**Location:** `/Users/sergio/projects/inkwell-cli/src/inkwell/utils/costs.py`
**Lines:** 329-353

**Risk:** Duplicate detection key too permissive, may miss legitimate entries.

**Issue:**
```python
existing_keys = {
    (
        u.timestamp.isoformat(),
        u.operation,
        u.provider,
        u.episode_title,
        u.input_tokens,  # Same input tokens could happen twice!
    )
    for u in existing
}
```

**Problem:** If same episode is processed twice with identical input tokens, second entry is dropped.

**Scenario:**
1. Process episode, extraction costs $0.05
2. User runs `--overwrite` on same episode
3. Extraction runs again with identical token counts
4. Cost tracker sees duplicate key, doesn't record second $0.05
5. **Result:** User underbilled, analytics incorrect

**Remediation:**
```python
# Use UUID for each usage record
class APIUsage(BaseModel):
    usage_id: str = Field(default_factory=lambda: str(uuid4()))
    # ... other fields

# In _save():
existing_keys = {u.usage_id for u in existing}
new_entries = [u for u in self.usage_history if u.usage_id not in existing_keys]
```

**Priority:** IMPORTANT - Cost tracking accuracy affects billing and analytics.

---

## Best Practice Suggestions (P3)

### P3.1: Add Write-Ahead Logging (WAL) for Critical Operations

**Location:** Config and session managers

**Suggestion:** Implement WAL pattern for multi-step operations.

**Example:**
```python
class ConfigManager:
    def add_feed_with_wal(self, name: str, feed_config: FeedConfig) -> None:
        # Write intent to WAL
        wal_entry = {
            "operation": "add_feed",
            "name": name,
            "config": feed_config.model_dump(),
            "timestamp": now_utc().isoformat(),
        }

        wal_file = self.config_dir / ".wal" / f"{uuid4()}.json"
        wal_file.parent.mkdir(exist_ok=True)
        wal_file.write_text(json.dumps(wal_entry))

        try:
            # Perform actual operation
            feeds = self.load_feeds()
            if name in feeds.feeds:
                raise DuplicateFeedError(...)
            feeds.feeds[name] = feed_config
            self.save_feeds(feeds)

            # Success - remove WAL entry
            wal_file.unlink()

        except Exception:
            # WAL entry remains for recovery
            raise

    def recover_from_wal(self) -> int:
        """Recover incomplete operations from WAL."""
        wal_dir = self.config_dir / ".wal"
        if not wal_dir.exists():
            return 0

        recovered = 0
        for wal_file in wal_dir.glob("*.json"):
            try:
                with open(wal_file) as f:
                    entry = json.load(f)

                # Replay operation
                if entry["operation"] == "add_feed":
                    # ... replay add_feed
                    pass

                wal_file.unlink()
                recovered += 1

            except Exception as e:
                logger.error(f"Failed to recover WAL entry {wal_file}: {e}")

        return recovered
```

**Priority:** BEST PRACTICE - Ensures no partial operations remain after crash.

---

### P3.2: Implement Data Retention Policies

**Location:** All cache and session managers

**Suggestion:** Add configurable retention with automatic cleanup.

**Example:**
```python
# In config/schema.py
class DataRetentionConfig(BaseModel):
    transcription_cache_days: int = 90
    extraction_cache_days: int = 90
    completed_session_days: int = 30
    abandoned_session_days: int = 7
    cost_history_days: int = 365
    enable_auto_cleanup: bool = True

class GlobalConfig(BaseModel):
    # ... existing fields
    data_retention: DataRetentionConfig = Field(default_factory=DataRetentionConfig)

# Schedule cleanup on startup or via cron
def auto_cleanup_all_caches():
    config = ConfigManager().load_config()
    retention = config.data_retention

    if not retention.enable_auto_cleanup:
        return

    # Cleanup transcription cache
    TranscriptCache(ttl_days=retention.transcription_cache_days).clear_expired()

    # Cleanup extraction cache
    ExtractionCache(ttl_days=retention.extraction_cache_days).clear_expired()

    # Cleanup sessions
    SessionManager().cleanup_old_sessions(days=retention.completed_session_days)
```

**Priority:** BEST PRACTICE - Prevents unbounded disk usage and maintains data hygiene.

---

### P3.3: Add Data Export/Import for Migration

**Location:** All managers (config, sessions, costs)

**Suggestion:** Provide export/import functionality for backups and migrations.

**Example:**
```python
# In config/manager.py
def export_all_data(self, export_dir: Path) -> dict[str, Path]:
    """Export all configuration and data to directory."""
    export_dir.mkdir(parents=True, exist_ok=True)

    exported = {}

    # Export config
    config = self.load_config()
    config_export = export_dir / "config.yaml"
    config_export.write_text(yaml.dump(config.model_dump()))
    exported["config"] = config_export

    # Export feeds (with encrypted credentials)
    feeds = self.load_feeds()
    feeds_export = export_dir / "feeds.yaml"
    feeds_export.write_text(yaml.dump(feeds.model_dump()))
    exported["feeds"] = feeds_export

    # Export keyfile (CRITICAL)
    if self.key_file.exists():
        keyfile_export = export_dir / ".keyfile"
        shutil.copy2(self.key_file, keyfile_export)
        exported["keyfile"] = keyfile_export

    # Export costs
    costs_file = self.config_dir / "costs.json"
    if costs_file.exists():
        costs_export = export_dir / "costs.json"
        shutil.copy2(costs_file, costs_export)
        exported["costs"] = costs_export

    # Create manifest
    manifest = {
        "export_date": now_utc().isoformat(),
        "version": "1.0",
        "files": {k: str(v) for k, v in exported.items()},
    }

    manifest_file = export_dir / "manifest.json"
    manifest_file.write_text(json.dumps(manifest, indent=2))

    return exported
```

**Priority:** BEST PRACTICE - Essential for user data portability and disaster recovery.

---

### P3.4: Add Health Checks for Data Integrity

**Location:** New module: `utils/health.py`

**Suggestion:** Periodic health checks to detect corruption early.

**Example:**
```python
class DataIntegrityChecker:
    """Perform health checks on all data stores."""

    def check_all(self) -> dict[str, Any]:
        """Run all integrity checks."""
        results = {
            "timestamp": now_utc().isoformat(),
            "checks": {},
        }

        results["checks"]["config"] = self._check_config_integrity()
        results["checks"]["feeds"] = self._check_feeds_integrity()
        results["checks"]["caches"] = self._check_cache_integrity()
        results["checks"]["sessions"] = self._check_session_integrity()
        results["checks"]["costs"] = self._check_costs_integrity()

        # Overall status
        all_passed = all(c["status"] == "ok" for c in results["checks"].values())
        results["overall_status"] = "ok" if all_passed else "degraded"

        return results

    def _check_config_integrity(self) -> dict[str, Any]:
        """Check config files are valid and loadable."""
        try:
            manager = ConfigManager()
            config = manager.load_config()
            feeds = manager.load_feeds()

            return {
                "status": "ok",
                "config_valid": True,
                "feeds_count": len(feeds.feeds),
            }

        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
            }

    # ... similar checks for other data stores
```

**Priority:** BEST PRACTICE - Proactive corruption detection.

---

### P3.5: Implement Structured Logging for Data Operations

**Location:** All file write operations

**Suggestion:** Log all data mutations with structured metadata.

**Example:**
```python
import structlog

logger = structlog.get_logger()

class ConfigManager:
    def save_feeds(self, feeds: Feeds) -> None:
        logger.info(
            "saving_feeds",
            feed_count=len(feeds.feeds),
            file_path=str(self.feeds_file),
            file_size_before=self.feeds_file.stat().st_size if self.feeds_file.exists() else 0,
        )

        # ... perform save

        logger.info(
            "feeds_saved",
            file_size_after=self.feeds_file.stat().st_size,
            operation_duration_ms=...,
        )
```

**Benefits:**
- Easy correlation of errors with specific operations
- Performance monitoring (file write times)
- Audit trail with searchable metadata

**Priority:** BEST PRACTICE - Essential for production debugging.

---

### P3.6: Add Rate Limiting for File Operations

**Location:** Output manager and cache managers

**Suggestion:** Prevent filesystem exhaustion from runaway processes.

**Example:**
```python
from inkwell.utils.rate_limiter import RateLimiter

class OutputManager:
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        # Limit to 10 episode writes per minute
        self.write_limiter = RateLimiter(max_calls=10, period_seconds=60)

    def write_episode(self, ...) -> EpisodeOutput:
        # Acquire rate limit token
        if not self.write_limiter.acquire(blocking=False):
            raise RuntimeError(
                "Episode write rate limit exceeded (10/minute). "
                "This may indicate a runaway process."
            )

        # ... perform write
```

**Priority:** BEST PRACTICE - Protects against filesystem exhaustion bugs.

---

## Summary of Findings

### Critical Issues Requiring Immediate Action

1. **P1.1: Race conditions in config/feed updates** - Add file locking
2. **P1.2: Missing file locking in session manager** - Add per-session locks
3. **P1.3: No recovery for failed atomic writes** - Implement proper rollback

### Data Loss Prevention Priorities

1. Implement file locking in `ConfigManager` and `SessionManager`
2. Add backup restoration logic in `OutputManager.write_episode()`
3. Add schema versioning to `EpisodeMetadata`
4. Implement WAL pattern for critical multi-step operations
5. Create backup mechanism for encryption keyfile

### Recommended Implementation Order

**Week 1 (Critical):**
- P1.1: File locking in ConfigManager
- P1.2: File locking in SessionManager
- P1.3: Proper rollback in OutputManager

**Week 2 (Important):**
- P2.1: Cache corruption detection
- P2.3: Metadata schema versioning
- P2.7: Keyfile backup mechanism

**Week 3 (Important + Best Practices):**
- P2.2: Credential validation on decrypt
- P2.4: Transactional session cleanup
- P3.1: Write-Ahead Logging implementation

**Week 4 (Best Practices):**
- P3.2: Data retention policies
- P3.3: Export/import functionality
- P3.4: Health check system

### Testing Recommendations

1. **Concurrency Tests:** Simulate multiple processes modifying same config/session files
2. **Corruption Tests:** Inject partial file writes, verify recovery
3. **Crash Recovery Tests:** Kill process mid-write, verify data intact
4. **Schema Migration Tests:** Test reading old metadata formats
5. **Backup/Restore Tests:** Export all data, restore to new installation

---

## Conclusion

The Inkwell CLI has **solid foundations** with atomic writes, fsync, and proper datetime handling. However, the **critical lack of file locking** in multi-access scenarios poses significant data loss risks, especially in configuration and session management.

The recommended fixes are **straightforward** and can leverage existing patterns in `costs.py` (which already implements file locking correctly). Implementing these changes will elevate the system from "good for single-user" to "production-grade with data integrity guarantees."

**Key Strengths:**
- Comprehensive atomic write operations with temp-file-rename pattern
- Excellent fsync usage for durability
- Timezone-aware datetime handling throughout
- Encryption for sensitive credentials
- Good error handling and validation

**Key Weaknesses:**
- No file locking for concurrent access
- Missing schema versioning for long-term compatibility
- Limited backup/recovery mechanisms
- No audit trail for configuration changes

**Risk Assessment:**
- **Single-user usage:** LOW risk (current implementation sufficient)
- **Multi-process usage:** HIGH risk (race conditions likely)
- **Long-term data migration:** MEDIUM risk (schema evolution needs planning)
- **Disaster recovery:** MEDIUM risk (keyfile loss is catastrophic)

Implementing the P1 (Critical) fixes will reduce multi-process risk from HIGH to LOW. Implementing P2 (Important) fixes will provide production-grade data integrity suitable for team/server deployments.
