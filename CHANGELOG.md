# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2025-12-16

### Added

- **Auto-paste feature**: Transcribed text is automatically pasted into the active window
  - Smart terminal detection using substring matching (supports Ghostty, Kitty, Alacritty, etc.)
  - Uses Ctrl+Shift+V for terminals, Ctrl+V for other apps
- **Model selection menu**: Change Whisper model from the system tray
  - Shows download status for each model
  - Automatically downloads models when selected
- **Desktop notifications**: Get notified when recording starts, stops, and transcription completes
- **Recording timer**: Live duration display in tray menu while recording
- **Progress notifications**: Visual feedback during recording with basic animation

### Fixed

- **Microphone detection on autostart**: Wait for WirePlumber/PipeWire to be ready
  - No more "microphone not found" errors when app starts at login
  - Properly waits for audio service initialization
- **Terminal detection**: Use substring matching instead of exact match
  - Fixes detection for terminals like Ghostty (`com.mitchellh.ghostty`)

### Changed

- Improved notification update interval to 200ms for better performance
- Simplified tray UI during recording/processing states

## [0.1.0] - 2025-12-15

### Added

- Initial release
- Local speech-to-text using faster-whisper
- CUDA GPU acceleration support
- Global hotkey toggle (Ctrl+Tab)
- System tray with recording status
- Microphone selection (persisted to config)
- Desktop integration (app launcher, autostart)
- Systemd service option
- Install/uninstall commands
