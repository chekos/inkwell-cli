# CI/CD Pipeline Excellence

**Category:** Testing | DX Improvement
**Quarter:** Q1
**T-shirt Size:** M

## Why This Matters

Inkwell has achieved production-ready status with 200+ tests and 100% pass rate, but this quality is enforced only locally through pre-commit hooks. There is no automated testing in the CI/CD pipeline—tests don't run on pull requests, coverage isn't tracked, and there are no required status checks. This creates significant risk: a single developer forgetting to run pre-commit hooks can merge broken code directly to main.

This initiative is foundational. Every other 2026 initiative depends on a reliable quality gate. You cannot safely refactor the CLI module (1,231 lines), add plugin architecture, or expand to new content types without automated verification that changes don't break existing functionality. The security gap around key rotation (`crypto.py:223`) also needs addressing before enterprise adoption.

## Current State

**What exists:**
- 200+ comprehensive tests (unit, integration, E2E)
- Pre-commit hooks configured (ruff, mypy)
- Test infrastructure in `tests/` with fixtures, mocks, async support
- Coverage tooling configured but not enforced (`pytest-cov`)
- Two GitHub Actions workflows: docs deployment and PyPI publishing

**What's missing:**
- No test execution on pull requests
- No coverage reporting or minimum thresholds
- No linting/type-checking in CI
- No branch protection rules
- No security scanning (SAST, dependency audits)
- Key rotation not implemented (security debt from `crypto.py`)
- 9 broad exception handlers that hide error root causes

**Files of concern:**
- `src/inkwell/config/crypto.py:223` - `NotImplementedError` for key rotation
- `.github/workflows/` - Missing test workflow
- `src/inkwell/cli.py` - 1,231 lines with complex `fetch_command`

## Proposed Future State

A world-class CI/CD pipeline that:

1. **Runs on every PR:**
   - Full test suite execution across Python 3.10, 3.11, 3.12
   - Ruff linting and mypy type checking
   - Coverage reporting with 80% minimum threshold
   - Security scanning (Bandit, Safety, pip-audit)

2. **Provides visibility:**
   - Coverage badges in README
   - PR comments with test/coverage status
   - Trend tracking over time

3. **Enforces quality:**
   - Branch protection requiring all checks to pass
   - No direct pushes to main
   - Required review before merge

4. **Addresses security debt:**
   - Key rotation implemented and tested
   - Broad exception handlers replaced with specific types
   - Credential handling audited

## Key Deliverables

- [ ] Create `.github/workflows/test.yml` running pytest on PR and push to main
- [ ] Add coverage reporting with Codecov or similar
- [ ] Add ruff and mypy checks to CI workflow
- [ ] Configure branch protection rules in repository settings
- [ ] Add security scanning (Bandit for SAST, Safety for dependencies)
- [ ] Implement key rotation in `src/inkwell/config/crypto.py`
- [ ] Create `.github/ISSUE_TEMPLATE/` with bug report and feature request templates
- [ ] Replace broad `except Exception:` handlers with specific exception types (9 instances)
- [ ] Add README badges for tests, coverage, and security status
- [ ] Document testing requirements in developer guide

## Prerequisites

None—this is the foundation everything else builds on.

## Risks & Open Questions

- **Risk:** Coverage threshold may initially fail if coverage is lower than expected. Mitigation: Start with measured baseline, increase gradually.
- **Risk:** Security scanning may find false positives. Mitigation: Configure allowlists for known safe patterns.
- **Question:** Should we use Codecov (free for open source) or GitHub's built-in coverage?
- **Question:** What's the right coverage threshold to start with? 80% is industry standard.
- **Question:** Should we add performance regression testing in CI?

## Notes

**Related ADRs:**
- `docs/building-in-public/adr/007-enforce-pre-commit-hooks.md` - Pre-commit strategy
- `docs/building-in-public/adr/008-use-uv-for-python-tooling.md` - Package management

**Specific code concerns:**
- `src/inkwell/utils/cache.py:322` - Silent file deletion errors
- `src/inkwell/utils/costs.py:255,375` - Broad exception in atomic writes
- `src/inkwell/config/manager.py:100,171` - Silent failures during config operations
- `src/inkwell/cli.py:265` - Silently skips malformed episodes

**Test infrastructure files:**
- `tests/conftest.py` - Shared fixtures
- `pyproject.toml` - pytest and coverage configuration
