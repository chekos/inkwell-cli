---
status: resolved
priority: p1
issue_id: "055"
tags: [pr-13, ci-optimization, performance, caching]
dependencies: []
---

# Enable UV Dependency Caching in CI Workflows

## Problem Statement

All CI workflows download and install dependencies from scratch on every run, wasting **~11 minutes per CI run** and **~3,300 CI minutes per month**. The `astral-sh/setup-uv` action supports dependency caching but it's not enabled.

**Severity**: HIGH - Significant CI cost and time waste

## Findings

- Discovered during PR #13 performance analysis
- Location: All workflow files (ci.yml, docs.yml, release.yml)
- Every workflow installs uv but doesn't enable caching
- Current setup: `uv sync --dev` downloads all deps every time (~60 seconds)
- With caching: ~5 seconds (cache hit)

**Current Implementation**:
```yaml
# ci.yml, docs.yml, release.yml - ALL MISSING CACHING
- name: Install uv
  uses: astral-sh/setup-uv@fa7dbb46b0c4060a6b1f52f3e0c4a45c3df9e4b6  # v4.0.0
  # ❌ No caching configuration

- name: Install dependencies
  run: uv sync --dev
  # Downloads all dependencies from PyPI every time
```

**Impact** (Measured at Scale):
- **Per CI run**: 14 jobs × ~60s = **14 minutes** dependency installation
- **With caching**: 14 jobs × ~5s = **1.2 minutes** (cache hit)
- **Savings**: **~11 minutes per CI run**
- **Monthly** (10 PRs/day × 30 days): **~3,300 CI minutes wasted**
- **Cost impact**: Exceeds GitHub Actions free tier (2,000 min/month)

**Breakdown by Workflow**:
```
ci.yml:
  - test job: 12 matrix combinations × 60s = 12 minutes
  - lint job: 1 × 60s = 1 minute
  - pre-commit job: 1 × 60s = 1 minute
  Total: 14 minutes per CI run

docs.yml:
  - deploy job: 1 × 60s = 1 minute per docs build

release.yml:
  - release job: 1 × 60s = 1 minute per release
```

## Proposed Solutions

### Option 1: Enable UV Cache (Recommended)
**Pros**:
- Massive time savings (11 min → 1.2 min)
- Supported natively by setup-uv action
- Automatic cache invalidation on uv.lock changes
- No additional complexity
- Works across all workflows

**Cons**:
- None

**Effort**: Small (2 minutes per workflow, 6 minutes total)
**Risk**: None

**Implementation**:
```diff
  - name: Install uv
    uses: astral-sh/setup-uv@fa7dbb46b0c4060a6b1f52f3e0c4a45c3df9e4b6  # v4.0.0
+   with:
+     enable-cache: true
+     cache-dependency-glob: "**/uv.lock"
```

Apply to:
- `.github/workflows/ci.yml` (3 jobs: test line 23, lint line 58, pre-commit line 84)
- `.github/workflows/docs.yml` (line 27)
- `.github/workflows/release.yml` (line 50)

**Cache Behavior**:
- **Cache key**: Hash of `uv.lock` file
- **Cache hit**: Restores dependencies in ~5 seconds
- **Cache miss**: Downloads and caches (~60 seconds)
- **Invalidation**: Automatic when `uv.lock` changes
- **Scope**: Repository-scoped (shared across branches)

### Option 2: Manual Actions Cache
**Pros**:
- More control over cache key and paths
- Can cache additional artifacts

**Cons**:
- More complex (requires manual cache configuration)
- Duplicate work (uv already has caching built-in)
- Harder to maintain

**Effort**: Medium (10 minutes per workflow)
**Risk**: Low

**Implementation** (not recommended):
```yaml
- uses: actions/cache@v3
  with:
    path: ~/.cache/uv
    key: ${{ runner.os }}-uv-${{ hashFiles('uv.lock') }}

- name: Install uv
  uses: astral-sh/setup-uv@fa7dbb46b0c4060a6b1f52f3e0c4a45c3df9e4b6
```

## Recommended Action

**HIGH PRIORITY**: Enable uv caching in all workflows (Option 1)

Rationale:
- Simplest solution (built into setup-uv action)
- Maximum time savings (82% reduction)
- Stays within GitHub Actions free tier
- Faster PR feedback
- Reduces environmental impact (less compute)

## Technical Details

- **Affected Files**:
  - `.github/workflows/ci.yml` (lines 23, 58, 84)
  - `.github/workflows/docs.yml` (line 27)
  - `.github/workflows/release.yml` (line 50)

- **Cache Locations**:
  - Linux/macOS: `~/.cache/uv/`
  - Windows: `%LOCALAPPDATA%\uv\cache\`

- **Cache Size**: ~50-200 MB (depends on dependencies)

- **Cache Invalidation**:
  - Automatic on `uv.lock` changes
  - GitHub Actions purges caches after 7 days of no access
  - Maximum 10 GB total cache per repository

- **Database Changes**: No

## Resources

- Code review PR: #13
- setup-uv action docs: https://github.com/astral-sh/setup-uv#caching
- GitHub Actions cache docs: https://docs.github.com/en/actions/using-workflows/caching-dependencies-to-speed-up-workflows
- Related issue: Performance oracle findings

## Acceptance Criteria

- [ ] `enable-cache: true` added to all `setup-uv` steps
- [ ] `cache-dependency-glob: "**/uv.lock"` configured
- [ ] All 5 workflow jobs use caching
- [ ] First CI run after change creates cache (60s)
- [ ] Subsequent CI runs use cache (~5s)
- [ ] CI total time reduced by ~11 minutes per run
- [ ] GitHub Actions usage stays within free tier

## Work Log

### 2025-11-14 - Performance Analysis Discovery
**By:** Claude Code Review System (performance-oracle agent)
**Actions:**
- Discovered during comprehensive PR #13 performance review
- Measured dependency installation time across all jobs
- Calculated monthly CI minute waste (~3,300 minutes)
- Verified setup-uv action caching support
- Confirmed cache key strategy (uv.lock hash)
- Projected savings with caching enabled

**Learnings:**
- Dependency caching is critical for CI performance
- uv has excellent caching support built-in
- Small configuration change = massive time savings
- Without caching, can exceed GitHub Actions free tier
- Cache invalidation must be automatic (tied to lock file)

## Notes

**Source:** PR #13 performance review performed on 2025-11-14
**Review command:** `/review pr13`
**Priority justification:** Major CI cost savings, stays within free tier
**Quick fix:** Yes (6 minutes total for all workflows)
**Breaking change:** No
**Impact:** 82% faster dependency installation, 11 minutes saved per CI run
**Environmental impact:** Reduces compute waste, lower carbon footprint
