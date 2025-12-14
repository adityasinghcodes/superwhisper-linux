"""Desktop notifications and audio feedback."""

import subprocess
from pathlib import Path

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

    def notify_recording_started(self):
        """Notify that recording has started."""
        self._notify(
            "Recording",
            "Speak now...",
            "audio-input-microphone",
        )
        self._play_sound("start")
        logger.debug("Notified: recording started")

    def notify_recording_stopped(self):
        """Notify that recording has stopped and transcription is starting."""
        self._notify(
            "Processing",
            "Transcribing audio...",
            "audio-x-generic",
        )
        self._play_sound("stop")
        logger.debug("Notified: recording stopped")

    def notify_transcription_complete(self, text: str, duration: float):
        """Notify that transcription is complete."""
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
        self._notify(
            "No Speech",
            "No speech detected in recording",
            "dialog-warning",
            urgency="low",
        )
        logger.debug("Notified: no speech detected")

    def notify_error(self, error: str):
        """Notify about an error."""
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
