---
status: pending
priority: p2
issue_id: "030"
tags: [code-review, architecture, duplication, refactoring]
dependencies: []
---

# Consolidate Cost Tracking - Eliminate Dual Tracking Systems

## Problem Statement

Cost tracking is duplicated across multiple systems: local variables in managers (`self.total_cost_usd`) and a global `CostTracker` class. This creates inconsistency, requires manual synchronization, and can lead to costs being tracked in one system but not the other.

**Severity**: IMPORTANT (Architecture duplication, data inconsistency risk)

## Findings

- Discovered during comprehensive architecture review by architecture-strategist agent
- Locations:
  - `src/inkwell/utils/costs.py` - Global CostTracker class
  - `src/inkwell/extraction/engine.py` - Local `self.total_cost_usd`
  - `src/inkwell/transcription/manager.py` - Per-transcription cost tracking
  - `src/inkwell/interview/manager.py` - Per-interview cost tracking
- Pattern: Two parallel tracking systems with manual synchronization
- Impact: Risk of inconsistent cost data, duplication of tracking logic

**Current problematic pattern:**

```python
# extraction/engine.py - LOCAL tracking
class ExtractionEngine:
    def __init__(self):
        self.total_cost_usd = 0.0  # ❌ Local tracking

    async def extract(self, template, transcript):
        # Manually track cost locally
        self.total_cost_usd += estimated_cost  # ❌ Manual increment

        # ALSO track in global tracker
        cost_tracker = get_cost_tracker()
        cost_tracker.track_cost("extraction", estimated_cost)  # ❌ Duplicate tracking

# utils/costs.py - GLOBAL tracking
class CostTracker:
    def track_cost(self, operation, cost):
        # Separate tracking system
        self.total_cost += cost
```

**Problems:**
1. Two sources of truth for costs (local + global)
2. Easy to forget to call `CostTracker.track()`
3. No automatic rollback on operation failure
4. Costs can be in manager but not tracker, or vice versa
5. No cost budgets or limits enforcement
6. Testing requires mocking both systems

**Impact:**
- Data inconsistency (which cost is "correct"?)
- Maintenance burden (update two systems)
- Risk of cost tracking bugs
- Cannot easily add features (budgets, alerts)
- Testing complexity

## Proposed Solutions

### Option 1: Single CostTracker with Dependency Injection (Recommended)

Make `CostTracker` the single source of truth, inject into managers:

```python
# src/inkwell/utils/costs.py (ENHANCED)
from contextlib import contextmanager

class CostTracker:
    """Singleton cost tracker with context managers and rollback."""

    def __init__(self):
        self.total_cost = 0.0
        self._operations: list[dict] = []

    @contextmanager
    def track_operation(self, operation: str, episode_url: str):
        """Track costs within operation scope with automatic rollback.

        Usage:
            with cost_tracker.track_operation("extraction", url):
                cost_tracker.add_cost("gemini", tokens, 0.05)
                # If exception raised, costs are rolled back
        """
        start_cost = self.total_cost

        try:
            yield self
        except Exception:
            # ✅ Rollback costs on failure
            logger.warning(f"Rolling back costs for {operation}")
            self.total_cost = start_cost
            raise
        finally:
            operation_cost = self.total_cost - start_cost
            self._operations.append({
                "operation": operation,
                "episode_url": episode_url,
                "cost_usd": operation_cost,
                "timestamp": now_utc(),
            })

    def add_cost(self, provider: str, tokens: int, cost_usd: float) -> None:
        """Single method to increment costs.

        Args:
            provider: LLM provider (gemini, claude, openai)
            tokens: Number of tokens used
            cost_usd: Cost in USD
        """
        self.total_cost += cost_usd
        logger.debug(f"{provider}: {tokens} tokens, ${cost_usd:.4f}")

    def get_total_cost(self) -> float:
        """Get total cost across all operations."""
        return self.total_cost

    def get_operation_costs(self) -> list[dict]:
        """Get per-operation cost breakdown."""
        return self._operations.copy()

# src/inkwell/extraction/engine.py (REFACTORED)
class ExtractionEngine:
    def __init__(self, cost_tracker: CostTracker | None = None):
        self.cost_tracker = cost_tracker or get_cost_tracker()
        # ❌ REMOVE: self.total_cost_usd = 0.0

    async def extract(
        self,
        template: ExtractionTemplate,
        transcript: str,
        metadata: dict[str, Any],
    ) -> str:
        """Extract content with automatic cost tracking."""

        with self.cost_tracker.track_operation("extraction", metadata.get("url", "")):
            # Extract content
            result = await extractor.extract(template, transcript, metadata)

            # ✅ Single method to track cost
            self.cost_tracker.add_cost(
                provider=provider_name,
                tokens=token_count,
                cost_usd=estimated_cost
            )

            return result

    def get_total_cost(self) -> float:
        """Get total extraction cost."""
        return self.cost_tracker.total_cost  # ✅ Delegate to tracker
```

**CLI usage:**
```python
@app.command("fetch")
def fetch_command(...):
    async def run_fetch() -> None:
        # Create shared cost tracker
        cost_tracker = CostTracker()

        # Inject into all managers
        transcription_manager = TranscriptionManager(cost_tracker=cost_tracker)
        extraction_engine = ExtractionEngine(cost_tracker=cost_tracker)
        interview_manager = InterviewManager(cost_tracker=cost_tracker)

        # All costs tracked in one place
        result = await orchestrator.process_episode(...)

        # Display total cost
        console.print(f"\n[dim]Total cost: ${cost_tracker.get_total_cost():.4f}[/dim]")
```

**Pros**:
- Single source of truth for costs
- Automatic cost tracking (no manual calls)
- Atomic operations with rollback on failure
- Centralized cost budgeting/limits (future)
- Better testability (inject mock tracker)
- Clean dependency injection pattern

**Cons**:
- Requires updating manager constructors
- Slightly more complex initialization

**Effort**: Small (1 day)
**Risk**: Low

---

### Option 2: Remove Local Tracking, Use Only Global

Simplify by using only `CostTracker`:

```python
# extraction/engine.py (SIMPLIFIED)
class ExtractionEngine:
    def __init__(self):
        # ❌ REMOVE: self.total_cost_usd
        pass  # No local tracking

    async def extract(...):
        # Use global tracker only
        cost_tracker = get_cost_tracker()
        cost_tracker.add_cost(provider, tokens, cost)

    def get_total_cost(self) -> float:
        # Delegate to global tracker
        return get_cost_tracker().total_cost
```

**Pros**:
- Simpler than Option 1 (no DI)
- Removes duplication
- Single source of truth

**Cons**:
- Global state (harder to test)
- No isolation between episodes
- Cannot track per-manager costs separately

**Effort**: Small (4 hours)
**Risk**: Low

---

### Option 3: Keep Local, Remove Global

Opposite approach - use only local tracking:

```python
# Remove utils/costs.py global tracker
# Keep self.total_cost_usd in managers

# CLI aggregates from managers
total_cost = (
    transcription_manager.total_cost_usd +
    extraction_engine.total_cost_usd +
    interview_manager.total_cost_usd
)
```

**Pros**:
- No global state
- Simple per-manager tracking

**Cons**:
- Loses centralized cost tracking
- Cannot track costs across episodes
- No persistent cost history
- Harder to add budgets/limits

**Effort**: Medium (remove global tracker, update CLI)
**Risk**: Medium (loses features)

## Recommended Action

**Implement Option 1: Single CostTracker with dependency injection**

Rationale:
1. Eliminates duplication (primary goal)
2. Enables advanced features (budgets, rollback)
3. Better testability (mock injection)
4. Single source of truth
5. Clean architecture (DI pattern)
6. Preserves cost history and reporting

## Technical Details

**Affected Files:**
- `src/inkwell/utils/costs.py` - Enhance with context manager
- `src/inkwell/extraction/engine.py` - Remove `self.total_cost_usd`, inject tracker
- `src/inkwell/transcription/manager.py` - Inject tracker
- `src/inkwell/interview/manager.py` - Inject tracker
- `src/inkwell/cli.py` - Create shared tracker, pass to managers

**Code changes:**

```diff
# extraction/engine.py
class ExtractionEngine:
-   def __init__(self, extractor: BaseExtractor | None = None):
+   def __init__(
+       self,
+       extractor: BaseExtractor | None = None,
+       cost_tracker: CostTracker | None = None
+   ):
        self.extractor = extractor
-       self.total_cost_usd = 0.0
+       self.cost_tracker = cost_tracker or get_cost_tracker()

    async def extract(self, ...):
-       self.total_cost_usd += cost
-       get_cost_tracker().track_cost("extraction", cost)
+       self.cost_tracker.add_cost(provider, tokens, cost)
```

**Database Changes**: No (costs.db already exists)

## Resources

- Architecture report: See architecture-strategist agent findings
- Dependency injection pattern: https://en.wikipedia.org/wiki/Dependency_injection
- Context managers in Python: https://docs.python.org/3/reference/datamodel.html#context-managers

## Acceptance Criteria

- [ ] `CostTracker` has `track_operation()` context manager
- [ ] All managers accept `cost_tracker` parameter
- [ ] `self.total_cost_usd` removed from managers
- [ ] CLI creates single `CostTracker` instance
- [ ] CLI passes tracker to all managers
- [ ] Cost rollback works on exceptions
- [ ] All tests pass with dependency injection
- [ ] Mock `CostTracker` used in unit tests
- [ ] Total cost displayed correctly at end of operation

## Work Log

### 2025-11-14 - Architecture Review Discovery
**By:** Claude Code Review System (architecture-strategist agent)
**Actions:**
- Discovered duplicate cost tracking systems
- Identified manual synchronization risks
- Found inconsistent cost data potential
- Proposed dependency injection solution
- Flagged as P2 architecture improvement

**Learnings:**
- Dual tracking systems create maintenance burden
- Single source of truth prevents inconsistencies
- Dependency injection enables testability
- Context managers provide clean transaction boundaries
- Cost tracking should be centralized for features like budgets

## Notes

**Why this matters:**
- Costs are critical for user budget management
- Inconsistent data undermines trust
- Single source of truth simplifies debugging
- Enables advanced features (alerts, limits)

**Testing with dependency injection:**
```python
# tests/unit/test_extraction_engine.py
def test_extraction_cost_tracking():
    """Verify cost tracking with mock tracker."""
    mock_tracker = Mock(spec=CostTracker)
    engine = ExtractionEngine(cost_tracker=mock_tracker)

    await engine.extract(template, transcript, {})

    # Verify cost was tracked
    mock_tracker.add_cost.assert_called_once_with(
        provider="gemini",
        tokens=1000,
        cost_usd=pytest.approx(0.05)
    )
```

**Rollback example:**
```python
# If extraction fails, costs are rolled back
with cost_tracker.track_operation("extraction", url):
    cost_tracker.add_cost("gemini", 1000, 0.05)
    # ... extraction fails here
    raise ExtractionError("Failed")
    # ✅ Cost of 0.05 is rolled back automatically
```

**Future enhancements:**
```python
# Add cost budgets
class CostTracker:
    def __init__(self, max_cost_usd: float | None = None):
        self.max_cost_usd = max_cost_usd

    def add_cost(self, ...):
        if self.max_cost_usd and self.total_cost > self.max_cost_usd:
            raise CostLimitExceededError(
                f"Cost limit ${self.max_cost_usd} exceeded"
            )
        self.total_cost += cost_usd
```

**Migration strategy:**
1. Enhance `CostTracker` with context manager
2. Add `cost_tracker` parameter to managers (default to global)
3. Update CLI to create shared tracker
4. Remove `self.total_cost_usd` from managers
5. Update tests to use mock tracker
6. Verify all cost tracking works end-to-end
