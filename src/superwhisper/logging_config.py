"""Logging configuration for SuperWhisper."""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


# Global logger
_logger: logging.Logger | None = None


def get_log_dir() -> Path:
    """Get the log directory path."""
    config_dir = Path.home() / ".config" / "superwhisper-linux"
    log_dir = config_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def setup_logging(console_level: int = logging.INFO, file_level: int = logging.DEBUG) -> logging.Logger:
    """Set up application logging with console and file handlers."""
    global _logger

    if _logger is not None:
        return _logger

    log_dir = get_log_dir()
    log_file = log_dir / "superwhisper.log"

    # Create logger
    _logger = logging.getLogger("superwhisper")
    _logger.setLevel(logging.DEBUG)

    # Prevent duplicate handlers
    if _logger.handlers:
        return _logger

    # Console handler - clean output
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(console_level)
    console_handler.setFormatter(logging.Formatter("%(message)s"))

    # File handler with rotation
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(file_level)
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    ))

    _logger.addHandler(console_handler)
    _logger.addHandler(file_handler)

    return _logger


def get_logger(name: str = "") -> logging.Logger:
    """Get a logger instance. Call setup_logging() first."""
    if _logger is None:
        setup_logging()

    if name:
        return _logger.getChild(name)
    return _logger
