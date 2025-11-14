---
status: completed
priority: p2
issue_id: "045"
tags: [data-integrity, cost-tracking, accounting, analytics]
dependencies: []
---

# Fix Cost Tracker Duplicate Detection Logic

## Problem Statement

The cost tracker's duplicate detection uses a composite key that's too permissive: `(timestamp, operation, provider, episode_title, input_tokens)`. If the same episode is processed twice with identical input tokens, the second cost entry is treated as a duplicate and dropped, causing underbilling and incorrect analytics.

**Severity**: IMPORTANT - Cost tracking accuracy affects billing and analytics.

## Findings

- Discovered during data integrity audit by data-integrity-guardian agent
- Location: `src/inkwell/utils/costs.py:329-353`
- Issue: Duplicate detection key includes `input_tokens` which can legitimately repeat
- Risk: Lost cost entries, inaccurate billing, wrong analytics

**Underbilling Scenario:**
1. User processes "My Podcast - Episode 1" at 10:00 AM
2. Extraction uses Gemini API → 1000 input tokens, costs $0.05
3. Cost recorded: `{timestamp: "2025-11-14T10:00:00", operation: "extract", provider: "gemini", episode_title: "Episode 1", input_tokens: 1000, cost: 0.05}`
4. User realizes there was a bug, runs `inkwell fetch podcast --overwrite` at 10:05 AM
5. Extraction runs **again** on same episode → same transcript → **same 1000 input tokens**
6. Cost tracker merge logic sees composite key: `("2025-11-14T10:00:00", "extract", "gemini", "Episode 1", 1000)`
7. Thinks it's a duplicate (same timestamp minute, same tokens)
8. Second $0.05 entry is **dropped**
9. **Result:** User actually spent $0.10 but cost tracker only shows $0.05

**Why This Happens:**
```python
# In costs.py:329-353
def _save(self) -> None:
    """Save usage history to file with file locking."""
    with self._lock_costs_file():
        # ... load existing costs

        # Merge with existing (avoid duplicates)
        existing_keys = {
            (
                u.timestamp.isoformat(),
                u.operation,
                u.provider,
                u.episode_title,
                u.input_tokens,  # ⚠️ PROBLEM: Same input can happen twice legitimately!
            )
            for u in existing
        }

        # Only add new entries not in existing
        new_entries = [
            u for u in self.usage_history
            if (
                u.timestamp.isoformat(),
                u.operation,
                u.provider,
                u.episode_title,
                u.input_tokens,
            ) not in existing_keys
        ]
        # ⚠️ Legitimate re-processing gets dropped as "duplicate"
```

**Legitimate Scenarios Where This Fails:**
1. **Re-processing with --overwrite:** Same episode, same transcript, same token count
2. **Retry after failure:** Process crashes mid-extraction, restart uses same tokens
3. **Batch processing same episode:** Multiple users processing same public podcast
4. **Template changes:** Reprocess with new template but same transcript (same input tokens)

**Current Implementation Problem:**
- Assumes same input tokens = duplicate entry
- No unique identifier per API call
- Timestamp precision (seconds) can have collisions
- Episode title + tokens not unique enough

## Proposed Solutions

### Option 1: Add UUID to Each Usage Record (Recommended)

Add unique identifier to each API usage record:

```python
from uuid import uuid4

class APIUsage(BaseModel):
    """API usage record with unique identifier."""

    # ✅ Add unique ID for true deduplication
    usage_id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Unique identifier for this usage record"
    )

    # Existing fields
    timestamp: datetime = Field(...)
    operation: str = Field(...)
    provider: str = Field(...)
    model: str = Field(...)
    episode_title: str | None = Field(default=None)
    input_tokens: int = Field(...)
    output_tokens: int = Field(...)
    total_cost: float = Field(...)


class CostTracker:
    def _save(self) -> None:
        """Save usage history to file with file locking."""
        with self._lock_costs_file():
            # Load existing costs
            existing = []
            if self.costs_file.exists():
                data = json.loads(self.costs_file.read_text())
                existing = [APIUsage(**u) for u in data]

            # ✅ Merge using unique IDs
            existing_ids = {u.usage_id for u in existing}
            new_entries = [
                u for u in self.usage_history
                if u.usage_id not in existing_ids
            ]

            # Combine and save
            all_entries = existing + new_entries
            self.costs_file.write_text(
                json.dumps([u.model_dump() for u in all_entries], indent=2)
            )

            logger.debug(f"Saved {len(new_entries)} new cost entries")
```

**Example Records:**
```json
[
  {
    "usage_id": "a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d",
    "timestamp": "2025-11-14T10:00:00+00:00",
    "operation": "extract",
    "provider": "gemini",
    "episode_title": "Episode 1",
    "input_tokens": 1000,
    "output_tokens": 500,
    "total_cost": 0.05
  },
  {
    "usage_id": "f6e7d8c9-b0a1-2f3e-4d5c-6b7a8c9d0e1f",
    "timestamp": "2025-11-14T10:05:00+00:00",
    "operation": "extract",
    "provider": "gemini",
    "episode_title": "Episode 1",
    "input_tokens": 1000,
    "output_tokens": 500,
    "total_cost": 0.05
  }
]
```

**Pros**:
- Truly unique deduplication (UUID collision probability: ~0%)
- Works for all legitimate re-processing scenarios
- Simple to implement
- No false positive duplicates

**Cons**:
- Adds UUID field to model (backward compatibility needed)
- Existing records won't have UUIDs (need migration)

**Effort**: Small (1 hour)
**Risk**: Low

### Option 2: Add Sequence Number

Use auto-incrementing sequence:

```python
class CostTracker:
    def __init__(self):
        self._next_sequence = 1

    def track_usage(self, ...):
        usage = APIUsage(
            sequence_id=self._next_sequence,
            ...
        )
        self._next_sequence += 1
```

**Pros**:
- Ordered by sequence
- Easy to understand

**Cons**:
- Requires state management (next sequence number)
- Race conditions in multi-process
- Complex migration

**Effort**: Medium (2 hours)
**Risk**: Medium

### Option 3: Add Microsecond Precision + Random Nonce

Improve timestamp precision and add randomness:

```python
existing_keys = {
    (
        u.timestamp.isoformat(timespec='microseconds'),  # More precision
        u.operation,
        u.provider,
        u.episode_title,
        u.input_tokens,
        random.randint(0, 1000000),  # Random nonce
    )
    for u in existing
}
```

**Pros**:
- No model changes needed

**Cons**:
- Still has collision possibility
- Not truly unique
- Hacky solution

**Effort**: Small (30 minutes)
**Risk**: Medium (still has edge cases)

## Recommended Action

**Implement Option 1: Add UUID to Each Usage Record**

This provides true uniqueness with minimal complexity. UUIDs are standard for this use case.

**Priority**: P2 IMPORTANT - Cost tracking accuracy

## Technical Details

**Affected Files:**
- `src/inkwell/utils/costs.py:329-353` (_save method)
- `src/inkwell/utils/models.py` or costs.py (APIUsage model)
- `tests/unit/utils/test_costs.py` (test duplicate handling)

**Related Components:**
- Cost tracking database: `~/.config/inkwell/costs.json`
- All API usage recording points

**Database Changes**: Yes (add `usage_id` field)

**Migration Strategy:**
```python
def _migrate_costs_add_uuid(self) -> None:
    """Migrate existing cost records to include UUIDs."""
    if not self.costs_file.exists():
        return

    data = json.loads(self.costs_file.read_text())

    # Add UUIDs to records that don't have them
    migrated = False
    for record in data:
        if "usage_id" not in record:
            record["usage_id"] = str(uuid4())
            migrated = True

    if migrated:
        # Save migrated data
        self.costs_file.write_text(json.dumps(data, indent=2))
        logger.info("Migrated cost records to include usage_id")
```

## Resources

- Original finding: DATA_INTEGRITY_REPORT.md (P2.8, lines 652-694)
- UUID specification: https://en.wikipedia.org/wiki/Universally_unique_identifier
- Python uuid module: https://docs.python.org/3/library/uuid.html

## Acceptance Criteria

- [ ] `usage_id` field added to APIUsage model
- [ ] UUIDs generated automatically (default_factory)
- [ ] Duplicate detection uses `usage_id` instead of composite key
- [ ] Migration function for existing records without UUIDs
- [ ] Migration runs automatically on first load
- [ ] Test: Same episode processed twice → both costs recorded ✓
- [ ] Test: Identical tokens, different UUID → not treated as duplicate ✓
- [ ] Test: Same UUID → correctly identified as duplicate ✓
- [ ] Test: Migration adds UUIDs to old records ✓
- [ ] All existing cost tracking tests still pass
- [ ] Cost analytics show accurate totals

## Work Log

### 2025-11-14 - Data Integrity Audit Discovery
**By:** Claude Code Review System (data-integrity-guardian agent)
**Actions:**
- Identified overly permissive duplicate detection
- Analyzed underbilling scenarios
- Classified as P2 IMPORTANT (cost accuracy)
- Recommended UUID-based deduplication

**Learnings:**
- Same input tokens can legitimately occur multiple times
- Composite keys without unique ID are error-prone
- Cost tracking accuracy critical for billing and analytics
- UUIDs are standard solution for unique identification

## Notes

**Why This Matters:**
- Cost tracking informs budget decisions
- Analytics depend on accurate cost data
- Underbilling hides true API costs
- Users may exceed budgets without realizing
- Financial reporting requires precision

**Cost Impact Example:**
```
Scenario: User processes 100 episodes, reprocesses 20 with --overwrite

Without fix:
- Initial processing: 100 × $0.05 = $5.00 recorded
- Reprocessing: 20 × $0.05 = $1.00 (dropped as duplicates)
- Total shown: $5.00
- Actual cost: $6.00
- Discrepancy: $1.00 (16.7% underbilling)

With fix:
- Initial processing: 100 × $0.05 = $5.00 recorded
- Reprocessing: 20 × $0.05 = $1.00 recorded
- Total shown: $6.00
- Actual cost: $6.00
- Discrepancy: $0.00 ✓
```

**UUID Benefits:**
- Globally unique (collision probability: ~5.3 × 10^-36)
- Time-independent (works across restarts)
- No coordination needed (unlike sequence numbers)
- Standard solution (widely understood)

**Testing Strategy:**
```python
def test_cost_tracker_records_duplicate_episodes(tmp_path):
    """Verify same episode processed twice records both costs."""
    tracker = CostTracker(tmp_path)

    # Process episode first time
    tracker.track_usage(
        operation="extract",
        provider="gemini",
        model="gemini-pro",
        episode_title="Episode 1",
        input_tokens=1000,
        output_tokens=500,
        cost=0.05,
    )
    tracker.save()

    # Process same episode again (--overwrite scenario)
    tracker.track_usage(
        operation="extract",
        provider="gemini",
        model="gemini-pro",
        episode_title="Episode 1",
        input_tokens=1000,  # Same tokens
        output_tokens=500,
        cost=0.05,
    )
    tracker.save()

    # Both should be recorded
    history = tracker.get_usage_history()
    assert len(history) == 2
    assert sum(u.total_cost for u in history) == 0.10

def test_cost_tracker_usage_ids_are_unique(tmp_path):
    """Verify each usage record has unique ID."""
    tracker = CostTracker(tmp_path)

    for i in range(10):
        tracker.track_usage(
            operation="extract",
            provider="gemini",
            model="gemini-pro",
            episode_title="Episode 1",
            input_tokens=1000,
            output_tokens=500,
            cost=0.05,
        )

    tracker.save()
    history = tracker.get_usage_history()

    # All UUIDs should be unique
    usage_ids = [u.usage_id for u in history]
    assert len(usage_ids) == len(set(usage_ids))

def test_cost_tracker_migrates_old_records(tmp_path):
    """Verify old records without UUID are migrated."""
    costs_file = tmp_path / "costs.json"

    # Create old-format record (no usage_id)
    old_record = {
        "timestamp": "2025-11-14T10:00:00+00:00",
        "operation": "extract",
        "provider": "gemini",
        "model": "gemini-pro",
        "input_tokens": 1000,
        "output_tokens": 500,
        "total_cost": 0.05,
    }
    costs_file.write_text(json.dumps([old_record]))

    # Load with tracker (should trigger migration)
    tracker = CostTracker(tmp_path)
    history = tracker.get_usage_history()

    # Should have UUID added
    assert len(history) == 1
    assert history[0].usage_id is not None
    assert len(history[0].usage_id) == 36  # UUID format
```

**Implementation Notes:**
- Use `uuid4()` for random UUIDs (not sequential)
- Store as string (36 characters: `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`)
- Migration should preserve all other fields
- Log migration for debugging

**Backward Compatibility:**
```python
class APIUsage(BaseModel):
    usage_id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Unique identifier for this usage record"
    )

    # Old records without usage_id will get one auto-generated
    # No breaking changes to existing code
```

**Analytics Impact:**
- Cost reports will now be accurate
- Budget tracking more reliable
- Per-episode cost analysis correct
- Provider comparison metrics accurate

Source: Triage session on 2025-11-14

### 2025-11-14 - Implementation Completed
**By:** Claude Code (code review resolution)
**Actions:**
- Added `usage_id` field with UUID to APIUsage model using `uuid4()` with default_factory
- Updated `_save()` method to use `usage_id` for deduplication instead of composite key
- Implemented migration in `_load()` method to add UUIDs to existing records automatically
- Added comprehensive test suite (7 new tests) covering all scenarios from acceptance criteria
- All 37 tests in test_costs.py passing (100% pass rate)

**Implementation Details:**
- UUID field: `usage_id: str = Field(default_factory=lambda: str(uuid4()))`
- Deduplication: Changed from composite key `(timestamp, operation, provider, episode_title, input_tokens)` to simple set lookup `{u.usage_id for u in existing}`
- Migration: Automatically adds UUIDs to old records on first load, saves atomically to disk
- No breaking changes: Existing code works without modification

**Tests Added:**
1. `test_cost_tracker_records_duplicate_episodes` - Verifies same episode processed twice records both costs
2. `test_cost_tracker_usage_ids_are_unique` - Verifies 10 identical operations get unique UUIDs
3. `test_cost_tracker_migrates_old_records` - Verifies old records without UUID are migrated
4. `test_same_uuid_correctly_deduplicated` - Verifies same UUID correctly identified as duplicate
5. `test_different_uuids_not_deduplicated` - Verifies different UUIDs not treated as duplicates
6. `test_api_usage_auto_generates_uuid` - Verifies UUID auto-generation
7. `test_multiple_instances_generate_different_uuids` - Verifies different instances get different UUIDs

**Files Changed:**
- `/Users/sergio/projects/inkwell-cli/src/inkwell/utils/costs.py` (Lines 11, 89-93, 230-265, 340-345)
- `/Users/sergio/projects/inkwell-cli/tests/unit/utils/test_costs.py` (Added 187 lines of tests)

**Acceptance Criteria Status:** All criteria met
- usage_id field added to APIUsage model
- UUIDs generated automatically (default_factory)
- Duplicate detection uses usage_id instead of composite key
- Migration function for existing records without UUIDs
- Migration runs automatically on first load
- Test: Same episode processed twice -> both costs recorded (PASS)
- Test: Identical tokens, different UUID -> not treated as duplicate (PASS)
- Test: Same UUID -> correctly identified as duplicate (PASS)
- Test: Migration adds UUIDs to old records (PASS)
- All existing cost tracking tests still pass (37/37 passing)
- Cost analytics will show accurate totals

**Resolution:** Issue fully resolved. Cost tracker now uses UUID-based deduplication which prevents false positive duplicates when same episode is processed multiple times with identical token counts.
