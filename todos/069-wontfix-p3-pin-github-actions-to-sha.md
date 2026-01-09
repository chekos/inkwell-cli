---
status: wontfix
priority: p3
issue_id: "069"
tags: [code-review, security, cicd, pr-26]
dependencies: []
created: 2025-12-29
pr: "#26"
---

# Pin GitHub Actions to SHA Commits

## Problem Statement

The CI workflow uses version tags (v4, v5) for GitHub Actions instead of SHA commits. This exposes the project to potential supply chain attacks if action tags are mutated.

**Location**: `/Users/chekos/projects/gh/inkwell-cli/.github/workflows/ci.yml` (lines 15, 17-18)

**Why It Matters**:
- Version tags can be moved to point to different commits
- Attackers who compromise action repos could inject malicious code
- SHA pinning provides immutable references

## Findings

**Agent**: security-sentinel

**Current Code**:
```yaml
- uses: actions/checkout@v4
- uses: astral-sh/setup-uv@v5
```

**Recommended Pattern**:
```yaml
- uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683  # v4.2.2
- uses: astral-sh/setup-uv@c7f87aa956e4c323abf06d5dec078e358f6b4d04  # v5.0.0
```

## Proposed Solutions

### Option A: SHA Pin All Actions (Recommended)

**Pros**: Maximum security, immutable references
**Cons**: Harder to read, requires manual updates
**Effort**: Small
**Risk**: None

```yaml
- uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683  # v4.2.2
- uses: astral-sh/setup-uv@c7f87aa956e4c323abf06d5dec078e358f6b4d04  # v5.0.0
```

### Option B: Add Dependabot for Actions

**Pros**: Automatic updates, keeps SHA pins current
**Cons**: Creates update PRs
**Effort**: Small
**Risk**: None

Create `.github/dependabot.yml`:
```yaml
version: 2
updates:
  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "weekly"
```

### Option C: Keep Version Tags

**Pros**: Readable, easy to update
**Cons**: Theoretically vulnerable to supply chain attacks
**Effort**: None
**Risk**: Low (trusted actions from GitHub and Astral)

Using version tags is common practice for trusted first-party actions.

## Recommended Action

**Option C** (keep version tags) is acceptable for this project because:
1. `actions/checkout` is official GitHub action
2. `astral-sh/setup-uv` is from Astral (makers of uv), reputable
3. The risk is theoretical, not practical for trusted sources

Consider **Option B** (Dependabot) as a low-effort enhancement.

## Technical Details

**Affected Files**:
- `.github/workflows/ci.yml`
- `.github/workflows/docs.yml` (also uses version tags)
- `.github/workflows/publish.yml` (also uses version tags)

## Acceptance Criteria

- [ ] If addressed: All actions pinned to SHA with version comments
- [ ] If Dependabot added: `.github/dependabot.yml` created
- [ ] CI workflow passes after changes

## Work Log

| Date | Action | Learning |
|------|--------|----------|
| 2025-12-29 | Created from PR #26 review | SHA pinning is best practice but not critical for trusted actions |

## Resources

- **PR**: https://github.com/chekos/inkwell-cli/pull/26
- **GitHub Security Hardening**: https://docs.github.com/en/actions/security-guides/security-hardening-for-github-actions
