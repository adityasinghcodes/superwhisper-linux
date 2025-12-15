"""Installation utilities for SuperWhisper Linux."""

import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

# Desktop entry template
DESKTOP_ENTRY = """[Desktop Entry]
Name=SuperWhisper
Comment=Speech-to-text using local Whisper models
Exec={exec_path}
Icon={icon_path}
Terminal=false
Type=Application
Categories=AudioVideo;Audio;Utility;
Keywords=speech;voice;whisper;transcribe;dictation;
StartupNotify=false
"""

# Systemd service template
SYSTEMD_SERVICE = """[Unit]
Description=SuperWhisper Linux - Speech to Text
Documentation=https://github.com/AditMeh/superwhisper-linux
After=graphical-session.target

[Service]
Type=simple
ExecStart={exec_path}
Restart=on-failure
RestartSec=5

# Environment for Wayland
Environment=DISPLAY=:0

[Install]
WantedBy=default.target
"""


def get_project_root() -> Path:
    """Get the project root directory."""
    return Path(__file__).parent.parent.parent


def get_icon_path() -> Path:
    """Get the path to the idle icon."""
    return get_project_root() / "assets" / "superwhisper-idle.svg"


def get_exec_path() -> str:
    """Get the executable path for superwhisper."""
    # Check if installed via uv tool
    uv_tool_bin = Path.home() / ".local" / "bin" / "superwhisper"
    if uv_tool_bin.exists():
        return str(uv_tool_bin)

    # Check if in PATH
    which = shutil.which("superwhisper")
    if which:
        return which

    # Fall back to uv run
    project_root = get_project_root()
    return f"uv run --project {project_root} superwhisper"


def get_desktop_dir() -> Path:
    """Get the applications directory."""
    return Path.home() / ".local" / "share" / "applications"


def get_autostart_dir() -> Path:
    """Get the autostart directory."""
    return Path.home() / ".config" / "autostart"


def get_systemd_user_dir() -> Path:
    """Get the systemd user directory."""
    return Path.home() / ".config" / "systemd" / "user"


def get_icon_install_dir() -> Path:
    """Get the icon installation directory."""
    return Path.home() / ".local" / "share" / "icons" / "hicolor" / "scalable" / "apps"


def install_icon() -> Path:
    """Install the icon to the standard location."""
    src_icon = get_icon_path()
    if not src_icon.exists():
        print(f"Warning: Icon not found at {src_icon}")
        return src_icon

    icon_dir = get_icon_install_dir()
    icon_dir.mkdir(parents=True, exist_ok=True)

    dest_icon = icon_dir / "superwhisper.svg"
    shutil.copy2(src_icon, dest_icon)
    print(f"Installed icon: {dest_icon}")
    return dest_icon


def install_desktop_entry(autostart: bool = True) -> Path:
    """Install the .desktop file."""
    exec_path = get_exec_path()
    icon_path = install_icon()

    desktop_content = DESKTOP_ENTRY.format(
        exec_path=exec_path,
        icon_path=icon_path,
    )

    # Install to applications directory
    desktop_dir = get_desktop_dir()
    desktop_dir.mkdir(parents=True, exist_ok=True)

    desktop_file = desktop_dir / "superwhisper.desktop"
    desktop_file.write_text(desktop_content)
    print(f"Installed desktop entry: {desktop_file}")

    # Also install to autostart if requested
    if autostart:
        autostart_dir = get_autostart_dir()
        autostart_dir.mkdir(parents=True, exist_ok=True)

        autostart_file = autostart_dir / "superwhisper.desktop"
        shutil.copy2(desktop_file, autostart_file)
        print(f"Installed autostart entry: {autostart_file}")

    # Update desktop database
    try:
        subprocess.run(
            ["update-desktop-database", str(desktop_dir)],
            capture_output=True,
            check=False,
        )
    except FileNotFoundError:
        pass  # update-desktop-database not installed

    return desktop_file


def install_systemd_service() -> Path:
    """Install the systemd user service."""
    exec_path = get_exec_path()

    service_content = SYSTEMD_SERVICE.format(exec_path=exec_path)

    systemd_dir = get_systemd_user_dir()
    systemd_dir.mkdir(parents=True, exist_ok=True)

    service_file = systemd_dir / "superwhisper.service"
    service_file.write_text(service_content)
    print(f"Installed systemd service: {service_file}")

    # Reload systemd
    subprocess.run(["systemctl", "--user", "daemon-reload"], check=False)
    print("Reloaded systemd user daemon")

    return service_file


def enable_systemd_service():
    """Enable the systemd service to start on login."""
    subprocess.run(["systemctl", "--user", "enable", "superwhisper.service"], check=False)
    print("Enabled superwhisper.service to start on login")


def start_systemd_service():
    """Start the systemd service now."""
    subprocess.run(["systemctl", "--user", "start", "superwhisper.service"], check=False)
    print("Started superwhisper.service")


def uninstall():
    """Remove all installed files."""
    files_to_remove = [
        get_desktop_dir() / "superwhisper.desktop",
        get_autostart_dir() / "superwhisper.desktop",
        get_systemd_user_dir() / "superwhisper.service",
        get_icon_install_dir() / "superwhisper.svg",
    ]

    # Stop and disable service first
    subprocess.run(["systemctl", "--user", "stop", "superwhisper.service"],
                   capture_output=True, check=False)
    subprocess.run(["systemctl", "--user", "disable", "superwhisper.service"],
                   capture_output=True, check=False)

    for f in files_to_remove:
        if f.exists():
            f.unlink()
            print(f"Removed: {f}")

    subprocess.run(["systemctl", "--user", "daemon-reload"], check=False)
    print("Uninstall complete")


def install_uv_tool():
    """Install superwhisper as a uv tool for global access."""
    project_root = get_project_root()

    print("Installing superwhisper as a global tool...")
    result = subprocess.run(
        ["uv", "tool", "install", "--reinstall", str(project_root)],
        check=False,
    )

    if result.returncode == 0:
        print("Installed! You can now run 'superwhisper' from anywhere.")
        return True
    else:
        print("Failed to install as uv tool. You can still use 'uv run superwhisper'")
        return False


def install_all(use_systemd: bool = False):
    """Run the full installation."""
    print("=" * 50)
    print("SuperWhisper Linux - Installation")
    print("=" * 50)
    print()

    # Step 1: Install as uv tool
    install_uv_tool()
    print()

    # Step 2: Install desktop entry and autostart
    install_desktop_entry(autostart=not use_systemd)
    print()

    if use_systemd:
        # Step 3a: Install and enable systemd service
        install_systemd_service()
        enable_systemd_service()
        print()
        print("To start now: systemctl --user start superwhisper")
    else:
        print("SuperWhisper will start automatically on login.")
        print("To start now, run: superwhisper")

    print()
    print("=" * 50)
    print("Installation complete!")
    print("=" * 50)
    print()
    print("The app will appear in your application launcher.")
    print("Run 'superwhisper keybind' to set up your hotkey.")


def print_status():
    """Print installation status."""
    print("SuperWhisper Installation Status")
    print("=" * 40)

    # Check uv tool
    uv_tool_bin = Path.home() / ".local" / "bin" / "superwhisper"
    print(f"UV tool binary:    {'✓' if uv_tool_bin.exists() else '✗'} {uv_tool_bin}")

    # Check desktop entry
    desktop_file = get_desktop_dir() / "superwhisper.desktop"
    print(f"Desktop entry:     {'✓' if desktop_file.exists() else '✗'} {desktop_file}")

    # Check autostart
    autostart_file = get_autostart_dir() / "superwhisper.desktop"
    print(f"Autostart entry:   {'✓' if autostart_file.exists() else '✗'} {autostart_file}")

    # Check systemd service
    service_file = get_systemd_user_dir() / "superwhisper.service"
    print(f"Systemd service:   {'✓' if service_file.exists() else '✗'} {service_file}")

    # Check if service is enabled
    result = subprocess.run(
        ["systemctl", "--user", "is-enabled", "superwhisper.service"],
        capture_output=True,
        text=True,
        check=False,
    )
    enabled = result.stdout.strip() == "enabled"
    print(f"Service enabled:   {'✓' if enabled else '✗'}")

    # Check if service is running
    result = subprocess.run(
        ["systemctl", "--user", "is-active", "superwhisper.service"],
        capture_output=True,
        text=True,
        check=False,
    )
    active = result.stdout.strip() == "active"
    print(f"Service running:   {'✓' if active else '✗'}")

    # Check icon
    icon_file = get_icon_install_dir() / "superwhisper.svg"
    print(f"Icon installed:    {'✓' if icon_file.exists() else '✗'} {icon_file}")
