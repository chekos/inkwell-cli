---
status: pending
priority: p2
issue_id: "057"
tags: [pr-13, consistency, configuration]
dependencies: ["053"]
---

# Standardize Python Versions Across Workflows

## Problem Statement

Python versions are inconsistent across workflows:
- CI workflow: Python 3.11
- Docs workflow: Python 3.11
- Release workflow: Python 3.10

This inconsistency suggests lack of intentionality and makes debugging release-specific issues harder.

**Severity**: MEDIUM - Configuration drift, potential for subtle bugs

## Findings

- Discovered during PR #13 architecture and data integrity review
- Location: Multiple workflow files
- No clear reason for release workflow to use different Python version
- Inconsistency makes release issues harder to reproduce locally

**Current State**:
```yaml
# ci.yml (3 occurrences)
- run: uv python install 3.11  # Line 62 (lint job)
- run: uv python install 3.11  # Line 88 (pre-commit job)
# (test job uses matrix: 3.10, 3.11, 3.12, 3.13)

# docs.yml
- run: uv python install 3.11  # Line 31

# release.yml
- uses: actions/setup-python@v5  # Line 45
  with:
    python-version: '3.10'  # ← DIFFERENT
```

**Impact**:
- 🤔 Suggests lack of intentional design
- 🐛 Release-specific issues harder to reproduce
- 📝 Maintenance confusion (which version is canonical?)
- ⚠️ Causes issue in TODO #053 (tomllib incompatibility)

## Proposed Solutions

### Option 1: Standardize on Python 3.11 (Recommended)
**Pros**:
- Consistent with 3 out of 4 workflow configurations
- Matches CI/docs workflows
- Resolves TODO #053 (tomllib incompatibility)
- Python 3.11 is stable and well-supported
- Simplifies debugging (same Python everywhere)

**Cons**:
- None (3.11 is newer and better than 3.10)

**Effort**: Small (1 minute)
**Risk**: None

**Implementation**:
```diff
# .github/workflows/release.yml

  - name: Set up Python
    uses: actions/setup-python@v5
    with:
-     python-version: '3.10'
+     python-version: '3.11'
```

Or better yet, use uv for consistency:
```diff
  - name: Install uv
    uses: astral-sh/setup-uv@fa7dbb46b0c4060a6b1f52f3e0c4a45c3df9e4b6
+   with:
+     enable-cache: true

- - name: Set up Python
-   uses: actions/setup-python@v5
-   with:
-     python-version: '3.10'
+ - name: Set up Python
+   run: uv python install 3.11
```

### Option 2: Extract to Workflow Variable
**Pros**:
- Single source of truth for Python version
- Easy to update all workflows at once

**Cons**:
- More complex (requires workflow-level env vars)
- GitHub Actions doesn't support cross-file constants

**Effort**: Medium (10 minutes)
**Risk**: Low

**Implementation**:
```yaml
# Each workflow file
env:
  DEFAULT_PYTHON_VERSION: '3.11'

# Then use:
- run: uv python install ${{ env.DEFAULT_PYTHON_VERSION }}
```

### Option 3: Document Why 3.10 is Used
**Pros**:
- Keeps current configuration
- Adds clarity if there's a reason

**Cons**:
- Only helpful if there's actually a reason (there isn't)
- Still inconsistent
- Doesn't resolve TODO #053

**Effort**: Small (add comment)
**Risk**: None

## Recommended Action

**MEDIUM PRIORITY**: Standardize on Python 3.11 (Option 1)

Rationale:
- Simplest solution
- Aligns with majority of workflows
- Resolves TODO #053 (tomllib issue)
- No downside

**Dependency**: Should be done when fixing TODO #053

## Technical Details

- **Affected Files**:
  - `.github/workflows/release.yml` (line 45-47)

- **Current Python Version Distribution**:
  - Python 3.11: 3 workflows (ci.yml lint, ci.yml pre-commit, docs.yml)
  - Python 3.10: 1 workflow (release.yml)
  - Python 3.10-3.13: 1 workflow (ci.yml test matrix)

- **Project Requirements**:
  - `pyproject.toml`: `requires-python = ">=3.10"`
  - Supports: 3.10, 3.11, 3.12, 3.13 (all tested in matrix)

- **Related Issues**:
  - TODO #053: release.yml uses 3.10 but needs 3.11 for tomllib
  - TODO #052: release.yml uses actions/setup-python (inconsistent with others)

- **Database Changes**: No

## Resources

- Code review PR: #13
- Related issue: TODO #053 (Python version incompatibility)
- Related issue: TODO #052 (unpinned action)
- Python 3.11 release notes: https://docs.python.org/3/whatsnew/3.11.html

## Acceptance Criteria

- [ ] All non-matrix workflows use Python 3.11
- [ ] Release workflow updated to 3.11
- [ ] No Python version inconsistencies across workflows
- [ ] Release workflow passes successfully
- [ ] Version validation works (tomllib available)

## Work Log

### 2025-11-14 - Consistency Review Discovery
**By:** Claude Code Review System (architecture-strategist + data-integrity-guardian agents)
**Actions:**
- Discovered during comprehensive PR #13 architecture review
- Mapped Python versions across all workflows
- Identified inconsistency in release workflow
- Verified no technical reason for difference
- Linked to TODO #053 (tomllib compatibility issue)

**Learnings:**
- Configuration consistency matters for debuggability
- Inconsistencies often indicate lack of intentional design
- Python version should be uniform across deployment workflows
- When most workflows agree, align outliers with majority
- Document if there's a real reason for difference

## Notes

**Source:** PR #13 architecture review performed on 2025-11-14
**Review command:** `/review pr13`
**Priority justification:** Configuration drift, affects debugging
**Quick fix:** Yes (1 minute)
**Breaking change:** No
**Related:** Should be done alongside TODO #053
**Impact:** Consistency, clarity, easier maintenance
