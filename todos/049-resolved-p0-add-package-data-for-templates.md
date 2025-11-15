---
status: resolved
priority: p0
issue_id: "049"
tags: [pr-11, code-review, data-integrity, packaging, pypi, critical]
dependencies: []
---

# Add Package Data Configuration for Template Files

## Problem Statement

The `src/inkwell/templates/` directory contains YAML template files that are **essential for runtime operation**, but they are **not configured to be included in the PyPI distribution**. This means:

1. `uv build` will exclude template files from the wheel/sdist
2. Users installing from PyPI will get a broken package
3. Runtime will fail when trying to load templates

**Severity**: CRITICAL - Package will be broken on PyPI

## Findings

- Discovered during PR #11 data integrity audit
- Location: `src/inkwell/templates/` directory
- No `[tool.setuptools.package-data]` configuration in `pyproject.toml`
- No `MANIFEST.in` file
- Dockerfile copies templates incorrectly (separate issue #XXX)

**Template Files Found**:
```
src/inkwell/templates/default/summary.yaml
src/inkwell/templates/default/quotes.yaml
src/inkwell/templates/default/key-concepts.yaml
src/inkwell/templates/categories/interview/books-mentioned.yaml
src/inkwell/templates/categories/interview/people-mentioned.yaml
src/inkwell/templates/categories/tech/tools-mentioned.yaml
src/inkwell/templates/categories/tech/frameworks-mentioned.yaml
```

**Impact**:
- PyPI package will install successfully but fail at runtime
- Users will get `FileNotFoundError` when processing podcasts
- Docker image may also be affected
- Silent failure (builds succeed, runtime fails)

**Test Case That Will Fail**:
```python
# After: pip install inkwell-cli
# This will fail:
from inkwell.extraction.templates import TemplateLoader
loader = TemplateLoader()
templates = loader.load_default_templates()  # FileNotFoundError!
```

## Proposed Solutions

### Option 1: setuptools package_data (Recommended for setuptools build)
**Pros**:
- Standard approach for setuptools
- Works with `uv build` (uses setuptools backend)
- Explicit and clear
- Well-documented

**Cons**:
- Setuptools-specific (but that's what we use)

**Effort**: Small (10 minutes)
**Risk**: Low

**Implementation**:
```toml
# Add to pyproject.toml
[tool.setuptools.package-data]
inkwell = [
    "templates/**/*.yaml",
    "templates/**/*.yml",
]
```

### Option 2: MANIFEST.in (Legacy approach)
**Pros**:
- Universal (works with all build backends)
- Includes in sdist

**Cons**:
- Legacy approach (PEP 621 deprecates this)
- Less explicit
- Easy to forget to update

**Effort**: Small (10 minutes)
**Risk**: Low

**Not recommended** - Use Option 1 instead

### Option 3: include-package-data + MANIFEST.in
**Pros**:
- Comprehensive
- Catches all data files

**Cons**:
- Overly broad (may include unwanted files)
- Still requires MANIFEST.in

**Not recommended** - Too broad

## Recommended Action

**Implement Option 1** - Add explicit `[tool.setuptools.package-data]` configuration to `pyproject.toml`.

**Process**:
1. Add configuration to `pyproject.toml`
2. Test build: `uv build`
3. Verify templates in wheel: `unzip -l dist/*.whl | grep templates`
4. Test installation: `pip install dist/*.whl && python -c "from inkwell.extraction.templates import TemplateLoader; TemplateLoader().load_default_templates()"`
5. Add to CI: Verify template files in built package

## Technical Details

**Affected Files**:
- `pyproject.toml` (add package-data configuration)
- `src/inkwell/templates/**/*.yaml` (files to include)

**Current pyproject.toml build configuration**:
```toml
[build-system]
requires = ["setuptools>=75.6.0", "wheel"]
build-backend = "setuptools.build_meta"
```

**Required Addition**:
```toml
[tool.setuptools.package-data]
inkwell = [
    "templates/**/*.yaml",
    "templates/**/*.yml",
]
```

**Alternative** (if using setup.py - NOT RECOMMENDED):
```python
setup(
    package_data={
        'inkwell': ['templates/**/*.yaml', 'templates/**/*.yml'],
    },
)
```

**Verification Commands**:
```bash
# Build package
uv build

# List contents of wheel
unzip -l dist/inkwell_cli-*.whl | grep templates

# Should see:
# inkwell/templates/default/summary.yaml
# inkwell/templates/default/quotes.yaml
# inkwell/templates/default/key-concepts.yaml
# ... etc

# Test installation
pip install dist/inkwell_cli-*.whl
python -c "from inkwell.extraction.templates import TemplateLoader; print('✓ Templates loaded')"
```

## Acceptance Criteria

- [ ] Add `[tool.setuptools.package-data]` to pyproject.toml
- [ ] Build package with `uv build`
- [ ] Verify templates included in wheel (unzip -l)
- [ ] Test wheel installation in clean venv
- [ ] Verify templates can be loaded at runtime
- [ ] Add CI check to verify package data inclusion
- [ ] All tests pass

## Work Log

### 2025-11-14 - Data Integrity Audit Discovery
**By:** Claude Code Review System (PR #11 Review)
**Actions:**
- Discovered during comprehensive data integrity audit
- Analyzed by data-integrity-guardian agent
- Categorized as P0 CRITICAL priority
- Identified missing package data configuration

**Learnings:**
- Default setuptools behavior: Only include .py files
- Package data must be explicitly configured
- Always verify wheel contents before PyPI publication
- Runtime failures from missing data are hard to debug

## Notes

**Python Packaging References**:
- PEP 621: Project metadata in pyproject.toml
- setuptools documentation: Including Data Files
- Wheel specification: What goes in wheels

**Common Pitfall**:
Many projects forget to configure package data and discover the issue only after PyPI publication. Testing the wheel before publishing is critical.

**Best Practice**:
Add CI check that verifies expected files in built wheel:
```yaml
- name: Verify package contents
  run: |
    uv build
    python -c "
    import zipfile
    wheel = zipfile.ZipFile('dist/inkwell_cli-*.whl')
    templates = [f for f in wheel.namelist() if 'templates/' in f]
    assert len(templates) > 0, 'No templates found in wheel!'
    print(f'✓ Found {len(templates)} template files')
    "
```

**Related Issues**:
- Dockerfile templates path issue (separate todo)
- Template loading logic verification needed

**Source**: Data integrity audit performed on 2025-11-14
**Review command**: /review pr11
