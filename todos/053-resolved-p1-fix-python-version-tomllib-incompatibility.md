---
status: resolved
priority: p1
issue_id: "053"
tags: [pr-13, python-compatibility, release-workflow, runtime-error]
dependencies: []
---

# Fix Python Version Incompatibility (tomllib)

## Problem Statement

The release workflow's version validation script uses `tomllib` (Python 3.11+ only) but the workflow sets up Python 3.10, causing a guaranteed `ModuleNotFoundError`.

**Severity**: HIGH - Release workflow will fail 100% of the time when triggered

## Findings

- Discovered during PR #13 Python-specific code review
- Location: `.github/workflows/release.yml` lines 24-29 (validation script) and 45-47 (Python setup)
- `tomllib` is stdlib in Python 3.11+, not available in 3.10
- Project declares `requires-python = ">=3.10"` so Python 3.10 is valid target
- Other workflows (ci.yml, docs.yml) use Python 3.11 consistently

**Current Implementation**:
```yaml
# Line 24-29: Uses tomllib
- name: Validate version tag matches pyproject.toml
  run: |
    PKG_VERSION=$(python -c "
    import tomllib  # ❌ Only available in Python 3.11+
    with open('pyproject.toml', 'rb') as f:
        data = tomllib.load(f)
        print(data['project']['version'])
    ")

# Line 45-47: Sets up Python 3.10
- name: Set up Python
  uses: actions/setup-python@v5
  with:
    python-version: '3.10'  # ❌ Too old for tomllib
```

**Impact**:
- ❌ Version validation will fail with `ModuleNotFoundError: No module named 'tomllib'`
- ❌ Release workflow cannot complete successfully
- ❌ No releases can be published to PyPI
- ❌ Version validation never actually runs (fails before comparison)

**Error Message** (when triggered):
```
ModuleNotFoundError: No module named 'tomllib'
Error: Process completed with exit code 1.
```

## Proposed Solutions

### Option 1: Use Python 3.11 (Recommended)
**Pros**:
- Simplest fix (1 line change)
- Consistent with other workflows (ci.yml, docs.yml use 3.11)
- No additional dependencies
- Matches team's Python version choice

**Cons**:
- None

**Effort**: Small (1 minute)
**Risk**: None

**Implementation**:
```diff
- name: Set up Python
  uses: actions/setup-python@v5
  with:
-   python-version: '3.10'
+   python-version: '3.11'  # Required for tomllib stdlib module
```

### Option 2: Install tomli Backport
**Pros**:
- Keeps Python 3.10 if there's a specific reason
- Works on any Python version

**Cons**:
- Adds external dependency for version check
- More complex (requires pip install)
- Inconsistent with other workflows

**Effort**: Small (3 minutes)
**Risk**: Low

**Implementation**:
```diff
- name: Set up Python
  uses: actions/setup-python@v5
  with:
    python-version: '3.10'

+ - name: Install tomli for Python 3.10 compatibility
+   run: pip install tomli

  - name: Validate version tag matches pyproject.toml
    run: |
      TAG_VERSION=${GITHUB_REF#refs/tags/v}

      PKG_VERSION=$(python -c "
+     try:
+         import tomllib  # Python 3.11+
+     except ImportError:
+         import tomli as tomllib  # Python 3.10 backport
+
      with open('pyproject.toml', 'rb') as f:
          data = tomllib.load(f)
          print(data['project']['version'])
      ")
```

### Option 3: Use uv python install
**Pros**:
- Consistent with CI workflow pattern
- Removes dependency on actions/setup-python
- uv manages Python version

**Cons**:
- Requires unpinning or pinning setup-python action first (see TODO #052)

**Effort**: Small (2 minutes)
**Risk**: Low

**Implementation**:
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

## Recommended Action

**IMMEDIATE**: Use Python 3.11 (Option 1)

Rationale:
- Simplest, cleanest fix
- Aligns with other workflows
- No additional dependencies
- Python 3.11 is well-supported and stable

## Technical Details

- **Affected Files**:
  - `.github/workflows/release.yml` (line 47)

- **Related Components**:
  - Version validation step (depends on tomllib)
  - PyPI release process (blocked by validation failure)
  - Package publishing (never reached if validation fails)

- **Python Version Context**:
  - CI workflows: Python 3.11 (ci.yml lines 62, 88)
  - Docs workflow: Python 3.11 (docs.yml line 31)
  - Release workflow: Python 3.10 ← INCONSISTENT
  - Project requirement: `>=3.10` (supports both)

- **Database Changes**: No

## Resources

- Code review PR: #13
- Python tomllib docs: https://docs.python.org/3/library/tomllib.html
- tomli backport (if needed): https://pypi.org/project/tomli/
- Related issue: TODO #050 (version validation implementation)

## Acceptance Criteria

- [ ] Python version updated to 3.11 in release.yml
- [ ] `import tomllib` works in release workflow
- [ ] Version validation executes successfully
- [ ] Release workflow completes end-to-end
- [ ] Python version is consistent across all workflows (3.11)

## Work Log

### 2025-11-14 - Code Review Discovery
**By:** Claude Code Review System (kieran-python-reviewer agent)
**Actions:**
- Discovered during comprehensive PR #13 Python compatibility review
- Verified tomllib availability in Python versions
- Checked Python version configuration across all workflows
- Identified inconsistency between validation script and Python setup
- Confirmed 100% failure rate when workflow is triggered

**Learnings:**
- Always verify Python version compatibility for stdlib modules
- Check consistency of Python versions across all workflows
- tomllib is 3.11+ only (no backport in older versions)
- Version validation is critical path - must work reliably
- Testing workflows locally can catch these issues before merge

## Notes

**Source:** PR #13 code review performed on 2025-11-14
**Review command:** `/review pr13`
**Priority justification:** Blocks all releases, 100% failure rate
**Quick fix:** Yes (1 minute)
**Breaking change:** No
**Alternative:** Could use tomli backport, but Python 3.11 is simpler and consistent
