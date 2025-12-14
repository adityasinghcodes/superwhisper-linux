"""Hotkey handling via Unix signals (for compositor keybinds)."""

import os
import signal
from pathlib import Path
from typing import Callable

from .logging_config import get_logger

logger = get_logger("hotkey")


def get_pid_file() -> Path:
    """Get path to PID file."""
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR", "/tmp")
    return Path(runtime_dir) / "superwhisper.pid"


class HotkeyListener:
    """Listens for toggle signal (SIGUSR1) from external keybind."""

    def __init__(self, hotkey: str = "CTRL+TAB", callback: Callable[[], None] = None):
        self.hotkey = hotkey
        self.callback = callback
        self._original_handler = None

    def _handle_signal(self, signum, frame):
        """Handle SIGUSR1 signal."""
        logger.info("Toggle signal received")
        if self.callback:
            self.callback()

    def start(self):
        """Start listening for signals and write PID file."""
        pid_file = get_pid_file()
        pid_file.write_text(str(os.getpid()))
        logger.debug("PID file written: %s", pid_file)

        self._original_handler = signal.signal(signal.SIGUSR1, self._handle_signal)
        logger.debug("Signal handler registered for SIGUSR1")

    def stop(self):
        """Stop listening and clean up PID file."""
        if self._original_handler:
            signal.signal(signal.SIGUSR1, self._original_handler)

        pid_file = get_pid_file()
        if pid_file.exists():
            pid_file.unlink()
            logger.debug("PID file removed")


def send_toggle_signal() -> bool:
    """Send toggle signal to running SuperWhisper instance."""
    pid_file = get_pid_file()

    if not pid_file.exists():
        logger.error("SuperWhisper is not running (no PID file)")
        return False

    try:
        pid = int(pid_file.read_text().strip())
        os.kill(pid, signal.SIGUSR1)
        logger.debug("Sent SIGUSR1 to PID %d", pid)
        return True
    except (ValueError, ProcessLookupError, PermissionError) as e:
        logger.error("Failed to send signal: %s", e)
        return False


def check_portal_available() -> bool:
    """Portal not used - always return True for signal-based approach."""
    return True
