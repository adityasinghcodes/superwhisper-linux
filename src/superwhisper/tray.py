"""System tray icon using AppIndicator."""

import gi
import time
from pathlib import Path

gi.require_version("Gtk", "3.0")
gi.require_version("AppIndicator3", "0.1")

from gi.repository import Gtk, AppIndicator3, GLib
from typing import Callable

from .audio import list_audio_devices, get_default_input_device
from .logging_config import get_logger

logger = get_logger("tray")

# Path to custom icons
ASSETS_DIR = Path(__file__).parent.parent.parent / "assets"


class TrayIcon:
    """System tray icon with status indicator."""

    def __init__(
        self,
        on_quit: Callable[[], None] | None = None,
        on_device_change: Callable[[int | None, str | None], None] | None = None,
        saved_device_name: str | None = None,
        model_info: str = "",
        show_timer: bool = True,
    ):
        self.on_quit = on_quit
        self.on_device_change = on_device_change
        self._saved_device_name = saved_device_name
        self._model_info = model_info
        self._show_timer = show_timer
        self._indicator: AppIndicator3.Indicator | None = None
        self._recording = False
        self._transcribing = False
        self._current_device: int | None = None
        self._device_menu_items: dict[int, Gtk.RadioMenuItem] = {}
        self._recording_start_time: float | None = None
        self._timer_source_id: int | None = None
        self._transcribing_start_time: float | None = None
        self._transcribing_timer_id: int | None = None
        self._queue_size: int = 0

    def _create_menu(self) -> Gtk.Menu:
        """Create the tray icon menu."""
        menu = Gtk.Menu()

        # Status item
        self._status_item = Gtk.MenuItem(label="Idle")
        self._status_item.set_sensitive(False)
        menu.append(self._status_item)

        # Model/device info item
        if self._model_info:
            self._model_item = Gtk.MenuItem(label=f"Model: {self._model_info}")
            self._model_item.set_sensitive(False)
            menu.append(self._model_item)

        # Queue status item (hidden when empty)
        self._queue_item = Gtk.MenuItem(label="")
        self._queue_item.set_sensitive(False)
        self._queue_item.set_no_show_all(True)
        self._queue_item.hide()
        menu.append(self._queue_item)

        menu.append(Gtk.SeparatorMenuItem())

        # Microphone submenu
        mic_item = Gtk.MenuItem(label="Microphone")
        mic_submenu = Gtk.Menu()
        mic_item.set_submenu(mic_submenu)

        devices = list_audio_devices()
        default_device = get_default_input_device()

        if not devices:
            no_dev = Gtk.MenuItem(label="No microphones found")
            no_dev.set_sensitive(False)
            mic_submenu.append(no_dev)
        else:
            group = None
            for dev in devices:
                # Determine if this device should be selected
                should_select = False
                if self._saved_device_name and dev["name"] == self._saved_device_name:
                    should_select = True
                elif not self._saved_device_name and dev["index"] == default_device:
                    should_select = True

                # Build label with checkmark for selected device
                label = f"{'✓ ' if should_select else '   '}{dev['name']}"
                if dev["index"] == default_device:
                    label += " [default]"

                item = Gtk.RadioMenuItem(label=label, group=group)
                if group is None:
                    group = item

                if should_select:
                    item.set_active(True)
                    self._current_device = dev["index"]

                item.connect("toggled", self._on_device_toggled, dev["index"], dev["name"])
                self._device_menu_items[dev["index"]] = item
                mic_submenu.append(item)

        menu.append(mic_item)
        menu.append(Gtk.SeparatorMenuItem())

        # Quit item
        quit_item = Gtk.MenuItem(label="Quit")
        quit_item.connect("activate", self._on_quit_clicked)
        menu.append(quit_item)

        menu.show_all()
        return menu

    def _on_device_toggled(self, widget: Gtk.RadioMenuItem, device_index: int, device_name: str):
        """Handle microphone selection change."""
        if widget.get_active():
            self._current_device = device_index
            self._current_device_name = device_name
            logger.info("Microphone selected: %s", device_name)

            # Update checkmarks in menu labels
            self._update_device_labels()

            if self.on_device_change:
                self.on_device_change(device_index, device_name)

    def _update_device_labels(self):
        """Update checkmarks in device menu labels."""
        for dev_index, item in self._device_menu_items.items():
            label = item.get_label()
            # Remove existing checkmark
            if label.startswith("✓ "):
                label = "   " + label[2:]
            elif label.startswith("   "):
                pass
            else:
                label = "   " + label

            # Add checkmark if this is the selected device
            if dev_index == self._current_device:
                label = "✓ " + label[3:]

            item.set_label(label)

    def _on_quit_clicked(self, widget):
        """Handle quit menu click."""
        logger.info("Quit requested from tray menu")
        if self.on_quit:
            self.on_quit()
        Gtk.main_quit()

    def set_recording(self, recording: bool):
        """Update the tray icon to show recording state."""
        self._recording = recording

        def update():
            if self._indicator:
                if recording:
                    # Stop any transcribing timer when starting new recording
                    self._stop_transcribing_timer()
                    self._indicator.set_icon_full("superwhisper-recording", "Recording")
                    self._recording_start_time = time.time()
                    self._start_timer()
                else:
                    self._stop_timer()
                    if self._transcribing:
                        self._indicator.set_icon_full("superwhisper-transcribing", "Transcribing")
                        self._start_transcribing_timer()
                    else:
                        self._indicator.set_icon_full("superwhisper-idle", "Idle")
                        self._status_item.set_label("Idle")
            return False

        GLib.idle_add(update)

    def set_transcribing(self, transcribing: bool):
        """Update the tray icon to show transcription in progress."""
        self._transcribing = transcribing

        def update():
            if self._indicator and not self._recording:
                if transcribing:
                    self._indicator.set_icon_full("superwhisper-transcribing", "Transcribing")
                    self._start_transcribing_timer()
                else:
                    self._stop_transcribing_timer()
                    self._indicator.set_icon_full("superwhisper-idle", "Idle")
                    self._status_item.set_label("Idle")
            return False

        GLib.idle_add(update)

    def set_queue_size(self, size: int):
        """Update queue status display."""
        self._queue_size = size

        def update():
            if size > 0:
                self._queue_item.set_label(f"Queue: {size} pending")
                self._queue_item.show()
            else:
                self._queue_item.hide()
            return False

        GLib.idle_add(update)

    def _start_timer(self):
        """Start the recording timer update."""
        if not self._show_timer:
            self._status_item.set_label("Recording...")
            return

        def update_timer():
            if self._recording and self._recording_start_time:
                elapsed = time.time() - self._recording_start_time
                mins = int(elapsed // 60)
                secs = int(elapsed % 60)
                self._status_item.set_label(f"Recording... {mins}:{secs:02d}")
                return True  # Continue timer
            return False  # Stop timer

        # Immediate first update
        self._status_item.set_label("Recording... 0:00")
        self._timer_source_id = GLib.timeout_add(1000, update_timer)

    def _stop_timer(self):
        """Stop the recording timer."""
        if self._timer_source_id:
            GLib.source_remove(self._timer_source_id)
            self._timer_source_id = None
        self._recording_start_time = None

    def _start_transcribing_timer(self):
        """Start the transcribing timer to show elapsed time."""
        self._transcribing_start_time = time.time()

        def update_timer():
            if self._transcribing and self._transcribing_start_time:
                elapsed = time.time() - self._transcribing_start_time
                mins = int(elapsed // 60)
                secs = int(elapsed % 60)
                if mins > 0:
                    self._status_item.set_label(f"Transcribing... {mins}m {secs}s")
                else:
                    self._status_item.set_label(f"Transcribing... {secs}s")
                return True  # Continue timer
            return False  # Stop timer

        # Immediate first update
        self._status_item.set_label("Transcribing... 0s")
        self._transcribing_timer_id = GLib.timeout_add(1000, update_timer)

    def _stop_transcribing_timer(self):
        """Stop the transcribing timer."""
        if self._transcribing_timer_id:
            GLib.source_remove(self._transcribing_timer_id)
            self._transcribing_timer_id = None
        self._transcribing_start_time = None

    def run(self):
        """Start the tray icon (blocks until quit)."""
        self._indicator = AppIndicator3.Indicator.new(
            "superwhisper",
            "superwhisper-idle",
            AppIndicator3.IndicatorCategory.APPLICATION_STATUS,
        )
        # Set custom icon path
        self._indicator.set_icon_theme_path(str(ASSETS_DIR))
        self._indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
        self._indicator.set_menu(self._create_menu())

        logger.debug("Tray icon started")
        Gtk.main()

    def quit(self):
        """Quit the tray icon."""
        GLib.idle_add(Gtk.main_quit)
