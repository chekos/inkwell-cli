# Research: Smart CLI Argument Parsing for Episode Selection

**Date:** 2025-12-21
**Status:** Complete
**Related Issues:** Episode selection functionality
**Tags:** CLI, argument-parsing, UX, yt-dlp

## Overview

This research investigates best practices for implementing flexible CLI argument parsing that auto-detects input types for the `--episode/-e` flag in Inkwell. The goal is to support multiple input formats:

- **Position numbers:** `"3"` → fetch episode at position 3
- **Ranges:** `"1-5"` → fetch episodes 1-5
- **Multiple selections:** `"1,3,7"` → fetch specific positions
- **Keyword search:** `"AI security"` → search by title

## Key Findings

### 1. yt-dlp Implementation (Gold Standard)

yt-dlp's `--playlist-items` is considered the gold standard for range parsing in CLI tools. Here's their complete implementation:

#### Regex Pattern
```python
PLAYLIST_ITEMS_RE = re.compile(r'''(?x)
    (?P<start>[+-]?\d+)?
    (?P<range>[:-]
        (?P<end>[+-]?\d+|inf(?:inite)?)?
        (?::(?P<step>[+-]?\d+))?
    )?''')
```

**Pattern breakdown:**
- `(?P<start>[+-]?\d+)?` - Optional start number (supports negative indices)
- `(?P<range>[:-]...)?` - Optional range operator (`:` or `-`)
- `(?P<end>[+-]?\d+|inf(?:inite)?)?` - Optional end (supports `inf`/`infinite` for "to end")
- `(?::(?P<step>[+-]?\d+))?` - Optional step size (e.g., `1:10:2` for every other)

#### Parser Implementation
```python
@classmethod
def parse_playlist_items(cls, string):
    for segment in string.split(','):
        if not segment:
            raise ValueError('There is two or more consecutive commas')
        mobj = cls.PLAYLIST_ITEMS_RE.fullmatch(segment)
        if not mobj:
            raise ValueError(f'{segment!r} is not a valid specification')
        start, end, step, has_range = mobj.group('start', 'end', 'step', 'range')
        if int_or_none(step) == 0:
            raise ValueError(f'Step in {segment!r} cannot be zero')
        yield slice(int_or_none(start), float_or_none(end), int_or_none(step)) if has_range else int(start)
```

**Key features:**
- Split on commas for multiple selections
- Validate each segment with regex
- Return Python `slice` objects for ranges, `int` for single items
- Clear error messages for invalid input
- Support negative indices (e.g., `-1` for last item)
- Generator pattern for memory efficiency

**Example usage:**
- `yt-dlp -I 2,4:6,-1` → items 2, 4, 5, 6, and last item
- `yt-dlp --playlist-items 1:5` → items 1-5
- `yt-dlp --playlist-items 1::2` → every other item starting from 1

**Source:** [yt-dlp utils/_utils.py](https://github.com/yt-dlp/yt-dlp/blob/master/yt_dlp/utils/_utils.py)

---

### 2. Simple Range Parsing Library Pattern

For basic comma-separated ranges without steps, this GitHub Gist pattern is widely used:

```python
from itertools import chain

def parse_range(rng):
    """Parse a single range like '2-5' or '7'"""
    parts = rng.split('-')
    if 1 > len(parts) > 2:
        raise ValueError(f"Bad range: '{rng}'")
    parts = [int(i) for i in parts]
    start = parts[0]
    end = start if len(parts) == 1 else parts[1]
    if start > end:
        end, start = start, end  # Auto-reverse
    return range(start, end + 1)

def parse_range_list(rngs):
    """Parse comma-separated ranges like '2-5,7,15-17,12'"""
    return sorted(set(chain(*[parse_range(rng) for rng in rngs.split(',')])))
```

**Example:** `'2-5,7,15-17,12'` → `[2, 3, 4, 5, 7, 12, 15, 16, 17]`

**Source:** [GitHub Gist by kgaughan](https://gist.github.com/kgaughan/2491663)

---

### 3. Typer/Click Custom Type Patterns

#### Pattern 1: Custom Parser Function (Typer)
```python
from typing_extensions import Annotated
import typer

def parse_episode_spec(value: str) -> list[int]:
    """Parse episode specification: '3', '1-5', '1,3,7', etc."""
    try:
        # Try simple int first
        return [int(value)]
    except ValueError:
        # Check if it's numeric range/list
        if any(c in value for c in ['-', ',']):
            return parse_range_list(value)
        # Otherwise treat as search query
        raise typer.BadParameter(
            f"'{value}' must be a number, range (1-5), or list (1,3,7)"
        )

@app.command()
def process(
    episode: Annotated[list[int], typer.Option(parser=parse_episode_spec)]
):
    print(f"Processing episodes: {episode}")
```

**Source:** [Typer Custom Types Documentation](https://typer.tiangolo.com/tutorial/parameter-types/custom-types/)

#### Pattern 2: Click ParamType Class
```python
import click

class EpisodeSpec(click.ParamType):
    name = "episode_spec"

    def convert(self, value, param, ctx):
        if isinstance(value, list):
            return value

        try:
            # Try single number
            return [int(value)]
        except ValueError:
            pass

        # Check for range/list notation
        if any(c in value for c in ['-', ',']):
            try:
                return parse_range_list(value)
            except ValueError as e:
                self.fail(f"Invalid range format: {e}", param, ctx)

        # Treat as search query - return None to signal keyword search
        return None

EPISODE_SPEC = EpisodeSpec()

@click.option('--episode', '-e', type=EPISODE_SPEC)
def process(episode):
    if episode is None:
        # Perform keyword search
        pass
    else:
        # Process episode numbers
        pass
```

**Key features:**
- Check if value is already converted (support defaults)
- Return early for valid types
- Use `self.fail()` for errors (proper Click error handling)
- Can return different types to signal different behaviors

**Source:** [Click Parameter Types Documentation](https://click.palletsprojects.com/en/stable/parameter-types/)

---

### 4. Auto-Detecting Numeric vs String Input

Best practice is to use a **heuristic-based approach** rather than pure auto-detection:

```python
def classify_episode_input(value: str) -> tuple[str, any]:
    """
    Classify input type and return (type, parsed_value).

    Returns:
        ('single', int) - Single episode number
        ('range', list[int]) - Range or list of episodes
        ('search', str) - Keyword search query
    """
    # Quick check: if it contains only digits, commas, hyphens, colons
    if re.match(r'^[0-9,:\-\s]+$', value):
        try:
            # Try parsing as range spec
            episodes = parse_range_list(value)
            if len(episodes) == 1:
                return ('single', episodes[0])
            return ('range', episodes)
        except ValueError:
            # Failed to parse as numeric, treat as search
            return ('search', value)

    # Contains non-numeric characters, definitely a search
    return ('search', value)
```

**Rationale:** Auto-detection is ambiguous for edge cases like "20" (episode 20 or search for "20"?). Better to use clear patterns:
- Pure numeric characters → episode numbers
- Contains letters → keyword search
- Mixed with special chars only (`,`, `-`, `:`) → ranges

**Source:** [Python argparse documentation](https://docs.python.org/3/library/argparse.html)

---

### 5. Error Handling Best Practices

#### Clear, Actionable Error Messages
```python
try:
    episodes = parse_range_list(value)
except ValueError as e:
    raise typer.BadParameter(
        f"Invalid episode format: {value!r}\n"
        f"Error: {e}\n"
        f"Valid formats:\n"
        f"  - Single: 3\n"
        f"  - Range: 1-5\n"
        f"  - List: 1,3,7\n"
        f"  - Mixed: 1-3,5,7-9"
    )
```

#### Validate Ranges Within Bounds
```python
def validate_episode_numbers(episodes: list[int], max_episodes: int):
    """Validate episode numbers are within valid range."""
    invalid = [e for e in episodes if e < 1 or e > max_episodes]
    if invalid:
        raise ValueError(
            f"Episode(s) {invalid} out of range. "
            f"Feed has {max_episodes} episodes (1-{max_episodes})"
        )
```

**Key principles:**
1. Catch specific exceptions (ValueError, not Exception)
2. Provide examples of valid input
3. Show what went wrong clearly
4. Use re-prompting loops for interactive CLIs
5. Raise custom exceptions with context

**Source:** [Python Input Validation Best Practices - DataCamp](https://www.datacamp.com/tutorial/python-user-input)

---

### 6. Batch Processing with Progress Indication

#### Using Rich's `track()` with Typer
```python
from rich.progress import track
import typer

@app.command()
def download(episodes: str):
    episode_list = parse_range_list(episodes)

    results = []
    for ep_num in track(episode_list, description="Downloading episodes..."):
        result = download_episode(ep_num)
        results.append(result)

    typer.echo(f"✓ Downloaded {len(results)} episodes")
```

#### Manual Progress with Multiple Metrics
```python
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

with Progress(
    SpinnerColumn(),
    TextColumn("[progress.description]{task.description}"),
    BarColumn(),
    TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
) as progress:
    download_task = progress.add_task("Downloading...", total=len(episodes))

    for ep_num in episodes:
        progress.update(download_task, description=f"Episode {ep_num}")
        download_episode(ep_num)
        progress.advance(download_task)
```

#### Handling Errors During Batch Processing
```python
from rich.console import Console

console = Console()
errors = []

for ep_num in track(episodes, description="Processing"):
    try:
        process_episode(ep_num)
    except Exception as e:
        errors.append((ep_num, str(e)))
        console.print(f"[yellow]⚠[/yellow] Episode {ep_num} failed: {e}")
        continue

if errors:
    console.print(f"\n[red]✗[/red] {len(errors)} episodes failed")
    for ep_num, error in errors:
        console.print(f"  Episode {ep_num}: {error}")
```

**Source:**
- [Typer Progress Bar Documentation](https://typer.tiangolo.com/tutorial/progressbar/)
- [Rich Progress Display Documentation](https://rich.readthedocs.io/en/stable/progress.html)

---

### 7. Python Libraries for Range Parsing

**No standard library exists** for this specific use case. Most projects use custom implementations. Options:

1. **Custom implementation** (recommended for control and simplicity)
   - Based on yt-dlp pattern or gist pattern above
   - ~20 lines of code
   - Full control over error messages

2. **NumPy's index notation** (overkill for CLI parsing)
   - Only works with actual arrays
   - Not suitable for parsing strings

3. **pyparsing** (too complex for this use case)
   - General-purpose parsing library
   - Heavy dependency for simple range parsing

**Recommendation:** Use custom implementation based on yt-dlp pattern for robustness, or simpler gist pattern if step notation isn't needed.

---

## Implementation Recommendations for Inkwell

### Recommended Approach

1. **Use a hybrid detection strategy:**
   ```python
   def parse_episode_arg(value: str, feed_episodes: list) -> list[int]:
       """Parse --episode argument with auto-detection."""
       # Check if purely numeric specification
       if re.match(r'^[0-9,:\-\s]+$', value):
           return parse_episode_range(value)

       # Otherwise, treat as keyword search
       return search_episodes_by_title(value, feed_episodes)
   ```

2. **Implement yt-dlp-style parser for numeric specs:**
   - Support: `3`, `1-5`, `1,3,7`, `1-3,5,7-9`
   - Consider adding: `1:10:2` (every 2nd episode from 1-10) if needed
   - Support negative indices: `-1` for latest, `-5` for 5th from end

3. **Provide clear error messages:**
   ```python
   Episode specification '1-a' is invalid.

   Valid formats:
     --episode 3          # Single episode
     --episode 1-5        # Range
     --episode 1,3,7      # Multiple episodes
     --episode "AI"       # Search by title
   ```

4. **Use Rich for batch progress:**
   - Show progress bar when processing multiple episodes
   - Display current episode being processed
   - Summarize errors at the end

5. **Validate against feed bounds:**
   ```python
   if max(episodes) > len(feed_episodes):
       raise ValueError(
           f"Episode {max(episodes)} not found. "
           f"Feed has only {len(feed_episodes)} episodes."
       )
   ```

### Example Implementation Sketch

```python
from typing import Annotated
import re
import typer
from rich.progress import track

def parse_episode_spec(value: str) -> list[int] | str:
    """Parse episode specification or return search query."""
    # Purely numeric spec
    if re.match(r'^[0-9,\-:\s]+$', value):
        return parse_range_list(value)  # Returns list[int]

    # Keyword search
    return value  # Returns str

def process_episodes(
    feed_url: str,
    episode: Annotated[str, typer.Option(
        "--episode", "-e",
        help="Episode selection: number (3), range (1-5), list (1,3,7), or search ('AI')"
    )]
):
    feed = parse_feed(feed_url)

    # Parse episode specification
    spec = parse_episode_spec(episode)

    if isinstance(spec, list):
        # Numeric selection
        episodes_to_process = [feed.episodes[i-1] for i in spec]
    else:
        # Keyword search
        episodes_to_process = search_episodes(feed.episodes, spec)

    # Process with progress
    for ep in track(episodes_to_process, description="Processing episodes"):
        process_episode(ep)
```

---

## References

### Documentation
- [yt-dlp Playlist Handling](https://yt-dlp.eknerd.com/docs/advanced%20features/playlist-handling/)
- [yt-dlp Manual Page](https://man.archlinux.org/man/yt-dlp.1)
- [Typer Custom Types](https://typer.tiangolo.com/tutorial/parameter-types/custom-types/)
- [Click Parameter Types](https://click.palletsprojects.com/en/stable/parameter-types/)
- [Typer Progress Bar](https://typer.tiangolo.com/tutorial/progressbar/)
- [Rich Progress Display](https://rich.readthedocs.io/en/stable/progress.html)

### Source Code Examples
- [yt-dlp parse_playlist_items](https://github.com/yt-dlp/yt-dlp/blob/master/yt_dlp/utils/_utils.py)
- [Python Range Parsing Gist](https://gist.github.com/kgaughan/2491663)

### Articles & Tutorials
- [Comparing Python CLI Tools - Medium](https://medium.com/@mohd_nass/navigating-the-cli-landscape-in-python-a-comparative-study-of-argparse-click-and-typer-480ebbb7172f)
- [Python Input Validation - DataCamp](https://www.datacamp.com/tutorial/python-user-input)
- [Error Handling Best Practices - TerminalNotes](https://terminalnotes.com/python-basics-part-10-error-handling-and-exception-patterns/)

---

## Next Steps

1. Decide on feature scope:
   - Do we need step notation (`1:10:2`)?
   - Do we support negative indices (`-1`, `-5`)?
   - Do we support `inf` for "all remaining"?

2. Implement parser based on yt-dlp pattern

3. Add comprehensive tests:
   - Valid ranges: `"3"`, `"1-5"`, `"1,3,7"`, `"1-3,5,7-9"`
   - Invalid input: `"1-"`, `"a-b"`, `"1--5"`, `"1,"`
   - Edge cases: `""`, `"0"`, negative numbers
   - Boundary validation

4. Create ADR documenting the decision and rationale

5. Update CLI help text with clear examples
