# Research: Typer Framework - Flexible Argument Parsing

**Date:** 2025-12-21
**Status:** Complete
**Related Issues:** Episode selection with `--episode` flag
**Purpose:** Understand how to implement flexible argument parsing in Typer that auto-detects input patterns

## Summary

This research explores Typer's capabilities for implementing flexible argument parsing, specifically for a `--episode` flag that should auto-detect different input formats:
- Single position: `"3"` → episode at position 3
- Range: `"1-5"` → episodes 1 through 5
- Multiple positions: `"1,3,7"` → episodes at positions 1, 3, and 7
- Keyword search: `"AI security"` → search episode titles/descriptions

## Key Findings

### 1. Custom Type Parsing in Typer

Typer provides **two main approaches** for custom type parsing:

#### A. Parser Functions (Simpler)
Use the `parser` parameter in `typer.Option()` or `typer.Argument()`:

```python
import typer
from typing import List

def parse_episode_selector(value: str) -> dict:
    """Parse episode selector and return structured data."""
    # Check if it's a range (e.g., "1-5")
    if '-' in value and value.replace('-', '').isdigit():
        start, end = value.split('-')
        return {'type': 'range', 'start': int(start), 'end': int(end)}

    # Check if it's a comma-separated list (e.g., "1,3,7")
    if ',' in value:
        try:
            positions = [int(x.strip()) for x in value.split(',')]
            return {'type': 'list', 'positions': positions}
        except ValueError:
            pass  # Not all integers, treat as keyword

    # Check if it's a single integer (e.g., "3")
    if value.isdigit():
        return {'type': 'position', 'value': int(value)}

    # Default to keyword search
    return {'type': 'keyword', 'value': value}

@app.command()
def process(
    episode: str = typer.Option(
        None,
        "--episode",
        parser=parse_episode_selector,
        help="Episode selector: position (3), range (1-5), list (1,3,7), or keyword"
    )
):
    if episode['type'] == 'range':
        typer.echo(f"Processing episodes {episode['start']} to {episode['end']}")
    elif episode['type'] == 'list':
        typer.echo(f"Processing episodes: {episode['positions']}")
    # ... handle other types
```

**Pros:**
- Simple, straightforward
- Good for basic parsing logic
- No extra imports needed

**Cons:**
- Less control over error messages
- Cannot access Click context for advanced features

#### B. Click ParamType (More Powerful)
Use `click_type` parameter with a custom `click.ParamType` subclass:

```python
import click
import typer
from typing import Union, List

class EpisodeSelector(click.ParamType):
    """Custom type for parsing episode selection patterns."""
    name = "episode_selector"

    def convert(self, value, param, ctx):
        """Convert string input to structured episode selector."""
        if value is None:
            return None

        # Already converted
        if isinstance(value, dict):
            return value

        # Parse range (e.g., "1-5")
        if '-' in value:
            parts = value.split('-')
            if len(parts) == 2 and all(p.strip().isdigit() for p in parts):
                try:
                    start, end = int(parts[0]), int(parts[1])
                    if start > end:
                        self.fail(
                            f"Invalid range: {value} (start must be <= end)",
                            param,
                            ctx
                        )
                    return {'type': 'range', 'start': start, 'end': end}
                except ValueError:
                    self.fail(f"Invalid range format: {value}", param, ctx)

        # Parse comma-separated list (e.g., "1,3,7")
        if ',' in value:
            try:
                positions = [int(x.strip()) for x in value.split(',')]
                if not positions:
                    self.fail("Empty position list", param, ctx)
                return {'type': 'list', 'positions': positions}
            except ValueError:
                # Not all integers, treat as keyword search
                pass

        # Parse single integer (e.g., "3")
        try:
            position = int(value)
            if position <= 0:
                self.fail("Episode position must be >= 1", param, ctx)
            return {'type': 'position', 'value': position}
        except ValueError:
            pass

        # Default: keyword search
        if len(value.strip()) == 0:
            self.fail("Episode selector cannot be empty", param, ctx)
        return {'type': 'keyword', 'value': value.strip()}

app = typer.Typer()

@app.command()
def process(
    episode: dict = typer.Option(
        None,
        "--episode",
        click_type=EpisodeSelector(),
        help="Episode: number (3), range (1-5), list (1,3,7), or keyword"
    )
):
    if episode is None:
        typer.echo("No episode specified")
        return

    if episode['type'] == 'range':
        typer.echo(f"Processing episodes {episode['start']}-{episode['end']}")
    elif episode['type'] == 'list':
        typer.echo(f"Processing episodes: {', '.join(map(str, episode['positions']))}")
    elif episode['type'] == 'position':
        typer.echo(f"Processing episode {episode['value']}")
    else:  # keyword
        typer.echo(f"Searching for: '{episode['value']}'")
```

**Pros:**
- Better error messages via `self.fail()`
- Access to Click context and param
- Reusable across multiple commands
- More sophisticated validation
- Better for complex parsing logic

**Cons:**
- More verbose
- Requires understanding Click's ParamType API

**Recommendation:** Use **Click ParamType approach** for the `--episode` flag due to:
1. Better error handling and user feedback
2. Complex validation requirements (ranges, lists, keywords)
3. Reusability if needed elsewhere

### 2. Handling Mixed Input Patterns

The key insight is to parse **in order of specificity**:

1. **Range detection first** (contains `-` and only digits)
2. **List detection** (contains `,` and try parsing as integers)
3. **Single position** (is a single integer)
4. **Keyword fallback** (everything else)

This ordering prevents ambiguity (e.g., "2-3" is clearly a range, not keyword).

### 3. Progress Bars with Rich for Batch Operations

When processing multiple episodes, use Rich's progress tracking:

```python
from rich.progress import Progress, track
import time

# Simple approach: track() wrapper
def process_episodes_simple(episodes: List[int]):
    for episode_num in track(episodes, description="Processing episodes..."):
        # Do work
        process_episode(episode_num)
        time.sleep(0.1)

# Advanced approach: Multiple progress bars
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TaskProgressColumn,
    TimeRemainingColumn,
)

def process_episodes_advanced(episodes: List[int]):
    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeRemainingColumn(),
    ) as progress:
        # Main task: overall progress
        overall = progress.add_task(
            "[cyan]Processing episodes...",
            total=len(episodes)
        )

        for episode_num in episodes:
            # Sub-task for each episode
            episode_task = progress.add_task(
                f"[green]Episode {episode_num}",
                total=100
            )

            # Simulate work with progress updates
            for i in range(100):
                time.sleep(0.01)
                progress.update(episode_task, advance=1)

            progress.update(overall, advance=1)
```

**Key Progress Patterns:**

1. **Simple iteration**: Use `track(iterable, description="...")`
2. **Multiple stages**: Create separate tasks with `add_task()`
3. **Transient bars**: Use `transient=True` to auto-clear when complete
4. **Custom columns**: Configure `Progress()` with custom column layout

### 4. Validation and Error Handling

Best practices for robust argument validation:

```python
class EpisodeSelector(click.ParamType):
    """Enhanced with comprehensive validation."""
    name = "episode_selector"

    def convert(self, value, param, ctx):
        if value is None:
            return None

        # Validate range
        if '-' in value:
            parts = value.split('-')
            if len(parts) != 2:
                self.fail(
                    f"Invalid range format: {value}. Expected format: '1-5'",
                    param,
                    ctx
                )
            try:
                start, end = int(parts[0]), int(parts[1])
                if start <= 0 or end <= 0:
                    self.fail(
                        "Episode positions must be positive integers",
                        param,
                        ctx
                    )
                if start > end:
                    self.fail(
                        f"Invalid range: start ({start}) > end ({end})",
                        param,
                        ctx
                    )
                # Optional: check reasonable upper limit
                if end > 1000:
                    self.fail(
                        "Episode range too large (max 1000)",
                        param,
                        ctx
                    )
                return {'type': 'range', 'start': start, 'end': end}
            except ValueError as e:
                self.fail(
                    f"Invalid range values: {value}. Must be integers.",
                    param,
                    ctx
                )

        # Validate list
        if ',' in value:
            try:
                positions = [int(x.strip()) for x in value.split(',')]
                if not positions:
                    self.fail("Empty position list", param, ctx)
                if any(p <= 0 for p in positions):
                    self.fail(
                        "All episode positions must be positive integers",
                        param,
                        ctx
                    )
                # Remove duplicates and sort
                positions = sorted(set(positions))
                return {'type': 'list', 'positions': positions}
            except ValueError:
                # Not all integers, treat as keyword
                pass

        # Validate single position
        try:
            position = int(value)
            if position <= 0:
                self.fail(
                    "Episode position must be a positive integer",
                    param,
                    ctx
                )
            return {'type': 'position', 'value': position}
        except ValueError:
            pass

        # Keyword search validation
        if len(value.strip()) < 2:
            self.fail(
                "Keyword search must be at least 2 characters",
                param,
                ctx
            )

        return {'type': 'keyword', 'value': value.strip()}
```

**Validation Checklist:**
- ✓ Check bounds (positive integers, reasonable limits)
- ✓ Validate format (correct separators, structure)
- ✓ Provide clear error messages with examples
- ✓ Handle edge cases (empty input, duplicates, whitespace)
- ✓ Normalize data (remove duplicates, trim whitespace, sort)

### 5. Integration with Existing Command Structure

To integrate with your existing feed-based structure:

```python
from typing import Optional
import typer
from rich.progress import track

@app.command()
def process(
    feed_url: Optional[str] = typer.Option(None, "--feed", "-f"),
    episode: Optional[dict] = typer.Option(
        None,
        "--episode",
        "-e",
        click_type=EpisodeSelector(),
        help="Episode: number (3), range (1-5), list (1,3,7), or keyword"
    ),
    latest: bool = typer.Option(False, "--latest", "-l"),
):
    """Process podcast episodes with flexible selection."""

    # Validate mutually exclusive options
    if sum([bool(episode), latest]) > 1:
        typer.echo("Error: --episode and --latest are mutually exclusive", err=True)
        raise typer.Exit(1)

    # Get episodes from feed
    episodes = fetch_episodes_from_feed(feed_url)

    # Select episodes based on option
    if latest:
        selected = [episodes[0]]
    elif episode:
        selected = select_episodes(episodes, episode)
    else:
        # Default behavior
        selected = episodes

    # Process with progress bar
    for ep in track(selected, description="Processing episodes"):
        process_episode(ep)

def select_episodes(all_episodes: List[Episode], selector: dict) -> List[Episode]:
    """Select episodes based on parsed selector."""
    if selector['type'] == 'range':
        start, end = selector['start'], selector['end']
        # Note: list indices are 0-based, but user input is 1-based
        return all_episodes[start-1:end]

    elif selector['type'] == 'list':
        positions = selector['positions']
        return [all_episodes[p-1] for p in positions if p <= len(all_episodes)]

    elif selector['type'] == 'position':
        pos = selector['value']
        if pos > len(all_episodes):
            typer.echo(f"Warning: Position {pos} exceeds episode count", err=True)
            return []
        return [all_episodes[pos-1]]

    else:  # keyword
        keyword = selector['value'].lower()
        return [
            ep for ep in all_episodes
            if keyword in ep.title.lower() or keyword in ep.description.lower()
        ]
```

**Key Integration Points:**
1. Validate mutual exclusivity with other flags (`--latest`)
2. Convert 1-based user input to 0-based list indices
3. Handle out-of-bounds gracefully (warn, don't crash)
4. Apply keyword search across title and description

## Code Patterns

### Pattern 1: Click ParamType with Comprehensive Validation

```python
import click
from typing import Dict, Any

class FlexibleArgumentParser(click.ParamType):
    """Template for flexible argument parsing."""
    name = "flexible_arg"

    def convert(self, value, param, ctx) -> Dict[str, Any]:
        if value is None:
            return None

        # Early return for already-converted values
        if isinstance(value, dict):
            return value

        # Try each pattern in order of specificity

        # Pattern 1: Range (most specific)
        result = self._try_parse_range(value)
        if result:
            return result

        # Pattern 2: List
        result = self._try_parse_list(value)
        if result:
            return result

        # Pattern 3: Single value
        result = self._try_parse_single(value)
        if result:
            return result

        # Pattern 4: Fallback
        return self._parse_fallback(value)

    def _try_parse_range(self, value: str) -> Optional[dict]:
        """Try parsing as range. Return None if not a range."""
        if '-' not in value:
            return None

        parts = value.split('-')
        if len(parts) != 2 or not all(p.isdigit() for p in parts):
            return None

        start, end = int(parts[0]), int(parts[1])
        # Add validation here
        return {'type': 'range', 'start': start, 'end': end}

    # ... similar methods for other patterns
```

### Pattern 2: Progress Bar for Batch Processing

```python
from rich.progress import Progress, track
from typing import List

def process_batch_simple(items: List[Any]):
    """Simple progress bar."""
    for item in track(items, description="Processing..."):
        process_item(item)

def process_batch_detailed(items: List[Any]):
    """Detailed progress with multiple bars."""
    with Progress() as progress:
        overall = progress.add_task("[cyan]Overall", total=len(items))

        for item in items:
            # Per-item progress
            item_task = progress.add_task(
                f"[green]{item.name}",
                total=100
            )

            # Update as work progresses
            for i in range(100):
                do_work_chunk(item, i)
                progress.update(item_task, advance=1)

            progress.update(overall, advance=1)
```

### Pattern 3: Mutual Exclusivity Validation

```python
def validate_mutually_exclusive(
    *flags: Optional[Any],
    names: List[str]
) -> None:
    """Validate that at most one flag is set."""
    set_flags = [
        name for name, flag in zip(names, flags)
        if flag is not None and flag is not False
    ]

    if len(set_flags) > 1:
        typer.echo(
            f"Error: {' and '.join(set_flags)} are mutually exclusive",
            err=True
        )
        raise typer.Exit(1)

# Usage
validate_mutually_exclusive(
    episode, latest, feed_id,
    names=["--episode", "--latest", "--feed-id"]
)
```

## Best Practices

1. **Parse in Order of Specificity**
   - Most specific patterns first (range with exact format)
   - Least specific last (keyword fallback)

2. **Provide Clear Error Messages**
   - Use `self.fail()` with helpful examples
   - Show expected format: "Expected format: '1-5' or '1,3,7'"

3. **Validate Early**
   - Check bounds and constraints during parsing
   - Fail fast with clear error messages

4. **Normalize Input**
   - Strip whitespace
   - Remove duplicates from lists
   - Convert to consistent case for keywords

5. **Use Appropriate Progress Indicators**
   - Simple `track()` for single operations
   - Multiple progress bars for complex workflows
   - Transient progress for temporary operations

6. **Handle Edge Cases**
   - Empty input
   - Out-of-bounds positions
   - Invalid separators
   - Mixed formats (don't silently ignore parts)

7. **Document Expected Formats**
   - In help text: show examples of each format
   - In error messages: remind users of valid formats

## References

### Official Documentation
- [Typer Custom Types](https://typer.tiangolo.com/tutorial/parameter-types/custom-types/)
- [Typer Multiple Values](https://typer.tiangolo.com/tutorial/multiple-values/arguments-with-multiple-values/)
- [Click Parameter Types](https://click.palletsprojects.com/en/stable/parameter-types/)
- [Rich Progress Bars](https://rich.readthedocs.io/en/stable/progress.html)

### Examples and Discussions
- [Typer Issue #77: Custom Parameter Types](https://github.com/fastapi/typer/issues/77)
- [Typer Discussion #590: Custom Parameter Types](https://github.com/fastapi/typer/discussions/590)
- [Click Issue #1898: Custom Parameter Types and convert()](https://github.com/pallets/click/issues/1898)
- [Parsing Comma-Separated Lists and Ranges (Gist)](https://gist.github.com/kgaughan/2491663)

### Related Libraries
- `click-params`: Pre-built Click parameter types for common patterns
- `typed-argument-parser`: Alternative type-safe argument parser

## Recommendations for Inkwell

1. **Implement Click ParamType for `--episode`**
   - Create `EpisodeSelector` class in `src/inkwell/cli_types.py`
   - Support all four patterns: position, range, list, keyword
   - Include comprehensive validation and error messages

2. **Use Rich Progress Bars**
   - Simple `track()` for single episode processing
   - Multi-bar Progress for batch operations with stages
   - Show: episode name, transcription progress, extraction progress

3. **Validate Mutual Exclusivity**
   - Create helper function for `--episode`, `--latest`, `--all` flags
   - Provide clear error messages when incompatible flags are used

4. **Document in Help Text**
   ```
   --episode TEXT  Select episode(s) to process:
                   - Single: '3' (third episode)
                   - Range: '1-5' (episodes 1 through 5)
                   - List: '1,3,7' (episodes at positions 1, 3, 7)
                   - Keyword: 'AI security' (search in titles/descriptions)
   ```

5. **Add Unit Tests**
   - Test each input pattern
   - Test validation (invalid ranges, empty input, etc.)
   - Test edge cases (single-episode feeds, out-of-bounds, etc.)

## Next Steps

1. Create `src/inkwell/cli_types.py` with `EpisodeSelector` class
2. Update `src/inkwell/cli.py` to use custom type
3. Add validation for mutual exclusivity
4. Implement Rich progress bars for batch processing
5. Write unit tests for all parsing patterns
6. Update documentation with examples
