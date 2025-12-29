---
status: complete
priority: p3
issue_id: "070"
tags: [code-review, cicd, dx, pr-26]
dependencies: []
created: 2025-12-29
pr: "#26"
---

# Add CI Job Timeout

## Problem Statement

The CI workflow lacks a job timeout. Long-running or stuck jobs could consume GitHub Actions minutes indefinitely.

**Location**: `/Users/chekos/projects/gh/inkwell-cli/.github/workflows/ci.yml`

**Why It Matters**:
- Stuck jobs waste CI minutes
- No timeout means infinite wait for hung processes
- Default timeout is 6 hours (360 minutes)

## Findings

**Agent**: pattern-recognition-specialist

**Current Code**:
```yaml
jobs:
  ci:
    runs-on: ubuntu-latest
    steps:
      # ... no timeout specified
```

**Missing Configuration**:
```yaml
jobs:
  ci:
    runs-on: ubuntu-latest
    timeout-minutes: 15  # Should be added
```

## Proposed Solutions

### Option A: Add Job Timeout (Recommended)

**Pros**: Prevents runaway jobs, protects CI minutes
**Cons**: None
**Effort**: Trivial
**Risk**: None

```yaml
jobs:
  ci:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      # ...
```

15 minutes is generous for:
- ~1000 tests
- Lint/format checks
- Mypy type checking

### Option B: Add Step Timeouts

**Pros**: More granular control
**Cons**: More verbose
**Effort**: Small
**Risk**: None

```yaml
- name: Run tests
  run: uv run pytest
  timeout-minutes: 10
```

## Recommended Action

**Option A** - Add a single job-level timeout of 15 minutes. This is sufficient for the current test suite and prevents runaway jobs.

## Technical Details

**Affected Files**:
- `.github/workflows/ci.yml`

**Expected CI Duration**:
| Step | Estimated Time |
|------|---------------|
| uv sync | 5-15s (cached) |
| ruff check | 1-3s |
| ruff format | 1-2s |
| mypy | 10-30s |
| pytest (1000 tests) | 30-90s |
| **Total** | 50-140s |

15 minutes provides 10x headroom for slow runs.

## Acceptance Criteria

- [ ] `timeout-minutes: 15` added to CI job
- [ ] CI workflow passes

## Work Log

| Date | Action | Learning |
|------|--------|----------|
| 2025-12-29 | Created from PR #26 review | Job timeouts are CI hygiene |

## Resources

- **PR**: https://github.com/chekos/inkwell-cli/pull/26
- **GitHub Actions Timeouts**: https://docs.github.com/en/actions/using-workflows/workflow-syntax-for-github-actions#jobsjob_idtimeout-minutes
