# Research: Rich Library Progress Patterns for Long-Running Operations

**Date**: 2025-12-21
**Status**: Complete
**Purpose**: Understand best practices for showing progress with elapsed time in Rich library

## Executive Summary

Rich provides three main approaches for showing progress in long-running CLI operations:

1. **Status** - Simple spinner with message (no progress tracking)
2. **Progress** - Full progress bar with percentage, ETA, and customizable columns
3. **Live** - Low-level building block for custom displays

**Recommendation**: For Inkwell's transcription operations:
- Use **Status** for indeterminate operations where total time is unknown
- Use **Progress** with `TimeElapsedColumn` when tracking file downloads/processing
- Avoid **Live** unless building complex custom layouts

## Current Implementation in Inkwell

From `/Users/chekos/projects/gh/inkwell-cli/src/inkwell/cli.py`:

### Pattern 1: Progress with Spinner (Indeterminate)
```python
with Progress(
    SpinnerColumn(),
    TextColumn("[progress.description]{task.description}"),
    console=console,
) as progress:
    progress.add_task("Parsing RSS feed...", total=None)
    feed = await parser.fetch_feed(str(feed_config.url), feed_config.auth)
```

### Pattern 2: Status with Manual Updates
```python
status_display = console.status(
    "[dim]Checking cache...[/dim]",
    spinner="dots"
)
status_display.start()

# Later, update with elapsed time
elapsed = get_elapsed()
status_display.update(f"[dim]{message}[/dim] [cyan]({elapsed})[/cyan]")

# Finally
status_display.stop()
```

**Current Issues**:
- Manual elapsed time tracking with `time.time()` and custom `get_elapsed()` function
- No automatic time display
- Status doesn't auto-update the elapsed time

## Rich Library Best Practices

### 1. Status vs Progress vs Live

| Feature | Status | Progress | Live |
|---------|--------|----------|------|
| **Visual** | Spinner + message | Progress bar + metrics | Fully custom |
| **Use Case** | Unknown duration | Trackable progress | Complex layouts |
| **Auto-refresh** | Yes (4 Hz default) | Yes (10 Hz default) | Yes (4 Hz default) |
| **Elapsed Time** | Manual only | Built-in column | Custom |
| **Multiple Tasks** | No | Yes | Yes (custom) |
| **ETA/Speed** | No | Yes | Custom |

### 2. TimeElapsedColumn Implementation

From Rich source code analysis:

```python
class TimeElapsedColumn(ProgressColumn):
    """Renders time elapsed."""

    def render(self, task: "Task") -> Text:
        """Show time elapsed."""
        elapsed = task.finished_time if task.finished else task.elapsed
        if elapsed is None:
            return Text("-:--:--", style="progress.elapsed")
        delta = timedelta(seconds=max(0, int(elapsed)))
        return Text(str(delta), style="progress.elapsed")
```

**Key Implementation Details**:
- Uses `task.elapsed` property which auto-updates
- Shows finished time when task completes
- Displays in HH:MM:SS format
- No manual tracking needed - handled by Progress internally
- Refreshes automatically at 10 Hz by default

### 3. Auto-Refresh Mechanism

**Progress Auto-Refresh**:
- Default: 10 updates per second (`refresh_per_second=10`)
- Uses internal `Live` display for rendering
- Background thread updates task elapsed time
- Disable with `auto_refresh=False` (requires manual `refresh()` calls)

**Status Auto-Refresh**:
- Does NOT auto-update elapsed time
- Only refreshes the spinner animation
- Elapsed time must be manually tracked and displayed

**Live Auto-Refresh**:
- Default: 4 updates per second (`refresh_per_second=4`)
- Lower-level primitive used by Progress and Status

### 4. Recommended Pattern for Long-Running Operations

Based on official documentation and real-world examples:

#### For Indeterminate Operations (Unknown Duration)

**Option A: Status (Simple)**
```python
with console.status("[bold]Transcribing audio...[/bold]"):
    result = await transcribe()
```

**Pros**: Clean, simple, minimal code
**Cons**: No elapsed time display, no substep updates

**Option B: Progress with Spinner + TimeElapsedColumn**
```python
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

with Progress(
    SpinnerColumn(),
    TextColumn("[progress.description]{task.description}"),
    TimeElapsedColumn(),
    console=console,
) as progress:
    task = progress.add_task("Transcribing audio...", total=None)
    result = await transcribe()
```

**Pros**: Auto-updating elapsed time, can update description, professional look
**Cons**: Slightly more code than Status

#### For Determinate Operations (Known Duration/Size)

```python
from rich.progress import (
    Progress,
    SpinnerColumn,
    BarColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
    DownloadColumn,
    TransferSpeedColumn,
)

# For file downloads
with Progress(
    TextColumn("[progress.description]{task.description}"),
    BarColumn(),
    DownloadColumn(),
    TransferSpeedColumn(),
    TimeElapsedColumn(),
    TimeRemainingColumn(),
) as progress:
    task = progress.add_task("Downloading audio", total=file_size_bytes)
    for chunk in download_chunks():
        progress.update(task, advance=len(chunk))
```

### 5. How pip Uses Rich

From `pip/src/pip/_internal/cli/progress_bars.py`:

**For unknown file size (indeterminate)**:
```python
Progress(
    TextColumn("[progress.description]{task.description}"),
    SpinnerColumn("line", speed=1.5),
    FileSizeColumn(),
    TransferSpeedColumn(),
    TimeElapsedColumn(),
)
```

**For known file size (determinate)**:
```python
Progress(
    TextColumn("[progress.description]{task.description}"),
    BarColumn(),
    DownloadColumn(),
    TransferSpeedColumn(),
    TimeElapsedColumn(),
    TimeRemainingColumn(),
)
```

**Key Insights**:
- pip uses `TimeElapsedColumn()` for ALL progress bars
- Combines with spinner for indeterminate, bar for determinate
- Always shows transfer speed for downloads
- No manual elapsed time tracking

### 6. How uv Uses Progress (Rust/indicatif)

uv is written in Rust and uses the `indicatif` crate (not Rich), but follows similar patterns:
- Multi-progress bars for parallel operations
- Elapsed time display built into the crate
- Auto-refreshing progress indicators
- Similar column-based approach to Rich

## Comparison: Current vs Recommended Patterns

### Current Inkwell Pattern (Manual)
```python
import time

current_status = {"start_time": time.time()}

def get_elapsed() -> str:
    elapsed = time.time() - float(current_status["start_time"])
    mins, secs = divmod(int(elapsed), 60)
    if mins > 0:
        return f"{mins}m {secs}s"
    return f"{secs}s"

status_display = console.status("[dim]Checking cache...[/dim]")
status_display.start()

# Update with manual elapsed time
elapsed = get_elapsed()
status_display.update(f"[dim]{message}[/dim] [cyan]({elapsed})[/cyan]")
```

**Issues**:
- Manual time tracking prone to errors
- Elapsed time only updates when substep changes
- Not a "live" counter - just snapshots
- Extra complexity with global state

### Recommended Pattern (Automatic)
```python
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

with Progress(
    SpinnerColumn(),
    TextColumn("[progress.description]{task.description}"),
    TimeElapsedColumn(),
    console=console,
) as progress:
    task = progress.add_task("Checking cache...", total=None)

    # Update description as needed
    progress.update(task, description="Downloading audio file...")

    # Elapsed time updates automatically at 10 Hz
```

**Benefits**:
- Automatic elapsed time tracking and display
- Live updates every 100ms without manual intervention
- Clean code - no manual time management
- Consistent with pip and other professional CLI tools

## Technical Details: How Auto-Refresh Works

From Rich source code analysis:

### Progress Internal Mechanism

1. **Initialization**:
   - Progress creates internal `Live` object with `auto_refresh=True`
   - Sets `refresh_per_second=10` (100ms intervals)

2. **Background Thread**:
   - `_TrackThread` runs in background
   - Checks `task.elapsed` property every update period
   - Calls `progress.refresh()` which triggers `live.refresh()`

3. **Task.elapsed Property**:
   - Updated automatically based on `task.started_time`
   - Calculated as `time.time() - started_time`
   - No manual tracking needed

4. **Rendering**:
   - Each refresh, `TimeElapsedColumn.render()` called
   - Reads current `task.elapsed` value
   - Formats as timedelta string
   - Displays in terminal

### Why This Matters

**For developers**:
- Don't track time manually
- Don't calculate elapsed time
- Don't format time strings
- Just use `TimeElapsedColumn()` and it works

**For users**:
- See live-updating elapsed time (10 updates/sec)
- Consistent time format across all tools
- Professional appearance

## Real-World Examples from Rich Documentation

### Example 1: Simple Indeterminate Progress with Elapsed Time
```python
from rich.progress import Progress, SpinnerColumn, TimeElapsedColumn

with Progress(
    SpinnerColumn(),
    *Progress.get_default_columns(),
    TimeElapsedColumn(),
) as progress:
    task = progress.add_task("Processing...", total=None)
    # Do work...
```

### Example 2: Multiple Tasks with Different Columns
```python
from rich.progress import Progress

# Create separate Progress instances for different purposes
current_app_progress = Progress(TimeElapsedColumn(), TextColumn("{task.description}"))
step_progress = Progress(SpinnerColumn("simpleDots"), TextColumn("{task.fields[action]}"))

# Combine them in a Live display if needed
```

### Example 3: Updating Task Description
```python
with Progress() as progress:
    task = progress.add_task("Starting...", total=None)

    progress.update(task, description="Checking cache...")
    await check_cache()

    progress.update(task, description="Downloading...")
    await download()

    progress.update(task, description="Processing...")
    await process()
```

## Recommendations for Inkwell

### 1. Replace Manual Elapsed Time Tracking

**Current** (lines 886-931 in cli.py):
```python
current_status: dict[str, object] = {
    "step": "",
    "substep": "",
    "start_time": time.time(),
}

def get_elapsed() -> str:
    elapsed = time.time() - float(current_status["start_time"])
    mins, secs = divmod(int(elapsed), 60)
    if mins > 0:
        return f"{mins}m {secs}s"
    return f"{secs}s"

status_display = console.status("[dim]Checking cache...[/dim]")
status_display.start()

# Manual updates
elapsed = get_elapsed()
status_display.update(f"[dim]{message}[/dim] [cyan]({elapsed})[/cyan]")
```

**Recommended**:
```python
with Progress(
    SpinnerColumn(),
    TextColumn("[progress.description]{task.description}"),
    TimeElapsedColumn(),
    console=console,
) as progress:
    task = progress.add_task("Checking cache...", total=None)

    # Update description as substeps change
    progress.update(task, description="Trying YouTube transcript...")
    progress.update(task, description="Downloading audio file...")
    progress.update(task, description="Transcribing with Gemini...")
```

### 2. Use Consistent Pattern Across All Operations

**For indeterminate operations**:
```python
Progress(SpinnerColumn(), TextColumn("{task.description}"), TimeElapsedColumn())
```

**For determinate operations** (future):
```python
Progress(
    TextColumn("{task.description}"),
    BarColumn(),
    DownloadColumn(),  # if file download
    TimeElapsedColumn(),
    TimeRemainingColumn(),
)
```

### 3. Remove Manual Time Tracking Code

- Delete `current_status` dictionary
- Delete `get_elapsed()` function
- Let Rich handle all time tracking automatically

### 4. Benefits of This Change

**Code Quality**:
- Simpler code (remove 50+ lines)
- No global state management
- No manual time calculations
- Self-documenting with column names

**User Experience**:
- Live-updating elapsed time (10 Hz)
- Consistent time format
- Professional appearance matching pip/uv
- Better visual feedback

**Maintainability**:
- Standard Rich patterns
- Less custom code to maintain
- Easier for contributors to understand

## Related Patterns

### Nested Progress Bars
```python
with Progress() as progress:
    overall = progress.add_task("Processing all episodes", total=10)

    for episode in episodes:
        episode_task = progress.add_task(f"Episode: {episode.title}", total=None)
        # Process episode
        progress.update(overall, advance=1)
```

### Progress with Logging
```python
from rich.progress import Progress
from rich.console import Console

console = Console()

with Progress(console=console) as progress:
    task = progress.add_task("Working...", total=None)

    # These will appear above the progress bar
    console.log("Step 1 complete")
    console.log("Step 2 complete")
```

### Custom Column Creation
```python
from rich.progress import ProgressColumn, Task, Text

class MyCustomColumn(ProgressColumn):
    def render(self, task: Task) -> Text:
        return Text(f"Custom: {task.fields.get('custom_value', 'N/A')}")

# Use it
with Progress(SpinnerColumn(), MyCustomColumn(), TimeElapsedColumn()) as progress:
    task = progress.add_task("Working...", total=None, custom_value="123")
```

## Testing Considerations

### Terminal Detection
Rich automatically detects terminal capabilities:
- In CI/CD (non-TTY): Disables animations
- In IDE terminals: Full color support
- In file redirection: Plain text output

### Manual Testing
```python
# Test in different environments
$ python -m inkwell fetch ... # Normal terminal
$ python -m inkwell fetch ... | tee log.txt # Piped output
$ python -m inkwell fetch ... > output.txt # File redirect
```

### Jupyter Notebooks
Auto-refresh is disabled in Jupyter:
```python
# Must manually refresh or use refresh=True
progress.refresh()
# or
progress.update(task, advance=1, refresh=True)
```

## Performance Considerations

### Refresh Rate Impact
- Default 10 Hz (100ms) has negligible CPU impact
- Can reduce to 4 Hz for slower operations: `refresh_per_second=4`
- Can disable for very fast operations: `auto_refresh=False`

### Memory Usage
- Progress bars use minimal memory (~1KB per task)
- TimeElapsedColumn stores single timestamp per task
- No accumulation of historical data

## Anti-Patterns to Avoid

### 1. Don't Mix Status and Progress for Same Operation
```python
# BAD - creates two separate displays
with console.status("Working..."):
    with Progress() as progress:
        task = progress.add_task("Processing...")
```

### 2. Don't Track Time Manually When Using Progress
```python
# BAD - TimeElapsedColumn already does this
start = time.time()
with Progress(TimeElapsedColumn()) as progress:
    elapsed = time.time() - start  # Unnecessary!
```

### 3. Don't Update Too Frequently
```python
# BAD - updates faster than refresh rate
with Progress() as progress:
    task = progress.add_task("Working...", total=1000)
    for i in range(1000):
        progress.update(task, advance=1)  # 1000 updates!

# GOOD - batch updates
with Progress() as progress:
    task = progress.add_task("Working...", total=1000)
    for i in range(0, 1000, 10):
        # Do 10 items worth of work
        progress.update(task, advance=10)  # 100 updates
```

## Summary: Key Takeaways

1. **Use Progress, not Status** for long-running operations where elapsed time matters
2. **TimeElapsedColumn auto-updates** at 10 Hz - no manual tracking needed
3. **Pattern**: `Progress(SpinnerColumn(), TextColumn(), TimeElapsedColumn())`
4. **Update task description** to show substeps: `progress.update(task, description="...")`
5. **Follow pip's example** - industry standard for CLI progress display
6. **Remove manual time tracking** - simpler code, better UX

## References

- [Rich Progress Display Documentation](https://rich.readthedocs.io/en/latest/progress.html)
- [Rich Live Display Documentation](https://rich.readthedocs.io/en/stable/live.html)
- [Rich Progress API Reference](https://rich.readthedocs.io/en/stable/reference/progress.html)
- [pip's Progress Bar Implementation](https://github.com/pypa/pip/blob/main/src/pip/_internal/cli/progress_bars.py)
- [Rich Examples - Dynamic Progress](https://github.com/Textualize/rich/blob/master/examples/dynamic_progress.py)
- [Using Rich Status Module](https://brianlinkletter.com/2021/03/using-python-rich-library-status-module/)
- [Real Python: Rich Package Guide](https://realpython.com/python-rich-package/)

## Next Steps

1. Update `fetch` command to use Progress with TimeElapsedColumn
2. Remove manual elapsed time tracking code
3. Test in different terminal environments
4. Update documentation with new pattern
5. Consider creating ADR for this pattern change
