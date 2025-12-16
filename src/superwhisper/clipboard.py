"""Clipboard and paste functionality for Wayland."""

import json
import shutil
import subprocess
import time

from .logging_config import get_logger

logger = get_logger("clipboard")

# Terminal emulators that use Ctrl+Shift+V for paste
DEFAULT_TERMINAL_CLASSES = {
    "kitty",
    "alacritty",
    "foot",
    "wezterm",
    "ghostty",
    "konsole",
    "gnome-terminal",
    "gnome-terminal-server",
    "xfce4-terminal",
    "terminator",
    "tilix",
    "st",
    "st-256color",
    "urxvt",
    "xterm",
    "contour",
    "warp",
    "rio",
    "blackbox",
    "ptyxis",
}


def check_dependencies() -> list[str]:
    """Check for required system commands. Returns list of missing commands."""
    missing = []
    for cmd in ["wl-copy", "wtype"]:
        if shutil.which(cmd) is None:
            missing.append(cmd)
    return missing


def copy_to_clipboard(text: str) -> bool:
    """Copy text to clipboard using wl-copy (non-blocking)."""
    try:
        # Don't wait for wl-copy - it stays running to serve clipboard on Wayland
        subprocess.Popen(
            ["wl-copy", text],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        logger.debug("Copied %d chars to clipboard", len(text))
        return True
    except OSError as e:
        logger.error("Failed to copy to clipboard: %s", e)
        return False


def get_active_window_class() -> str | None:
    """Get the class of the currently focused window on Hyprland."""
    try:
        result = subprocess.run(
            ["hyprctl", "activewindow", "-j"],
            capture_output=True,
            text=True,
            timeout=1,
        )
        if result.returncode == 0 and result.stdout.strip():
            data = json.loads(result.stdout)
            window_class = data.get("class", "")
            logger.debug("Active window class: %s", window_class)
            return window_class.lower() if window_class else None
    except subprocess.TimeoutExpired:
        logger.warning("hyprctl timed out")
    except subprocess.SubprocessError as e:
        logger.debug("hyprctl not available: %s", e)
    except json.JSONDecodeError as e:
        logger.warning("Failed to parse hyprctl output: %s", e)
    return None


def is_terminal(window_class: str | None, terminal_classes: set[str] | None = None) -> bool:
    """Check if the window class is a terminal emulator."""
    if not window_class:
        return False
    classes = terminal_classes or DEFAULT_TERMINAL_CLASSES
    return window_class in classes


def send_paste_shortcut(use_shift: bool = False) -> bool:
    """Send paste keyboard shortcut using wtype.

    Args:
        use_shift: If True, send Ctrl+Shift+V (for terminals), else Ctrl+V
    """
    try:
        if use_shift:
            # Ctrl+Shift+V for terminals
            subprocess.run(
                ["wtype", "-M", "ctrl", "-M", "shift", "v", "-m", "shift", "-m", "ctrl"],
                check=True,
                capture_output=True,
                timeout=2,
            )
            logger.debug("Sent Ctrl+Shift+V")
        else:
            # Ctrl+V for regular apps
            subprocess.run(
                ["wtype", "-M", "ctrl", "v", "-m", "ctrl"],
                check=True,
                capture_output=True,
                timeout=2,
            )
            logger.debug("Sent Ctrl+V")
        return True
    except subprocess.TimeoutExpired:
        logger.error("wtype timed out")
        return False
    except subprocess.CalledProcessError as e:
        logger.error("Failed to send paste shortcut: %s", e)
        return False


def type_text(text: str, delay_ms: int = 5) -> bool:
    """Type text into active window character-by-character using wtype.

    Args:
        text: Text to type
        delay_ms: Delay between keystrokes in milliseconds (prevents crashes)
    """
    try:
        subprocess.run(
            ["wtype", "-d", str(delay_ms), text],
            check=True,
            capture_output=True,
            timeout=30,
        )
        logger.debug("Typed %d chars via wtype", len(text))
        return True
    except subprocess.TimeoutExpired:
        logger.error("wtype timed out while typing")
        return False
    except subprocess.CalledProcessError as e:
        logger.error("Failed to type text: %s", e)
        return False


def auto_paste(text: str, terminal_classes: set[str] | None = None) -> bool:
    """Copy text to clipboard and paste into active window.

    Automatically detects if the active window is a terminal and uses
    the appropriate paste shortcut (Ctrl+Shift+V for terminals, Ctrl+V otherwise).

    Args:
        text: Text to paste
        terminal_classes: Optional custom set of terminal class names

    Returns:
        True if paste was successful
    """
    # Copy to clipboard first
    if not copy_to_clipboard(text):
        return False

    # Small delay for clipboard to settle
    time.sleep(0.05)

    # Detect if active window is a terminal
    window_class = get_active_window_class()
    is_term = is_terminal(window_class, terminal_classes)

    if is_term:
        logger.info("Terminal detected (%s), using Ctrl+Shift+V", window_class)
    else:
        logger.info("Non-terminal window (%s), using Ctrl+V", window_class or "unknown")

    return send_paste_shortcut(use_shift=is_term)


def paste_text(text: str) -> bool:
    """Legacy function - copy text to clipboard and type it.

    Deprecated: Use auto_paste() instead for better reliability.
    """
    copy_to_clipboard(text)
    return type_text(text)
