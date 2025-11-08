# ADR-022: Interview UI Framework

**Status**: Accepted
**Date**: 2025-11-08
**Deciders**: Development Team
**Related**: Phase 4 Unit 1, [Research: Terminal Interview UX](../research/terminal-interview-ux.md)

## Context

Interview Mode requires a beautiful, responsive terminal interface that makes the conversation feel natural and engaging. We need to display streaming responses, collect multiline input, show progress, and create a delightful user experience—all within a terminal.

### Requirements

1. **Streaming Display** - Show Claude's responses in real-time as they generate
2. **Multiline Input** - Collect user responses across multiple lines/paragraphs
3. **Rich Formatting** - Colors, styles, panels, markdown for visual hierarchy
4. **Progress Indicators** - Spinners and status messages
5. **Responsive** - Low latency, smooth updates
6. **Terminal Compatibility** - Work on modern terminals and basic TTY
7. **Accessibility** - Don't rely solely on color, support screen readers

### Key UI Moments

1. **Welcome screen** - Episode info, instructions, set expectations
2. **Question display** - Numbered, styled, clear
3. **Streaming response** - Real-time Claude output
4. **Multiline input** - Natural text entry, easy to edit
5. **Progress tracking** - Question N of M, cost, time
6. **Completion summary** - Stats, output location, success message

## Decision

**Use the Rich library for terminal UI**, which is already included as a dependency through `typer[all]`.

### Implementation

```python
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.live import Live
from rich.text import Text

# Create shared console
console = Console()

def display_welcome(episode_title: str):
    """Display welcome screen"""
    welcome = Markdown(f"# Interview Mode\n\nEpisode: **{episode_title}**")
    console.print(Panel(welcome, title="🎙️  Inkwell", border_style="blue"))

async def stream_response(text_stream) -> str:
    """Display streaming response"""
    buffer = ""
    with Live("", console=console, refresh_per_second=10) as live:
        async for chunk in text_stream:
            buffer += chunk
            live.update(Text(buffer, style="green"))
    return buffer

def get_multiline_input(prompt: str = "Your response") -> str:
    """Get multiline input from user"""
    console.print(f"[cyan]{prompt}[/cyan] [dim](Enter twice when done)[/dim]")

    lines = []
    empty_count = 0

    while empty_count < 2:
        line = input()
        if not line.strip():
            empty_count += 1
        else:
            empty_count = 0
        lines.append(line)

    # Remove trailing empty lines
    while lines and not lines[-1].strip():
        lines.pop()

    return "\n".join(lines)
```

**Why Rich**:
- Already a dependency (via `typer[all]`)
- Excellent streaming support (`Live` display)
- Beautiful styled output (colors, panels, markdown)
- Good terminal compatibility
- Well-documented and maintained
- Active community

## Alternatives Considered

### Alternative 1: Prompt_toolkit

**Description**: Full-featured library for building interactive CLIs

**Pros**:
- Excellent multiline editor with syntax highlighting
- Built-in readline support (arrows, Ctrl+A/E, etc.)
- Autocompletion capabilities
- History management
- Very polished input experience
- Vi/Emacs key bindings

**Cons**:
- **Additional dependency** (~2MB, complex)
- Much more complex than we need
- Overkill for simple multiline input
- Steeper learning curve
- Event loop management complexity
- Async integration challenges

**Why Rejected**: While it offers a better input experience, the complexity and additional dependency aren't justified for our simple use case. Basic multiline input with `input()` is sufficient.

### Alternative 2: Textual

**Description**: Modern TUI framework (by makers of Rich)

**Pros**:
- Beautiful, reactive interfaces
- Widget system
- Event-driven architecture
- Built on Rich
- Modern Python async

**Cons**:
- **Additional dependency** (heavy)
- Full TUI framework (way too complex)
- Async event loop conflicts with our flow
- Designed for apps, not conversational CLI
- Requires entire app restructure
- Massive overkill

**Why Rejected**: Textual is for building full TUI apps (like htop). Our interview is linear, conversational, not a widget-based interface.

### Alternative 3: Blessed

**Description**: Curses-based terminal library

**Pros**:
- Full terminal control
- Cursor positioning
- Low-level control

**Cons**:
- **Additional dependency**
- Much lower level than needed
- Manual terminal state management
- Curses complexity
- Platform compatibility issues
- No streaming helpers

**Why Rejected**: Too low-level. We don't need cursor control or full terminal manipulation.

### Alternative 4: Plain Print/Input

**Description**: Just use built-in `print()` and `input()`

**Pros**:
- No dependencies
- Simple
- Works everywhere
- Maximum compatibility

**Cons**:
- No colors or styling
- No streaming display
- No panels or formatting
- Ugly, unprofessional output
- Poor UX

**Why Rejected**: Interview Mode is a premium feature. The UX matters. Plain text would make Inkwell feel amateurish.

### Alternative 5: Click's Echo + Style

**Description**: Use Click's built-in output formatting

**Pros**:
- Lightweight
- Simple color support
- Already familiar (similar to typer)

**Cons**:
- No streaming support
- Basic colors only (no Rich markup)
- No panel/layout support
- No markdown rendering
- Limited compared to Rich

**Why Rejected**: Click's styling is too basic. We need streaming, panels, and rich formatting.

## Decision Rationale

### Why Rich is Perfect

1. **Already a Dependency**
   - Included via `typer[all]`
   - Zero additional install weight
   - Already loaded in memory

2. **Streaming Support**
   - `Live` display for real-time updates
   - Smooth rendering (< 10 FPS cap to avoid flicker)
   - Perfect for showing Claude's streaming responses

3. **Beautiful Output**
   - Colors, bold, italic, dim styles
   - Panels with borders and titles
   - Markdown rendering
   - Tables for summaries
   - Professional appearance

4. **Simple API**
   - `console.print()` with markup
   - Easy to learn and use
   - Good documentation
   - Lots of examples

5. **Terminal Compatibility**
   - Graceful degradation on basic terminals
   - Detects terminal capabilities
   - Works in SSH, TTY, modern terminals
   - Good Windows support

6. **Accessibility**
   - Can detect if terminal supports color
   - Provides `console.is_terminal` flag
   - Can fallback to plain text
   - Doesn't break screen readers

### What We're Building

**Rich-based Interview UI** with:

- **Welcome panel** - Styled introduction with episode info
- **Streaming questions** - Real-time display of Claude's questions
- **Styled prompts** - Clear input prompts with instructions
- **Progress tracking** - Question numbers, cost display
- **Completion summary** - Beautiful panel with stats
- **Graceful fallback** - Plain text if Rich features unavailable

### Custom Multiline Input

**Note**: We'll implement our own multiline input rather than using Prompt_toolkit:

```python
def get_multiline_input() -> str:
    """Simple multiline input (Enter twice to submit)"""
    lines = []
    empty_line_count = 0

    while True:
        line = input()
        if not line.strip():
            empty_line_count += 1
            if empty_line_count >= 2:
                break
        else:
            empty_line_count = 0
        lines.append(line)

    # Clean up trailing empty lines
    while lines and not lines[-1].strip():
        lines.pop()

    return "\n".join(lines)
```

**Reasoning**:
- Simple, works perfectly for our needs
- No additional dependencies
- Users press Enter twice to submit (intuitive)
- Can easily add Ctrl+D support
- 15 lines of code vs heavy dependency

## Consequences

### Positive

- ✅ **No new dependencies** - Uses existing Rich
- ✅ **Beautiful UX** - Professional, polished appearance
- ✅ **Streaming support** - Real-time response display
- ✅ **Simple implementation** - Clean, readable code
- ✅ **Well documented** - Lots of examples and help
- ✅ **Terminal compatible** - Works on all modern terminals
- ✅ **Accessible** - Detects capabilities, graceful fallback

### Negative

- ⚠️ **Basic input** - No readline features (arrows, Ctrl+A/E, etc.)
  - *Mitigation*: "Enter twice" is simple enough, most users type continuously
- ⚠️ **No edit during stream** - Can't interrupt streaming display
  - *Mitigation*: Streams are short (< 5 seconds), Ctrl+C works
- ⚠️ **Rich markup learning** - Team needs to learn `[cyan]...[/cyan]` syntax
  - *Mitigation*: Simple, well-documented, similar to markdown

### Trade-offs Accepted

- **Simplicity over Features** - Basic multiline input vs Prompt_toolkit editor
- **Dependencies over Complexity** - Use existing Rich vs add Prompt_toolkit
- **UX over Minimalism** - Rich formatting vs plain `print()`

## Implementation Guidelines

### Console Instance

**Create once, reuse throughout**:

```python
# interview/ui/display.py
from rich.console import Console

# Module-level console
console = Console()

def display_question(text: str):
    console.print(f"[yellow]{text}[/yellow]")
```

### Markup Style Guide

**Consistent colors**:
- Questions: `[yellow]`
- User input prompts: `[cyan]`
- Claude streaming: `[green]`
- Success messages: `[bold green]`
- Errors: `[red]`
- Hints/instructions: `[dim]`
- Emphasis: `[bold]`

### Streaming Pattern

**Standard streaming template**:

```python
async def stream_text(text_iterator):
    """Stream text with Live display"""
    buffer = ""

    with Live("", console=console, refresh_per_second=10) as live:
        async for chunk in text_iterator:
            buffer += chunk
            live.update(Text(buffer, style="green"))

    console.print()  # Newline after stream
    return buffer
```

### Graceful Fallback

**Check terminal capabilities**:

```python
if console.is_terminal:
    # Use Rich features
    console.print(Panel("Welcome", border_style="blue"))
else:
    # Fallback to plain text
    print("=== Welcome ===")
```

## Testing Strategy

### Unit Tests

Mock console output:

```python
from io import StringIO
from rich.console import Console

def test_display_question():
    """Test question display"""
    output = StringIO()
    console = Console(file=output, force_terminal=True)

    display_question(1, 5, "What surprised you?", console=console)

    result = output.getvalue()
    assert "Question 1" in result
    assert "What surprised you?" in result
```

### Manual Testing

Test on multiple terminals:
- ✅ iTerm2 (macOS)
- ✅ Terminal.app (macOS)
- ✅ Windows Terminal
- ✅ Basic SSH TTY
- ✅ VSCode integrated terminal

### Accessibility Testing

- ✅ Works without color
- ✅ Screen reader compatible
- ✅ Clear text alternatives for icons
- ✅ Keyboard-only navigation

## Examples

### Welcome Screen
```python
display_welcome("The Future of AI", "My Podcast")

# Output:
# ┌─ 🎙️  Inkwell Interview ─────────────────┐
# │                                          │
# │  # Interview Mode                        │
# │                                          │
# │  Episode: **The Future of AI**           │
# │  Podcast: _My Podcast_                   │
# │  ...                                     │
# └──────────────────────────────────────────┘
```

### Question Display
```python
display_question(1, 5, "What surprised you about the AI safety discussion?")

# Output:
# Question 1 of ~5
#
# 💭 What surprised you about the AI safety discussion?
```

### Completion Summary
```python
display_completion(session, output_file)

# Output:
# ┌────────────────────────────────────┐
# │ ✓ Interview Complete!              │
# │                                    │
# │ Questions: 5                       │
# │ Time: 12.3 minutes                 │
# │ Cost: $0.18                        │
# │                                    │
# │ Saved to: .../my-notes.md          │
# └────────────────────────────────────┘
```

## Monitoring & Review

### Success Criteria

- Interview UI feels professional and polished
- Streaming responses appear smoothly
- Users can easily input multiline responses
- Works on all target terminal environments
- No performance issues or flicker

### Review Trigger

Consider revisiting if:
- Users report significant UX issues with multiline input
- Need for advanced editor features becomes common
- Rich library has breaking changes or is abandoned
- Performance issues emerge (unlikely)

## References

- [Rich Documentation](https://rich.readthedocs.io/)
- [Rich Live Display](https://rich.readthedocs.io/en/stable/live.html)
- [Rich Console](https://rich.readthedocs.io/en/stable/console.html)
- [Research: Terminal Interview UX](../research/terminal-interview-ux.md)

## Related Decisions

- ADR-020: Interview Framework Selection
- ADR-021: Interview State Persistence
- ADR-023: Interview Template System

---

**Decision**: Use Rich library for terminal UI
**Rationale**: Already a dependency, excellent streaming support, beautiful output
**Status**: ✅ Accepted
