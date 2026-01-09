"""Tests for logging utilities."""

import logging
from pathlib import Path

from inkwell.utils.logging import get_logger, setup_logging


class TestLoggingSetup:
    """Tests for logging configuration."""

    def test_setup_logging_creates_logger(self, tmp_path: Path) -> None:
        """Test that setup_logging creates a logger."""
        logger = setup_logging(level="INFO")

        assert logger.name == "inkwell"
        assert logger.level == logging.INFO
        assert len(logger.handlers) > 0

    def test_setup_logging_with_file(self, tmp_path: Path) -> None:
        """Test logging with file handler."""
        log_file = tmp_path / "test.log"

        logger = setup_logging(level="DEBUG", log_file=log_file)

        # Log a message
        logger.info("Test message")

        # File should be created
        assert log_file.exists()

        # Should contain the message
        content = log_file.read_text()
        assert "Test message" in content

    def test_setup_logging_levels(self) -> None:
        """Test different log levels."""
        for level in ["DEBUG", "INFO", "WARNING", "ERROR"]:
            logger = setup_logging(level=level)
            assert logger.level == getattr(logging, level)

    def test_get_logger_returns_same_instance(self) -> None:
        """Test that get_logger returns the same logger instance."""
        logger1 = get_logger()
        logger2 = get_logger()

        assert logger1 is logger2
        assert logger1.name == "inkwell"

    def test_logger_does_not_propagate(self) -> None:
        """Test that logger does not propagate to root."""
        logger = setup_logging(level="INFO")

        assert logger.propagate is False

    def test_setup_logging_with_rich_console(self) -> None:
        """Test logging with rich console handler."""
        logger = setup_logging(level="INFO", rich_console=True)

        # Should have a handler
        assert len(logger.handlers) > 0

        # Handler should be RichHandler
        from rich.logging import RichHandler

        has_rich_handler = any(isinstance(h, RichHandler) for h in logger.handlers)
        assert has_rich_handler

    def test_setup_logging_without_rich_console(self) -> None:
        """Test logging without rich console handler."""
        logger = setup_logging(level="INFO", rich_console=False)

        # Should have a handler
        assert len(logger.handlers) > 0

        # Handler should be StreamHandler (not RichHandler)
        from rich.logging import RichHandler

        has_rich_handler = any(isinstance(h, RichHandler) for h in logger.handlers)
        assert not has_rich_handler

    def test_logger_clears_existing_handlers(self) -> None:
        """Test that setup_logging clears existing handlers."""
        # Setup logger twice
        logger1 = setup_logging(level="INFO")
        handler_count_1 = len(logger1.handlers)

        logger2 = setup_logging(level="DEBUG")
        handler_count_2 = len(logger2.handlers)

        # Should not accumulate handlers
        assert handler_count_1 == handler_count_2

    def test_log_file_creates_parent_directories(self, tmp_path: Path) -> None:
        """Test that log file creation creates parent directories."""
        log_file = tmp_path / "logs" / "subdir" / "test.log"

        logger = setup_logging(level="INFO", log_file=log_file)
        logger.info("Test message")

        # Directory and file should be created
        assert log_file.parent.exists()
        assert log_file.exists()
