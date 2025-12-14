# SuperWhisper Linux - Setup Guide

Step-by-step setup for Arch Linux with Hyprland.

## 1. Install System Dependencies

```bash
# Required
sudo pacman -S uv wl-clipboard wtype libappindicator-gtk3

# For GPU acceleration (recommended)
sudo pacman -S cuda cudnn
```

After installing CUDA, **reboot** for library paths to take effect.

## 2. Clone and Install

```bash
cd ~/projects  # or wherever you want
git clone <repo-url> superwhisper-linux
cd superwhisper-linux

# Install Python dependencies
uv sync
```

## 3. Test the App

```bash
uv run superwhisper
```

You should see:
- Model loading (downloads ~75MB on first run)
- "Ready!" message
- System tray icon appears

## 4. Configure Hyprland Keybind

Add to `~/.config/hypr/hyprland.conf`:

```
bind = CTRL, TAB, exec, /home/YOUR_USERNAME/projects/superwhisper-linux/.venv/bin/superwhisper toggle
```

Replace `YOUR_USERNAME` with your actual username.

Reload Hyprland:

```bash
hyprctl reload
```

## 5. Select Microphone

1. Click the tray icon
2. Go to **Microphone** submenu
3. Select your microphone (e.g., "Scarlett 2i2...")

The selection is saved automatically.

## 6. Usage

1. Press **Ctrl+Tab** to start recording (tray icon changes)
2. Speak
3. Press **Ctrl+Tab** again to stop
4. Text is transcribed and pasted into the active window

## Troubleshooting

### "libcublas.so.12 not found"

Install CUDA and reboot:

```bash
sudo pacman -S cuda
reboot
```

### "No speech detected"

- Check microphone selection in tray menu
- Ensure microphone volume is up in system settings
- Check logs: `~/.config/superwhisper-linux/logs/superwhisper.log`

### Keybind not working

1. Ensure you're using the **full path** to superwhisper
2. Test manually: `/path/to/.venv/bin/superwhisper toggle`
3. Check if superwhisper is running (tray icon visible)

### Slow transcription

- Using CPU instead of GPU - install `cuda` and `cudnn`
- Try smaller model: edit `~/.config/superwhisper-linux/config.json` and set `"model": "tiny"`

## Files

| Path | Purpose |
|------|---------|
| `~/.config/superwhisper-linux/config.json` | Settings |
| `~/.config/superwhisper-linux/logs/` | Log files |
| `/run/user/1000/superwhisper.pid` | PID file (while running) |

## Configuration Options

Edit `~/.config/superwhisper-linux/config.json`:

```json
{
  "model": "tiny",
  "device": "auto",
  "compute_type": "auto",
  "language": "en",
  "hotkey": "CTRL+TAB",
  "microphone": "Your Microphone Name"
}
```

**Models** (speed vs accuracy tradeoff):
- `tiny` - Fastest, ~75MB, good for quick notes
- `base` - ~145MB
- `small` - ~465MB
- `medium` - ~1.5GB
- `large-v3` - Best accuracy, ~3GB, slower

**Device**:
- `auto` - Use GPU if available, else CPU
- `cuda` - Force GPU
- `cpu` - Force CPU
