---
status: complete
priority: p3
issue_id: "091"
tags: [code-review, testing, coverage-gap, pr-36]
dependencies: []
---

# Add Tests for Table Output Format in list_latest

## Problem Statement

All success tests for `list latest` use the `--json` flag. No tests verify the Rich table output for successful feeds, including:
- Table column headers and structure
- Title truncation behavior
- Duration formatting
- Date formatting
- Feed name sorting (line 355)

**Why it matters**: Table output path has no test coverage for success cases.

## Findings

**Location**: `/Users/chekos/projects/gh/inkwell-cli/tests/integration/test_cli_list.py`, lines 131-341

**Current test coverage**:
| Test | Table Output | JSON Output |
|------|--------------|-------------|
| No feeds | ✓ | ✓ |
| Single feed success | - | ✓ |
| Partial failure | - | ✓ |
| All fail | ✓ (error path) | - |
| Empty feed | - | ✓ |

**Missing tests**:
1. `test_list_latest_table_single_feed_success` - Table with one feed
2. `test_list_latest_table_multiple_feeds_sorted` - Verify feed name sorting
3. `test_list_latest_table_title_truncation` - Very long titles
4. `test_list_latest_table_partial_failure` - Table shows errors inline

## Proposed Solutions

### Option A: Add table output tests (Recommended)

**Pros**: Complete coverage, catches Rich formatting issues
**Cons**: More test code
**Effort**: Medium (30-45 minutes)
**Risk**: Very low

```python
def test_list_latest_table_single_feed_success(self, tmp_path: Path, monkeypatch) -> None:
    """Should display latest episode in table format."""
    # ... setup with mocked feed

    result = runner.invoke(app, ["list", "latest"])  # No --json

    assert result.exit_code == 0
    assert "Latest Episodes" in result.stdout
    assert "test-podcast" in result.stdout
    assert "Test Episode Title" in result.stdout
    assert "✓" in result.stdout or "succeeded" in result.stdout

def test_list_latest_table_feeds_sorted_alphabetically(self, tmp_path: Path, monkeypatch) -> None:
    """Feeds should be sorted by name in table output."""
    # Setup: Add feeds "zebra" and "apple"

    result = runner.invoke(app, ["list", "latest"])

    # Verify "apple" appears before "zebra" in output
    apple_pos = result.stdout.find("apple")
    zebra_pos = result.stdout.find("zebra")
    assert apple_pos < zebra_pos

def test_list_latest_table_title_truncation(self, tmp_path: Path, monkeypatch) -> None:
    """Long titles should be truncated with ellipsis."""
    # Setup: Episode with 60+ character title

    result = runner.invoke(app, ["list", "latest"])

    assert "..." in result.stdout
    # Full title should NOT appear
    assert "This is a very long title that should be truncated" not in result.stdout
```

### Option B: Rely on JSON tests only

**Pros**: Less test code
**Cons**: Table formatting bugs would go undetected
**Effort**: None
**Risk**: Medium - missed bugs in display logic

## Recommended Action

**Option A**: Add comprehensive table output tests for success scenarios.

## Technical Details

**Affected Files**:
- `/Users/chekos/projects/gh/inkwell-cli/tests/integration/test_cli_list.py`

**Tests to add**:
1. `test_list_latest_table_single_feed_success`
2. `test_list_latest_table_feeds_sorted_alphabetically`
3. `test_list_latest_table_title_truncation`

## Acceptance Criteria

- [ ] Test for table output with successful feed
- [ ] Test for alphabetical feed sorting
- [ ] Test for title truncation in table
- [ ] All tests pass
- [ ] Coverage improved for `_output_latest_table()` function

## Work Log

| Date | Action | Notes |
|------|--------|-------|
| 2026-01-11 | Created | From PR #36 code review by pattern-recognition-specialist agent |

## Resources

- PR #36: https://github.com/chekos/inkwell-cli/pull/36
- Existing test patterns: `TestListEpisodes`, `TestListFeeds`
