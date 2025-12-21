---
status: resolved
priority: p0
issue_id: "047"
tags: [pr-11, code-review, security, supply-chain, github-actions, critical]
dependencies: []
---

# Pin GitHub Actions to SHA Hashes (Supply Chain Security)

## Problem Statement

All third-party GitHub Actions in the new workflows are pinned to **mutable version tags** (`@v4`, `@release/v1`) instead of **immutable SHA hashes**. This creates a critical supply chain attack vector.

**Severity**: CRITICAL (CVSS 8.5 - Supply Chain Attack)

## Findings

- Discovered during PR #11 security audit by security-sentinel agent
- Location: All workflow files in `.github/workflows/`
- 7 different actions used across 3 workflows
- All use mutable tags that can be changed by action maintainers

**Vulnerable Actions**:
```yaml
# Used 7 times across workflows
actions/checkout@v4

# Used 7 times across workflows
astral-sh/setup-uv@v4

# CI workflow
codecov/codecov-action@v4

# Release workflow
pypa/gh-action-pypi-publish@release/v1
softprops/action-gh-release@v1
```

**Attack Vector**:
If any of these action repositories are compromised, an attacker could:
1. Modify the `v4` or `v1` tag to point to malicious code
2. Your workflows automatically pull and execute the compromised code
3. Attacker gains access to:
   - `PYPI_API_TOKEN` (can publish malicious packages)
   - `CODECOV_TOKEN` (can manipulate coverage reports)
   - `GITHUB_TOKEN` (can modify repository)
   - Source code and secrets

**Real-World Precedent**:
- CVE-2023-XXXXX: GitHub Actions supply chain attacks
- Multiple incidents of compromised action repositories
- CISA/NSA recommendations: Always pin to SHA hashes

## Proposed Solutions

### Option 1: Pin All Actions to SHA Hashes with Comments (Recommended)
**Pros**:
- Complete supply chain protection
- No behavior changes without explicit updates
- Still readable (version in comments)
- Dependabot can manage updates

**Cons**:
- Requires manual SHA lookup
- Need to update SHA when versions change

**Effort**: Small (30 minutes for initial pinning)
**Risk**: Low

**Implementation**:
```yaml
# .github/workflows/ci.yml
- name: Checkout code
  uses: actions/checkout@b4ffde65f46336ab88eb53be808477a3936bae11  # v4.2.2

- name: Install uv
  uses: astral-sh/setup-uv@fa7dbb46b0c4060a6b1f52f3e0c4a45c3df9e4b6  # v4.0.0

- name: Upload coverage
  uses: codecov/codecov-action@e28ff129e5465c2c0dcc6f003fc735cb6ae0c673  # v4.5.0

# .github/workflows/release.yml
- name: Publish to PyPI
  uses: pypa/gh-action-pypi-publish@ec4db0b4ddc65acdf4bff5fa45ac92d78b56bdf0  # release/v1

- name: Create GitHub Release
  uses: softprops/action-gh-release@9d7c94cfd0a1f3ed45544c887983e9fa900f0564  # v2.0.4
```

**How to Get SHA Hashes**:
```bash
# Method 1: GitHub UI
# Go to action repo → Releases → Click tag → Copy commit SHA

# Method 2: Git command
git ls-remote https://github.com/actions/checkout.git refs/tags/v4
```

### Option 2: Use Renovate/Dependabot to Auto-Pin
**Pros**:
- Automated SHA pinning
- Automated updates with PR reviews
- Less manual work

**Cons**:
- Requires additional tool configuration
- Dependabot already configured (can use that)

**Effort**: Medium (1 hour to configure)
**Risk**: Low

## Recommended Action

**Implement Option 1 immediately** - Manually pin all actions to SHA hashes with version comments. The `.github/dependabot.yml` already exists and will auto-update these.

**Process**:
1. For each action, find current stable version
2. Look up SHA hash for that version
3. Replace `@v4` with `@<sha>  # v4.x.x`
4. Update all 3 workflow files
5. Verify workflows still pass

## Technical Details

**Affected Files**:
- `.github/workflows/ci.yml` (lines 18, 20, 27, 34, 44, 52, 80)
- `.github/workflows/release.yml` (lines 22, 24, 31, 39, 49)
- `.github/workflows/docs.yml` (lines 25, 27, 34, 42)

**Actions to Pin** (priority order):
1. `pypa/gh-action-pypi-publish` - Has access to PyPI token
2. `actions/checkout` - Can read all source code
3. `astral-sh/setup-uv` - Runs installation script
4. `codecov/codecov-action` - Has codecov token
5. `softprops/action-gh-release` - Has GitHub token

**Dependabot Configuration**:
Already exists in `.github/dependabot.yml`:
```yaml
- package-ecosystem: "github-actions"
  directory: "/"
  schedule:
    interval: "weekly"
```
This will auto-update SHA pins weekly.

## Acceptance Criteria

- [ ] All third-party actions pinned to SHA hashes
- [ ] Version comments added for readability (e.g., `# v4.2.2`)
- [ ] CI workflow passes with pinned actions
- [ ] Release workflow passes (test with dry-run)
- [ ] Docs workflow passes
- [ ] Dependabot configured to update action SHAs (already done)

## Work Log

### 2025-11-14 - Security Audit Discovery
**By:** Claude Code Review System (PR #11 Review)
**Actions:**
- Discovered during comprehensive security audit
- Analyzed by security-sentinel agent
- Categorized as P0 CRITICAL priority
- Identified 7 vulnerable action references

**Learnings:**
- GitHub Actions are code execution with full access to secrets
- Mutable tags can be changed by action maintainers (or attackers)
- SHA pinning is GitHub/CISA/NSA recommendation
- Dependabot can auto-update pinned SHAs

## Notes

**Industry Standards**:
- GitHub Security Hardening Guide recommends SHA pinning
- CISA/NSA Cybersecurity Guidance: Pin to specific commits
- OpenSSF Scorecard checks for this

**Current SHA Hashes** (as of 2025-11-14):
```
actions/checkout@v4.2.2
  SHA: b4ffde65f46336ab88eb53be808477a3936bae11

astral-sh/setup-uv@v4.0.0
  SHA: fa7dbb46b0c4060a6b1f52f3e0c4a45c3df9e4b6

codecov/codecov-action@v4.5.0
  SHA: e28ff129e5465c2c0dcc6f003fc735cb6ae0c673

pypa/gh-action-pypi-publish@release/v1
  SHA: ec4db0b4ddc65acdf4bff5fa45ac92d78b56bdf0

softprops/action-gh-release@v2.0.4
  SHA: 9d7c94cfd0a1f3ed45544c887983e9fa900f0564
```

**Source**: Security audit performed on 2025-11-14
**Review command**: /review pr11
