"""Logging configuration for Inkwell."""

import logging
import sys
from pathlib import Path

from rich.console import Console
from rich.logging import RichHandler


def setup_logging(
    level: str = "INFO", log_file: Path | None = None, rich_console: bool = True
) -> logging.Logger:
    """Configure logging for Inkwell.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        log_file: Optional file path for log output
        rich_console: Whether to use rich formatting for console output

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger("inkwell")
    logger.setLevel(level)

    # Remove existing handlers to avoid duplicates
    logger.handlers.clear()

    # Console handler with rich formatting
    if rich_console:
        console = Console(stderr=True)
        console_handler = RichHandler(
            console=console,
            show_time=False,
            show_path=False,
            rich_tracebacks=True,
            tracebacks_show_locals=False,
        )
    else:
        console_handler = logging.StreamHandler(sys.stderr)
        console_formatter = logging.Formatter("%(levelname)s: %(message)s")
        console_handler.setFormatter(console_formatter)

    console_handler.setLevel(level)
    logger.addHandler(console_handler)

    # File handler (if specified)
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        file_handler.setFormatter(file_formatter)
        file_handler.setLevel(logging.DEBUG)  # Always DEBUG for file
        logger.addHandler(file_handler)

    # Prevent propagation to root logger
    logger.propagate = False

    return logger


def get_logger() -> logging.Logger:
    """Get the configured Inkwell logger.

    Returns:
        Logger instance (creates default if not yet configured)
    """
    logger = logging.getLogger("inkwell")

    # If not configured yet, set up with defaults
    if not logger.handlers:
        setup_logging()

    return logger
