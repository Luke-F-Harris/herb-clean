"""Configuration manager with YAML loading and validation."""

import os
from pathlib import Path
from typing import Any

import yaml


class ConfigManager:
    """Load and validate bot configuration from YAML files."""

    DEFAULT_CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "default_config.yaml"

    def __init__(self, config_path: str | Path | None = None):
        """Initialize config manager.

        Args:
            config_path: Path to config file. Uses default if None.
        """
        self.config_path = Path(config_path) if config_path else self.DEFAULT_CONFIG_PATH
        self._config: dict[str, Any] = {}
        self._load_config()
        self._validate_config()

    def _load_config(self) -> None:
        """Load configuration from YAML file."""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self.config_path}")

        with open(self.config_path, "r") as f:
            self._config = yaml.safe_load(f)

    def _validate_config(self) -> None:
        """Validate required configuration sections exist."""
        required_sections = [
            "window",
            "timing",
            "mouse",
            "click",
            "breaks",
            "fatigue",
            "attention",
            "vision",
            "safety",
        ]

        for section in required_sections:
            if section not in self._config:
                raise ValueError(f"Missing required config section: {section}")

        # Validate specific values
        timing = self._config["timing"]
        if timing["click_herb_min"] >= timing["click_herb_max"]:
            raise ValueError("click_herb_min must be less than click_herb_max")

        safety = self._config["safety"]
        if safety["max_session_hours"] <= 0:
            raise ValueError("max_session_hours must be positive")

    def get(self, key: str, default: Any = None) -> Any:
        """Get a config value using dot notation.

        Args:
            key: Dot-separated key path (e.g., 'timing.click_herb_mean')
            default: Default value if key not found

        Returns:
            Config value or default
        """
        keys = key.split(".")
        value = self._config

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    def get_section(self, section: str) -> dict[str, Any]:
        """Get an entire config section.

        Args:
            section: Section name

        Returns:
            Section dict or empty dict if not found
        """
        return self._config.get(section, {})

    @property
    def timing(self) -> dict[str, Any]:
        """Get timing configuration."""
        return self._config.get("timing", {})

    @property
    def mouse(self) -> dict[str, Any]:
        """Get mouse configuration."""
        return self._config.get("mouse", {})

    @property
    def click(self) -> dict[str, Any]:
        """Get click configuration."""
        return self._config.get("click", {})

    @property
    def breaks(self) -> dict[str, Any]:
        """Get break configuration."""
        return self._config.get("breaks", {})

    @property
    def fatigue(self) -> dict[str, Any]:
        """Get fatigue configuration."""
        return self._config.get("fatigue", {})

    @property
    def attention(self) -> dict[str, Any]:
        """Get attention drift configuration."""
        return self._config.get("attention", {})

    @property
    def vision(self) -> dict[str, Any]:
        """Get vision/template matching configuration."""
        return self._config.get("vision", {})

    @property
    def safety(self) -> dict[str, Any]:
        """Get safety configuration."""
        return self._config.get("safety", {})

    @property
    def window(self) -> dict[str, Any]:
        """Get window configuration."""
        return self._config.get("window", {})

    @property
    def templates_dir(self) -> Path:
        """Get templates directory path."""
        return self.config_path.parent / "templates"
