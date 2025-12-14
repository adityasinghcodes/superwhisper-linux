"""Configuration management."""

import json
from dataclasses import dataclass, asdict, field
from pathlib import Path

from .logging_config import get_logger

logger = get_logger("config")


@dataclass
class Config:
    """Application configuration."""

    hotkey: str = "CTRL+TAB"
    model: str = "tiny"
    language: str = "en"
    device: str = "auto"  # auto, cuda, or cpu
    compute_type: str = "auto"  # auto, float16, int8, float32
    microphone: str | None = None  # Device name (not index - indices change!)

    @classmethod
    def get_config_dir(cls) -> Path:
        """Get the configuration directory path."""
        config_dir = Path.home() / ".config" / "superwhisper-linux"
        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir

    @classmethod
    def get_config_path(cls) -> Path:
        """Get the configuration file path."""
        return cls.get_config_dir() / "config.json"

    @classmethod
    def load(cls) -> "Config":
        """Load configuration from file, or return defaults."""
        config_path = cls.get_config_path()
        if config_path.exists():
            try:
                with open(config_path) as f:
                    data = json.load(f)
                logger.debug("Loaded config from %s", config_path)
                return cls(**data)
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning("Error loading config: %s, using defaults", e)
        return cls()

    def save(self):
        """Save configuration to file."""
        config_path = self.get_config_path()
        with open(config_path, "w") as f:
            json.dump(asdict(self), f, indent=2)
        logger.debug("Saved config to %s", config_path)
