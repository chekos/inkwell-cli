# Lessons Learned: Phase 2 Unit 8 - CLI Integration

**Date:** 2025-11-07
**Unit:** Phase 2, Unit 8
**Component:** CLI commands for transcription and cache management
**Duration:** ~1.5 hours
**Lines of Code:** ~171 new (2 commands)

---

## Summary

Integrated TranscriptionManager with CLI by adding two new commands: `transcribe` (main transcription interface) and `cache` (cache management). Implemented async/await bridging, Rich progress bars, cost confirmation UX, and comprehensive error handling.

---

## Key Lessons Learned

### 1. Typer B008 False Positive and Configuration

**What Happened:**
Linter flagged B008 error for `typer.Option()` calls in function parameter defaults, which is the standard Typer pattern.

**The Error:**
```
B008 Do not perform function call `typer.Option` in argument defaults
```

**Why It's a False Positive:**
Typer's design requires function calls in defaults for CLI parameter definitions. This is documented behavior:
```python
def command(
    output: Path | None = typer.Option(None, "--output", "-o", help="..."),  # ✓ Correct
):
    pass
```

**Solution:**
Add per-file ignore in `pyproject.toml`:
```toml
[tool.ruff.lint.per-file-ignores]
"src/inkwell/cli.py" = ["B008"]  # Allow typer.Option in function defaults (Typer pattern)
```

**Lesson:** For framework-specific patterns that violate general linting rules, use per-file ignores with clear comments explaining why.

---

### 2. Bridging Sync CLI with Async Operations

**Pattern:**
```python
@app.command("transcribe")
def transcribe_command(...) -> None:  # Sync signature (Typer requirement)
    """Command docstring"""

    async def run_transcription() -> None:
        # Async operations
        manager = TranscriptionManager()
        result = await manager.transcribe(url)

    # Bridge: Run async code from sync function
    asyncio.run(run_transcription())
```

**Why This Works:**
- Typer commands must be synchronous functions
- `asyncio.run()` creates new event loop for async operations
- Keeps async logic isolated in inner function
- Error handling can happen at either level

**Benefits:**
- Clean separation of CLI layer (sync) and business logic (async)
- No need for complex event loop management
- Works with Typer's parameter injection

**Lesson:** Use `asyncio.run()` wrapper pattern to integrate async operations into sync CLI frameworks.

---

### 3. Interactive Cost Confirmation UX

**Pattern:**
```python
def confirm_cost(estimate: CostEstimate) -> bool:
    """Callback for cost confirmation."""
    console.print(
        f"\n[yellow]⚠[/yellow] Gemini transcription will cost approximately "
        f"[bold]{estimate.formatted_cost}[/bold]"
    )
    console.print(f"[dim]File size: {estimate.file_size_mb:.1f} MB[/dim]")
    return typer.confirm("Proceed with transcription?")

manager = TranscriptionManager(cost_confirmation_callback=confirm_cost)
```

**Benefits:**
- User sees cost estimate before spending money
- Can cancel if cost too high
- Callback pattern allows different UX in CLI vs library usage
- Cost estimate includes file size context

**Alternative Considered:**
Always auto-confirm below threshold, but rejected because:
- Thresholds are subjective
- Better to always confirm for transparency
- User can skip confirmation in future if desired

**Lesson:** For operations with financial cost, always confirm with user and show clear cost estimate.

---

### 4. Rich Progress Integration Patterns

**Basic Progress Spinner:**
```python
with Progress(
    SpinnerColumn(),
    TextColumn("[progress.description]{task.description}"),
    console=console,
) as progress:
    task = progress.add_task("Transcribing...", total=None)
    result = await manager.transcribe(url)
    progress.update(task, completed=True)
```

**Why This Pattern:**
- `total=None` for indeterminate progress (unknown duration)
- Spinner gives visual feedback that work is happening
- Auto-closes when context exits
- Reuses global `console` for consistent output

**Not Used (Yet):**
Percentage-based progress bars because:
- Transcription duration unpredictable
- Multiple tiers with different durations
- Would need progress callbacks from yt-dlp and Gemini

**Lesson:** Use spinners for operations with unpredictable duration; save progress bars for measurable tasks.

---

### 5. CLI Output Organization

**Pattern:**
```python
# Success path
console.print("\n[green]✓[/green] Transcription complete")
console.print(f"[dim]Source: {result.transcript.source}[/dim]")
console.print(f"[dim]Language: {result.transcript.language}[/dim]")
console.print(f"[dim]Duration: {result.duration_seconds:.1f}s[/dim]")

if result.cost_usd > 0:
    console.print(f"[dim]Cost: ${result.cost_usd:.4f}[/dim]")

if result.from_cache:
    console.print("[dim]✓ Retrieved from cache[/dim]")
```

**Design Choices:**
- Success symbol (✓) with color
- Metadata in dim style (secondary information)
- Conditional output (cost only if > 0, cache only if from cache)
- Consistent formatting across commands

**Lesson:** Structure CLI output hierarchically - primary message, then metadata, then conditional details.

---

### 6. Error Handling in CLI Commands

**Pattern:**
```python
try:
    # Main operation
    result = await manager.transcribe(url)

    if not result.success:
        console.print(f"[red]✗[/red] Transcription failed: {result.error}")
        sys.exit(1)

    # Success handling...

except KeyboardInterrupt:
    console.print("\n[yellow]Cancelled by user[/yellow]")
    sys.exit(130)  # Standard Unix exit code for SIGINT
except Exception as e:
    console.print(f"[red]✗[/red] Error: {e}")
    sys.exit(1)
```

**Exit Codes:**
- `0`: Success
- `1`: General error
- `130`: User cancellation (CTRL+C)

**Why This Matters:**
- Scripts can check exit codes
- Different errors have different codes
- KeyboardInterrupt handled gracefully

**Lesson:** Always handle KeyboardInterrupt separately and use appropriate exit codes for CLI tools.

---

## Patterns to Repeat

### 1. Async CLI Command Pattern
```python
@app.command("name")
def sync_command(...) -> None:
    async def async_logic() -> None:
        # Async operations
        pass

    asyncio.run(async_logic())
```

### 2. Cost Confirmation Callback
```python
def confirm_callback(estimate: CostEstimate) -> bool:
    # Show estimate
    # Prompt user
    return user_decision

manager = Manager(cost_confirmation_callback=confirm_callback)
```

### 3. Conditional Metadata Display
```python
if value > 0:
    console.print(f"[dim]Metric: {value}[/dim]")

if from_cache:
    console.print("[dim]✓ From cache[/dim]")
```

---

## Anti-Patterns to Avoid

❌ **Don't make Typer commands async**
```python
@app.command("name")
async def command(...):  # BAD: Typer doesn't support this
    pass
```

✅ **Use asyncio.run() wrapper**
```python
@app.command("name")
def command(...):
    async def run():
        pass
    asyncio.run(run())
```

---

❌ **Don't ignore framework-specific linter warnings without documentation**
```toml
"src/inkwell/cli.py" = ["B008"]  # BAD: No explanation
```

✅ **Document why it's safe to ignore**
```toml
"src/inkwell/cli.py" = ["B008"]  # Allow typer.Option in function defaults (Typer pattern)
```

---

## Technical Insights

### CLI Command Complexity Comparison

**Before (Manual Orchestration):**
User would need to:
1. Initialize TranscriptionManager
2. Handle async/await
3. Parse command-line args
4. Format output
5. Handle errors

**After (CLI Commands):**
```bash
inkwell transcribe https://youtube.com/watch?v=xyz
inkwell cache stats
```

**Reduction:** From ~50 lines of Python → 1 line of shell

---

### Typer vs Click

**Why Typer:**
- Type hints for automatic validation
- Better help text generation
- Automatic option parsing from type hints
- Built on Click, so all Click features available

**Example:**
```python
# Automatic conversion and validation
output: Path | None = typer.Option(None, ...)
# No need to parse string to Path, Typer handles it
```

---

## Statistics

- **New code:** 171 lines (2 commands)
- **Modified files:** 2 (cli.py, pyproject.toml)
- **Tests:** All 307 tests pass
- **Linter:** All checks pass (after B008 ignore)

---

## References

- [Typer Documentation](https://typer.tiangolo.com/) - CLI framework
- [Rich Documentation](https://rich.readthedocs.io/) - Terminal formatting
- [asyncio.run()](https://docs.python.org/3/library/asyncio-runner.html#asyncio.run) - Async/sync bridging
- [Unit 7: TranscriptionManager](/docs/devlog/2025-11-07-phase-2-unit-7-transcription-manager.md)
