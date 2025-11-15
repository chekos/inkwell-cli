---
status: resolved
priority: p0
issue_id: "052"
tags: [pr-13, security, supply-chain, github-actions, critical]
dependencies: []
---

# Pin setup-python GitHub Action to SHA Hash

## Problem Statement

PR #13 successfully pins all GitHub Actions to immutable SHA hashes (TODO #047) to prevent supply chain attacks, but **one critical action was missed** in the release workflow:

```yaml
- uses: actions/setup-python@v5  # ❌ MUTABLE TAG
```

This creates an **inconsistent security posture** where 5 actions are properly secured but 1 remains vulnerable.

**Severity**: CRITICAL - Supply chain attack vector in release workflow

## Findings

- Discovered during comprehensive PR #13 security audit
- Location: `.github/workflows/release.yml` line 45
- All other actions properly pinned (5 total across 3 workflows)
- This action runs **before package build and PyPI publish** - most critical step
- The `v5` tag is mutable and can be modified by action maintainers

**Current Status**:
```yaml
# release.yml line 44-47
- name: Set up Python
  uses: actions/setup-python@v5  # ❌ NOT PINNED
  with:
    python-version: '3.10'
```

**Other Actions** (properly pinned):
```yaml
# ci.yml
actions/checkout@b4ffde65f46336ab88eb53be808477a3936bae11  # v4.2.2 ✅
astral-sh/setup-uv@fa7dbb46b0c4060a6b1f52f3e0c4a45c3df9e4b6  # v4.0.0 ✅
codecov/codecov-action@e28ff129e5465c2c0dcc6f003fc735cb6ae0c673  # v4.5.0 ✅

# release.yml
actions/checkout@b4ffde65f46336ab88eb53be808477a3936bae11  # v4.2.2 ✅
astral-sh/setup-uv@fa7dbb46b0c4060a6b1f52f3e0c4a45c3df9e4b6  # v4.0.0 ✅
pypa/gh-action-pypi-publish@ec4db0b4ddc65acdf4bff5fa45ac92d78b56bdf0  # release/v1 ✅

# docs.yml
actions/checkout@b4ffde65f46336ab88eb53be808477a3936bae11  # v4.2.2 ✅
astral-sh/setup-uv@fa7dbb46b0c4060a6b1f52f3e0c4a45c3df9e4b6  # v4.0.0 ✅
```

**Impact**:
- ⚠️ Supply chain attack vector remains in most critical workflow (release/publish)
- ⚠️ Inconsistent with PR #13 security objectives
- ⚠️ The v5 tag can be modified, introducing non-deterministic builds
- ⚠️ Undermines the supply chain hardening accomplished by TODO #047
- ⚠️ Official GitHub action (lower risk than third-party, but still vulnerable)

## Proposed Solutions

### Option 1: Pin to SHA Hash (Recommended)
**Pros**:
- Completes the supply chain security improvements
- Consistent with all other actions
- Prevents tag moving attacks
- Aligns with SLSA/CISA/NSA security recommendations

**Cons**:
- None

**Effort**: Small (2 minutes)
**Risk**: Low

**Implementation**:
```diff
- name: Set up Python
- uses: actions/setup-python@v5
+ uses: actions/setup-python@0b93645e9fea7318ecaed2b359559ac225c90a20  # v5.3.0
  with:
    python-version: '3.10'
```

**SHA Hash Source**: https://github.com/actions/setup-python/releases/tag/v5.3.0
**Verification**: `git ls-remote https://github.com/actions/setup-python.git v5.3.0`

### Option 2: Use uv python install (Alternative)
**Pros**:
- Removes dependency on third-party action entirely
- Consistent with CI workflows (already using `uv python install`)
- Simpler, fewer moving parts

**Cons**:
- Small change in behavior (uv manages Python instead of actions/setup-python)

**Effort**: Small (3 minutes)
**Risk**: Low

**Implementation**:
```diff
- name: Set up Python
- uses: actions/setup-python@v5
-   with:
-     python-version: '3.10'
+ run: uv python install 3.11
```

Note: Also update to Python 3.11 for consistency with CI workflows.

## Recommended Action

**IMMEDIATE**: Pin to SHA hash (Option 1)

This is a **blocking P0 issue** because:
1. It's the entire purpose of PR #13 TODO #047
2. Inconsistency undermines security posture
3. Release workflow is most critical (publishes to PyPI)
4. Quick fix (2 minutes)

## Technical Details

- **Affected Files**:
  - `.github/workflows/release.yml` (line 45)

- **Related Components**:
  - PyPI package publishing
  - Version validation workflow
  - Package build process

- **Supply Chain Security Context**:
  - This action runs before `uv build` and `pypa/gh-action-pypi-publish`
  - Compromised action could inject malicious code before package creation
  - Affects all users who install from PyPI

- **Database Changes**: No

## Resources

- Code review PR: #13
- Related issue: TODO #047 (pin GitHub Actions to SHA hashes)
- GitHub Actions security best practices: https://docs.github.com/en/actions/security-guides/security-hardening-for-github-actions#using-third-party-actions
- setup-python releases: https://github.com/actions/setup-python/releases

## Acceptance Criteria

- [ ] `actions/setup-python` pinned to SHA hash `0b93645e9fea7318ecaed2b359559ac225c90a20`
- [ ] Version comment added: `# v5.3.0`
- [ ] Release workflow syntax validated
- [ ] No other unpinned actions remain in any workflow
- [ ] Dependabot configured to update action SHAs (if not already)

## Work Log

### 2025-11-14 - Security Audit Discovery
**By:** Claude Code Security Audit (security-sentinel agent)
**Actions:**
- Discovered during comprehensive PR #13 security review
- Verified all other actions properly pinned (5/6)
- Identified inconsistency in release workflow
- Confirmed SHA hash for v5.3.0 from official repository
- Categorized as P0 due to security objective violation

**Learnings:**
- When pinning actions across multiple workflows, use checklist to verify all instances
- Release workflows are highest priority for supply chain security
- Official actions (GitHub-owned) are lower risk but should still be pinned
- Consistency matters - partial security improvements can create false confidence

## Notes

**Source:** PR #13 security audit performed on 2025-11-14
**Review command:** `/review pr13`
**Priority justification:** Undermines core PR objective (supply chain security)
**Quick fix:** Yes (2 minutes)
**Breaking change:** No
**Related compliance:** SLSA, CISA/NSA SCF, OpenSSF Scorecard
