# SuperWhisper Linux

A local speech-to-text application for Linux. Press a hotkey, speak, and get your transcription.

> **Note**: This is a personal project built for my own use on Arch Linux with Hyprland. It may not work on other setups without modifications.

## Features

- **Local transcription** - Uses [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (no cloud, no API keys)
- **GPU accelerated** - CUDA support for fast transcription
- **Global hotkey** - Toggle recording with Ctrl+Tab (configurable)
- **System tray** - Shows status with colored icons (gray = idle, red = recording, blue = transcribing)
- **Desktop notifications** - Get notified when recording starts, stops, and when transcription completes
- **Audio feedback** - Optional sound effects for recording start/stop (requires PipeWire)
- **Recording timer** - Live duration display in tray menu while recording
- **Auto-paste** - Transcribed text is typed into the active window
- **Microphone selection** - Choose your mic from the tray menu (persisted across restarts)
- **Desktop integration** - Shows in app launcher, autostart on login

## Requirements

- Arch Linux (tested on Hyprland/Wayland)
- Python 3.13+
- PipeWire audio
- NVIDIA GPU with CUDA (optional, falls back to CPU)

## Installation

### 1. Install System Dependencies

```bash
sudo pacman -S uv wl-clipboard wtype libappindicator-gtk3
```

### 2. Clone the Repository

```bash
git clone https://github.com/adityasinghcodes/superwhisper-linux.git
cd superwhisper-linux
uv sync
```

### 3. Install the App

```bash
uv run superwhisper install
```

This will:
- Install `superwhisper` command globally (via `uv tool install`)
- Add a desktop entry (shows up in app launchers)
- Set up autostart on login
- Install the app icon

### 4. Add to PATH (if needed)

If you see a warning about `~/.local/bin` not being in PATH:

```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

### 5. Set Up Hyprland Keybind

Run `superwhisper keybind` for instructions, or add manually to `~/.config/hypr/hyprland.conf`:

```
bind = CTRL, TAB, exec, superwhisper toggle
```

Then reload: `hyprctl reload`

### 6. Start the App

```bash
superwhisper
```

Or search "SuperWhisper" in your app launcher. After the first login, it will start automatically.

GPU acceleration works automatically if you have an NVIDIA GPU with CUDA drivers installed.

## Alternative: Systemd Service

If you prefer systemd to manage the app instead of autostart:

```bash
uv run superwhisper install --systemd
```

Control it with:
```bash
systemctl --user start superwhisper    # Start now
systemctl --user stop superwhisper     # Stop
systemctl --user restart superwhisper  # Restart
systemctl --user status superwhisper   # Check status
journalctl --user -u superwhisper -f   # View logs live
```

## Updating

When you pull new changes from the repository, the installed app doesn't update automatically. To apply updates:

```bash
cd superwhisper-linux
git pull
superwhisper install
```

Then restart the app:
- If running manually: quit from tray menu and run `superwhisper`
- If using systemd: `systemctl --user restart superwhisper`
- Or log out and back in

## CLI Commands

```bash
superwhisper            # Start the app
superwhisper toggle     # Toggle recording (used by keybind)
superwhisper keybind    # Print Hyprland setup instructions
superwhisper install    # Install desktop entry, autostart, global command
superwhisper install --systemd  # Use systemd instead of autostart
superwhisper uninstall  # Remove all installed files
superwhisper status     # Show installation status
superwhisper --help     # Show help
```

## Usage

1. Launch SuperWhisper from your app launcher (or it starts automatically on login)
2. Press **Ctrl+Tab** to start recording (icon turns red)
3. Speak
4. Press **Ctrl+Tab** again to stop
5. Text is transcribed and pasted into the active window

### Microphone Selection

1. Click the tray icon
2. Go to **Microphone** submenu
3. Select your microphone

The selection is saved automatically.

## Configuration

Edit `~/.config/superwhisper-linux/config.json`:

```json
{
  "model": "tiny",
  "device": "auto",
  "compute_type": "auto",
  "language": "en",
  "hotkey": "CTRL+TAB",
  "microphone": "Your Microphone Name",
  "notifications_enabled": true,
  "audio_feedback_enabled": false,
  "show_model_info": true,
  "show_recording_timer": true
}
```

**Models** (speed vs accuracy tradeoff):
| Model | Size | Use Case |
|-------|------|----------|
| `tiny` | ~75MB | Fastest, good for quick notes |
| `base` | ~145MB | Balanced |
| `small` | ~465MB | Better accuracy |
| `medium` | ~1.5GB | High accuracy |
| `large-v3` | ~3GB | Best accuracy, slower |

**Device**:
- `auto` - Use GPU if available, else CPU (recommended)
- `cuda` - Force GPU
- `cpu` - Force CPU

**Notifications & Feedback**:
- `notifications_enabled` - Show desktop notifications (default: true)
- `audio_feedback_enabled` - Play sounds on record start/stop (default: false)
- `show_model_info` - Display model name in tray menu (default: true)
- `show_recording_timer` - Show live recording duration in tray (default: true)

## Troubleshooting

### Check Installation Status

```bash
superwhisper status
```

This shows what's installed and what's missing.

### View Logs

```bash
# View log file
cat ~/.config/superwhisper-linux/logs/superwhisper.log

# Watch logs live
tail -f ~/.config/superwhisper-linux/logs/superwhisper.log

# If using systemd
journalctl --user -u superwhisper -f
```

### "No speech detected"

1. Check microphone selection in tray menu
2. Ensure microphone volume is up in system settings
3. Test your mic: `arecord -d 3 test.wav && aplay test.wav`
4. Check logs for errors

### Keybind Not Working

1. Verify superwhisper is running (tray icon visible)
2. Test manually: `superwhisper toggle`
3. Check Hyprland config syntax
4. Reload Hyprland: `hyprctl reload`

### Slow Transcription

1. Check if GPU is being used:
   ```bash
   grep -i "cuda\|device" ~/.config/superwhisper-linux/logs/superwhisper.log
   ```
2. If using CPU, try a smaller model in config.json: `"model": "tiny"`
3. Ensure NVIDIA drivers and CUDA are installed: `nvidia-smi`

### App Won't Start

1. Check for errors:
   ```bash
   superwhisper 2>&1 | head -50
   ```
2. Check if another instance is running:
   ```bash
   pgrep -f superwhisper
   ```
3. Remove stale PID file:
   ```bash
   rm -f /run/user/$(id -u)/superwhisper.pid
   ```

### Reinstall

If things are broken, do a clean reinstall:

```bash
superwhisper uninstall
uv tool uninstall superwhisper
uv run superwhisper install
```

## Uninstall

### Remove App Integration

```bash
superwhisper uninstall
```

This removes:
- Desktop entry (`~/.local/share/applications/superwhisper.desktop`)
- Autostart entry (`~/.config/autostart/superwhisper.desktop`)
- Systemd service (if installed)
- App icon

### Remove Global Command

```bash
uv tool uninstall superwhisper
```

### Remove Configuration and Logs

```bash
rm -rf ~/.config/superwhisper-linux
```

### Complete Removal

```bash
# Stop if running
pkill -f superwhisper

# Remove everything
superwhisper uninstall
uv tool uninstall superwhisper
rm -rf ~/.config/superwhisper-linux

# Remove the source code
cd ..
rm -rf superwhisper-linux
```

## Files

| Path | Purpose |
|------|---------|
| `~/.config/superwhisper-linux/config.json` | Settings |
| `~/.config/superwhisper-linux/logs/` | Log files (rotates at 5MB) |
| `~/.local/share/applications/superwhisper.desktop` | Desktop entry |
| `~/.config/autostart/superwhisper.desktop` | Autostart entry |
| `~/.config/systemd/user/superwhisper.service` | Systemd service (if installed) |
| `~/.local/bin/superwhisper` | Global command |
| `/run/user/$UID/superwhisper.pid` | PID file (while running) |

## License

MIT
