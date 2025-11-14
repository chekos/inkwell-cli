---
status: completed
priority: p2
issue_id: "042"
tags: [data-integrity, corruption-detection, yaml, checksums]
dependencies: []
completed_date: 2025-11-14
---

# Add Integrity Checks for YAML Files

## Problem Statement

YAML files (config, feeds, metadata) are written without checksums or integrity verification. Silent corruption from filesystem errors, improper encoding, or bugs can go undetected until data is used, causing mysterious failures with unclear root causes.

**Severity**: IMPORTANT - Detects corruption early before it causes data loss.

## Findings

- Discovered during data integrity audit by data-integrity-guardian agent
- Location: All YAML write operations (config, feeds, metadata)
- Issue: No checksum or integrity verification
- Risk: Silent corruption goes undetected, causing cryptic errors later

**Corruption Scenario:**
1. User processes 50 podcast episodes → `.metadata.yaml` files written to disk
2. Filesystem corruption occurs (bad disk sector, cosmic ray, buggy filesystem driver, interrupted write)
3. One `.metadata.yaml` file becomes corrupted:
   ```yaml
   podcast_name: "My Podcast"
   episode_title: "Great Episo�������������
   pub_date: "2025-11-14T10:00:00+00:00"
   duration_seconds: 3600
   ```
4. User runs `inkwell list` weeks later to browse episodes
5. YAML parser fails with cryptic error:
   ```
   yaml.scanner.ScannerError: while scanning a quoted scalar
     in "<unicode string>", line 3, column 16
   found unexpected end of stream
   ```
6. **Result:** User cannot access that episode, doesn't know which file is corrupt, must manually inspect YAML files to find corruption

**Current Implementation:**
```python
# In config/manager.py, output/manager.py
def _write_metadata(self, metadata_file: Path, episode_metadata: EpisodeMetadata) -> None:
    metadata_dict = episode_metadata.model_dump()
    content = yaml.dump(metadata_dict, default_flow_style=False, sort_keys=False)
    self._write_file_atomic(metadata_file, content)
    # ⚠️ No checksum, no integrity verification

def load_config(self) -> GlobalConfig:
    with self.config_file.open("r") as f:
        data = yaml.safe_load(f)
    # ⚠️ No verification that file is intact
    return GlobalConfig(**data)
```

**Why This Happens:**
- Filesystem corruption is rare but real (bad sectors, cosmic rays, bugs)
- Power loss during write can leave partial files
- Encoding issues can introduce invalid characters
- No way to detect if file has been corrupted since writing

**Real-World Corruption Causes:**
- Bad disk sectors (HDD aging)
- Filesystem bugs (especially network filesystems)
- Interrupted writes (power loss, process kill during fsync)
- Bit flips in memory or storage (cosmic rays, hardware faults)
- Encoding conversion errors (UTF-8 ↔ system encoding)
- Antivirus/backup software interference

## Proposed Solutions

### Option 1: Embedded Checksum in YAML Comments (Recommended)

Add SHA-256 checksum as YAML comment, verify on read:

```python
import hashlib

class YAMLWithIntegrity:
    """YAML read/write with integrity checking."""

    @staticmethod
    def write_yaml_with_checksum(file_path: Path, data: dict) -> None:
        """Write YAML with embedded checksum for integrity verification."""
        # Generate YAML content
        yaml_content = yaml.dump(data, default_flow_style=False, sort_keys=False)

        # Calculate checksum (SHA-256 of content)
        checksum = hashlib.sha256(yaml_content.encode('utf-8')).hexdigest()

        # Add checksum as comment at end (YAML parsers ignore comments)
        final_content = f"{yaml_content}\n# checksum: {checksum}\n"

        # Write atomically
        temp_file = file_path.with_suffix('.tmp')
        temp_file.write_text(final_content, encoding='utf-8')
        temp_file.replace(file_path)

    @staticmethod
    def read_yaml_with_verification(file_path: Path) -> dict:
        """Read YAML and verify checksum."""
        content = file_path.read_text(encoding='utf-8')

        # Extract checksum if present
        if "# checksum: " in content:
            # Split on checksum line
            main_content, checksum_line = content.rsplit("# checksum: ", 1)
            expected_checksum = checksum_line.strip()

            # Recalculate checksum
            actual_checksum = hashlib.sha256(main_content.encode('utf-8')).hexdigest()

            # Verify integrity
            if actual_checksum != expected_checksum:
                raise ValueError(
                    f"YAML file {file_path} failed integrity check.\n"
                    f"Expected: {expected_checksum}\n"
                    f"Actual:   {actual_checksum}\n"
                    f"The file may be corrupted. Try restoring from backup."
                )

            # Use main content (without checksum comment)
            content = main_content
        else:
            # No checksum (old file format), log warning
            logger.warning(f"YAML file {file_path} has no integrity checksum (old format)")

        return yaml.safe_load(content)
```

**Usage in Managers:**
```python
# In OutputManager, ConfigManager, etc.
from inkwell.utils.yaml_integrity import YAMLWithIntegrity

class OutputManager:
    def _write_metadata(self, metadata_file: Path, episode_metadata: EpisodeMetadata) -> None:
        metadata_dict = episode_metadata.model_dump()
        YAMLWithIntegrity.write_yaml_with_checksum(metadata_file, metadata_dict)

    def load_episode_metadata(self, episode_dir: Path) -> EpisodeMetadata:
        metadata_file = episode_dir / ".metadata.yaml"
        data = YAMLWithIntegrity.read_yaml_with_verification(metadata_file)
        return EpisodeMetadata(**data)
```

**Example YAML File:**
```yaml
podcast_name: "My Podcast"
episode_title: "Great Episode"
pub_date: "2025-11-14T10:00:00+00:00"
duration_seconds: 3600

# checksum: 5f3b8c4a9e2d1f6a8b3c7e4d2a9f1b5c8e3a6d2f9b4c1e7a3d8f2b6c9e1a4d7
```

**Pros**:
- Detects any corruption (even single bit flip)
- Backward compatible (old files without checksum still load)
- No external metadata files needed
- YAML parsers ignore comments automatically
- Clear error message tells user file is corrupt

**Cons**:
- Slight overhead on read/write (SHA-256 computation)
- Requires careful parsing to extract checksum

**Effort**: Medium (2-3 hours)
**Risk**: Low

### Option 2: Separate Checksum Files

Store checksum in adjacent `.sha256` file:

```
episode-dir/
├── .metadata.yaml
└── .metadata.yaml.sha256  # Contains "checksum filename"
```

**Pros**:
- Simpler implementation
- Standard format (sha256sum compatible)

**Cons**:
- Two files per YAML (clutter)
- Checksum file can be lost independently
- Not atomic with main file

**Effort**: Small (1 hour)
**Risk**: Medium (file synchronization issues)

### Option 3: Add Magic Bytes Header

Add custom header to YAML:

```yaml
# Inkwell YAML v1 - DO NOT EDIT MANUALLY
# integrity: sha256:abc123...
podcast_name: "My Podcast"
```

**Pros**:
- Easy to identify Inkwell files
- Can add version info

**Cons**:
- Not standard YAML
- May confuse some parsers

**Effort**: Medium (2 hours)
**Risk**: Low

## Recommended Action

**Implement Option 1: Embedded Checksum in YAML Comments**

This is the most robust solution with backward compatibility. Checksums are embedded in the files they protect, and YAML parsers naturally ignore comments.

**Priority**: P2 IMPORTANT - Proactive corruption detection

## Technical Details

**Affected Files:**
- `src/inkwell/utils/yaml_integrity.py` (new module)
- `src/inkwell/config/manager.py` (use for config/feeds)
- `src/inkwell/output/manager.py` (use for metadata)
- `tests/unit/utils/test_yaml_integrity.py` (new tests)

**Related Components:**
- All YAML files: `config.yaml`, `feeds.yaml`, `.metadata.yaml`
- Atomic write operations (already exist)

**Database Changes**: No

**YAML Files to Protect:**
1. `~/.config/inkwell/config.yaml` (global config)
2. `~/.config/inkwell/feeds.yaml` (feed definitions)
3. `output/episode-dir/.metadata.yaml` (episode metadata)

## Resources

- Original finding: DATA_INTEGRITY_REPORT.md (P2.5, lines 480-530)
- SHA-256 reference: https://en.wikipedia.org/wiki/SHA-2
- YAML specification: https://yaml.org/spec/1.2.2/

## Acceptance Criteria

- [x] `YAMLWithIntegrity` utility class created in `utils/yaml_integrity.py`
- [x] `write_yaml_with_checksum()` embeds SHA-256 checksum as comment
- [x] `read_yaml_with_verification()` verifies checksum on load
- [x] Clear error message when checksum mismatch detected
- [x] Backward compatible: Old YAML files without checksum still load (with warning)
- [x] ConfigManager uses integrity checking for config.yaml and feeds.yaml
- [x] OutputManager uses integrity checking for .metadata.yaml
- [x] Test: Write and read with valid checksum → success
- [x] Test: Corrupt file → ValueError with clear message
- [x] Test: Old file without checksum → loads with warning
- [x] Test: Checksum in wrong format → graceful handling
- [x] All existing YAML tests still pass

## Work Log

### 2025-11-14 - Data Integrity Audit Discovery
**By:** Claude Code Review System (data-integrity-guardian agent)
**Actions:**
- Identified missing integrity checks in YAML files
- Analyzed corruption scenarios and detection methods
- Classified as P2 IMPORTANT (corruption prevention)
- Recommended embedded checksum approach

**Learnings:**
- Silent corruption is hard to debug without checksums
- YAML comments provide clean way to embed metadata
- SHA-256 is fast enough for file-level verification
- Backward compatibility essential (old files exist)

### 2025-11-14 - Implementation Completed
**By:** Claude Code (code review resolution)
**Actions:**
- Created YAMLWithIntegrity utility class in src/inkwell/utils/yaml_integrity.py
- Implemented write_yaml_with_checksum() with embedded SHA-256 checksums
- Implemented read_yaml_with_verification() with integrity checking
- Added comprehensive test suite (23 tests, all passing)
- Integrated into ConfigManager for config.yaml and feeds.yaml
- Integrated into OutputManager for .metadata.yaml
- All existing tests pass (1188 unit tests)

**Implementation Details:**
- Checksums embedded as YAML comments (transparent to parsers)
- Backward compatible: old files without checksums load with warning
- Invalid checksums raise YAMLIntegrityError with clear error messages
- Atomic write pattern maintained (temp file + rename)
- Graceful degradation for invalid checksum formats

**Testing:**
- Verified corruption detection (bit flips, truncation, encoding issues)
- Verified backward compatibility with existing YAML files
- Verified atomic write cleanup on errors
- All 23 new tests passing
- All 1188 existing unit tests passing

## Notes

**Why This Matters:**
- YAML files contain critical configuration and metadata
- Corruption can make entire codebase unusable
- Early detection prevents cryptic downstream errors
- Clear error messages help users recover (restore from backup)

**Performance Impact:**
```python
# SHA-256 is very fast for small files
import hashlib
import timeit

yaml_content = "podcast_name: My Podcast\n" * 100  # ~3KB
timeit.timeit(
    lambda: hashlib.sha256(yaml_content.encode()).hexdigest(),
    number=10000
)
# Result: ~0.15 seconds for 10,000 iterations = 0.015ms per file
# Negligible overhead
```

**Corruption Detection Examples:**
```python
# Example 1: Bit flip
Original: podcast_name: "Great Episode"
Corrupted: podcast_name: "Greit Episode"  # 'e' → 'i' (bit flip)
→ Checksum mismatch detected ✓

# Example 2: Truncation
Original: (100 lines of YAML)
Corrupted: (98 lines - file truncated)
→ Checksum mismatch detected ✓

# Example 3: Encoding corruption
Original: episode_title: "Café Discussion"
Corrupted: episode_title: "Caf� Discussion"  # UTF-8 → Latin-1 conversion
→ Checksum mismatch detected ✓
```

**Testing Strategy:**
```python
def test_yaml_integrity_detects_corruption(tmp_path):
    """Verify checksum detects file corruption."""
    yaml_file = tmp_path / "test.yaml"
    data = {"name": "Test", "value": 123}

    # Write with checksum
    YAMLWithIntegrity.write_yaml_with_checksum(yaml_file, data)

    # Corrupt the file (change one character)
    content = yaml_file.read_text()
    corrupted = content.replace("Test", "Tent")
    yaml_file.write_text(corrupted)

    # Should detect corruption
    with pytest.raises(ValueError) as exc_info:
        YAMLWithIntegrity.read_yaml_with_verification(yaml_file)

    assert "integrity check" in str(exc_info.value).lower()
    assert "corrupted" in str(exc_info.value).lower()

def test_yaml_integrity_backward_compatible(tmp_path):
    """Verify old YAML files without checksum still load."""
    yaml_file = tmp_path / "old.yaml"

    # Write old-style YAML (no checksum)
    data = {"name": "Old Format", "value": 456}
    content = yaml.dump(data)
    yaml_file.write_text(content)

    # Should load with warning
    with pytest.warns(UserWarning, match="no integrity checksum"):
        loaded = YAMLWithIntegrity.read_yaml_with_verification(yaml_file)

    assert loaded == data

def test_yaml_integrity_checksum_format(tmp_path):
    """Verify checksum is valid SHA-256 hex."""
    yaml_file = tmp_path / "test.yaml"
    data = {"name": "Test"}

    YAMLWithIntegrity.write_yaml_with_checksum(yaml_file, data)

    content = yaml_file.read_text()
    assert "# checksum: " in content

    # Extract checksum
    checksum = content.split("# checksum: ")[1].strip()

    # Verify format: 64 hex characters
    assert len(checksum) == 64
    assert all(c in "0123456789abcdef" for c in checksum)
```

**Implementation Notes:**
- Use `hashlib.sha256()` from Python standard library
- Encode YAML as UTF-8 before hashing
- Strip trailing newlines consistently
- Consider adding `--verify-integrity` CLI command to check all YAML files

**Error Message Design:**
```
Bad (current):
yaml.scanner.ScannerError: while scanning a quoted scalar

Good (with integrity):
ValueError: YAML file /path/to/.metadata.yaml failed integrity check.
Expected checksum: 5f3b8c4a9e2d1f6a8b3c7e4d2a9f1b5c8e3a6d2f9b4c1e7a3d8f2b6c9e1a4d7
Actual checksum:   5f3b8c4a9e2d1f6a8b3CORRUPTED9f1b5c8e3a6d2f9b4c1e7a3d8f2b6c9e1a4d7

The file may be corrupted. Possible fixes:
1. Restore from backup if available
2. Delete and regenerate the file
3. Check filesystem for errors (run fsck/chkdsk)
```

**Future Enhancements:**
- Add `inkwell verify-integrity` command to scan all YAML files
- Store checksums in central manifest for batch verification
- Add automatic backup before overwriting corrupted files

Source: Triage session on 2025-11-14
