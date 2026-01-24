---
status: complete
priority: p2
issue_id: "087"
tags: [code-review, performance, scalability, pr-36]
dependencies: []
---

# Add Concurrency Limit for Parallel Feed Fetching

## Problem Statement

The `list latest` command fetches all configured feeds in parallel using `asyncio.gather()` with no concurrency limit. This can cause issues with many feeds:
- Connection exhaustion at OS level
- Rate limiting by feed hosts
- Memory pressure from concurrent HTTP clients

**Why it matters**: Users with 50-100+ feeds could experience command failures, rate limiting, or system instability.

## Findings

**Location**: `/Users/chekos/projects/gh/inkwell-cli/src/inkwell/cli_list.py`, lines 340-352

```python
tasks = [_fetch_latest_for_feed(parser, name, config) for name, config in feeds.items()]

# Fetch all feeds in parallel - NO LIMIT
if json_output:
    results = await asyncio.gather(*tasks)
else:
    with Progress(...) as progress:
        results = await asyncio.gather(*tasks)
```

**Scalability Impact**:

| Feed Count | Memory Usage | Concurrent Connections | Failure Risk |
|------------|--------------|------------------------|--------------|
| 10 feeds | ~50 MB | 10 concurrent | LOW |
| 50 feeds | ~250 MB | 50 concurrent | MEDIUM |
| 100 feeds | ~500 MB+ | 100 concurrent | HIGH |
| 500 feeds | ~2 GB+ | OS limit hit | VERY HIGH |

**Additional Issue**: Each call to `fetch_feed` creates a new `httpx.AsyncClient` instance (parser.py line 54), preventing connection reuse.

## Proposed Solutions

### Option A: Add Semaphore-based concurrency limit (Recommended)

**Pros**: Simple, effective, minimal code change
**Cons**: None significant
**Effort**: Small (30 minutes)
**Risk**: Very low

```python
MAX_CONCURRENT_FEEDS = 10

async def run_latest() -> None:
    manager = ConfigManager()
    feeds = manager.list_feeds()

    if not feeds:
        # ... early return

    parser = RSSParser()
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_FEEDS)

    async def fetch_with_limit(name: str, config: FeedConfig) -> LatestEpisodeResult:
        async with semaphore:
            return await _fetch_latest_for_feed(parser, name, config)

    tasks = [fetch_with_limit(name, config) for name, config in feeds.items()]

    # Rest unchanged
    results = await asyncio.gather(*tasks)
```

### Option B: Share HTTP client across all requests

**Pros**: Connection pooling for same-host feeds, ~30-50% latency reduction
**Cons**: Requires modifying RSSParser interface
**Effort**: Medium (2 hours)
**Risk**: Low

```python
async with httpx.AsyncClient(timeout=30, limits=httpx.Limits(max_connections=20)) as client:
    tasks = [_fetch_latest_for_feed(client, name, config) for ...]
```

### Option C: Both A and B

**Pros**: Maximum efficiency and safety
**Cons**: More code changes
**Effort**: Medium-Large (3 hours)
**Risk**: Low

## Recommended Action

**Start with Option A** (semaphore) for immediate protection, then consider Option B for a future performance optimization PR.

## Technical Details

**Affected Files**:
- `/Users/chekos/projects/gh/inkwell-cli/src/inkwell/cli_list.py`

**Constants to add**:
```python
MAX_CONCURRENT_FEEDS = 10  # Conservative default
```

## Acceptance Criteria

- [ ] Concurrent feed fetches limited to MAX_CONCURRENT_FEEDS
- [ ] Command works correctly with 1, 10, 50, 100 feeds
- [ ] No degradation in performance for small feed counts
- [ ] Test added for concurrency limiting behavior
- [ ] Existing tests still pass

## Work Log

| Date | Action | Notes |
|------|--------|-------|
| 2026-01-11 | Created | From PR #36 code review by performance-oracle agent |

## Resources

- PR #36: https://github.com/chekos/inkwell-cli/pull/36
- asyncio.Semaphore docs: https://docs.python.org/3/library/asyncio-sync.html#asyncio.Semaphore
- httpx connection limits: https://www.python-httpx.org/advanced/#pool-limit-configuration
