---
status: resolved
priority: p2
issue_id: "040"
tags: [data-integrity, schema-evolution, backward-compatibility, metadata]
dependencies: []
resolved_date: 2025-11-14
---

# Add Schema Versioning to Episode Metadata

## Problem Statement

Episode metadata files (`.metadata.yaml`) are written without a schema version field. When the `EpisodeMetadata` Pydantic model evolves (adding/removing fields, renaming), old metadata files become unreadable, breaking users' ability to access previously processed episodes.

**Severity**: IMPORTANT - Essential for long-term data migration and backward compatibility.

## Findings

- Discovered during data integrity audit by data-integrity-guardian agent
- Location: `src/inkwell/output/manager.py:273-286`
- Issue: No `schema_version` field in metadata YAML files
- Risk: Schema changes break ability to read old episode metadata

**Breaking Change Scenario:**
1. User processes 100 podcast episodes → creates `.metadata.yaml` files with current schema
2. Inkwell v0.2 releases with updated `EpisodeMetadata` model:
   - **Adds** new required field: `processing_duration: float`
   - **Renames** field: `pub_date` → `published_at`
   - **Removes** field: `raw_transcript` (moved to separate file)
3. User upgrades to v0.2, runs `inkwell list` to see processed episodes
4. Pydantic validation fails on old metadata files:
   ```
   ValidationError: 1 validation error for EpisodeMetadata
     processing_duration
       field required (type=value_error.missing)
   ```
5. **Result:** All 100 previously processed episodes are now inaccessible
6. User cannot view, search, or re-process old episodes
7. Only options: Manually migrate metadata or regenerate all episodes (expensive, hours of processing)

**Current Implementation:**
```python
def _write_metadata(self, metadata_file: Path, episode_metadata: EpisodeMetadata) -> None:
    """Write episode metadata to YAML file."""
    metadata_dict = episode_metadata.model_dump()
    # ⚠️ No schema_version field added
    content = yaml.dump(metadata_dict, default_flow_style=False, sort_keys=False)
    self._write_file_atomic(metadata_file, content)

# No load_episode_metadata() method exists
# No migration logic exists
```

**Why This Matters:**
- Podcast episodes can take hours to process (transcription + extraction)
- Users accumulate hundreds of processed episodes over time
- Schema evolution is inevitable as features are added
- Breaking users' existing data on upgrade is unacceptable

## Proposed Solutions

### Option 1: Add Schema Version + Migration System (Recommended)

Add versioning to model and implement migration framework:

```python
# In src/inkwell/output/models.py
class EpisodeMetadata(BaseModel):
    """Episode metadata with schema versioning support."""

    schema_version: int = Field(
        default=1,
        description="Metadata schema version for migration support"
    )

    # Existing fields...
    podcast_name: str = Field(...)
    episode_title: str = Field(...)
    pub_date: datetime = Field(...)
    # ... all other fields


# In src/inkwell/output/manager.py
class OutputManager:
    CURRENT_METADATA_SCHEMA_VERSION = 1

    def load_episode_metadata(self, episode_dir: Path) -> EpisodeMetadata:
        """Load and migrate episode metadata if needed."""
        metadata_file = episode_dir / ".metadata.yaml"

        if not metadata_file.exists():
            raise FileNotFoundError(f"Metadata file not found: {metadata_file}")

        with metadata_file.open("r") as f:
            data = yaml.safe_load(f)

        # Handle schema migrations
        schema_version = data.get("schema_version", 0)

        if schema_version == 0:
            # Migrate v0 (no version) -> v1
            data = self._migrate_metadata_v0_to_v1(data)
            logger.info(f"Migrated {metadata_file} from v0 to v1")

        if schema_version > self.CURRENT_METADATA_SCHEMA_VERSION:
            logger.warning(
                f"Metadata schema version {schema_version} is newer than supported "
                f"({self.CURRENT_METADATA_SCHEMA_VERSION}). Some fields may be missing."
            )

        return EpisodeMetadata(**data)

    def _migrate_metadata_v0_to_v1(self, data: dict) -> dict:
        """Migrate metadata from v0 (no version) to v1."""
        # Add schema version
        data["schema_version"] = 1

        # Add any new required fields with defaults
        if "processing_duration" not in data:
            data["processing_duration"] = 0.0  # Unknown for old episodes

        # Handle renamed fields (future example)
        # if "pub_date" in data and "published_at" not in data:
        #     data["published_at"] = data.pop("pub_date")

        return data

    def _write_metadata(self, metadata_file: Path, episode_metadata: EpisodeMetadata) -> None:
        """Write episode metadata to YAML file."""
        metadata_dict = episode_metadata.model_dump()

        # Ensure schema_version is set
        if "schema_version" not in metadata_dict:
            metadata_dict["schema_version"] = self.CURRENT_METADATA_SCHEMA_VERSION

        content = yaml.dump(metadata_dict, default_flow_style=False, sort_keys=False)
        self._write_file_atomic(metadata_file, content)
```

**Migration Framework for Future Changes:**
```python
# When releasing v0.3 with schema v2:

CURRENT_METADATA_SCHEMA_VERSION = 2

def load_episode_metadata(self, episode_dir: Path) -> EpisodeMetadata:
    # ... load YAML

    if schema_version == 0:
        data = self._migrate_metadata_v0_to_v1(data)
        schema_version = 1

    if schema_version == 1:
        data = self._migrate_metadata_v1_to_v2(data)
        schema_version = 2

    return EpisodeMetadata(**data)

def _migrate_metadata_v1_to_v2(self, data: dict) -> dict:
    """Migrate metadata from v1 to v2."""
    data["schema_version"] = 2

    # Example: Rename field
    if "pub_date" in data:
        data["published_at"] = data.pop("pub_date")

    # Example: Split field
    if "raw_transcript" in data:
        # Move to separate file
        del data["raw_transcript"]

    return data
```

**Pros**:
- Backward compatible with all old metadata files
- Automatic migration on load
- Clear upgrade path for future schema changes
- No data loss for users

**Cons**:
- Requires writing migration code for each schema change
- Slightly more complex implementation

**Effort**: Medium (2-3 hours)
**Risk**: Low

### Option 2: Pydantic Model Evolution with Defaults

Make all new fields optional with defaults:

```python
class EpisodeMetadata(BaseModel):
    schema_version: int = 1  # Default for old files

    # All new fields must have defaults
    processing_duration: float = 0.0
    # Never rename or remove required fields
```

**Pros**:
- Simple - no migration code needed
- Works automatically

**Cons**:
- Cannot rename or remove fields (ever)
- Limited schema evolution flexibility
- Accumulates technical debt over time

**Effort**: Small (1 hour)
**Risk**: Medium (restricts future changes)

### Option 3: Store Migration Metadata Separately

Keep original metadata unchanged, store migrations in separate file:

```
episode-dir/
├── .metadata.yaml (original v0)
└── .metadata.v1.yaml (migrated to v1)
```

**Pros**:
- Preserves original metadata
- Can recover from bad migrations

**Cons**:
- File duplication (disk space)
- Complex to manage multiple versions
- Confusing for users

**Effort**: Medium (3 hours)
**Risk**: Medium

## Recommended Action

**Implement Option 1: Schema Version + Migration System**

This is the industry-standard approach for data schema evolution. It provides flexibility for future changes while maintaining backward compatibility.

**Priority**: P2 IMPORTANT - Prevents data loss on upgrades

## Technical Details

**Affected Files:**
- `src/inkwell/output/models.py` (add schema_version field)
- `src/inkwell/output/manager.py` (add load + migration methods)
- `tests/unit/output/test_manager.py` (add migration tests)

**Related Components:**
- `src/inkwell/cli.py` (may need to call load_episode_metadata)
- All episode output directories with `.metadata.yaml`

**Database Changes**: No

**Metadata File Structure:**
```yaml
# New format (v1):
schema_version: 1
podcast_name: "My Podcast"
episode_title: "Episode 1"
pub_date: "2025-11-14T10:00:00+00:00"
duration_seconds: 3600
# ... other fields

# Old format (v0 - no version):
podcast_name: "My Podcast"
episode_title: "Episode 1"
pub_date: "2025-11-14T10:00:00+00:00"
duration_seconds: 3600
# ... other fields
```

## Resources

- Original finding: DATA_INTEGRITY_REPORT.md (P2.3, lines 339-395)
- Pydantic migration patterns: https://docs.pydantic.dev/latest/concepts/models/
- Database migration comparison (similar concept): Alembic, Django migrations

## Acceptance Criteria

- [ ] `schema_version` field added to `EpisodeMetadata` model
- [ ] `schema_version: 1` written to all new metadata files
- [ ] `load_episode_metadata()` method implemented
- [ ] `_migrate_metadata_v0_to_v1()` migration function implemented
- [ ] Migration handles missing schema_version (treats as v0)
- [ ] Warning logged when reading newer schema version
- [ ] Test: Load v0 metadata (no version) → migrates to v1 ✓
- [ ] Test: Load v1 metadata → no migration needed ✓
- [ ] Test: Load v2 metadata (future) → warning logged ✓
- [ ] Test: Write new metadata → includes schema_version: 1 ✓
- [ ] All existing output tests still pass
- [ ] Migration preserves all original data

## Resolution Summary

**Implemented on:** 2025-11-14
**Status:** RESOLVED - All acceptance criteria met

### Changes Made

1. **Added `schema_version` field to `EpisodeMetadata` model** (`src/inkwell/output/models.py`)
   - Field defaults to `1` for new metadata
   - Provides forward/backward compatibility support
   - Documented purpose in field description

2. **Updated `OutputManager._write_metadata()`** (`src/inkwell/output/manager.py`)
   - Ensures `schema_version` is always written to metadata files
   - Falls back to `CURRENT_METADATA_SCHEMA_VERSION` if not set
   - All new `.metadata.yaml` files now include `schema_version: 1`

3. **Enhanced `OutputManager.load_episode_metadata()`** (`src/inkwell/output/manager.py`)
   - Automatically detects schema version (defaults to 0 if missing)
   - Calls appropriate migration function for v0 metadata
   - Logs info message when migration occurs
   - Warns if loading newer schema version than supported

4. **Implemented migration framework** (`src/inkwell/output/manager.py`)
   - Added `CURRENT_METADATA_SCHEMA_VERSION = 1` class constant
   - Created `_migrate_metadata_v0_to_v1()` method
   - Migration preserves all existing data
   - Framework ready for future schema changes (v1→v2, v2→v3, etc.)

5. **Comprehensive test coverage** (`tests/unit/test_output_manager.py`)
   - 7 new tests in `TestOutputManagerSchemaVersioning` class
   - Tests v0→v1 migration with data preservation
   - Tests v1 metadata loads without migration
   - Tests warning for future schema versions (v2+)
   - Tests schema version is written to new files
   - All 88 output tests pass (59 manager + 29 models)

### Files Modified
- `src/inkwell/output/models.py` - Added `schema_version` field
- `src/inkwell/output/manager.py` - Migration framework + updated write/load
- `tests/unit/test_output_manager.py` - 7 new tests + logging import

### Acceptance Criteria Status
- ✅ `schema_version` field added to `EpisodeMetadata` model
- ✅ `schema_version: 1` written to all new metadata files
- ✅ `load_episode_metadata()` method enhanced with migration support
- ✅ `_migrate_metadata_v0_to_v1()` migration function implemented
- ✅ Migration handles missing schema_version (treats as v0)
- ✅ Warning logged when reading newer schema version
- ✅ Test: Load v0 metadata (no version) → migrates to v1
- ✅ Test: Load v1 metadata → no migration needed
- ✅ Test: Load v2 metadata (future) → warning logged
- ✅ Test: Write new metadata → includes schema_version: 1
- ✅ All existing output tests still pass (88/88)
- ✅ Migration preserves all original data

### Benefits
1. **Backward Compatibility:** Old metadata files (v0) automatically migrate on load
2. **Forward Compatibility:** Framework ready for future schema changes
3. **No Data Loss:** Users' processed episodes remain accessible after upgrades
4. **Zero Breaking Changes:** All existing code continues to work
5. **Production Ready:** Comprehensive test coverage ensures reliability

### Future Schema Migrations
The framework is now ready for future schema evolution. Example for v1→v2:

```python
CURRENT_METADATA_SCHEMA_VERSION = 2

def load_episode_metadata(self, episode_dir: Path) -> EpisodeMetadata:
    # ... existing v0→v1 migration ...

    if schema_version == 1:
        data = self._migrate_metadata_v1_to_v2(data)
        schema_version = 2

    return EpisodeMetadata(**data)

def _migrate_metadata_v1_to_v2(self, data: dict) -> dict:
    """Migrate metadata from v1 to v2."""
    data["schema_version"] = 2
    # Add new fields, rename fields, etc.
    return data
```

## Work Log

### 2025-11-14 - Implementation Complete
**By:** Claude Code (code review resolution specialist)
**Actions:**
- Implemented schema versioning system
- Added migration framework
- Wrote comprehensive tests
- Verified all tests pass (88/88)
- Updated todo status to resolved

**Results:**
- Zero breaking changes
- All acceptance criteria met
- Production-ready implementation
- Framework for future migrations established

### 2025-11-14 - Data Integrity Audit Discovery
**By:** Claude Code Review System (data-integrity-guardian agent)
**Actions:**
- Identified missing schema versioning in metadata
- Analyzed schema evolution scenarios
- Classified as P2 IMPORTANT (long-term compatibility)
- Recommended schema version + migration framework

**Learnings:**
- Schema evolution is inevitable as software matures
- Versioning prevents breaking changes from affecting users
- Migration code is one-time cost, saves users from data loss
- Industry standard: Store version in data, not just code

## Notes

**Why This Matters:**
- Users invest significant time processing episodes (hours)
- Breaking existing data on upgrade is unacceptable UX
- Professional tools handle backward compatibility gracefully
- Podcast collections grow over time (hundreds of episodes)

**Schema Evolution Examples:**
```python
# v0 → v1 (current implementation)
# Add: schema_version field

# v1 → v2 (future example - rename field)
def _migrate_metadata_v1_to_v2(self, data: dict) -> dict:
    data["schema_version"] = 2
    if "pub_date" in data:
        data["published_at"] = data.pop("pub_date")
    return data

# v2 → v3 (future example - remove field)
def _migrate_metadata_v2_to_v3(self, data: dict) -> dict:
    data["schema_version"] = 3
    # Remove raw_transcript (moved to separate file)
    data.pop("raw_transcript", None)
    return data

# v3 → v4 (future example - add required field)
def _migrate_metadata_v3_to_v4(self, data: dict) -> dict:
    data["schema_version"] = 4
    # Add new field with sensible default
    if "processing_duration" not in data:
        data["processing_duration"] = 0.0  # Unknown for old episodes
    return data
```

**Testing Strategy:**
```python
def test_load_metadata_v0_migrates_to_v1(tmp_path):
    """Verify v0 metadata (no version) is migrated to v1."""
    episode_dir = tmp_path / "episode"
    episode_dir.mkdir()

    # Create v0 metadata (no schema_version)
    metadata_file = episode_dir / ".metadata.yaml"
    metadata_file.write_text("""
podcast_name: "Test Podcast"
episode_title: "Episode 1"
pub_date: "2025-11-14T10:00:00+00:00"
duration_seconds: 3600
    """)

    manager = OutputManager(tmp_path)
    metadata = manager.load_episode_metadata(episode_dir)

    # Should be migrated to v1
    assert metadata.schema_version == 1
    assert metadata.podcast_name == "Test Podcast"

def test_write_metadata_includes_version(tmp_path):
    """Verify new metadata includes schema_version."""
    manager = OutputManager(tmp_path)

    episode_metadata = EpisodeMetadata(
        podcast_name="Test Podcast",
        episode_title="Episode 1",
        # ... other fields
    )

    metadata_file = tmp_path / ".metadata.yaml"
    manager._write_metadata(metadata_file, episode_metadata)

    # Reload and verify
    with metadata_file.open() as f:
        data = yaml.safe_load(f)

    assert data["schema_version"] == 1
```

**Migration Best Practices:**
1. **Never remove migration code** - Old versions may still exist
2. **Test migrations with real data** - Copy production metadata
3. **Log all migrations** - Help users understand what happened
4. **Provide rollback docs** - If migration fails, how to recover
5. **Version CLI commands** - `inkwell migrate-metadata` for manual runs

**Rollout Strategy:**
1. Release v0.2 with schema_version support
2. All writes include `schema_version: 1`
3. All reads handle v0 (migrate) and v1 (no-op)
4. v0.3+ can safely evolve schema to v2, v3, etc.

Source: Triage session on 2025-11-14
