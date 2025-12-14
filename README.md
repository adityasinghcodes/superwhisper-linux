# SuperWhisper Linux

A local speech-to-text application for Linux. Press a hotkey, speak, and the transcribed text is pasted into your active window.

> **Note**: This is a personal project built for my own use on Arch Linux with Hyprland. It may not work on other setups without modifications.

## Features

- **Local transcription** - Uses [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (no cloud, no API keys)
- **GPU accelerated** - CUDA support for fast transcription
- **Global hotkey** - Toggle recording with Ctrl+Tab (configurable)
- **System tray** - Shows recording status (gray = idle, red = recording)
- **Auto-paste** - Transcribed text is typed into the active window
- **Microphone selection** - Choose your mic from the tray menu (persisted across restarts)

## Requirements

- Arch Linux (tested on Hyprland/Wayland)
- PipeWire audio
- NVIDIA GPU with CUDA (optional, falls back to CPU)

## Installation

```bash
# Required
sudo pacman -S uv wl-clipboard wtype libappindicator-gtk3

# Clone and install
git clone https://github.com/adityasinghcodes/superwhisper-linux.git
cd superwhisper-linux
uv sync

# Run
uv run superwhisper
```

GPU acceleration works automatically if you have an NVIDIA GPU with CUDA drivers installed.

You should see:
- Model loading (downloads ~75MB on first run)
- "Ready!" message
- System tray icon appears

## Hyprland Keybind

Add to `~/.config/hypr/hyprland.conf`:

```
bind = CTRL, TAB, exec, /home/YOUR_USERNAME/projects/superwhisper-linux/.venv/bin/superwhisper toggle
```

Replace `YOUR_USERNAME` with your actual username.

Reload Hyprland:

```bash
hyprctl reload
```

## Usage

1. Run `uv run superwhisper` (tray icon appears)
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

## Troubleshooting

### "No speech detected"

- Check microphone selection in tray menu
- Ensure microphone volume is up in system settings
- Check logs: `~/.config/superwhisper-linux/logs/superwhisper.log`

### Keybind not working

1. Ensure you're using the **full path** to superwhisper
2. Test manually: `/path/to/.venv/bin/superwhisper toggle`
3. Check if superwhisper is running (tray icon visible)

### Slow transcription

- Check if GPU is being used (logs show "Model loaded on CUDA")
- Try smaller model: set `"model": "tiny"` in config.json

## Files

| Path | Purpose |
|------|---------|
| `~/.config/superwhisper-linux/config.json` | Settings |
| `~/.config/superwhisper-linux/logs/` | Log files |
| `/run/user/1000/superwhisper.pid` | PID file (while running) |

## License

MIT
