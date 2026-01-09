# Research: Terminal Interview UX with Rich

**Date**: 2025-11-08
**Author**: Claude Code
**Status**: Research Complete
**Related**: Phase 4 Unit 1

## Overview

This document researches terminal UI patterns for building an engaging, beautiful interview experience using the Rich library. The goal is to create a terminal interface that feels natural, responsive, and professional.

---

## Rich Library Overview

### What We Have

**Package**: `rich` (included via `typer[all]`)
**Already installed**: Yes
**Version**: 13.0+

### Core Capabilities for Interviews

1. **Styled Text** - Colors, bold, italic, etc.
2. **Markdown Rendering** - Display formatted text
3. **Progress Indicators** - Spinners, progress bars
4. **Panels** - Boxed content
5. **Console** - Advanced printing with markup
6. **Live Display** - Update regions in-place
7. **Prompt** - User input collection

---

## Interview UI Components

### 1. Welcome Screen

```python
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown

console = Console()

def display_welcome(episode_title: str, podcast_name: str):
    """Display interview welcome screen"""

    welcome_text = f"""
    # Interview Mode

    Episode: **{episode_title}**
    Podcast: _{podcast_name}_

    I've reviewed the extracted content and I'm ready to ask you
    some thoughtful questions to help you reflect on this episode.

    This should take about **10-15 minutes**. You can:
    - Type 'skip' to skip a question
    - Type 'done' to end the interview early
    - Press Ctrl+C to cancel

    Let's begin!
    """

    console.print(Panel(
        Markdown(welcome_text),
        title="🎙️  Inkwell Interview",
        border_style="blue",
        padding=(1, 2)
    ))
    console.print()
```

**Output**:
```
┌─ 🎙️  Inkwell Interview ────────────────────────────────────┐
│                                                              │
│  # Interview Mode                                            │
│                                                              │
│  Episode: **The Future of AI**                               │
│  Podcast: _My Podcast_                                       │
│                                                              │
│  I've reviewed the extracted content and I'm ready to ask    │
│  you some thoughtful questions to help you reflect on this   │
│  episode.                                                    │
│                                                              │
│  This should take about **10-15 minutes**. You can:          │
│  - Type 'skip' to skip a question                            │
│  - Type 'done' to end the interview early                    │
│  - Press Ctrl+C to cancel                                    │
│                                                              │
│  Let's begin!                                                │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 2. Question Display

```python
from rich.text import Text

def display_question(question_number: int, total: int, question_text: str):
    """Display interview question"""

    # Question header
    header = Text()
    header.append(f"Question {question_number}", style="bold cyan")
    header.append(f" of ~{total}", style="dim")

    console.print()
    console.print(header)
    console.print()

    # Question text (wrapped, with icon)
    console.print(f"💭 {question_text}", style="yellow")
    console.print()
```

**Output**:
```

Question 1 of ~5

💭 What aspect of the AI safety discussion surprised you most, and how
   does it relate to your own work in software engineering?

```

### 3. Streaming Response Display

```python
from rich.live import Live
from rich.text import Text
import asyncio

async def display_streaming_response(text_stream):
    """Display Claude's streaming response in real-time"""

    console.print("🤔 ", style="dim", end="")

    buffer = ""
    with Live("", console=console, refresh_per_second=10) as live:
        async for chunk in text_stream:
            buffer += chunk
            # Update live display with current buffer
            live.update(Text(buffer, style="green"))

    console.print()  # Newline after complete
    return buffer
```

**Output** (updates in real-time):
```
🤔 That's a fascinating connection between alignment and your day-to-day
   work. Let me ask you this: can you think of a specific project where...
   [text appears as it streams]
```

### 4. Multiline Input Collection

**Challenge**: Need to collect multi-paragraph responses

**Option 1: Simple Prompt** (Limited)
```python
from rich.prompt import Prompt

response = Prompt.ask("Your response")
```

❌ Problem: Single line only

**Option 2: Custom Multiline Handler** (Recommended)
```python
import sys
from rich.console import Console

def get_multiline_input(prompt: str = "Your response") -> str:
    """Get multiline input from user"""

    console.print(f"[cyan]{prompt}[/cyan] [dim](Enter twice when done, or 'skip')[/dim]")
    console.print()

    lines = []
    empty_line_count = 0

    while True:
        try:
            line = input()

            # Check for skip
            if line.strip().lower() in ["skip", "done", "quit"]:
                return line.strip().lower()

            # Track empty lines
            if not line.strip():
                empty_line_count += 1
                if empty_line_count >= 2:
                    # Two empty lines = done
                    break
            else:
                empty_line_count = 0

            lines.append(line)

        except EOFError:
            # Ctrl+D pressed
            break
        except KeyboardInterrupt:
            # Ctrl+C pressed
            console.print("\n[yellow]Interview cancelled[/yellow]")
            return None

    # Remove trailing empty lines
    while lines and not lines[-1].strip():
        lines.pop()

    return "\n".join(lines)
```

**Usage**:
```python
response = get_multiline_input()
if response is None:
    # User cancelled
    return
elif response in ["skip", "done", "quit"]:
    # Handle command
    pass
else:
    # Got actual response
    process_response(response)
```

**User Experience**:
```
Your response (Enter twice when done, or 'skip')

> Well, I hadn't really thought about alignment problems at
> the scale they discussed. It made me realize that even in
> my day-to-day work, we often don't think carefully enough
> about what we're optimizing for.
>
>

```

### 5. Progress Tracking

```python
from rich.progress import Progress, SpinnerColumn, TextColumn

def show_processing(message: str):
    """Show processing indicator"""

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True  # Disappears when done
    ) as progress:
        task = progress.add_task(message, total=None)
        # Do work...
        yield
```

**Usage**:
```python
with show_processing("Generating next question..."):
    question = await agent.generate_question(...)
```

**Output**:
```
⠋ Generating next question...
```

### 6. Conversation History Display

```python
from rich.table import Table

def display_conversation_summary(exchanges: list[Exchange]):
    """Display conversation history"""

    table = Table(title="Interview Summary", show_header=True, header_style="bold")
    table.add_column("Q#", style="cyan", width=4)
    table.add_column("Question", style="yellow", width=50)
    table.add_column("Response", style="green", width=40)

    for exchange in exchanges:
        question_preview = exchange.question.text[:47] + "..."
        response_preview = exchange.response.text[:37] + "..."

        table.add_row(
            str(exchange.question.question_number),
            question_preview,
            response_preview
        )

    console.print(table)
```

**Output**:
```
                        Interview Summary
┏━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Q# ┃ Question                         ┃ Response                  ┃
┡━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ 1  │ What aspect of the AI safety...  │ Well, I hadn't really...  │
│ 2  │ Can you give an example of...    │ Actually yes! Last...     │
└────┴──────────────────────────────────┴───────────────────────────┘
```

### 7. Completion Summary

```python
from rich.panel import Panel
from rich.text import Text

def display_completion_summary(session: InterviewSession, output_file: Path):
    """Display interview completion summary"""

    summary = Text()
    summary.append("✓ Interview Complete!\n\n", style="bold green")
    summary.append(f"Questions answered: {session.question_count}\n")
    summary.append(f"Time spent: {session.total_thinking_time / 60:.1f} minutes\n")
    summary.append(f"Cost: ${session.total_cost_usd:.2f}\n")
    summary.append(f"\nSaved to: {output_file}\n", style="cyan")

    console.print(Panel(summary, border_style="green", padding=(1, 2)))
```

**Output**:
```
┌───────────────────────────────────────────────────────────┐
│                                                           │
│  ✓ Interview Complete!                                    │
│                                                           │
│  Questions answered: 5                                    │
│  Time spent: 12.3 minutes                                 │
│  Cost: $0.18                                              │
│                                                           │
│  Saved to: output/podcast-2025-11-08-title/my-notes.md   │
│                                                           │
└───────────────────────────────────────────────────────────┘
```

---

## Complete Interview Flow UX

### Full Interaction Pattern

```python
async def run_interview(
    episode_output: EpisodeOutput,
    config: InterviewConfig,
) -> InterviewResult:
    """Run complete interview with Rich UI"""

    console = Console()

    # 1. Welcome screen
    display_welcome(episode_output.metadata.episode_title, episode_output.metadata.podcast_name)

    # 2. Build context
    with show_processing("Preparing interview context..."):
        context = build_context(episode_output, config.guidelines)

    # 3. Initialize session
    session = InterviewSession(
        episode_url=episode_output.metadata.episode_url,
        episode_title=episode_output.metadata.episode_title,
        podcast_name=episode_output.metadata.podcast_name,
        max_questions=config.question_count,
    )

    # 4. Conversation loop
    while not should_end_interview(session):
        # Generate question
        with show_processing("Generating next question..."):
            question = await agent.generate_question(context, session)

        # Display question
        display_question(
            session.question_count + 1,
            config.question_count,
            question.text
        )

        # Get user response
        response_text = get_multiline_input()

        # Handle special commands
        if response_text is None:
            # Cancelled
            console.print("[yellow]Interview cancelled[/yellow]")
            return None
        elif response_text in ["done", "quit"]:
            console.print("[green]Ending interview...[/green]")
            break
        elif response_text == "skip":
            console.print("[dim]Skipping question[/dim]")
            continue

        # Create response object
        response = Response(
            question_id=question.id,
            text=response_text,
            word_count=len(response_text.split()),
        )

        # Add exchange to session
        exchange = Exchange(question=question, response=response)
        session.exchanges.append(exchange)

        # Check if should generate follow-up
        if should_follow_up(response):
            console.print("[dim italic]That's interesting. Let me dig deeper...[/dim italic]")
            # Follow-up will be generated in next iteration

    # 5. Format and save
    with show_processing("Formatting interview transcript..."):
        result = format_interview(session, config)

    # 6. Display summary
    display_completion_summary(session, result.output_file)

    return result
```

---

## Advanced UI Patterns

### 1. Inline Response Preview

```python
def preview_response(text: str, max_length: int = 100) -> str:
    """Show preview of user's response"""
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."
```

**Display after user responds**:
```python
preview = preview_response(response_text)
console.print(f"[dim]You said: {preview}[/dim]")
console.print()
```

### 2. Typing Indicator

```python
import asyncio
from rich.live import Live
from rich.text import Text

async def show_thinking_indicator():
    """Show 'Claude is thinking' animation"""
    frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    idx = 0

    with Live("", console=console, refresh_per_second=10) as live:
        while True:
            text = Text(f"{frames[idx]} Thinking...", style="dim")
            live.update(text)
            idx = (idx + 1) % len(frames)
            await asyncio.sleep(0.1)
```

### 3. Help Screen

```python
def display_help():
    """Display help information"""

    help_text = """
    # Interview Commands

    While answering questions:

    - **Press Enter twice** to submit your response
    - **Type 'skip'** to skip the current question
    - **Type 'done'** to end the interview
    - **Press Ctrl+C** to cancel the interview
    - **Type 'help'** to see this message

    Tips for great interviews:
    - Take your time to think
    - Be specific with examples
    - Don't worry about perfect answers
    - It's okay to skip questions
    """

    console.print(Panel(Markdown(help_text), border_style="blue"))
```

---

## Keyboard Shortcuts & Commands

### Commands to Support

| Command | Action | When Available |
|---------|--------|----------------|
| `skip` | Skip current question | During response input |
| `done` | End interview | During response input |
| `quit` | End interview | During response input |
| `help` | Show help | During response input |
| `back` | Go to previous question | Future enhancement |
| Ctrl+C | Cancel interview | Anytime |
| Ctrl+D | Submit response | During input (EOF) |

### Implementation

```python
def handle_command(command: str, session: InterviewSession) -> str:
    """Handle special commands"""

    command = command.strip().lower()

    if command == "help":
        display_help()
        return "help"
    elif command in ["skip", "next", "pass"]:
        return "skip"
    elif command in ["done", "finish", "quit", "exit"]:
        return "done"
    else:
        return "response"
```

---

## Error Handling & Edge Cases

### 1. Network Errors During Streaming

```python
async def stream_with_fallback(stream):
    """Stream with error handling"""
    try:
        async for chunk in stream:
            yield chunk
    except asyncio.TimeoutError:
        console.print("[red]Network timeout. Retrying...[/red]")
        # Retry logic
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        yield "[Error occurred - please try again]"
```

### 2. Empty Response Handling

```python
response = get_multiline_input()

if not response or not response.strip():
    console.print("[yellow]No response provided. Skipping question.[/yellow]")
    continue
```

### 3. Very Long Responses

```python
if len(response.split()) > 500:
    console.print("[yellow]That's a very detailed response! Consider breaking it down.[/yellow]")
    confirm = Prompt.ask("Continue with this response?", choices=["y", "n"])
    if confirm == "n":
        continue
```

### 4. Ctrl+C Handling

```python
try:
    response = get_multiline_input()
except KeyboardInterrupt:
    console.print("\n[yellow]Interview interrupted[/yellow]")
    should_save = Prompt.ask(
        "Save progress and resume later?",
        choices=["y", "n"],
        default="y"
    )

    if should_save == "y":
        save_session(session)
        console.print("[green]Progress saved. Resume with: inkwell interview resume[/green]")

    return None
```

---

## Performance Considerations

### 1. Console Object Reuse

**Pattern**: Create one console instance, reuse throughout

```python
# Good
console = Console()

def display_question(text: str):
    console.print(text)

def display_response(text: str):
    console.print(text)
```

**Avoid**: Creating new console for each print

### 2. Streaming Buffer Management

**Pattern**: Buffer chunks, update display periodically

```python
buffer = ""
last_update = time.time()

async for chunk in stream:
    buffer += chunk

    # Update every 100ms
    if time.time() - last_update > 0.1:
        live.update(buffer)
        last_update = time.time()
```

### 3. Large Conversation Rendering

**Pattern**: Use pagination for history display

```python
def display_conversation_history(exchanges: list[Exchange], page_size: int = 10):
    """Display conversation with pagination"""

    if len(exchanges) <= page_size:
        display_all(exchanges)
    else:
        # Show last N exchanges
        recent = exchanges[-page_size:]
        console.print(f"[dim]Showing last {page_size} of {len(exchanges)} exchanges[/dim]")
        display_all(recent)
```

---

## Accessibility Considerations

### 1. Screen Reader Support

**Best Practices**:
- Use semantic markup (don't rely solely on color)
- Provide text alternatives for icons
- Use clear, descriptive text

```python
# Good
console.print("✓ Complete", style="green")
console.print("Question 1 of 5", style="bold")

# Also good (text-only fallback)
console.print("Complete (✓)", style="green")
```

### 2. Color Blindness

**Best Practices**:
- Don't rely on color alone to convey meaning
- Use icons + color
- Use bold/dim in addition to color

```python
# Good - multiple indicators
console.print("✓ Success", style="bold green")
console.print("✗ Error", style="bold red")

# Not ideal - color only
console.print("Success", style="green")
```

### 3. Terminal Compatibility

**Test on**:
- Modern terminals (iTerm2, Windows Terminal, etc.)
- Basic terminals (TTY, basic SSH)
- Different backgrounds (light/dark)

**Graceful degradation**:
```python
from rich.console import Console

console = Console()

if not console.is_terminal:
    # Fallback to plain text
    print("Question 1: What surprised you?")
else:
    # Use Rich features
    console.print("💭 [yellow]Question 1:[/yellow] What surprised you?")
```

---

## Testing UX Patterns

### 1. Mock Terminal Output

```python
from io import StringIO
from rich.console import Console

def test_display_question():
    """Test question display"""

    # Create console with string buffer
    output = StringIO()
    console = Console(file=output, force_terminal=True)

    # Display question
    display_question(1, 5, "What surprised you?", console=console)

    # Check output
    result = output.getvalue()
    assert "Question 1" in result
    assert "What surprised you?" in result
```

### 2. Mock User Input

```python
import sys
from io import StringIO

def test_multiline_input():
    """Test multiline input collection"""

    # Mock user input
    sys.stdin = StringIO("Line 1\nLine 2\n\n")

    response = get_multiline_input()

    assert response == "Line 1\nLine 2"
```

---

## Best Practices Summary

### DO:
✓ Use Rich for beautiful output
✓ Show progress indicators
✓ Handle Ctrl+C gracefully
✓ Support multiline input
✓ Show clear completion summaries
✓ Use color + text for meaning
✓ Test on multiple terminals

### DON'T:
❌ Create new Console instances unnecessarily
❌ Rely on color alone for meaning
❌ Ignore keyboard interrupts
❌ Force single-line responses
❌ Use complex Unicode that may not render
❌ Update display too frequently (> 30 FPS)

---

## Implementation Checklist

- [ ] Welcome screen with episode info
- [ ] Question display with numbering
- [ ] Multiline input collection
- [ ] Streaming response display
- [ ] Progress indicators
- [ ] Completion summary
- [ ] Error handling (network, input, interrupts)
- [ ] Keyboard shortcut support
- [ ] Help command
- [ ] Conversation history view
- [ ] Graceful degradation for basic terminals

---

## References

- [Rich Documentation](https://rich.readthedocs.io/)
- [Rich Examples](https://github.com/Textualize/rich/tree/master/examples)
- [Terminal UX Best Practices](https://clig.dev/)
- [Command Line Interface Guidelines](https://clig.dev/)

---

## Next Steps

1. Implement welcome screen
2. Build multiline input handler
3. Create streaming response display
4. Add progress indicators
5. Implement completion summary
6. Test on multiple terminals
7. Add keyboard shortcut support

---

**Status**: Research complete, patterns identified, ready for implementation
