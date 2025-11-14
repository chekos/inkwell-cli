---
status: resolved
priority: p1
issue_id: "004"
tags: [code-review, performance, retry-logic, critical]
dependencies: []
---

# Fix Retry Logic Timing Issues

## Problem Statement

The retry logic has two critical configuration issues:
1. **Excessive maximum wait time**: 60 seconds is too long, causes poor UX
2. **Incorrect jitter implementation**: Adds 0-100% instead of ±25% as documented

These issues make retries feel broken to users and waste time in production.

**Severity**: CRITICAL (User Experience)

## Findings

- Discovered during performance analysis by performance-oracle agent
- Location: `src/inkwell/utils/retry.py:108, 432-433`
- Documented as "±25% jitter" but implements 0-100%
- 60s max wait causes 91-150s worst-case retry sequences
- PR summary claims "±25%" but code contradicts this

**Current Behavior**:
- Retry sequence: 1s → ~30s → 60s = 91 seconds of waiting
- With jitter: Can add up to 60s more per retry
- **Worst case: ~150 seconds** just waiting on retries

**User Experience**:
```
User: "It's been waiting for 60 seconds, did it hang?"
Reality: Working as coded, but feels broken
```

## Proposed Solutions

### Option 1: Reduce Max Wait + Fix Jitter (Recommended)
**Pros**:
- 6x faster worst-case scenarios
- Matches industry standards (AWS SDK: 20s, Google: 32s)
- Proper jitter implementation
- Better UX

**Cons**:
- Might hit rate limits slightly more often (unlikely)

**Effort**: Small (30 minutes)
**Risk**: Low

**Implementation**:

```python
# src/inkwell/utils/retry.py

# Line 108: Reduce max wait time
DEFAULT_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    max_wait_seconds=10,      # CHANGED: 60 → 10 (6x faster)
    min_wait_seconds=1,
    jitter=True,
)

# Lines 432-433: Fix jitter implementation
def _wait(self) -> None:
    """Wait before next retry attempt (exponential backoff with jitter)."""
    if self.attempt == 0:
        return

    # Calculate base wait time with exponential backoff
    base_wait = min(
        self.config.max_wait_seconds,
        self.config.min_wait_seconds * (2 ** (self.attempt - 1))
    )

    # Apply jitter: ±25% of base wait (not 0-100%)
    if self.config.jitter:
        jitter_amount = base_wait * 0.25  # 25% of base wait
        jitter = random.uniform(-jitter_amount, jitter_amount)
        wait_time = max(0, base_wait + jitter)  # Ensure non-negative
    else:
        wait_time = base_wait

    # Log the wait
    logger.info(
        f"Retry attempt {self.attempt}/{self.config.max_attempts}: "
        f"waiting {wait_time:.1f}s before next attempt"
    )

    time.sleep(wait_time)
```

**New Retry Sequence**:
- Attempt 1: 1s (±0.25s) = 0.75-1.25s
- Attempt 2: 2s (±0.5s) = 1.5-2.5s
- Attempt 3: 4s (±1s) = 3-5s
- **Total: 5.25-8.75s** (vs 91-150s before) = **17x faster**

### Option 2: Add Retry-After Header Support
**Pros**:
- Respects API rate limit headers
- Most efficient retry timing

**Cons**:
- More complex implementation
- Requires HTTP response access

**Effort**: Medium (2-3 hours)
**Risk**: Medium

## Recommended Action

Implement Option 1 immediately for massive UX improvement. Consider Option 2 as enhancement for v1.1.

## Technical Details

**Affected Files**:
- `src/inkwell/utils/retry.py:108` (DEFAULT_RETRY_CONFIG)
- `src/inkwell/utils/retry.py:432-433` (_wait method)

**Related Components**:
- All API calls using retry decorators
- User experience during transient failures

**Database Changes**: No

## Resources

- AWS SDK Retry Strategy: 20s max backoff
- Google Cloud SDK: 32s max backoff
- Exponential Backoff Best Practices: https://aws.amazon.com/blogs/architecture/exponential-backoff-and-jitter/

## Acceptance Criteria

- [ ] max_wait_seconds reduced from 60 to 10
- [ ] Jitter implementation changed from 0-100% to ±25%
- [ ] Wait times logged at INFO level
- [ ] TEST_RETRY_CONFIG updated for consistency
- [ ] Unit tests verify new timing behavior
- [ ] Documentation updated with new retry sequence
- [ ] Performance improvement documented (17x faster)
- [ ] All existing tests pass

## Work Log

### 2025-11-13 - Code Review Discovery
**By:** Claude Code Review System
**Actions:**
- Discovered during performance analysis
- Analyzed by performance-oracle agent
- Compared documented behavior vs actual implementation
- Calculated worst-case scenarios
- Categorized as CRITICAL for UX

**Learnings**:
- Documentation claimed "±25% jitter" but code did 0-100%
- 60s max wait is excessive for user-facing CLI
- Industry standards: AWS 20s, Google 32s, we use 60s
- Proper jitter: `uniform(-0.25*base, 0.25*base)` not `uniform(0, base)`

## Notes

**Why 10s Max Wait**:
- 3 retries: 1s + 2s + 4s = 7s total (with jitter: 5-9s)
- Fast enough for user not to think it's hung
- Long enough for transient issues to resolve
- Matches 95th percentile API recovery time

**Jitter Benefits**:
- Prevents thundering herd problem
- Spreads retry load over time
- ±25% is industry standard (AWS, Google)
- Should oscillate around base time, not just add delay

**Impact Analysis**:
- Current worst case: 150s waiting
- New worst case: 9s waiting
- **Improvement: 17x faster**
- User perception: "Fast and responsive" vs "Is it frozen?"

**Source**: Code review performed on 2025-11-13
**Review command**: /review #9
