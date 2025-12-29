---
title: ADR 007 - Enforce Pre-commit Hooks for Code Quality
adr:
  author: Claude
  created: 06-Nov-2025
  status: accepted
---

# ADR 007: Enforce Pre-commit Hooks for Code Quality

**Date:** 2025-11-06
**Status:** Accepted

## Context

During PR review for Phase 1 (#3), Copilot identified 7 code quality issues that Ruff should have caught:
- 5 unused imports (F401)
- 1 missing f-string prefix (F541)
- 1 empty except clause without comment

We have Ruff configured with pre-commit hooks (`.pre-commit-config.yaml`) that should catch these issues, but they weren't triggered before the code was pushed. This suggests pre-commit hooks weren't installed or were bypassed during commit.

**Problem:** Code quality issues that tooling should catch are making it into PRs, creating noise in code reviews and requiring manual fixes.

## Decision

We will enforce pre-commit hooks through multiple mechanisms:

1. **Documentation:** Add pre-commit hook installation to the setup instructions in README.md
2. **Verification:** Add a Makefile target to verify hooks are installed
3. **CI Check:** Future CI pipeline will run Ruff to catch bypassed hooks
4. **Developer Education:** Document why hooks matter and how to properly use them

We will NOT add git commit-msg hooks that block commits without verification, as this can frustrate developers in legitimate edge cases.

## Consequences

### Benefits
- Catches lint issues (unused imports, f-strings, etc.) before commit
- Reduces noise in code reviews
- Maintains consistent code quality
- Developers get immediate feedback in their editor/terminal

### Trade-offs
- Adds ~1-2 seconds to commit time (Ruff is fast)
- Developers might bypass with `--no-verify` in frustration
- Requires education about proper git workflow

### Risks
- Developers might not install hooks despite documentation
- Pre-commit hook updates require manual `pre-commit autoupdate`

### Mitigations
- Clear setup documentation
- Makefile helper: `make setup-hooks`
- CI will catch bypassed hooks (future)
- Periodic reminders in team communications

## Alternatives Considered

1. **Rely on CI only** — Slower feedback loop, wastes CI resources
2. **Git server-side hooks** — Requires infrastructure we don't have yet
3. **Mandatory commit-msg hooks** — Too rigid, blocks legitimate edge cases
4. **IDE integration only** — Not all developers use same IDE

## Implementation

Add to README.md:
```bash
# After installing dependencies
pre-commit install
```

Add Makefile target:
```makefile
setup-hooks:
	pre-commit install
	@echo "✓ Pre-commit hooks installed"

check-hooks:
	@pre-commit run --all-files || echo "Run 'make setup-hooks' to install"
```

## References

- PR #3: https://github.com/chekos/inkwell-cli/pull/3
- Ruff rules: F401 (unused imports), F541 (f-string missing)
- Pre-commit docs: https://pre-commit.com/
