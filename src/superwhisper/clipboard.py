"""Clipboard and paste functionality for Wayland."""

import shutil
import subprocess

from .logging_config import get_logger

logger = get_logger("clipboard")


def check_dependencies() -> list[str]:
    """Check for required system commands. Returns list of missing commands."""
    missing = []
    for cmd in ["wl-copy", "wtype"]:
        if shutil.which(cmd) is None:
            missing.append(cmd)
    return missing


def copy_to_clipboard(text: str) -> bool:
    """Copy text to clipboard using wl-copy."""
    try:
        subprocess.run(
            ["wl-copy", text],
            check=True,
            capture_output=True,
        )
        logger.debug("Copied %d chars to clipboard", len(text))
        return True
    except subprocess.CalledProcessError as e:
        logger.error("Failed to copy to clipboard: %s", e)
        return False


def type_text(text: str) -> bool:
    """Type text into active window using wtype."""
    try:
        subprocess.run(
            ["wtype", text],
            check=True,
            capture_output=True,
        )
        logger.debug("Typed %d chars via wtype", len(text))
        return True
    except subprocess.CalledProcessError as e:
        logger.error("Failed to type text: %s", e)
        return False


def paste_text(text: str) -> bool:
    """Copy text to clipboard and type it into the active window."""
    copy_to_clipboard(text)
    return type_text(text)
