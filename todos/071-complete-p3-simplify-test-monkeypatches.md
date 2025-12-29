---
status: complete
priority: p3
issue_id: "071"
tags: [code-review, testing, dx, pr-26]
dependencies: []
created: 2025-12-29
pr: "#26"
---

# Simplify Test Path Monkeypatches

## Problem Statement

The CLI tests use 4 separate monkeypatches for path isolation when only 1 is needed. The other path functions derive from `get_config_dir()`.

**Location**: `/Users/chekos/projects/gh/inkwell-cli/tests/integration/test_cli.py` (lines 78-82)

**Why It Matters**:
- 4 lines instead of 1
- Maintenance burden if path functions change
- Pattern is repeated in multiple test files

## Findings

**Agent**: code-simplicity-reviewer

**Current Code** (4 lines):
```python
monkeypatch.setattr("inkwell.utils.paths.get_config_dir", lambda: tmp_path)
monkeypatch.setattr("inkwell.utils.paths.get_config_file", lambda: tmp_path / "config.yaml")
monkeypatch.setattr("inkwell.utils.paths.get_feeds_file", lambda: tmp_path / "feeds.yaml")
monkeypatch.setattr("inkwell.utils.paths.get_key_file", lambda: tmp_path / ".keyfile")
```

**Path Functions Implementation** (utils/paths.py):
```python
def get_config_file() -> Path:
    return get_config_dir() / "config.yaml"

def get_feeds_file() -> Path:
    return get_config_dir() / "feeds.yaml"

def get_key_file() -> Path:
    return get_config_dir() / ".keyfile"
```

All functions call `get_config_dir()` internally, so mocking it is sufficient.

## Proposed Solutions

### Option A: Single Monkeypatch (Recommended)

**Pros**: 3 fewer lines, DRY, matches implementation
**Cons**: Less explicit
**Effort**: Trivial
**Risk**: Low

```python
# Simpler: Just mock get_config_dir, others derive from it
monkeypatch.setattr("inkwell.utils.paths.get_config_dir", lambda: tmp_path)
```

### Option B: Extract to Shared Fixture

**Pros**: Reusable, single source of truth
**Cons**: More abstraction
**Effort**: Small
**Risk**: None

In `conftest.py`:
```python
@pytest.fixture
def isolated_config_dir(tmp_path, monkeypatch):
    """Isolate all config paths to tmp_path."""
    monkeypatch.setattr("inkwell.utils.paths.get_config_dir", lambda: tmp_path)
    return tmp_path
```

Usage in tests:
```python
def test_list_empty_feeds(self, isolated_config_dir) -> None:
    result = runner.invoke(app, ["list"])
    # ...
```

### Option C: Keep Current Pattern

**Pros**: Explicit, defensive
**Cons**: Verbose, redundant
**Effort**: None
**Risk**: None

The current approach works correctly but is more verbose than necessary.

## Recommended Action

**Option A** for the immediate fix, followed by **Option B** if the pattern appears in multiple test files.

## Technical Details

**Affected Files**:
- `tests/integration/test_cli.py`

**Verification**: Check that other tests don't directly call `get_config_file()` etc. without going through `get_config_dir()`.

## Acceptance Criteria

- [ ] Reduce 4 monkeypatches to 1
- [ ] All existing tests pass
- [ ] (Optional) Extract to shared fixture in conftest.py

## Work Log

| Date | Action | Learning |
|------|--------|----------|
| 2025-12-29 | Created from PR #26 review | Mock the root, not the leaves |

## Resources

- **PR**: https://github.com/chekos/inkwell-cli/pull/26
- **pytest monkeypatch**: https://docs.pytest.org/en/stable/how-to/monkeypatch.html
