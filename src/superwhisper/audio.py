"""Audio recording module using sounddevice."""

import subprocess
import time
import numpy as np
import sounddevice as sd
from threading import Lock

from .logging_config import get_logger

logger = get_logger("audio")


def resample(audio: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
    """Resample audio to target sample rate using linear interpolation."""
    if orig_sr == target_sr:
        return audio

    duration = len(audio) / orig_sr
    target_length = int(duration * target_sr)

    x_old = np.linspace(0, duration, len(audio))
    x_new = np.linspace(0, duration, target_length)
    return np.interp(x_new, x_old, audio).astype(np.float32)


class AudioRecorder:
    """Records audio from the microphone."""

    TARGET_SAMPLE_RATE = 16000  # Whisper expects 16kHz
    CHANNELS = 1  # Mono audio

    def __init__(self, device: int | str | None = None):
        self._recording = False
        self._audio_data: list[np.ndarray] = []
        self._lock = Lock()
        self._stream: sd.InputStream | None = None
        self.device = device
        self._device_sample_rate: int = self.TARGET_SAMPLE_RATE

    def set_device(self, device: int | str | None):
        """Set the recording device."""
        self.device = device

        if device is not None:
            try:
                dev_info = sd.query_devices(device)
                self._device_sample_rate = int(dev_info["default_samplerate"])
                logger.info("Audio device: %s (%dHz)", dev_info["name"], self._device_sample_rate)
            except Exception as e:
                logger.warning("Could not query device %s: %s", device, e)
                self._device_sample_rate = self.TARGET_SAMPLE_RATE
        else:
            self._device_sample_rate = self.TARGET_SAMPLE_RATE
            logger.info("Audio device: system default")

    def _audio_callback(self, indata: np.ndarray, frames: int, time, status):
        """Called by sounddevice for each audio chunk."""
        if status:
            logger.warning("Audio callback status: %s", status)
        with self._lock:
            if self._recording:
                self._audio_data.append(indata.copy())

    def start(self):
        """Start recording audio."""
        if self.device is not None and self._device_sample_rate == self.TARGET_SAMPLE_RATE:
            try:
                dev_info = sd.query_devices(self.device)
                self._device_sample_rate = int(dev_info["default_samplerate"])
            except Exception:
                pass

        with self._lock:
            self._audio_data = []
            self._recording = True

        self._stream = sd.InputStream(
            samplerate=self._device_sample_rate,
            channels=self.CHANNELS,
            dtype=np.float32,
            device=self.device,
            callback=self._audio_callback,
        )
        self._stream.start()
        logger.debug("Recording started at %dHz", self._device_sample_rate)

    def stop(self) -> np.ndarray:
        """Stop recording and return the audio data."""
        with self._lock:
            self._recording = False

        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None

        with self._lock:
            if not self._audio_data:
                return np.array([], dtype=np.float32)

            audio = np.concatenate(self._audio_data, axis=0)
            audio = audio.flatten()
            self._audio_data = []  # Clear for GC

            if len(audio) > 0:
                max_amp = np.max(np.abs(audio))
                logger.debug("Audio: %d samples, max amplitude: %.4f", len(audio), max_amp)
                if max_amp < 0.01:
                    logger.warning("Audio level very low - check microphone")

            if self._device_sample_rate != self.TARGET_SAMPLE_RATE:
                logger.debug("Resampling %dHz -> %dHz", self._device_sample_rate, self.TARGET_SAMPLE_RATE)
                audio = resample(audio, self._device_sample_rate, self.TARGET_SAMPLE_RATE)

            return audio

    @property
    def is_recording(self) -> bool:
        """Check if currently recording."""
        with self._lock:
            return self._recording


def list_audio_devices() -> list[dict]:
    """List available audio input devices (filtered to real microphones)."""
    devices = sd.query_devices()
    inputs = []

    # Keywords that suggest a real microphone
    mic_positive = [
        "mic", "input", "line", "scarlett", "focusrite", "rode", "blue",
        "shure", "at2020", "yeti", "snowball", "usb audio", "headset",
    ]

    # Keywords that indicate NOT a microphone
    mic_negative = [
        "monitor", "output", "hdmi", "displayport", "speaker", "headphone",
        "spdif", "front", "surround", "iec958", "dmix", "split", "rear",
    ]

    # Virtual device names to exclude entirely
    virtual_devices = ["sysdefault", "pipewire", "default", "pulse", "null"]

    for i, dev in enumerate(devices):
        if dev["max_input_channels"] <= 0:
            continue

        name = dev["name"]
        name_lower = name.lower()

        # Skip virtual devices
        if name_lower in virtual_devices:
            continue

        # Skip negative keywords
        if any(kw in name_lower for kw in mic_negative):
            continue

        # Skip high channel count (virtual aggregators)
        if dev["max_input_channels"] > 8:
            continue

        # Include if: hardware device OR looks like a microphone
        is_hw_device = "(hw:" in name
        is_likely_mic = any(kw in name_lower for kw in mic_positive)

        if is_hw_device or is_likely_mic:
            inputs.append({
                "index": i,
                "name": name,
                "channels": dev["max_input_channels"],
                "sample_rate": int(dev["default_samplerate"]),
            })

    # Sort: hardware devices first
    inputs.sort(key=lambda d: (0 if "(hw:" in d["name"] else 1, d["name"]))

    logger.debug("Found %d microphone devices", len(inputs))
    return inputs


def get_default_input_device() -> int | None:
    """Get the default input device index."""
    try:
        return sd.default.device[0]
    except Exception:
        return None


def wait_for_audio_service(timeout: float = 10.0) -> bool:
    """Wait for the audio service (PipeWire or PulseAudio) to be ready.

    On login, the audio daemon may not be fully initialized yet.
    This function waits until the service reports as active.

    Args:
        timeout: Maximum time to wait in seconds

    Returns:
        True if audio service is ready, False if timeout reached
    """
    # Services to check (in order of preference)
    services = ["pipewire.service", "pipewire-pulse.service", "pulseaudio.service"]

    start_time = time.time()
    check_interval = 0.5

    while (time.time() - start_time) < timeout:
        for service in services:
            try:
                result = subprocess.run(
                    ["systemctl", "--user", "is-active", service],
                    capture_output=True,
                    text=True,
                    timeout=2,
                )
                if result.returncode == 0 and result.stdout.strip() == "active":
                    logger.debug("Audio service ready: %s", service)
                    return True
            except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
                continue

        time.sleep(check_interval)

    logger.warning("Audio service not ready after %.1fs", timeout)
    return False


def wait_for_microphone(
    target_name: str | None = None,
    timeout: float = 15.0,
    stabilize_time: float = 1.0,
) -> list[dict]:
    """Wait for microphones to be available, optionally waiting for a specific one.

    On login, hardware microphones may take longer to enumerate than virtual
    devices. This function waits until either:
    - The target microphone appears (if specified)
    - The device list stabilizes (no new devices for stabilize_time)

    Args:
        target_name: Optional microphone name to wait for specifically
        timeout: Maximum time to wait in seconds
        stabilize_time: Time to wait for device list to stabilize

    Returns:
        List of audio device dictionaries
    """
    # First, wait for audio service to be ready
    wait_for_audio_service(timeout=min(timeout, 10.0))

    start_time = time.time()
    last_device_count = -1
    stable_since: float | None = None
    check_interval = 0.5

    while (time.time() - start_time) < timeout:
        devices = list_audio_devices()
        current_count = len(devices)

        # If we're looking for a specific microphone, check if it's present
        if target_name:
            for dev in devices:
                if dev["name"] == target_name:
                    elapsed = time.time() - start_time
                    if elapsed > 0.1:  # Only log if we actually waited
                        logger.info(
                            "Found target microphone '%s' after %.1fs",
                            target_name, elapsed
                        )
                    return devices

        # Track when device count stabilizes
        if current_count != last_device_count:
            last_device_count = current_count
            stable_since = time.time()
            logger.debug("Device count changed to %d", current_count)
        elif stable_since and (time.time() - stable_since) >= stabilize_time:
            # Device list has been stable long enough
            if current_count > 0:
                elapsed = time.time() - start_time
                if elapsed > stabilize_time + 0.1:  # Only log if we actually waited
                    logger.info(
                        "Device list stabilized with %d microphone(s) after %.1fs",
                        current_count, elapsed
                    )
                return devices

        time.sleep(check_interval)

    # Timeout reached, return whatever we have
    devices = list_audio_devices()
    if target_name and devices:
        logger.warning(
            "Target microphone '%s' not found after %.1fs, found %d other device(s)",
            target_name, timeout, len(devices)
        )
    elif not devices:
        logger.warning("No microphones found after %.1fs", timeout)

    return devices
