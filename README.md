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

## Quick Start

```bash
# Install dependencies
sudo pacman -S uv wl-clipboard wtype libappindicator-gtk3

# Clone and install
git clone https://github.com/adityasinghcodes/superwhisper-linux.git
cd superwhisper-linux
uv sync

# Run
uv run superwhisper
```

## Setup Guide

See [SETUP.md](SETUP.md) for detailed setup instructions including:
- Hyprland keybind configuration
- GPU acceleration setup
- Microphone selection
- Troubleshooting

## Usage

1. Run `uv run superwhisper` (tray icon appears)
2. Press **Ctrl+Tab** to start recording
3. Speak
4. Press **Ctrl+Tab** again to stop
5. Text is transcribed and pasted

## License

MIT
