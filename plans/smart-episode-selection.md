# feat: Smart Episode Selection UX (Simplified)

## Overview

Enhance the `--episode/-e` flag to accept position numbers, ranges, and lists in addition to keyword search. Users can reference episodes by the `#` column from `inkwell episodes`.

```bash
inkwell episodes lennys     # See: #1, #2, #3...
inkwell fetch lennys -e 3   # Fetch episode #3
inkwell fetch lennys -e 1-5 # Fetch episodes 1-5
```

## Implementation

**No new files.** Just modify two existing files:

### 1. Add to `src/inkwell/feeds/parser.py` (~25 lines)

```python
import re

def parse_and_fetch_episodes(
    self,
    feed: feedparser.FeedParserDict,
    selector: str,
    podcast_name: str,
) -> list[Episode]:
    """Parse selector and return matching episodes.

    Args:
        feed: Parsed RSS feed
        selector: Position (3), range (1-5), list (1,3,7), or keyword
        podcast_name: Name of the podcast

    Returns:
        List of matching episodes

    Raises:
        ValidationError: If selector format is invalid
        NotFoundError: If position is out of bounds
    """
    selector = selector.strip()
    feed_size = len(feed.entries)

    # Single position: "3"
    if re.match(r'^\d+$', selector):
        positions = [int(selector)]

    # Range: "1-5" (auto-correct reversed ranges)
    elif match := re.match(r'^(\d+)-(\d+)$', selector):
        start, end = int(match.group(1)), int(match.group(2))
        positions = list(range(min(start, end), max(start, end) + 1))

    # List: "1,3,7"
    elif re.match(r'^\d+(,\s*\d+)+$', selector):
        positions = [int(x.strip()) for x in selector.split(',')]

    # Keyword search (existing behavior)
    else:
        return [self.get_episode_by_title(feed, selector, podcast_name)]

    # Validate positions
    invalid = [p for p in positions if p < 1 or p > feed_size]
    if invalid:
        raise NotFoundError(
            resource_type="Episode position",
            resource_id=str(invalid),
            details={"feed_size": feed_size, "requested": positions},
            suggestion=f"Valid positions are 1-{feed_size}. Run 'inkwell episodes {podcast_name}' to see available episodes."
        )

    # Fetch episodes (1-indexed to 0-indexed)
    return [
        self.extract_episode_metadata(feed.entries[pos - 1], podcast_name)
        for pos in positions
    ]
```

### 2. Update `src/inkwell/cli.py` (~10 lines changed)

Replace the current episode handling logic:

```python
# Current (lines 819-843):
if latest:
    ep = parser.get_latest_episode(feed, url_or_feed)
else:
    ep = parser.get_episode_by_title(feed, episode, url_or_feed)

# New:
if latest:
    episodes = [parser.get_latest_episode(feed, url_or_feed)]
else:
    episodes = parser.parse_and_fetch_episodes(feed, episode, url_or_feed)

# Process all episodes (works for 1 or N)
for ep in episodes:
    # ... existing single-episode processing logic
```

Update help text:

```python
episode: str | None = typer.Option(
    None, "--episode", "-e",
    help="Position (3), range (1-5), list (1,3,7), or title keyword"
)
```

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Reversed range `5-1` | Auto-correct to `1-5` | Forgiving UX beats strict errors |
| Duplicates `1,1,3` | Process all | User's intent is explicit |
| `--latest` + `-e` | Both allowed | `--latest` = `-e 1`, no conflict |
| Batch failures | Fail fast | Stop on first error, simpler |

## Acceptance Criteria

- [ ] `-e 3` fetches episode at position 3
- [ ] `-e 1-5` fetches episodes 1 through 5
- [ ] `-e 1,3,7` fetches episodes at those positions
- [ ] `-e "keyword"` searches by title (existing behavior)
- [ ] Out-of-bounds positions show clear error with valid range
- [ ] Help text updated with examples

## Tests to Add

**In `tests/unit/test_feeds_parser.py`:**

```python
class TestParseAndFetchEpisodes:
    def test_single_position(self, mock_feed):
        episodes = parser.parse_and_fetch_episodes(mock_feed, "3", "test")
        assert len(episodes) == 1

    def test_range(self, mock_feed):
        episodes = parser.parse_and_fetch_episodes(mock_feed, "1-3", "test")
        assert len(episodes) == 3

    def test_range_reversed_auto_corrects(self, mock_feed):
        episodes = parser.parse_and_fetch_episodes(mock_feed, "3-1", "test")
        assert len(episodes) == 3

    def test_list(self, mock_feed):
        episodes = parser.parse_and_fetch_episodes(mock_feed, "1,3,5", "test")
        assert len(episodes) == 3

    def test_list_with_spaces(self, mock_feed):
        episodes = parser.parse_and_fetch_episodes(mock_feed, "1, 3, 5", "test")
        assert len(episodes) == 3

    def test_keyword_fallback(self, mock_feed):
        episodes = parser.parse_and_fetch_episodes(mock_feed, "AI security", "test")
        assert len(episodes) == 1

    def test_position_out_of_bounds(self, mock_feed_small):
        with pytest.raises(NotFoundError) as exc:
            parser.parse_and_fetch_episodes(mock_feed_small, "50", "test")
        assert "1-10" in str(exc.value.suggestion)

    def test_zero_position_invalid(self, mock_feed):
        with pytest.raises(NotFoundError):
            parser.parse_and_fetch_episodes(mock_feed, "0", "test")
```

## Files Changed

| File | Change |
|------|--------|
| `src/inkwell/feeds/parser.py` | Add `parse_and_fetch_episodes()` method |
| `src/inkwell/cli.py` | Update fetch command to use new method |
| `tests/unit/test_feeds_parser.py` | Add tests for new method |

## What Was Cut (per reviewer feedback)

- ~~`selector.py` module~~ → method in parser.py
- ~~`SelectorType` enum~~ → not needed
- ~~`EpisodeSelector` dataclass~~ → not needed
- ~~Separate `get_episode_by_position()` method~~ → combined
- ~~Batch processing with progress bars~~ → simple loop
- ~~Partial failure handling~~ → fail fast
- ~~Deduplication logic~~ → process what user typed
- ~~Mutual exclusivity validation~~ → both flags allowed

**Original plan: ~180 lines across 2 new files**
**Simplified: ~35 lines in existing files**
