"""Logging configuration for Inkwell."""

import logging
from pathlib import Path

from rich.logging import RichHandler


def setup_logging(verbose: bool = False, log_file: Path | None = None) -> None:
    """Configure application logging.

    Args:
        verbose: Enable verbose (DEBUG) logging
        log_file: Optional file path for log output

    Examples:
        >>> setup_logging(verbose=True)
        >>> setup_logging(log_file=Path("inkwell.log"))
    """
    # Set level based on verbosity
    level = logging.DEBUG if verbose else logging.INFO

    # Create handlers
    handlers: list[logging.Handler] = []

    # Console handler with Rich formatting
    console_handler = RichHandler(
        rich_tracebacks=True,
        show_path=verbose,
        markup=True,
        omit_repeated_times=False,
    )
    console_handler.setLevel(level)
    handlers.append(console_handler)

    # File handler if specified
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        file_handler.setFormatter(file_formatter)
        handlers.append(file_handler)

    # Configure root logger
    logging.basicConfig(
        level=level,
        handlers=handlers,
        format="%(message)s",
    )

    # Set external library log levels to reduce noise
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("anthropic").setLevel(logging.WARNING)
    logging.getLogger("google").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("yt_dlp").setLevel(logging.WARNING)
