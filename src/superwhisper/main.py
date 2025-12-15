"""Main entry point for SuperWhisper Linux."""

import os
import queue
import subprocess
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


def install(use_systemd: bool = False):
    """Install desktop entry, autostart, and system integration."""
    from .install import install_all
    install_all(use_systemd=use_systemd)


def uninstall():
    """Remove all installed files."""
    from .install import uninstall as do_uninstall
    do_uninstall()


def status():
    """Show installation status."""
    from .install import print_status
    print_status()


def main():
    """Entry point."""
    # Handle subcommands before any other imports
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "toggle":
            toggle()
            return
        elif cmd == "keybind":
            keybind()
            return
        elif cmd == "install":
            use_systemd = "--systemd" in sys.argv
            install(use_systemd=use_systemd)
            return
        elif cmd == "uninstall":
            uninstall()
            return
        elif cmd == "status":
            status()
            return
        elif cmd in ("-h", "--help"):
            print("Usage: superwhisper [command]")
            print("")
            print("Commands:")
            print("  (none)      Start the application")
            print("  toggle      Toggle recording (send signal to running instance)")
            print("  keybind     Print Hyprland keybind setup instructions")
            print("  install     Install desktop entry, autostart, and global command")
            print("              --systemd  Use systemd service instead of autostart")
            print("  uninstall   Remove all installed files")
            print("  status      Show installation status")
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
    from .audio import AudioRecorder, list_audio_devices, list_audio_devices_with_retry
    from .config import Config
    from .hotkey import HotkeyListener
    from .notifications import NotificationManager
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
            self.notifications = NotificationManager(self.config)

            # Worker thread for transcription (single thread, no concurrency issues)
            self._audio_queue: queue.Queue = queue.Queue()
            worker = threading.Thread(target=self._worker_loop, daemon=True)
            worker.start()
            logger.info("Worker thread started")

            # Restore saved microphone
            if self.config.microphone:
                self._restore_microphone()

        def _restore_microphone(self):
            """Restore saved microphone from config.

            Uses retry logic on startup since audio system (PulseAudio/PipeWire)
            may not be fully initialized yet, especially on auto-start at login.
            """
            devices = list_audio_devices_with_retry()
            for dev in devices:
                if dev["name"] == self.config.microphone:
                    self.recorder.set_device(dev["index"])
                    logger.info("Restored microphone: %s", dev["name"])
                    return

            if devices:
                logger.warning("Saved microphone '%s' not found, using default", self.config.microphone)
            else:
                logger.warning("No microphones found during startup, will retry when tray menu is opened")

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
            self.notifications.notify_recording_started()

        def _stop_recording(self):
            """Stop recording and queue for transcription."""
            logger.info("Recording stopped")
            if self.tray:
                self.tray.set_recording(False)
                self.tray.set_transcribing(True)

            audio = self.recorder.stop()

            if len(audio) == 0:
                logger.warning("No audio recorded")
                self.notifications.notify_error("No audio recorded")
                if self.tray:
                    self.tray.set_transcribing(False)
                return

            self.notifications.notify_recording_stopped()

            # Queue audio for worker thread
            import time
            logger.info("[%.3f] Queuing audio", time.time() % 1000)
            self._audio_queue.put(audio)
            if self.tray:
                self.tray.set_queue_size(self._audio_queue.qsize())

        def _worker_loop(self):
            """Worker thread that processes audio queue sequentially."""
            import time
            logger.info("Worker loop running")
            while True:
                try:
                    audio = self._audio_queue.get()
                    start = time.time()
                    logger.info("[%.3f] Got audio (%.1fs)", time.time() % 1000, len(audio) / 16000)

                    # Update queue size display
                    if self.tray:
                        self.tray.set_queue_size(self._audio_queue.qsize())

                    # Drain queue to get only the latest audio
                    while not self._audio_queue.empty():
                        try:
                            audio = self._audio_queue.get_nowait()
                            logger.info("Skipping older recording, using latest")
                        except queue.Empty:
                            break

                    text = self.transcriber.transcribe(audio, self.config.language)
                    duration = time.time() - start
                    logger.info("Transcription took %.1fs", duration)

                    # Skip if newer audio arrived during transcription
                    if not self._audio_queue.empty():
                        logger.info("Newer recording available, skipping clipboard")
                        continue

                    # Update tray state
                    if self.tray:
                        self.tray.set_transcribing(False)
                        self.tray.set_queue_size(0)

                    if text:
                        logger.info("Clipboard: %s", text[:50] + "..." if len(text) > 50 else text)
                        # Don't wait for wl-copy - it stays running to serve clipboard
                        subprocess.Popen(["wl-copy", text], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        self.notifications.notify_transcription_complete(text, duration)
                    else:
                        logger.info("No speech detected")
                        self.notifications.notify_no_speech()
                except Exception as e:
                    logger.error("Worker error: %s", e)
                    import traceback
                    logger.error(traceback.format_exc())
                    self.notifications.notify_error(str(e))
                    if self.tray:
                        self.tray.set_transcribing(False)

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

            # Initialize notifications on main thread
            self.notifications.initialize()

            # Build model info string for tray
            device_name = self.transcriber._actual_device.upper()
            model_info = f"{self.config.model} ({device_name})"

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
                model_info=model_info if self.config.show_model_info else "",
                show_timer=self.config.show_recording_timer,
            )

            logger.info("=" * 50)
            logger.info("Ready! Run 'superwhisper keybind' for setup instructions.")
            logger.info("=" * 50)

            self.tray.run()

    app = SuperWhisper()
    app.run()


if __name__ == "__main__":
    main()
