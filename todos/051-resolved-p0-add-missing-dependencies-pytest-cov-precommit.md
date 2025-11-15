---
status: resolved
priority: p0
issue_id: "051"
tags: [pr-13, code-review, dependencies, critical, build-breaking]
dependencies: []
---

# Add Missing Critical Dependencies (pytest-cov, pre-commit)

## Problem Statement

When consolidating dependencies from `[project.optional-dependencies]` to `[dependency-groups]` in PR #13, **two critical packages were accidentally omitted**:
- `pytest-cov>=4.1.0` - Required by CI workflow
- `pre-commit>=3.6.0` - Required by CI workflow

This creates a **broken build** where CI workflows expect dependencies that are not declared in `pyproject.toml`.

**Severity**: CRITICAL - 100% guaranteed CI failure

## Findings

- Discovered during comprehensive PR #13 code review
- Location: `pyproject.toml` lines 119-135 (dependency-groups section)
- CI workflows reference these packages:
  - `.github/workflows/ci.yml` line 38: `uv run pytest --cov=inkwell`
  - `.github/workflows/ci.yml` line 94: `uv run pre-commit run --all-files`
- Packages exist in old `[project.optional-dependencies]` but missing in new `[dependency-groups]`

**Impact**:
- ❌ CI test job WILL FAIL when attempting `pytest --cov=inkwell`
- ❌ CI pre-commit job WILL FAIL when attempting `pre-commit run`
- ❌ 100% guaranteed CI failure on every PR
- ❌ Breaks referential integrity between workflows and dependency declarations
- ❌ Violates single source of truth principle

**Original Configuration** (before PR #13):
```toml
[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-cov>=4.1.0",      # ← WAS HERE
    "pytest-mock>=3.12.0",
    "pytest-asyncio>=0.23.0",
    "ruff>=0.3.0",
    "mypy>=1.8.0",
    "pre-commit>=3.6.0",      # ← WAS HERE
    "types-pyyaml",
    "respx>=0.20.0",
]
```

**Current Configuration** (PR #13):
```toml
[dependency-groups]
dev = [
    "mkdocs>=1.6.1",
    "mkdocs-material>=9.6.23",
    "mkdocs-material-adr>=1.2.1",
    "mypy>=1.18.2",
    "pytest>=8.4.2",
    "pytest-asyncio>=1.2.0",
    "pytest-mock>=3.15.1",
    # ❌ pytest-cov MISSING
    # ❌ pre-commit MISSING
    "respx>=0.22.0",
    "ruff>=0.14.4",
    "types-aiofiles>=25.1.0.20251011",
    "types-pyyaml>=6.0.12.20250915",
    "types-regex>=2025.11.3.20251106",
    "types-requests>=2.32.4.20250913",
    "types-setuptools>=80.9.0.20250822",
]
```

## Proposed Solutions

### Option 1: Add Missing Dependencies (Recommended)
**Pros**:
- Fixes CI failures immediately
- Maintains all CI workflow functionality
- Minimal change to PR #13 scope
- Preserves coverage reporting
- Keeps pre-commit hooks functional

**Cons**:
- None

**Effort**: Small (5 minutes)
**Risk**: Low

**Implementation**:
```diff
[dependency-groups]
dev = [
    "mkdocs>=1.6.1",
    "mkdocs-material>=9.6.23",
    "mkdocs-material-adr>=1.2.1",
    "mypy>=1.18.2",
    "pytest>=8.4.2",
    "pytest-asyncio>=1.2.0",
+   "pytest-cov>=4.1.0",
    "pytest-mock>=3.15.1",
+   "pre-commit>=3.6.0",
    "respx>=0.22.0",
    "ruff>=0.14.4",
    "types-aiofiles>=25.1.0.20251011",
    "types-pyyaml>=6.0.12.20250915",
    "types-regex>=2025.11.3.20251106",
    "types-requests>=2.32.4.20250913",
    "types-setuptools>=80.9.0.20250822",
]
```

Then run:
```bash
uv sync --dev
uv lock
```

## Recommended Action

**IMMEDIATE**: Add both missing dependencies to `[dependency-groups].dev`

This is a **blocking P0 issue** - PR #13 cannot be merged without this fix.

## Technical Details

- **Affected Files**:
  - `pyproject.toml` (dependency declaration)
  - `uv.lock` (will be updated after adding deps)
  - `.github/workflows/ci.yml` (references both packages)

- **Related Components**:
  - CI/CD workflows
  - Testing infrastructure
  - Pre-commit hooks
  - Coverage reporting

- **Database Changes**: No

## Resources

- Code review PR: #13
- Related issue: TODO #046 (dependency consolidation)
- CI workflow: `.github/workflows/ci.yml`

## Acceptance Criteria

- [ ] `pytest-cov>=4.1.0` added to `[dependency-groups].dev`
- [ ] `pre-commit>=3.6.0` added to `[dependency-groups].dev`
- [ ] `uv sync --dev` executes successfully
- [ ] `uv lock` completes and updates lock file
- [ ] `uv run pytest --cov=inkwell` executes successfully
- [ ] `uv run pre-commit run --all-files` executes successfully
- [ ] CI workflows pass on PR #13

## Work Log

### 2025-11-14 - Code Review Discovery
**By:** Claude Code Review System (Multi-Agent Analysis)
**Actions:**
- Discovered during comprehensive PR #13 code review
- Analyzed by kieran-python-reviewer and data-integrity-guardian agents
- Identified missing packages in dependency consolidation
- Verified CI workflow requirements
- Confirmed 100% failure rate without fix

**Learnings:**
- Dependency consolidation requires careful verification of all referenced packages
- CI workflows must be checked against declared dependencies
- Lock file sync alone doesn't catch missing dependency declarations
- Always verify workflows can execute after dependency changes

## Notes

**Source:** PR #13 code review performed on 2025-11-14
**Review command:** `/review pr13`
**Priority justification:** Blocking CI failure, prevents all PR merges
**Quick fix:** Yes (5 minutes)
**Breaking change:** No (adds missing functionality)
