"""Rich terminal display components for interview mode.

This module provides beautiful, interactive terminal UI components using the Rich library.
All display functions use a shared Console instance for consistent output.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.text import Text

from inkwell.interview.models import Exchange, InterviewSession

# Shared console instance for all display functions
console = Console()


def display_welcome(
    episode_title: str,
    podcast_name: str,
    template_name: str,
    max_questions: int,
) -> None:
    """Display interview welcome screen.

    Args:
        episode_title: Title of the episode
        podcast_name: Name of the podcast
        template_name: Interview template being used
        max_questions: Target number of questions
    """
    welcome_text = f"""
# Interview Mode

**Episode**: {episode_title}
**Podcast**: _{podcast_name}_
**Template**: {template_name}

I've reviewed the extracted content and I'm ready to ask you
some thoughtful questions to help you reflect on this episode.

This should take about **10-15 minutes**. You can:
- Type multiline responses (Ctrl-D or double-enter to submit)
- Type 'skip' to skip a question
- Type 'done' to end the interview early
- Press Ctrl+C to pause and save progress

**Target**: ~{max_questions} questions (including follow-ups)

Let's begin!
    """

    console.print(
        Panel(
            Markdown(welcome_text.strip()),
            title="🎙️  Inkwell Interview",
            border_style="blue",
            padding=(1, 2),
        )
    )
    console.print()


def display_question(
    question_number: int, total_questions: int, question_text: str, is_follow_up: bool = False
) -> None:
    """Display interview question.

    Args:
        question_number: Current question number
        total_questions: Target total questions
        question_text: The question to display
        is_follow_up: Whether this is a follow-up question
    """
    # Question header
    header = Text()
    if is_follow_up:
        header.append("Follow-up", style="bold magenta")
    else:
        header.append(f"Question {question_number}", style="bold cyan")
        header.append(f" of ~{total_questions}", style="dim")

    console.print()
    console.print(header)
    console.print()

    # Question text (wrapped, with icon)
    icon = "🔍" if is_follow_up else "💭"
    console.print(f"{icon} {question_text}", style="yellow")
    console.print()


async def display_streaming_question(
    question_number: int,
    total_questions: int,
    text_stream: AsyncIterator[str],
    is_follow_up: bool = False,
) -> str:
    """Display question as it streams from the agent.

    Args:
        question_number: Current question number
        total_questions: Target total questions
        text_stream: Async iterator yielding text chunks
        is_follow_up: Whether this is a follow-up question

    Returns:
        The complete question text
    """
    # Question header
    header = Text()
    if is_follow_up:
        header.append("Follow-up", style="bold magenta")
    else:
        header.append(f"Question {question_number}", style="bold cyan")
        header.append(f" of ~{total_questions}", style="dim")

    console.print()
    console.print(header)
    console.print()

    # Stream question text
    icon = "🔍" if is_follow_up else "💭"
    console.print(f"{icon} ", style="yellow", end="")

    buffer = ""
    with Live("", console=console, refresh_per_second=10) as live:
        async for chunk in text_stream:
            buffer += chunk
            live.update(Text(buffer, style="yellow"))

    console.print()  # Newline after complete
    return buffer


def display_response_preview(response_text: str, max_length: int = 100) -> None:
    """Display preview of user's response.

    Args:
        response_text: User's response text
        max_length: Maximum length for preview
    """
    if len(response_text) <= max_length:
        preview = response_text
    else:
        preview = response_text[:max_length] + "..."

    console.print(f"[dim]You said: {preview}[/dim]")
    console.print()


def display_thinking(message: str = "Thinking...") -> None:
    """Display a brief thinking indicator.

    Args:
        message: Message to display while thinking
    """
    console.print(f"[dim italic]{message}[/dim italic]")


def display_conversation_summary(exchanges: list[Exchange]) -> None:
    """Display conversation history as a table.

    Args:
        exchanges: List of question/response exchanges
    """
    if not exchanges:
        return

    table = Table(title="Interview Summary", show_header=True, header_style="bold")
    table.add_column("Q#", style="cyan", width=4, no_wrap=True)
    table.add_column("Question", style="yellow", width=50)
    table.add_column("Response", style="green", width=40)

    for exchange in exchanges:
        question_preview = (
            exchange.question.text[:47] + "..."
            if len(exchange.question.text) > 50
            else exchange.question.text
        )
        response_preview = (
            exchange.response.text[:37] + "..."
            if len(exchange.response.text) > 40
            else exchange.response.text
        )

        table.add_row(
            str(exchange.question.question_number),
            question_preview,
            response_preview,
        )

    console.print()
    console.print(table)
    console.print()


def display_completion_summary(session: InterviewSession, output_file: Path | None = None) -> None:
    """Display interview completion summary.

    Args:
        session: Completed interview session
        output_file: Path to output file (if saved)
    """
    duration_minutes = session.duration.total_seconds() / 60.0

    summary = Text()
    summary.append("✓ Interview Complete!\n\n", style="bold green")
    summary.append(f"Questions answered: {session.question_count}\n")
    summary.append(f"Substantive responses: {session.substantive_response_count}\n")
    summary.append(f"Time spent: {duration_minutes:.1f} minutes\n")
    summary.append(f"Tokens used: {session.total_tokens_used:,}\n")
    summary.append(f"Cost: ${session.total_cost_usd:.4f}\n")

    if output_file:
        summary.append(f"\nSaved to: {output_file}\n", style="cyan")

    console.print(Panel(summary, border_style="green", padding=(1, 2)))
    console.print()


def display_pause_message(session: InterviewSession) -> None:
    """Display message when interview is paused.

    Args:
        session: Paused interview session
    """
    message = Text()
    message.append("⏸️  Interview Paused\n\n", style="bold yellow")
    message.append(f"Session ID: {session.session_id}\n", style="dim")
    message.append(f"Progress: {session.question_count} questions answered\n")
    message.append("\nYou can resume this interview later using:\n", style="cyan")
    message.append(f"  inkwell interview resume {session.session_id}\n", style="bold")

    console.print(Panel(message, border_style="yellow", padding=(1, 2)))
    console.print()


def display_error(error_message: str, title: str = "Error") -> None:
    """Display error message in a panel.

    Args:
        error_message: Error message to display
        title: Title for the error panel
    """
    console.print(Panel(error_message, title=title, border_style="red", padding=(1, 2)))
    console.print()


def display_info(message: str, title: str = "Info") -> None:
    """Display info message in a panel.

    Args:
        message: Info message to display
        title: Title for the info panel
    """
    console.print(Panel(message, title=title, border_style="blue", padding=(1, 2)))
    console.print()


def display_session_stats(session: InterviewSession) -> None:
    """Display current session statistics.

    Args:
        session: Current interview session
    """
    duration_minutes = session.duration.total_seconds() / 60.0
    completion_rate = (
        session.question_count / session.max_questions if session.max_questions > 0 else 0.0
    )

    stats = Text()
    stats.append("📊 Session Stats\n\n", style="bold")
    stats.append(f"Questions: {session.question_count} / {session.max_questions}\n")
    stats.append(f"Completion: {completion_rate * 100:.0f}%\n")
    stats.append(f"Duration: {duration_minutes:.1f} minutes\n")
    stats.append(f"Tokens: {session.total_tokens_used:,}\n")
    stats.append(f"Cost: ${session.total_cost_usd:.4f}\n")

    console.print(Panel(stats, border_style="cyan", padding=(1, 2)))
    console.print()


class ProcessingIndicator:
    """Context manager for showing processing indicators.

    Example:
        with ProcessingIndicator("Generating question..."):
            question = await agent.generate_question(...)
    """

    def __init__(self, message: str, transient: bool = True):
        """Initialize processing indicator.

        Args:
            message: Message to display
            transient: Whether indicator disappears when done
        """
        self.message = message
        self.transient = transient
        self.progress: Progress | None = None
        self.task_id = None

    def __enter__(self):
        """Start displaying progress indicator."""
        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=self.transient,
        )
        self.progress.start()
        self.task_id = self.progress.add_task(self.message, total=None)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Stop displaying progress indicator."""
        if self.progress:
            self.progress.stop()
        return False

    def update(self, message: str) -> None:
        """Update progress message.

        Args:
            message: New message to display
        """
        if self.progress and self.task_id is not None:
            self.progress.update(self.task_id, description=message)
