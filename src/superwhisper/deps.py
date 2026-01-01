"""Dependency checking with helpful error messages."""

import shutil
from dataclasses import dataclass


@dataclass
class MissingDep:
    """A missing dependency."""
    name: str
    install_cmd: str
    description: str


def check_all() -> list[MissingDep]:
    """Check all dependencies. Returns list of missing ones."""
    missing = []

    # Check system commands
    commands = {
        "wl-copy": ("wl-clipboard", "clipboard support"),
        "wtype": ("wtype", "typing text into windows"),
    }
    for cmd, (pkg, desc) in commands.items():
        if shutil.which(cmd) is None:
            missing.append(MissingDep(
                name=cmd,
                install_cmd=f"sudo pacman -S {pkg}",
                description=desc,
            ))

    # Check GTK/AppIndicator
    try:
        import gi
        gi.require_version("Gtk", "3.0")
        gi.require_version("AppIndicator3", "0.1")
        from gi.repository import Gtk, AppIndicator3  # noqa: F401
    except (ImportError, ValueError) as e:
        if "AppIndicator3" in str(e):
            missing.append(MissingDep(
                name="AppIndicator3",
                install_cmd="sudo pacman -S libappindicator-gtk3",
                description="system tray icon",
            ))
        elif "Gtk" in str(e):
            missing.append(MissingDep(
                name="GTK3",
                install_cmd="sudo pacman -S gtk3",
                description="GUI toolkit",
            ))

    # Check libnotify for desktop notifications
    try:
        import gi
        gi.require_version("Notify", "0.7")
        from gi.repository import Notify  # noqa: F401
    except (ImportError, ValueError):
        missing.append(MissingDep(
            name="libnotify",
            install_cmd="sudo pacman -S libnotify",
            description="desktop notifications",
        ))

    return missing


def print_missing(missing: list[MissingDep]):
    """Print missing dependencies with install instructions."""
    print("\n" + "=" * 50)
    print("Missing dependencies:")
    print("=" * 50 + "\n")

    for dep in missing:
        print(f"  {dep.name}")
        print(f"    Needed for: {dep.description}")
        print(f"    Install:    {dep.install_cmd}")
        print()

    print("Install all with:")
    # Collect unique pacman packages
    pacman_pkgs = []
    for dep in missing:
        if dep.install_cmd.startswith("sudo pacman"):
            pkg = dep.install_cmd.split()[-1]
            if pkg not in pacman_pkgs:
                pacman_pkgs.append(pkg)

    if pacman_pkgs:
        print(f"  sudo pacman -S {' '.join(pacman_pkgs)}")
    print()
