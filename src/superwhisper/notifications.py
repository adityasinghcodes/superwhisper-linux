"""Desktop notifications and audio feedback."""

import subprocess
import time
from pathlib import Path
from typing import Callable

import gi

gi.require_version("Notify", "0.7")
from gi.repository import Notify, GLib

from .config import Config
from .logging_config import get_logger

logger = get_logger("notifications")


class NotificationManager:
    """Manages desktop notifications and audio feedback."""

    def __init__(self, config: Config):
        self.config = config
        self._initialized = False
        self._gst_available = False
        self._paplay_available = False
        self._processing_notification: "Notify.Notification | None" = None
        self._processing_timer_id: int | None = None
        self._processing_start_time: float | None = None
        self._recording_notification: "Notify.Notification | None" = None
        self._recording_timer_id: int | None = None
        self._level_callback: "Callable[[], float] | None" = None
        self._level_history: list[float] = []  # Recent levels for waveform display

    def initialize(self):
        """Initialize libnotify. Call from main thread."""
        if self._initialized:
            return

        Notify.init("SuperWhisper")
        self._initialized = True
        self._check_audio_backends()
        logger.debug("Notification manager initialized")

    def _check_audio_backends(self):
        """Check available audio backends for feedback sounds."""
        # Check GStreamer
        try:
            gi.require_version("Gst", "1.0")
            from gi.repository import Gst
            Gst.init(None)
            self._gst_available = True
            logger.debug("GStreamer available for audio feedback")
        except (ValueError, ImportError):
            self._gst_available = False

        # Check paplay (PulseAudio/PipeWire)
        import shutil
        self._paplay_available = shutil.which("paplay") is not None
        if self._paplay_available:
            logger.debug("paplay available for audio feedback")

        if not self._gst_available and not self._paplay_available:
            logger.debug("No audio backend available, audio feedback disabled")

    def _notify(self, title: str, body: str, icon: str = "audio-input-microphone",
                urgency: str = "normal"):
        """Send a desktop notification. Thread-safe."""
        if not self.config.notifications_enabled:
            return

        def _send():
            if not self._initialized:
                self.initialize()
            notification = Notify.Notification.new(title, body, icon)
            urgency_map = {
                "low": Notify.Urgency.LOW,
                "normal": Notify.Urgency.NORMAL,
                "critical": Notify.Urgency.CRITICAL,
            }
            notification.set_urgency(urgency_map.get(urgency, Notify.Urgency.NORMAL))
            try:
                notification.show()
            except Exception as e:
                logger.warning("Failed to show notification: %s", e)
            return False  # Remove from idle queue

        GLib.idle_add(_send)

    def _play_sound(self, sound_name: str):
        """Play a feedback sound. Thread-safe."""
        if not self.config.audio_feedback_enabled:
            return

        # Use freedesktop sound theme names
        sound_map = {
            "start": "message-new-instant",
            "stop": "message-sent-instant",
            "complete": "complete",
            "error": "dialog-error",
        }
        sound_id = sound_map.get(sound_name, sound_name)

        def _play():
            if self._paplay_available:
                try:
                    # Use paplay with freedesktop sound theme
                    subprocess.Popen(
                        ["paplay", f"/usr/share/sounds/freedesktop/stereo/{sound_id}.oga"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                except Exception as e:
                    logger.debug("paplay failed: %s", e)
            return False

        GLib.idle_add(_play)

    def notify_recording_started(self, level_callback: Callable[[], float] | None = None):
        """Notify that recording has started with live audio level display.

        Args:
            level_callback: Optional callback that returns current audio level (0.0-1.0)
        """
        self._play_sound("start")
        self._level_callback = level_callback
        self._level_history = []
        self._start_recording_notification()
        logger.debug("Notified: recording started")

    def _level_to_bars(self, level: float) -> str:
        """Convert audio level (0.0-1.0) to Unicode bar character."""
        bars = " ▁▂▃▄▅▆▇█"
        index = int(level * (len(bars) - 1))
        return bars[min(index, len(bars) - 1)]

    def _get_waveform_display(self) -> str:
        """Get waveform display string from level history."""
        if not self._level_history:
            return "▁▁▁▁▁▁▁▁"
        # Take last 8 samples for display
        recent = self._level_history[-8:]
        # Pad with low bars if not enough history
        while len(recent) < 8:
            recent.insert(0, 0.0)
        return "".join(self._level_to_bars(level) for level in recent)

    def _start_recording_notification(self):
        """Start a persistent notification that shows audio level during recording."""
        if not self.config.notifications_enabled:
            return

        def _create():
            if not self._initialized:
                self.initialize()

            # Create notification that we'll update
            self._recording_notification = Notify.Notification.new(
                "Recording",
                "Speak now...  ▁▁▁▁▁▁▁▁",
                "audio-input-microphone"
            )
            self._recording_notification.set_urgency(Notify.Urgency.LOW)
            try:
                self._recording_notification.show()
            except Exception as e:
                logger.warning("Failed to show recording notification: %s", e)

            # Start timer to update notification with audio level (every 150ms for smooth updates)
            self._recording_timer_id = GLib.timeout_add(150, self._update_recording_notification)
            return False

        GLib.idle_add(_create)

    def _update_recording_notification(self) -> bool:
        """Update the recording notification with current audio level."""
        if self._recording_notification is None:
            return False  # Stop timer

        # Get current level from callback
        if self._level_callback is not None:
            try:
                level = self._level_callback()
                self._level_history.append(level)
                # Keep only last 16 samples
                if len(self._level_history) > 16:
                    self._level_history = self._level_history[-16:]
            except Exception:
                pass

        waveform = self._get_waveform_display()

        try:
            self._recording_notification.update(
                "Recording",
                f"Speak now...  {waveform}",
                "audio-input-microphone"
            )
            self._recording_notification.show()
        except Exception as e:
            logger.debug("Failed to update recording notification: %s", e)
            return False  # Stop timer on error

        return True  # Continue timer

    def _stop_recording_notification(self):
        """Stop and close the recording notification."""
        if self._recording_timer_id is not None:
            GLib.source_remove(self._recording_timer_id)
            self._recording_timer_id = None

        if self._recording_notification is not None:
            try:
                self._recording_notification.close()
            except Exception:
                pass  # Ignore close errors
            self._recording_notification = None

        self._level_callback = None
        self._level_history = []

    def notify_busy(self):
        """Notify that the system is busy processing and user should wait."""
        self._notify(
            "Please Wait",
            "Still processing previous recording...",
            "audio-x-generic",
            urgency="low",
        )
        logger.debug("Notified: busy, please wait")

    def notify_recording_stopped(self):
        """Notify that recording has stopped and transcription is starting."""
        self._stop_recording_notification()
        self._play_sound("stop")
        self._start_processing_notification()
        logger.debug("Notified: recording stopped")

    def _start_processing_notification(self):
        """Start a persistent notification that updates during processing."""
        if not self.config.notifications_enabled:
            return

        self._processing_start_time = time.time()

        def _create():
            if not self._initialized:
                self.initialize()

            # Create notification that we'll update
            self._processing_notification = Notify.Notification.new(
                "Processing",
                "Transcribing audio...",
                "audio-x-generic"
            )
            self._processing_notification.set_urgency(Notify.Urgency.LOW)
            try:
                self._processing_notification.show()
            except Exception as e:
                logger.warning("Failed to show processing notification: %s", e)

            # Start timer to update notification every 2 seconds
            self._processing_timer_id = GLib.timeout_add(2000, self._update_processing_notification)
            return False

        GLib.idle_add(_create)

    def _update_processing_notification(self) -> bool:
        """Update the processing notification with elapsed time. Returns True to continue timer."""
        if self._processing_notification is None or self._processing_start_time is None:
            return False  # Stop timer

        elapsed = time.time() - self._processing_start_time
        mins = int(elapsed // 60)
        secs = int(elapsed % 60)

        if mins > 0:
            time_str = f"{mins}m {secs}s"
        else:
            time_str = f"{secs}s"

        try:
            self._processing_notification.update(
                "Processing",
                f"Transcribing audio... ({time_str})",
                "audio-x-generic"
            )
            self._processing_notification.show()
        except Exception as e:
            logger.debug("Failed to update processing notification: %s", e)
            return False  # Stop timer on error

        return True  # Continue timer

    def _stop_processing_notification(self):
        """Stop and close the processing notification."""
        if self._processing_timer_id is not None:
            GLib.source_remove(self._processing_timer_id)
            self._processing_timer_id = None

        if self._processing_notification is not None:
            try:
                self._processing_notification.close()
            except Exception:
                pass  # Ignore close errors
            self._processing_notification = None

        self._processing_start_time = None

    def notify_transcription_complete(self, text: str, duration: float):
        """Notify that transcription is complete."""
        self._stop_processing_notification()
        # Truncate preview if too long
        preview = text[:100] + "..." if len(text) > 100 else text
        self._notify(
            "Done",
            f"Copied ({duration:.1f}s)\n{preview}",
            "dialog-information",
        )
        self._play_sound("complete")
        logger.debug("Notified: transcription complete")

    def notify_no_speech(self):
        """Notify that no speech was detected."""
        self._stop_processing_notification()
        self._notify(
            "No Speech",
            "No speech detected in recording",
            "dialog-warning",
            urgency="low",
        )
        logger.debug("Notified: no speech detected")

    def notify_error(self, error: str):
        """Notify about an error."""
        self._stop_processing_notification()
        self._notify(
            "Error",
            error,
            "dialog-error",
            urgency="critical",
        )
        self._play_sound("error")
        logger.debug("Notified: error - %s", error)

    def shutdown(self):
        """Clean up notification resources."""
        if self._initialized:
            Notify.uninit()
            self._initialized = False
