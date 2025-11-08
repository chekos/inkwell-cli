"""Multiline input handlers for interview mode.

This module provides multiline input collection with support for:
- Multiple paragraphs of text
- Ctrl-D to submit (EOF)
- Double-enter to submit
- Special commands (skip, done, quit)
- Graceful Ctrl-C handling
"""

from __future__ import annotations

from rich.console import Console
from rich.prompt import Confirm

# Shared console instance
console = Console()


class UserCommand:
    """Special user commands during interview."""

    SKIP = "skip"
    DONE = "done"
    QUIT = "quit"
    HELP = "help"

    ALL_COMMANDS = [SKIP, DONE, QUIT, HELP]


def get_multiline_input(
    prompt: str = "Your response",
    allow_empty: bool = False,
    show_instructions: bool = True,
) -> str | None:
    """Get multiline input from user.

    The user can submit their response in three ways:
    1. Press Ctrl-D (EOF)
    2. Press Enter twice (double empty line)
    3. Type a special command (skip, done, quit)

    Args:
        prompt: Prompt message to display
        allow_empty: Whether to allow empty responses
        show_instructions: Whether to show input instructions

    Returns:
        User's response text, or None if cancelled (Ctrl-C)
        Special commands (skip, done, quit) are returned as-is

    Example:
        >>> response = get_multiline_input()
        >>> if response is None:
        ...     print("User cancelled")
        >>> elif response == "skip":
        ...     print("User skipped question")
        >>> else:
        ...     print(f"Got response: {response}")
    """
    # Display prompt
    if show_instructions:
        console.print(
            f"[cyan]{prompt}[/cyan] [dim](Ctrl-D or double-enter to submit, 'skip' to skip)[/dim]"
        )
    else:
        console.print(f"[cyan]{prompt}[/cyan]")

    console.print()

    lines = []
    empty_line_count = 0

    while True:
        try:
            line = input()

            # Check for special commands (must be alone on first line)
            if not lines and line.strip().lower() in UserCommand.ALL_COMMANDS:
                return line.strip().lower()

            # Track consecutive empty lines
            if not line.strip():
                empty_line_count += 1
                if empty_line_count >= 2:
                    # Two consecutive empty lines = submit
                    break
            else:
                empty_line_count = 0

            lines.append(line)

        except EOFError:
            # Ctrl-D pressed - submit current input
            break

        except KeyboardInterrupt:
            # Ctrl-C pressed - ask for confirmation
            console.print()
            should_cancel = Confirm.ask(
                "[yellow]Do you want to pause this interview?[/yellow]",
                default=False,
            )
            if should_cancel:
                return None
            else:
                # Resume input
                console.print("[dim]Resuming...[/dim]")
                console.print()
                continue

    # Remove trailing empty lines
    while lines and not lines[-1].strip():
        lines.pop()

    response_text = "\n".join(lines).strip()

    # Check if empty
    if not response_text and not allow_empty:
        console.print("[yellow]Empty response - treating as 'skip'[/yellow]")
        return UserCommand.SKIP

    return response_text


def confirm_action(message: str, default: bool = False) -> bool:
    """Ask user to confirm an action.

    Args:
        message: Confirmation message
        default: Default choice if user just presses Enter

    Returns:
        True if user confirmed, False otherwise
    """
    return Confirm.ask(message, default=default)


def get_single_line_input(prompt: str, default: str | None = None) -> str | None:
    """Get single-line input from user.

    Args:
        prompt: Prompt message to display
        default: Default value if user presses Enter

    Returns:
        User's input, or None if cancelled
    """
    try:
        if default:
            console.print(f"[cyan]{prompt}[/cyan] [dim](default: {default})[/dim]")
        else:
            console.print(f"[cyan]{prompt}[/cyan]")

        line = input("> ")
        return line.strip() or default

    except KeyboardInterrupt:
        console.print("\n[yellow]Cancelled[/yellow]")
        return None
    except EOFError:
        return default


def get_choice(
    prompt: str,
    choices: list[str],
    default: str | None = None,
) -> str | None:
    """Get user's choice from a list of options.

    Args:
        prompt: Prompt message to display
        choices: List of valid choices
        default: Default choice if user just presses Enter

    Returns:
        User's choice, or None if cancelled

    Example:
        >>> template = get_choice(
        ...     "Select interview template",
        ...     ["reflective", "analytical", "creative"],
        ...     default="reflective"
        ... )
    """
    console.print(f"[cyan]{prompt}[/cyan]")
    console.print()

    for i, choice in enumerate(choices, 1):
        marker = "→" if choice == default else " "
        style = "bold" if choice == default else ""
        console.print(f"  {marker} [{i}] {choice}", style=style)

    console.print()

    while True:
        try:
            if default:
                console.print(f"[dim]Choice (default: {default})[/dim]")
            user_input = input("> ").strip()

            if not user_input and default:
                return default

            # Accept number or text
            if user_input.isdigit():
                index = int(user_input) - 1
                if 0 <= index < len(choices):
                    return choices[index]
            elif user_input in choices:
                return user_input

            console.print("[yellow]Invalid choice. Please try again.[/yellow]")

        except KeyboardInterrupt:
            console.print("\n[yellow]Cancelled[/yellow]")
            return None
        except EOFError:
            return default


def display_help() -> None:
    """Display help for interview commands."""
    help_text = """
# Interview Commands

During the interview, you can use these commands:

- **skip** - Skip the current question
- **done** - End the interview early (saves progress)
- **quit** - Same as done
- **help** - Show this help message

## Input Methods

You can submit your response in two ways:

1. **Ctrl-D** - Submit immediately (works on any line)
2. **Double Enter** - Press Enter twice on empty lines

## Interrupting

- **Ctrl-C** - Pause and save progress (you can resume later)

## Tips

- Take your time - there's no rush
- Write as much or as little as you want
- Skip questions that don't resonate
- Use 'done' when you feel satisfied with the conversation
    """

    console.print(help_text.strip())
    console.print()
