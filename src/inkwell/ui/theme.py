"""Theme system for Inkwell CLI.

Provides centralized color definitions with dark/light mode support.
Colors are optimized for readability in both terminal backgrounds.

Usage:
    from inkwell.ui import get_theme

    theme = get_theme()  # Gets current theme based on config
    console.print(f"[{theme.success}]✓[/{theme.success}] Done!")

    # Or use the markup helpers
    console.print(theme.success_text("Done!"))
"""

import os
from dataclasses import dataclass
from enum import Enum
from typing import Literal


class ThemeMode(str, Enum):
    """Available theme modes."""

    LIGHT = "light"
    DARK = "dark"
    AUTO = "auto"


@dataclass(frozen=True)
class Theme:
    """Color theme for terminal output.

    All colors are rich-compatible color names or hex codes.
    """

    # Mode identifier
    mode: str

    # Status colors
    success: str  # Checkmarks, completed items
    error: str  # Errors, failures
    warning: str  # Warnings, cautions
    info: str  # Informational messages

    # Semantic colors
    primary: str  # Primary accent (names, titles)
    secondary: str  # Secondary accent (URLs, secondary data)
    muted: str  # Dim/muted text (metadata, hints)
    emphasis: str  # Bold emphasis

    # Data colors (for tables, lists)
    data_name: str  # Names, identifiers
    data_url: str  # URLs, links
    data_value: str  # Values, counts
    data_date: str  # Dates, timestamps
    data_provider: str  # Provider names (Gemini, Claude)

    # Progress/status indicators
    progress_active: str  # Currently running stage
    progress_pending: str  # Pending stage
    progress_complete: str  # Completed stage
    progress_failed: str  # Failed stage

    # Table styling
    table_header: str  # Table headers
    table_border: str  # Table borders

    def success_text(self, text: str) -> str:
        """Format text with success color and checkmark."""
        return f"[{self.success}]✓[/{self.success}] {text}"

    def error_text(self, text: str) -> str:
        """Format text with error color and X mark."""
        return f"[{self.error}]✗[/{self.error}] {text}"

    def warning_text(self, text: str) -> str:
        """Format text with warning color and warning symbol."""
        return f"[{self.warning}]⚠[/{self.warning}] {text}"

    def info_text(self, text: str) -> str:
        """Format text with info color and arrow."""
        return f"[{self.info}]→[/{self.info}] {text}"

    def muted_text(self, text: str) -> str:
        """Format text as muted/dim."""
        return f"[{self.muted}]{text}[/{self.muted}]"

    def bold(self, text: str) -> str:
        """Format text as bold."""
        return f"[bold]{text}[/bold]"

    def primary_text(self, text: str) -> str:
        """Format text with primary color."""
        return f"[{self.primary}]{text}[/{self.primary}]"


# Dark theme - optimized for dark terminal backgrounds
DARK_THEME = Theme(
    mode="dark",
    # Status
    success="green",
    error="red",
    warning="yellow",
    info="cyan",
    # Semantic
    primary="cyan",
    secondary="blue",
    muted="dim",
    emphasis="bold",
    # Data
    data_name="cyan",
    data_url="steel_blue1",  # Softer blue for dark bg
    data_value="white",
    data_date="green",
    data_provider="magenta",
    # Progress
    progress_active="cyan",
    progress_pending="dim",
    progress_complete="green",
    progress_failed="red",
    # Table
    table_header="bold cyan",
    table_border="dim",
)

# Light theme - optimized for light terminal backgrounds
LIGHT_THEME = Theme(
    mode="light",
    # Status
    success="green",
    error="red",
    warning="dark_orange",  # Better contrast on light bg
    info="dark_cyan",
    # Semantic
    primary="dark_cyan",
    secondary="blue",
    muted="grey50",
    emphasis="bold",
    # Data
    data_name="dark_cyan",
    data_url="blue",
    data_value="black",
    data_date="dark_green",
    data_provider="dark_magenta",
    # Progress
    progress_active="dark_cyan",
    progress_pending="grey50",
    progress_complete="dark_green",
    progress_failed="red",
    # Table
    table_header="bold dark_cyan",
    table_border="grey50",
)


def detect_terminal_theme() -> Literal["light", "dark"]:
    """Attempt to detect if terminal has light or dark background.

    Uses common environment variables and heuristics.
    Defaults to dark (most common for developers).
    """
    # Check for explicit color scheme env vars
    colorfgbg = os.environ.get("COLORFGBG", "")
    if colorfgbg:
        # Format is "foreground;background" where 15=white bg, 0=black bg
        parts = colorfgbg.split(";")
        if len(parts) >= 2:
            try:
                bg = int(parts[-1])
                # Higher values typically indicate lighter backgrounds
                if bg >= 7:
                    return "light"
                return "dark"
            except ValueError:
                pass

    # Check TERM_PROGRAM for known light-by-default terminals
    term_program = os.environ.get("TERM_PROGRAM", "").lower()
    if term_program in ("apple_terminal",):
        # macOS Terminal defaults to light
        return "light"

    # Check for explicitly set theme hints
    if os.environ.get("INKWELL_THEME", "").lower() == "light":
        return "light"

    # Default to dark (most developer terminals are dark)
    return "dark"


# Cache for current theme (cleared when config changes)
_current_theme: Theme | None = None


def set_theme(mode: ThemeMode | str) -> Theme:
    """Set and cache the current theme.

    Args:
        mode: Theme mode ('light', 'dark', or 'auto')

    Returns:
        The active Theme instance
    """
    global _current_theme

    if isinstance(mode, str):
        mode = ThemeMode(mode.lower())

    if mode == ThemeMode.AUTO:
        detected = detect_terminal_theme()
        _current_theme = LIGHT_THEME if detected == "light" else DARK_THEME
    elif mode == ThemeMode.LIGHT:
        _current_theme = LIGHT_THEME
    else:
        _current_theme = DARK_THEME

    return _current_theme


def get_theme() -> Theme:
    """Get the current theme.

    If no theme is set, uses auto-detection.

    Returns:
        The active Theme instance
    """
    global _current_theme

    if _current_theme is None:
        return set_theme(ThemeMode.AUTO)

    return _current_theme


def reset_theme() -> None:
    """Reset the theme cache, forcing re-detection on next access."""
    global _current_theme
    _current_theme = None
