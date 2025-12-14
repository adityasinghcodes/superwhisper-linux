"""Whisper transcription module using faster-whisper."""

import numpy as np
from faster_whisper import WhisperModel
from huggingface_hub import snapshot_download, try_to_load_from_cache

from .logging_config import get_logger

logger = get_logger("transcribe")

MODEL_INFO = {
    "tiny": "~75MB",
    "base": "~145MB",
    "small": "~465MB",
    "medium": "~1.5GB",
    "large-v2": "~3GB",
    "large-v3": "~3GB",
}


def check_cuda_available() -> bool:
    """Check if CUDA is properly available."""
    try:
        import ctranslate2
        cuda_types = ctranslate2.get_supported_compute_types("cuda")
        return len(cuda_types) > 0
    except Exception:
        return False


def ensure_model_downloaded(model_size: str) -> None:
    """Download model with progress bar if not cached."""
    repo_id = f"Systran/faster-whisper-{model_size}"

    # Check if model is already cached by looking for model.bin
    cached = try_to_load_from_cache(repo_id, "model.bin")
    if cached is not None:
        return  # Already downloaded

    size_info = MODEL_INFO.get(model_size, "")
    logger.info("Downloading model %s %s...", model_size, size_info)
    print(f"Downloading Whisper model: {model_size} {size_info}")
    print("This only happens once...")

    # Download with default progress bar (tqdm)
    snapshot_download(repo_id)
    print("Download complete!")


class Transcriber:
    """Transcribes audio using Whisper."""

    def __init__(
        self,
        model_size: str = "large-v3",
        device: str = "auto",
        compute_type: str = "auto",
    ):
        self.model_size = model_size
        self._requested_device = device
        self._requested_compute_type = compute_type
        self._model: WhisperModel | None = None
        self._actual_device: str = "cpu"

    def load_model(self):
        """Load the Whisper model with automatic CUDA fallback."""
        if self._model is not None:
            return

        # Determine device
        if self._requested_device == "auto":
            device = "cuda" if check_cuda_available() else "cpu"
        else:
            device = self._requested_device

        # Determine compute type
        if self._requested_compute_type == "auto":
            compute_type = "float16" if device == "cuda" else "int8"
        else:
            compute_type = self._requested_compute_type

        # Download model if not cached (shows progress bar)
        ensure_model_downloaded(self.model_size)

        size_info = MODEL_INFO.get(self.model_size, "unknown size")
        logger.info("Loading Whisper model: %s (%s)", self.model_size, size_info)
        logger.info("Device: %s, Compute: %s", device, compute_type)

        # Try loading with preferred device, fallback to CPU
        try:
            self._model = WhisperModel(
                self.model_size,
                device=device,
                compute_type=compute_type,
            )
            self._actual_device = device
        except Exception as e:
            if device == "cuda":
                logger.warning("CUDA failed: %s", e)
                logger.info("Falling back to CPU...")
                try:
                    self._model = WhisperModel(
                        self.model_size,
                        device="cpu",
                        compute_type="int8",
                    )
                    self._actual_device = "cpu"
                except Exception as e2:
                    logger.error("CPU also failed: %s", e2)
                    raise
            else:
                raise

        logger.info("Model loaded on %s", self._actual_device.upper())

    def transcribe(self, audio: np.ndarray, language: str = "en") -> str:
        """Transcribe audio to text."""
        self.load_model()

        if len(audio) == 0:
            return ""

        duration = len(audio) / 16000
        logger.info("Transcribing %.1fs of audio...", duration)

        try:
            segments, info = self._model.transcribe(
                audio,
                language=language,
                beam_size=5,
                vad_filter=True,
            )

            text_parts = [segment.text.strip() for segment in segments]
            result = " ".join(text_parts)
            logger.info("Transcription complete: %d chars", len(result))
            logger.debug("Result: %s", result[:100] if result else "(empty)")
            return result
        except Exception as e:
            logger.error("Transcription error: %s", e)
            return ""
