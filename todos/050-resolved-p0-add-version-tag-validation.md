---
status: resolved
priority: p0
issue_id: "050"
tags: [pr-11, code-review, data-integrity, ci-cd, release, critical]
dependencies: []
---

# Add Version Tag Validation to Release Workflow

## Problem Statement

The release workflow triggers on **any** tag matching `v*` pattern but does **not validate** that the tag version matches the `pyproject.toml` version. This can cause:

1. Publishing wrong version to PyPI (tag: v1.0.0, package: v1.0.1)
2. Corrupted version history
3. Users installing mismatched versions
4. Broken changelog references

**Severity**: CRITICAL - Data integrity violation, corrupts releases

## Findings

- Discovered during PR #11 data integrity audit
- Location: `.github/workflows/release.yml`
- Workflow triggers on `push: tags: v*`
- No validation step before build/publish
- Could create version mismatches between Git, PyPI, and GitHub Releases

**Attack Scenarios**:
```bash
# Scenario 1: Typo in tag
# pyproject.toml has version = "1.2.3"
git tag v1.2.4  # Oops, typo!
git push origin v1.2.4
# → PyPI gets package version 1.2.3
# → GitHub release says v1.2.4
# → Users confused

# Scenario 2: Forgot to bump version
# pyproject.toml still has version = "1.0.0"
git tag v1.1.0  # Create new version tag
git push origin v1.1.0
# → PyPI gets package version 1.0.0 (overwrites existing!)
# → GitHub release says v1.1.0
# → PyPI rejects duplicate version

# Scenario 3: Premature tag
git tag v2.0.0  # Before updating pyproject.toml
git push origin v2.0.0
# → Releases v1.0.0 as v2.0.0
# → Major version mismatch
```

**Impact**:
- Version confusion for users
- PyPI may reject upload (duplicate version)
- Broken package installations
- Unreliable version history
- Trust issues with package

## Proposed Solutions

### Option 1: Validate Before Build (Recommended)
**Pros**:
- Catches errors early (before build)
- Clear error message
- Fast feedback
- Prevents bad releases

**Cons**:
- Requires Python to read pyproject.toml
- Adds ~10 seconds to workflow

**Effort**: Small (15 minutes)
**Risk**: Low

**Implementation**:
```yaml
# Add to .github/workflows/release.yml after checkout
- name: Validate version tag matches pyproject.toml
  run: |
    # Extract version from tag (v1.2.3 → 1.2.3)
    TAG_VERSION=${GITHUB_REF#refs/tags/v}

    # Extract version from pyproject.toml
    PKG_VERSION=$(python -c "
    import tomllib
    with open('pyproject.toml', 'rb') as f:
        data = tomllib.load(f)
        print(data['project']['version'])
    ")

    # Compare versions
    if [ "$TAG_VERSION" != "$PKG_VERSION" ]; then
      echo "❌ ERROR: Version mismatch!"
      echo "  Git tag version: v$TAG_VERSION"
      echo "  pyproject.toml version: $PKG_VERSION"
      echo ""
      echo "Please update pyproject.toml version to match the tag,"
      echo "or delete the tag and create a new one."
      exit 1
    fi

    echo "✅ Version validation passed: $TAG_VERSION"
```

### Option 2: Auto-Update pyproject.toml from Tag
**Pros**:
- Tag becomes source of truth
- No manual version bumps

**Cons**:
- Surprising behavior (commits during release)
- Goes against conventional workflow
- Can create dirty commits

**Not recommended** - Tags should reflect code, not modify it

### Option 3: Use Semantic Release Tool
**Pros**:
- Fully automated versioning
- Changelog generation
- Conventional commits enforcement

**Cons**:
- Complex setup
- Changes workflow significantly
- Overkill for current project size

**Not recommended** - Save for v2.0 if needed

## Recommended Action

**Implement Option 1** - Add version validation step before building the package.

**Process**:
1. Add validation step to `.github/workflows/release.yml` after checkout
2. Test with matching tag (should pass)
3. Test with mismatched tag (should fail with clear error)
4. Document in CONTRIBUTING.md: "Ensure pyproject.toml version matches tag"
5. Add to release checklist

## Technical Details

**Affected Files**:
- `.github/workflows/release.yml` (add validation step)
- `.github/CONTRIBUTING.md` (document release process)

**Current Workflow**:
```yaml
on:
  push:
    tags:
      - 'v*'

jobs:
  release:
    steps:
      - uses: actions/checkout@v4
      - name: Install uv
        # ... setup
      - name: Build package  # ← No validation before this!
        run: uv build
      - name: Publish to PyPI
        # ... publish
```

**Updated Workflow**:
```yaml
on:
  push:
    tags:
      - 'v*'

jobs:
  release:
    steps:
      - uses: actions/checkout@v4

      - name: Validate version tag matches pyproject.toml
        run: |
          TAG_VERSION=${GITHUB_REF#refs/tags/v}
          PKG_VERSION=$(python -c "import tomllib; print(tomllib.load(open('pyproject.toml', 'rb'))['project']['version'])")
          if [ "$TAG_VERSION" != "$PKG_VERSION" ]; then
            echo "❌ ERROR: Version mismatch! Tag: $TAG_VERSION, Package: $PKG_VERSION"
            exit 1
          fi
          echo "✅ Version validation passed: $TAG_VERSION"

      - name: Install uv
        # ... setup
      - name: Build package
        run: uv build
      - name: Publish to PyPI
        # ... publish
```

**Release Process Documentation**:
```markdown
## Creating a Release

1. Update version in `pyproject.toml`:
   ```toml
   version = "1.2.3"
   ```

2. Update CHANGELOG.md with changes

3. Commit changes:
   ```bash
   git commit -am "chore: Bump version to 1.2.3"
   ```

4. Create and push tag:
   ```bash
   git tag v1.2.3
   git push origin main --tags
   ```

5. GitHub Actions will:
   - Validate tag matches pyproject.toml version ✓
   - Run tests ✓
   - Build package ✓
   - Publish to PyPI ✓
   - Create GitHub Release ✓

**Note**: If tag doesn't match pyproject.toml, the release will fail.
```

## Acceptance Criteria

- [ ] Add version validation step to release workflow
- [ ] Test validation with matching version (should pass)
- [ ] Test validation with mismatched version (should fail)
- [ ] Clear error message shows both versions
- [ ] Document release process in CONTRIBUTING.md
- [ ] Add to PR template release checklist

## Work Log

### 2025-11-14 - Data Integrity Audit Discovery
**By:** Claude Code Review System (PR #11 Review)
**Actions:**
- Discovered during comprehensive data integrity audit
- Analyzed by data-integrity-guardian agent
- Categorized as P0 CRITICAL priority
- Identified missing version validation in release workflow

**Learnings:**
- Git tags and package versions must stay synchronized
- Automated releases need validation gates
- Early validation prevents expensive failures
- Clear error messages save debugging time

## Notes

**Best Practices**:
- Always validate versions before building/publishing
- Make tags immutable (don't reuse/overwrite)
- Document release process clearly
- Test release workflow before going live

**Alternative Approaches**:
- bump2version: Auto-updates version across files
- semantic-release: Fully automated version management
- Manual verification: Release checklist in CONTRIBUTING.md

**Common Pitfalls**:
- Forgetting to bump version before tagging
- Typos in tag names
- Creating tags before updating pyproject.toml
- Reusing/overwriting existing tags

**Testing the Validation**:
```bash
# Create test branch
git checkout -b test-release-validation

# Update version in pyproject.toml to 1.0.1
sed -i 's/version = "1.0.0"/version = "1.0.1"/' pyproject.toml

# Commit
git commit -am "test: Update version for release validation test"

# Create matching tag (should pass)
git tag v1.0.1
git push origin v1.0.1

# Create mismatched tag (should fail)
git tag v1.0.2
git push origin v1.0.2
# → Workflow should fail with clear error
```

**Source**: Data integrity audit performed on 2025-11-14
**Review command**: /review pr11
