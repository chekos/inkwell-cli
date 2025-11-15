---
status: resolved
priority: p0
issue_id: "046"
tags: [pr-11, code-review, data-integrity, dependencies, critical]
dependencies: []
---

# Fix Duplicate Dependency Declarations with Version Conflicts

## Problem Statement

The project declares development dependencies in BOTH `[project.optional-dependencies]` and `[dependency-groups]` with **conflicting version requirements**. This violates the single source of truth principle and creates non-deterministic builds.

**Severity**: CRITICAL - Will cause CI/CD failures and environment mismatches

## Findings

- Discovered during PR #11 code review by data-integrity-guardian agent
- Location: `pyproject.toml` lines 67-78 and 152-161
- Multiple packages declared twice with different version constraints
- Creates ambiguity in dependency resolution between `uv` and `pip`

**Conflicting Versions**:
```toml
# [project.optional-dependencies] (lines 67-78)
mypy>=1.8.0
pytest>=8.0.0
pytest-asyncio>=0.23.0
respx>=0.20.0
ruff>=0.3.0

# [dependency-groups] (lines 152-161)
mypy>=1.18.2        # 10 MINOR VERSIONS APART
pytest>=8.4.2
pytest-asyncio>=1.2.0  # MAJOR VERSION CHANGE
respx>=0.22.0
ruff>=0.14.4        # 11 MINOR VERSIONS APART
```

**Impact**:
- `uv sync --dev` uses `dependency-groups` (newer versions)
- `pip install -e .[dev]` uses `optional-dependencies` (older versions)
- CI/CD could install different versions than local development
- Lock file (`uv.lock`) may not reflect actual installed dependencies
- Type checking/testing tools may behave differently between environments

## Proposed Solutions

### Option 1: Remove optional-dependencies, Keep dependency-groups (Recommended)
**Pros**:
- PEP 735 `dependency-groups` is the modern standard
- This is what `uv` uses natively
- Aligns with ADR-008 (use uv for Python tooling)
- Single source of truth

**Cons**:
- Less compatible with traditional pip workflows
- Requires updating any documentation referencing `.[dev]`

**Effort**: Small (15 minutes)
**Risk**: Low

**Implementation**:
```diff
- [project.optional-dependencies]
- dev = [
-     "pytest>=8.0.0",
-     "pytest-cov>=4.1.0",
-     "pytest-mock>=3.12.0",
-     "pytest-asyncio>=0.23.0",
-     "ruff>=0.3.0",
-     "respx>=0.20.0",
-     "pre-commit>=3.6.0",
- ]

[dependency-groups]
dev = [
    "mkdocs>=1.6.1",
    "mkdocs-material>=9.6.23",
    "mkdocs-material-adr>=1.2.1",
    "pytest>=8.4.2",
    "pytest-asyncio>=1.2.0",
    "pytest-cov>=4.1.0",
    "pytest-mock>=3.15.1",
    "respx>=0.22.0",
    "ruff>=0.14.4",
    "mypy>=1.18.2",
    "types-pyyaml>=6.0.12.20250915",
    "types-aiofiles>=25.1.0.20251011",
    "types-regex>=2025.11.3.20251106",
    "pre-commit>=3.6.0",
]
```

### Option 2: Consolidate into optional-dependencies
**Pros**:
- Better pip compatibility
- More traditional approach

**Cons**:
- Goes against ADR-008 (uv tooling)
- PEP 735 is the future standard

**Effort**: Small (15 minutes)
**Risk**: Low

## Recommended Action

**Implement Option 1** - Remove `[project.optional-dependencies]` entirely, consolidate all dev dependencies into `[dependency-groups]`. This aligns with the project's choice to use `uv` as the primary package manager.

## Technical Details

**Affected Files**:
- `pyproject.toml` (lines 67-78 to be removed)
- `.github/CONTRIBUTING.md` (update installation instructions if needed)
- `README.md` (update installation instructions if needed)

**Related Components**:
- CI/CD workflows (already use `uv sync --dev`)
- Local development setup
- Docker build process

**Testing Requirements**:
- Verify `uv sync --dev` installs all dependencies
- Verify tests pass with unified dependencies
- Verify linters (ruff, mypy) work correctly
- Verify pre-commit hooks work

## Acceptance Criteria

- [ ] Remove `[project.optional-dependencies]` section from pyproject.toml
- [ ] Verify all dependencies consolidated into `[dependency-groups]`
- [ ] Update uv.lock file (`uv sync --dev`)
- [ ] All tests pass locally
- [ ] CI workflows pass
- [ ] Documentation updated if installation commands changed

## Work Log

### 2025-11-14 - Code Review Discovery
**By:** Claude Code Review System (PR #11 Review)
**Actions:**
- Discovered during comprehensive data integrity audit
- Analyzed by data-integrity-guardian agent
- Categorized as P0 CRITICAL priority
- Identified version conflicts across 5+ packages

**Learnings:**
- Duplicate dependency declarations create non-deterministic builds
- PEP 735 `dependency-groups` is the modern standard for `uv`
- Always maintain single source of truth for dependencies

## Notes

**Related Issues**:
- PR #11: Production-grade documentation upgrade
- ADR-008: Use uv for Python tooling

**Reference**:
- PEP 621: Project metadata in pyproject.toml
- PEP 735: Dependency groups (experimental, but uv standard)

**Source**: Code review performed on 2025-11-14
**Review command**: /review pr11
