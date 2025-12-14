"""Main entry point for SuperWhisper Linux."""

import os
import sys
import threading

# Preload CUDA 12 libraries for ctranslate2 compatibility
def _preload_cuda12_libs():
    """Preload CUDA 12 libraries from pip-installed nvidia packages."""
    try:
        import ctypes
        import nvidia.cublas
        lib_path = os.path.join(nvidia.cublas.__path__[0], "lib")
        for lib in ["libcublas.so.12", "libcublasLt.so.12"]:
            lib_file = os.path.join(lib_path, lib)
            if os.path.exists(lib_file):
                ctypes.CDLL(lib_file, mode=ctypes.RTLD_GLOBAL)
    except (ImportError, IndexError, OSError):
        pass

_preload_cuda12_libs()


def keybind():
    """Print Hyprland keybind configuration."""
    from .config import Config
    config = Config.load()

    # Parse hotkey (e.g., "CTRL+TAB" -> "CTRL, TAB")
    parts = config.hotkey.split("+")
    mod = parts[0] if len(parts) > 1 else ""
    key = parts[-1]

    print("")
    print("=" * 60)
    print("Hyprland Keybind Setup")
    print("=" * 60)
    print("")
    print("Add this line to ~/.config/hypr/hyprland.conf:")
    print("")
    print(f"  bind = {mod}, {key}, exec, superwhisper toggle")
    print("")
    print("Then reload Hyprland:")
    print("  hyprctl reload")
    print("")
    print("=" * 60)
    print("")


def toggle():
    """Send toggle signal to running instance."""
    from .hotkey import send_toggle_signal
    success = send_toggle_signal()
    sys.exit(0 if success else 1)


def main():
    """Entry point."""
    # Handle subcommands before any other imports
    if len(sys.argv) > 1:
        if sys.argv[1] == "toggle":
            toggle()
            return
        elif sys.argv[1] == "keybind":
            keybind()
            return
        elif sys.argv[1] in ("-h", "--help"):
            print("Usage: superwhisper [command]")
            print("")
            print("Commands:")
            print("  (none)     Start the application")
            print("  toggle     Toggle recording (send signal to running instance)")
            print("  keybind    Print Hyprland keybind setup instructions")
            return

    # Initialize logging first
    from .logging_config import setup_logging, get_logger, get_log_dir
    setup_logging()
    logger = get_logger("main")

    # Check dependencies
    from .deps import check_all, print_missing
    missing = check_all()
    if missing:
        print_missing(missing)
        sys.exit(1)

    # Now safe to import everything
    from .audio import AudioRecorder, list_audio_devices
    from .clipboard import paste_text
    from .config import Config
    from .hotkey import HotkeyListener
    from .transcribe import Transcriber
    from .tray import TrayIcon

    class SuperWhisper:
        """Main application class."""

        def __init__(self):
            self.config = Config.load()
            self.recorder = AudioRecorder()
            self.transcriber = Transcriber(
                model_size=self.config.model,
                device=self.config.device,
                compute_type=self.config.compute_type,
            )
            self.tray: TrayIcon | None = None
            self.hotkey_listener: HotkeyListener | None = None
            self._cancel_transcription = threading.Event()
            self._transcribe_thread: threading.Thread | None = None

            # Restore saved microphone
            if self.config.microphone:
                self._restore_microphone()

        def _restore_microphone(self):
            """Restore saved microphone from config."""
            devices = list_audio_devices()
            for dev in devices:
                if dev["name"] == self.config.microphone:
                    self.recorder.set_device(dev["index"])
                    logger.info("Restored microphone: %s", dev["name"])
                    return

            logger.warning("Saved microphone '%s' not found, using default", self.config.microphone)

        def _on_hotkey(self):
            """Called when the hotkey is pressed."""
            if self.recorder.is_recording:
                self._stop_recording()
            else:
                self._start_recording()

        def _start_recording(self):
            """Start recording audio."""
            logger.info("Recording started")
            self.recorder.start()
            if self.tray:
                self.tray.set_recording(True)

        def _stop_recording(self):
            """Stop recording and transcribe."""
            logger.info("Recording stopped")
            if self.tray:
                self.tray.set_recording(False)

            audio = self.recorder.stop()

            if len(audio) == 0:
                logger.warning("No audio recorded")
                return

            # Cancel any previous transcription
            if self._transcribe_thread and self._transcribe_thread.is_alive():
                logger.info("Cancelling previous transcription")
                self._cancel_transcription.set()
                self._transcribe_thread.join(timeout=0.1)

            # Reset cancel flag for new transcription
            self._cancel_transcription.clear()

            def transcribe():
                text = self.transcriber.transcribe(audio, self.config.language)
                if self._cancel_transcription.is_set():
                    logger.info("Transcription cancelled")
                    return
                if text:
                    logger.info("Pasting: %s", text[:50] + "..." if len(text) > 50 else text)
                    paste_text(text)
                else:
                    logger.info("No speech detected")

            self._transcribe_thread = threading.Thread(target=transcribe, daemon=True)
            self._transcribe_thread.start()

        def _on_quit(self):
            """Called when quit is requested."""
            if self.hotkey_listener:
                self.hotkey_listener.stop()

        def _on_device_change(self, device_index: int | None, device_name: str | None):
            """Called when microphone selection changes."""
            self.recorder.set_device(device_index)
            self.config.microphone = device_name
            self.config.save()
            logger.info("Microphone saved: %s", device_name)

        def run(self):
            """Run the application."""
            logger.info("=" * 50)
            logger.info("SuperWhisper Linux")
            logger.info("=" * 50)
            logger.info("Config: %s", Config.get_config_path())
            logger.info("Logs: %s", get_log_dir())
            logger.info("Model: %s | Device: %s | Language: %s",
                       self.config.model, self.config.device, self.config.language)

            # Pre-load the model
            self.transcriber.load_model()

            # Set up signal listener
            self.hotkey_listener = HotkeyListener(
                hotkey=self.config.hotkey,
                callback=self._on_hotkey,
            )
            self.hotkey_listener.start()

            # Set up and run tray icon
            self.tray = TrayIcon(
                on_quit=self._on_quit,
                on_device_change=self._on_device_change,
                saved_device_name=self.config.microphone,
            )

            logger.info("=" * 50)
            logger.info("Ready! Run 'superwhisper keybind' for setup instructions.")
            logger.info("=" * 50)

            self.tray.run()

    app = SuperWhisper()
    app.run()


if __name__ == "__main__":
    main()
