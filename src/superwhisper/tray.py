"""System tray icon using AppIndicator."""

import gi
from pathlib import Path

gi.require_version("Gtk", "3.0")
gi.require_version("AppIndicator3", "0.1")

from gi.repository import Gtk, AppIndicator3, GLib
from typing import Callable

from .audio import list_audio_devices, wait_for_microphone, get_default_input_device
from .transcribe import get_available_models
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
        on_model_change: Callable[[str], None] | None = None,
        saved_device_name: str | None = None,
        current_model: str = "tiny",
        device_info: str = "",
        show_timer: bool = True,
    ):
        self.on_quit = on_quit
        self.on_device_change = on_device_change
        self.on_model_change = on_model_change
        self._saved_device_name = saved_device_name
        self._current_model = current_model
        self._device_info = device_info
        self._show_timer = show_timer
        self._indicator: AppIndicator3.Indicator | None = None
        self._recording = False
        self._transcribing = False
        self._current_device: int | None = None
        self._current_device_name: str | None = saved_device_name
        self._device_menu_items: dict[int, Gtk.RadioMenuItem] = {}
        self._model_menu_items: dict[str, Gtk.RadioMenuItem] = {}
        self._recording_start_time: float | None = None
        self._timer_source_id: int | None = None
        self._queue_size: int = 0
        self._mic_submenu: Gtk.Menu | None = None
        self._first_menu_build = True

    def _create_menu(self) -> Gtk.Menu:
        """Create the tray icon menu."""
        menu = Gtk.Menu()

        # Status item
        self._status_item = Gtk.MenuItem(label="Idle")
        self._status_item.set_sensitive(False)
        menu.append(self._status_item)

        # Device info item (shows CPU/CUDA)
        if self._device_info:
            self._device_info_item = Gtk.MenuItem(label=f"Device: {self._device_info}")
            self._device_info_item.set_sensitive(False)
            menu.append(self._device_info_item)

        # Queue status item (hidden when empty)
        self._queue_item = Gtk.MenuItem(label="")
        self._queue_item.set_sensitive(False)
        self._queue_item.set_no_show_all(True)
        self._queue_item.hide()
        menu.append(self._queue_item)

        menu.append(Gtk.SeparatorMenuItem())

        # Model submenu
        model_item = Gtk.MenuItem(label="Model")
        model_submenu = Gtk.Menu()
        model_item.set_submenu(model_submenu)

        models = get_available_models()
        group = None
        for model in models:
            is_selected = model["name"] == self._current_model

            # Build label with checkmark and download status
            label = f"{'✓ ' if is_selected else '   '}{model['name']} ({model['size']})"
            if not model["downloaded"]:
                label += " [not downloaded]"

            item = Gtk.RadioMenuItem(label=label, group=group)
            if group is None:
                group = item

            if is_selected:
                item.set_active(True)

            item.connect("toggled", self._on_model_toggled, model["name"], model["downloaded"])
            self._model_menu_items[model["name"]] = item
            model_submenu.append(item)

        menu.append(model_item)

        # Microphone submenu
        mic_item = Gtk.MenuItem(label="Microphone")
        self._mic_submenu = Gtk.Menu()
        mic_item.set_submenu(self._mic_submenu)

        # Build device list (wait for target mic on first build for autostart scenario)
        self._populate_mic_submenu(wait_for_target=self._first_menu_build)
        self._first_menu_build = False

        menu.append(mic_item)
        menu.append(Gtk.SeparatorMenuItem())

        # Quit item
        quit_item = Gtk.MenuItem(label="Quit")
        quit_item.connect("activate", self._on_quit_clicked)
        menu.append(quit_item)

        menu.show_all()
        return menu

    def _populate_mic_submenu(
        self,
        wait_for_target: bool = False,
        refresh: bool = False,
        timeout: float = 30.0,
    ):
        """Populate the microphone submenu with available devices.

        Args:
            wait_for_target: If True, wait for audio service and target microphone
            refresh: If True, force a PortAudio device list refresh
            timeout: Max time to wait for audio service when wait_for_target is True
        """
        if self._mic_submenu is None:
            return

        # Clear existing items
        for child in self._mic_submenu.get_children():
            self._mic_submenu.remove(child)
        self._device_menu_items.clear()

        # Get devices (wait for target on first build / autostart)
        if wait_for_target:
            target_name = self._current_device_name or self._saved_device_name
            devices = wait_for_microphone(target_name=target_name, refresh=refresh, timeout=timeout)
        else:
            devices = list_audio_devices(refresh=refresh)

        default_device = get_default_input_device()

        if not devices:
            no_dev = Gtk.MenuItem(label="No microphones found")
            no_dev.set_sensitive(False)
            self._mic_submenu.append(no_dev)
        else:
            group = None
            for dev in devices:
                # Determine if this device should be selected
                should_select = False
                # Use current device name if set, otherwise fall back to saved name
                target_name = self._current_device_name or self._saved_device_name
                if target_name and dev["name"] == target_name:
                    should_select = True
                elif not target_name and dev["index"] == default_device:
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
                self._mic_submenu.append(item)

        # Add separator and refresh button
        self._mic_submenu.append(Gtk.SeparatorMenuItem())
        refresh_item = Gtk.MenuItem(label="↻ Refresh Devices")
        refresh_item.connect("activate", self._on_refresh_devices)
        self._mic_submenu.append(refresh_item)

        self._mic_submenu.show_all()

    def _on_refresh_devices(self, widget):
        """Handle refresh devices menu click."""
        logger.info("Refreshing audio devices...")
        self._populate_mic_submenu(wait_for_target=True, refresh=True, timeout=5.0)
        logger.info("Audio devices refreshed")

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

    def _on_model_toggled(self, widget: Gtk.RadioMenuItem, model_name: str, is_downloaded: bool):
        """Handle model selection change."""
        if widget.get_active():
            self._current_model = model_name
            logger.info("Model selected: %s (downloaded: %s)", model_name, is_downloaded)

            # Update checkmarks in menu labels
            self._update_model_labels()

            if self.on_model_change:
                self.on_model_change(model_name)

    def _update_model_labels(self):
        """Update checkmarks in model menu labels."""
        # Refresh download status
        models = get_available_models()
        model_download_status = {m["name"]: m["downloaded"] for m in models}

        for model_name, item in self._model_menu_items.items():
            # Find model info
            model_info = next((m for m in models if m["name"] == model_name), None)
            if not model_info:
                continue

            is_selected = model_name == self._current_model
            is_downloaded = model_download_status.get(model_name, False)

            # Rebuild label
            label = f"{'✓ ' if is_selected else '   '}{model_name} ({model_info['size']})"
            if not is_downloaded:
                label += " [not downloaded]"

            item.set_label(label)

    def refresh_model_menu(self):
        """Refresh the model menu to update download status."""
        def update():
            self._update_model_labels()
            return False
        GLib.idle_add(update)

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
                    self._indicator.set_icon_full("superwhisper-recording", "Recording")
                else:
                    if self._transcribing:
                        self._indicator.set_icon_full("superwhisper-transcribing", "Transcribing")
                    else:
                        self._indicator.set_icon_full("superwhisper-idle", "Idle")
            return False

        GLib.idle_add(update)

    def set_transcribing(self, transcribing: bool):
        """Update the tray icon to show transcription in progress."""
        self._transcribing = transcribing

        def update():
            if self._indicator and not self._recording:
                if transcribing:
                    self._indicator.set_icon_full("superwhisper-transcribing", "Transcribing")
                else:
                    self._indicator.set_icon_full("superwhisper-idle", "Idle")
            return False

        GLib.idle_add(update)

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
