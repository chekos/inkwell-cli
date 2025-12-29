# Lesson: Pre-commit Hooks Must Be Actively Enforced

**Date:** 2025-11-06
**Author:** Sergio Sánchez
**Context:** PR #3 review revealed linting issues that pre-commit hooks should have caught

## What Happened

During code review of PR #3, Copilot identified 7 code quality issues:
- 5 unused imports (would be caught by Ruff F401)
- 1 missing f-string prefix (would be caught by Ruff F541)
- 1 empty except without comment (would be flagged by linters)

**The Problem:** We have Ruff configured correctly with pre-commit hooks in `.pre-commit-config.yaml`, but these issues still made it into the PR.

**Root Cause:** Pre-commit hooks weren't running before commits were pushed. Likely causes:
1. Developer didn't run `pre-commit install` after cloning
2. Commits made with `git commit --no-verify` to bypass hooks
3. Hooks not properly configured in developer's environment

## What We Learned

### Configuration ≠ Enforcement

Having tools configured in the repo doesn't mean they're being used:
- `.pre-commit-config.yaml` exists and is correct
- `pyproject.toml` has proper Ruff configuration
- But hooks weren't actually running during development

### The Gap in Developer Experience

There's a gap between:
1. Cloning the repo
2. Installing dependencies (`pip install -e ".[dev]"`)
3. **Installing pre-commit hooks** ← This step is missing from docs
4. Starting development

Most developers skip step 3 because it's not documented or enforced.

### Why This Matters

**Impact of missed linting:**
- Wastes reviewer time on trivial issues
- Creates noise in PR comments
- Requires follow-up commits to fix
- Reduces confidence in code quality
- Slows down development velocity

**Cost calculation:**
- 7 issues found in review
- ~5 minutes to review and comment
- ~10 minutes to fix and push
- Could have been caught in < 2 seconds at commit time

### Pre-commit Hooks Are Developer Tooling

Pre-commit hooks are not optional nice-to-haves - they're essential developer tooling that:
- Provide immediate feedback (faster than CI)
- Prevent broken commits (better than fixing later)
- Maintain consistent code quality (better than code review nitpicks)
- Save time for everyone (developer, reviewer, CI)

## What We'll Do Differently

### 1. Document Hook Installation

Add to README.md setup section:
```bash
# Install development dependencies
pip install -e ".[dev]"

# Install pre-commit hooks (REQUIRED)
pre-commit install
```

Make it clear this is **required**, not optional.

### 2. Add Verification Helpers

Create Makefile targets:
```makefile
setup-hooks:
    pre-commit install
    @echo "✓ Pre-commit hooks installed"

check-hooks:
    @pre-commit run --all-files
```

Developers can run `make setup-hooks` as part of onboarding.

### 3. Add CI Backup

When CI is set up, run the same Ruff checks:
- Catches bypassed hooks (`git commit --no-verify`)
- Verifies hooks are working correctly
- Prevents broken code from merging

### 4. Educate, Don't Block

**Don't:** Add git hooks that prevent commits
**Do:** Educate developers on why hooks matter

Some developers need to bypass hooks for legitimate reasons (emergency hotfixes, WIP commits). Trust but verify via CI.

### 5. Create CONTRIBUTING.md

Document the full development workflow:
- How to set up environment
- Why pre-commit hooks matter
- When it's okay to bypass (`--no-verify`)
- How to run checks manually

## Broader Lessons

### For Any Project with Linting

1. **Document installation explicitly** - Don't assume developers will figure it out
2. **Make it easy to verify** - Provide `make` or script to check setup
3. **Run same checks in CI** - Hooks are not enough on their own
4. **Show the value** - Explain why hooks save time
5. **Monitor compliance** - Check if hooks are actually running

### For Developer Experience

Good DX isn't just about having tools - it's about making tools **discoverable** and **easy to use**:
- ✅ Tools configured in repo
- ✅ Installation documented in README
- ✅ Verification helpers available
- ✅ CI enforces same standards
- ✅ Clear guidance on when/how to bypass

### For Code Quality

Code quality is a **team discipline**, not an individual responsibility:
- Linters catch mechanical issues
- Reviews focus on design/logic
- Pre-commit hooks enforce basics
- CI verifies compliance
- Documentation guides developers

## Related

- ADR: [ADR-007](../adr/007-enforce-pre-commit-hooks.md)
- Devlog: [2025-11-06 PR Review](../devlog/2025-11-06-pr-review-learnings.md)
- PR: #3

## Action Items

- [ ] Update README.md with pre-commit installation
- [ ] Add Makefile targets for hook setup/verification
- [ ] Create CONTRIBUTING.md with development workflow
- [ ] Plan CI integration to run Ruff checks
- [ ] Consider adding hook verification to onboarding checklist
