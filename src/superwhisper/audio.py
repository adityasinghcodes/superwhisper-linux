"""Audio recording module using sounddevice."""

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


def list_audio_devices_with_retry(
    max_attempts: int = 5,
    initial_delay: float = 1.0,
    max_delay: float = 5.0,
) -> list[dict]:
    """List audio devices with retry logic for system startup.

    On login, audio subsystem (PulseAudio/PipeWire) may not be ready yet.
    This function retries with exponential backoff until devices are found
    or max attempts are exhausted.

    Args:
        max_attempts: Maximum number of attempts to find devices
        initial_delay: Initial delay between attempts in seconds
        max_delay: Maximum delay between attempts in seconds

    Returns:
        List of audio device dictionaries
    """
    delay = initial_delay

    for attempt in range(1, max_attempts + 1):
        devices = list_audio_devices()

        if devices:
            if attempt > 1:
                logger.info("Found %d microphone(s) on attempt %d", len(devices), attempt)
            return devices

        if attempt < max_attempts:
            logger.info(
                "No microphones found (attempt %d/%d), audio system may still be initializing. "
                "Retrying in %.1fs...",
                attempt, max_attempts, delay
            )
            time.sleep(delay)
            # Exponential backoff with cap
            delay = min(delay * 1.5, max_delay)

    logger.warning(
        "No microphones found after %d attempts. "
        "Audio system may not be ready or no microphones are connected.",
        max_attempts
    )
    return []
