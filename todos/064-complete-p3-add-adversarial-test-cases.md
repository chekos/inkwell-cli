---
status: complete
priority: p3
issue_id: "064"
tags:
  - code-review
  - pr-22
  - testing
  - security
dependencies:
  - "060"
---

# Add Adversarial Test Cases

## Problem Statement

The test suite covers happy paths and basic edge cases, but lacks adversarial tests for security and robustness scenarios.

**Why it matters:** Edge cases and attack vectors should be tested to ensure robust input handling.

## Findings

### Agent: Security Sentinel
**Missing Security Tests:**
- Large range attack (e.g., `"1-1000000000"`)
- Large list attack (e.g., 10,000 comma-separated values)
- Extremely large single number (e.g., `"999999999999999999"`)
- Maximum input length (e.g., 1MB string)
- Special characters in keyword mode

### Agent: Kieran Python Reviewer
**Missing Edge Cases:**
- Empty string selector: `parser.parse_and_fetch_episodes(feed, "", "Tech Talks")`
- Negative numbers: `parser.parse_and_fetch_episodes(feed, "-5", "Tech Talks")`
- Range with start == end: `parser.parse_and_fetch_episodes(feed, "3-3", "Tech Talks")`
- Single comma (no numbers): `parser.parse_and_fetch_episodes(feed, ",", "Tech Talks")`
- Duplicate positions in list: `parser.parse_and_fetch_episodes(feed, "1,1,1", "Tech Talks")`

## Proposed Solutions

### Solution 1: Add Adversarial Test Class
**Pros:**
- Comprehensive coverage
- Documents expected behavior for edge cases
- Prevents regressions

**Cons:**
- More test code to maintain

**Effort:** Medium (30 minutes)
**Risk:** None

```python
class TestParseAndFetchEpisodesAdversarial:
    """Adversarial and edge case tests for parse_and_fetch_episodes."""

    def test_empty_string_selector(self, valid_rss_feed: str) -> None:
        """Test that empty string is handled gracefully."""
        feed = feedparser.parse(valid_rss_feed)
        parser = RSSParser()
        # Expected: either error or treated as keyword (no matches)
        with pytest.raises((ValidationError, NotFoundError)):
            parser.parse_and_fetch_episodes(feed, "", "Tech Talks")

    def test_large_range_rejected(self, valid_rss_feed: str) -> None:
        """Test that excessively large ranges are rejected."""
        feed = feedparser.parse(valid_rss_feed)
        parser = RSSParser()
        with pytest.raises(ValidationError, match="exceeds maximum"):
            parser.parse_and_fetch_episodes(feed, "1-1000000", "Tech Talks")

    def test_large_list_rejected(self, valid_rss_feed: str) -> None:
        """Test that excessively large lists are rejected."""
        feed = feedparser.parse(valid_rss_feed)
        parser = RSSParser()
        large_list = ",".join(str(i) for i in range(1, 1001))
        with pytest.raises(ValidationError, match="exceeds maximum"):
            parser.parse_and_fetch_episodes(feed, large_list, "Tech Talks")

    def test_negative_number_treated_as_keyword(self, valid_rss_feed: str) -> None:
        """Test that negative numbers fall through to keyword search."""
        feed = feedparser.parse(valid_rss_feed)
        parser = RSSParser()
        # "-5" doesn't match position/range/list patterns, so keyword search
        with pytest.raises(ValidationError, match="No episode found"):
            parser.parse_and_fetch_episodes(feed, "-5", "Tech Talks")

    def test_range_start_equals_end(self, valid_rss_feed: str) -> None:
        """Test range where start == end returns single episode."""
        feed = feedparser.parse(valid_rss_feed)
        parser = RSSParser()
        episodes = parser.parse_and_fetch_episodes(feed, "2-2", "Tech Talks")
        assert len(episodes) == 1

    def test_duplicates_in_list(self, valid_rss_feed: str) -> None:
        """Test that duplicate positions are handled."""
        feed = feedparser.parse(valid_rss_feed)
        parser = RSSParser()
        episodes = parser.parse_and_fetch_episodes(feed, "1,1,2", "Tech Talks")
        # Current behavior: duplicates processed as-is (3 episodes, 2 unique)
        # Could change to deduplicate in future
        assert len(episodes) >= 2
```

## Recommended Action

Add comprehensive adversarial tests after implementing TODO #060 (resource limits).

## Technical Details

**Affected Files:**
- `tests/unit/test_feeds_parser.py`

## Acceptance Criteria

- [ ] Test for empty string selector
- [ ] Test for large range rejection (requires #060)
- [ ] Test for large list rejection (requires #060)
- [ ] Test for negative numbers
- [ ] Test for range where start == end
- [ ] Test for duplicate positions in list
- [ ] Test for extremely large single number

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2025-12-21 | Security and code quality review | Always test adversarial inputs, not just happy paths |
| 2025-12-21 | Approved during triage - Status: ready | Depends on #060 for limit-related tests |

## Resources

- PR #22: https://github.com/chekos/inkwell-cli/pull/22
- Security Sentinel analysis
- Kieran Python Review analysis
