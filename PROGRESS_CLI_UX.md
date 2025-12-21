# CLI UX Improvement Plan: Multi-Stage Progress Display

**Created:** 2025-12-21
**Status:** Complete
**Goal:** Replace frozen elapsed time display with Docker-style multi-stage progress

## Problem Statement

The current `inkwell fetch` command has poor UX:
1. Elapsed time shows "(0s)" and stays frozen during long operations
2. Uses `console.status()` which doesn't auto-update the time
3. Users don't know what's happening during 5-10 minute transcription jobs
4. No indication of overall progress through the pipeline

## Research Findings

### Technical (Rich Library)
- `Status` does NOT auto-update elapsed time - manual tracking required
- `Progress` with `TimeElapsedColumn` auto-updates at 10 Hz automatically
- This is how pip implements their progress display

### UX Best Practices
- **Don't show elapsed time counting UP** - it's "psychological torture"
- **Show time remaining (countdown)** instead - reduces perceived wait time
- **Show all stages upfront** (Docker model) - users can see overall progress
- **Use determinate progress bars** for operations >10 seconds

## Target UX (Docker-style)

```
Inkwell Extraction Pipeline
Output: /Users/chekos/podcasts

[1/4] Transcribing    ━━━━━━━━━━━━━━━━━━━━ 100%  3m 24s
[2/4] Selecting       ━━━━━━━━━━━━━━━━━━━━ 100%  0.2s
[3/4] Extracting      ━━━━━━━━━━━╸━━━━━━━━  52%  ~1m remaining
[4/4] Writing         ○ pending
```

For indeterminate operations (unknown duration), show:
```
[1/4] Transcribing    ◐ Downloading audio...     2m 15s
```

## Implementation Plan

### Phase 1: Create Progress Display Component

**File:** `src/inkwell/cli/progress.py` (new file)

Create a reusable `PipelineProgress` class that:
- Shows all 4 stages upfront (transcribe, select, extract, write)
- Uses Rich's `Progress` with auto-updating `TimeElapsedColumn`
- Supports both determinate (with %) and indeterminate (spinner) modes
- Updates stage status: pending → in_progress → complete
- Shows sub-step descriptions (e.g., "Downloading audio...", "Trying YouTube...")

### Phase 2: Update CLI fetch command

**File:** `src/inkwell/cli.py` (lines ~860-1020)

Replace current `handle_progress` callback with new progress display:
- Remove manual `time.time()` tracking
- Remove `Status` usage
- Use new `PipelineProgress` component
- Map transcription sub-steps to progress updates

### Phase 3: Add Time Remaining Estimates

**File:** `src/inkwell/utils/time_estimates.py` (new file)

- Store historical durations in config/cache
- Calculate estimates based on episode duration
- Show "~Xm remaining" for long operations

## Files to Modify

1. **src/inkwell/cli.py**
   - Lines 10-13: Update imports (remove unused, add Progress components)
   - Lines 860-1020: Rewrite `run_fetch()` progress handling
   - Remove `current_status` dict and `get_elapsed()` function
   - Remove `status_display` variable and manual updates

2. **src/inkwell/pipeline/orchestrator.py**
   - Already has progress callbacks - no changes needed
   - Sub-step callbacks already implemented in transcription

3. **src/inkwell/transcription/manager.py**
   - Already emits progress callbacks - no changes needed

## Key Code Sections

### Current Progress Callback (to replace)
Location: `src/inkwell/cli.py` lines ~888-1009

```python
# This entire section needs rewriting:
current_status: dict[str, object] = {
    "step": "",
    "substep": "",
    "start_time": time.time(),
}
status_display: Status | None = None

def get_elapsed() -> str:
    # Manual time tracking - REMOVE
    ...

def handle_progress(step_name: str, step_data: dict[str, Any]) -> None:
    # 100+ lines of manual status management - REPLACE
    ...
```

### New Progress Display Pattern
```python
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeElapsedColumn

# Create progress with all stages visible
with Progress(
    SpinnerColumn(),
    TextColumn("[progress.description]{task.description}"),
    BarColumn(),
    TaskProgressColumn(),
    TimeElapsedColumn(),
    console=console,
) as progress:
    # Add all tasks upfront
    transcribe_task = progress.add_task("[cyan]Transcribing", total=None)
    select_task = progress.add_task("[dim]Selecting", total=None, visible=True)
    extract_task = progress.add_task("[dim]Extracting", total=None, visible=True)
    write_task = progress.add_task("[dim]Writing", total=None, visible=True)

    # Update as pipeline progresses
    progress.update(transcribe_task, description="[cyan]Transcribing: Downloading audio...")
```

## Testing

After implementation:
1. Run `uv run inkwell fetch lennys --latest`
2. Verify elapsed time updates continuously (not frozen)
3. Verify all 4 stages show from the start
4. Verify sub-step descriptions update correctly
5. Verify completion checkmarks appear

## Related Files Created

- `/Users/chekos/projects/gh/inkwell-cli/docs/research/rich-progress-patterns.md`
- `/Users/chekos/projects/gh/inkwell-cli/docs/research/cli-progress-indicators-ux.md`

## Implementation Complete

### What Was Implemented

1. **PipelineProgress Component** (`src/inkwell/utils/progress.py`)
   - Docker-style multi-stage progress display
   - Uses Rich's `Progress` with `TimeElapsedColumn` for auto-updating time
   - Shows all stages upfront with pending/in_progress/complete states
   - Spinner for indeterminate progress, checkmarks for completion

2. **CLI Integration** (`src/inkwell/cli.py`)
   - Replaced manual `time.time()` tracking with `PipelineProgress`
   - Removed `Status` component that didn't auto-update
   - Maps transcription sub-steps to user-friendly messages
   - Shows 4 stages (or 5 with interview)

3. **Audio Download Caching** (`src/inkwell/audio/downloader.py`)
   - Added URL-hash-based caching to `~/Library/Caches/inkwell/audio/`
   - Prevents re-downloading same episodes (saves ~10 min per episode)
   - Cache can be bypassed with `use_cache=False`

4. **Bug Fixes**
   - `transcript.text` → `transcript.full_text` in manager.py
   - `TemplateSelector(loader=loader)` → `TemplateSelector(loader)`
   - Added error handling around cost tracking so it doesn't crash transcription

### Result

```
Inkwell Extraction Pipeline
Output: /Users/chekos/podcasts

✓ [1/4] Transcribing        ✓ from cache  0:00:00
✓ [2/4] Selecting templates ✓ 4 templates 0:00:00
⠋ [3/4] Extracting content  Processing... 0:00:45
⠋ [4/4] Writing files       ○ pending     0:00:45
```

## Git Status

Modified files (uncommitted):
- `docs/tutorial.md` - Updated to use Lenny's Podcast
- `docs/inkwell-list.svg` - Regenerated with lennys feed
- `src/inkwell/cli.py` - Config display simplification + new progress display
- `src/inkwell/utils/progress.py` - NEW: PipelineProgress component
- `src/inkwell/audio/downloader.py` - Added audio download caching
- `src/inkwell/transcription/manager.py` - Added progress callbacks + bug fixes
- `src/inkwell/pipeline/orchestrator.py` - Added transcription progress passthrough + bug fix
- `tests/unit/audio/test_downloader.py` - Updated for cache behavior
- `tests/unit/transcription/test_manager.py` - Updated error message test
