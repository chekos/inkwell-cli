# CI/CD Pipeline Excellence

**Category:** Testing | DX Improvement
**Priority:** Foundation - all 2026 initiatives depend on this
**Complexity:** Small (T-shirt Size S)

## Overview

Add automated testing to PRs. Currently, 200+ tests exist but only run locally via pre-commit hooks. A developer forgetting to run hooks can merge broken code to main.

## Problem Statement

- Tests don't run on pull requests
- No branch protection prevents broken code from merging
- Quality enforcement is local-only

## Proposed Solution

One workflow file. One job. Done in an hour.

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [main]
  pull_request:

jobs:
  ci:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
        with:
          enable-cache: true
      - run: uv sync --dev --frozen
      - run: uv run ruff check .
      - run: uv run ruff format --check .
      - run: uv run mypy src/
      - run: uv run pytest
```

Then enable branch protection requiring the `ci` job to pass.

## Implementation

### Prerequisites (Must Fix First)

Before CI can pass, these issues need resolution:

- [ ] Fix failing tests (if any exist)
- [ ] Verify `pytest-cov` is in `[dependency-groups].dev` in pyproject.toml

### Phase 1: Basic CI (2 hours)

**Deliverables:**
- [ ] Create `.github/workflows/ci.yml`
- [ ] Enable branch protection requiring CI to pass

**Files to create:**
- `.github/workflows/ci.yml`

### Phase 2: Coverage Reporting (Optional, defer)

Add Codecov integration when you want PR comments showing coverage changes.

**Deliverables:**
- [ ] Add `--cov` flags to pytest command
- [ ] Add Codecov action to workflow
- [ ] Set CODECOV_TOKEN in repository secrets

**Updated workflow:**
```yaml
- run: uv run pytest --cov=src/inkwell --cov-report=xml
- uses: codecov/codecov-action@v5
  with:
    token: ${{ secrets.CODECOV_TOKEN }}
    fail_ci_if_error: false  # Non-blocking initially
```

No `codecov.yml` needed - defaults work fine.

### Phase 3: Multi-Version Testing (Optional, defer)

Add Python version matrix when you encounter version-specific bugs.

**Updated workflow:**
```yaml
strategy:
  matrix:
    python-version: ["3.10", "3.11", "3.12"]
steps:
  - uses: astral-sh/setup-uv@v5
    with:
      python-version: ${{ matrix.python-version }}
```

## What's NOT in This Plan

These items were identified in the original roadmap but don't belong in CI/CD infrastructure:

| Item | Why Removed | Where It Belongs |
|------|-------------|------------------|
| Exception handler refactoring | Code quality, not CI | Separate issue: "Code Quality: Exception Handling" |
| Key rotation implementation | Feature development | Separate issue: "Feature: Key Rotation" |
| Issue templates | Nice-to-have | Add when you get confusing bug reports |
| Security scanning (Bandit) | Premature; no security incidents | Enable Dependabot instead (zero config) |
| README badges | Cosmetic | Add after CI is stable |

## Acceptance Criteria

- [ ] CI workflow runs on every PR and push to main
- [ ] Tests pass in CI
- [ ] Ruff linting passes in CI
- [ ] Mypy type checking passes in CI
- [ ] Branch protection blocks PRs that fail CI

## Branch Protection Configuration

Navigate to **Settings > Branches > Add rule** for `main`:

| Setting | Value |
|---------|-------|
| Require status checks | `ci` job |
| Require branches up to date | Enabled |
| Block force pushes | Enabled |

Reviews are optional for a single-maintainer project.

## Dependencies & Prerequisites

- Fix any failing tests before CI can pass
- Ensure dev dependencies are complete in pyproject.toml

## References

### Internal
- `docs/building-in-public/adr/007-enforce-pre-commit-hooks.md` - Pre-commit strategy
- `docs/building-in-public/adr/008-use-uv-for-python-tooling.md` - Package management

### External
- [astral-sh/setup-uv](https://github.com/astral-sh/setup-uv)

---

## Deferred Items (Create Separate Issues When Needed)

### Exception Handler Refactoring

The original plan identified 9 broad exception handlers. However, most are correct:
- CLI boundaries *should* catch `Exception` to show clean errors
- Cache cleanup *should* ignore deletion failures
- Template loading with fallbacks *should* continue on errors

Create a separate issue only if you have a bug caused by swallowed exceptions.

### Key Rotation

The `NotImplementedError` stub at `crypto.py:212` is fine. Implement when:
- A user actually requests it
- You have a clear threat model
- You understand the credential storage architecture (per-feed in `feeds.yaml`)

### Security Scanning

Instead of Bandit/pip-audit in CI, enable **Dependabot** in GitHub settings:
- Zero configuration
- Automatic PRs for vulnerable dependencies
- No false positives blocking your PRs
