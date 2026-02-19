"""Attention drift - random mouse movements to simulate distraction."""

from dataclasses import dataclass
from enum import Enum
from typing import Optional

import numpy as np

from utils import create_rng, clamp


class DriftTarget(Enum):
    """Targets for attention drift."""

    MINIMAP = "minimap"
    CHAT = "chat"
    SKILLS_TAB = "skills_tab"
    RANDOM = "random"


@dataclass
class DriftConfig:
    """Configuration for attention drift."""

    drift_chance: float = 0.03  # 3% per action
    drift_targets: list[dict] = None  # [{"name": "minimap", "weight": 3}, ...]

    def __post_init__(self):
        if self.drift_targets is None:
            self.drift_targets = [
                {"name": "minimap", "weight": 3},
                {"name": "chat", "weight": 2},
                {"name": "skills_tab", "weight": 1},
                {"name": "random", "weight": 1},
            ]


@dataclass
class DriftRegion:
    """Screen region for drift target."""

    x: int
    y: int
    width: int
    height: int


class AttentionDrift:
    """Simulate random attention drift movements."""

    # Default regions (relative to window, assuming 765x503 fixed size)
    # These are approximate and should be adjusted for actual client
    DEFAULT_REGIONS = {
        "minimap": DriftRegion(x=550, y=5, width=150, height=150),
        "chat": DriftRegion(x=5, y=340, width=500, height=130),
        "skills_tab": DriftRegion(x=550, y=210, width=200, height=260),
    }

    def __init__(
        self,
        config: Optional[DriftConfig] = None,
        window_width: int = 765,
        window_height: int = 503,
    ):
        """Initialize attention drift.

        Args:
            config: Drift configuration
            window_width: Game window width
            window_height: Game window height
        """
        self.config = config or DriftConfig()
        self._rng = create_rng()
        self._window_width = window_width
        self._window_height = window_height
        self._regions = self.DEFAULT_REGIONS.copy()
        self._drift_count = 0

    def set_window_size(self, width: int, height: int) -> None:
        """Update window size for region calculations.

        Args:
            width: Window width
            height: Window height
        """
        self._window_width = width
        self._window_height = height

    def set_region(self, name: str, region: DriftRegion) -> None:
        """Set or update a drift region.

        Args:
            name: Region name
            region: Region definition
        """
        self._regions[name] = region

    def should_drift(self, fatigue_level: float = 0.0) -> bool:
        """Check if attention should drift.

        Drift chance increases slightly with fatigue.

        Args:
            fatigue_level: Current fatigue (0-1)

        Returns:
            True if should drift
        """
        # Base chance + fatigue bonus (up to +3% at max fatigue)
        chance = self.config.drift_chance + (fatigue_level * 0.03)

        return self._rng.random() < chance

    def get_drift_target(self) -> tuple[DriftTarget, tuple[int, int]]:
        """Get a random drift target position.

        Returns:
            (DriftTarget, (x, y)) tuple with target type and position
        """
        # Select target based on weights
        targets = self.config.drift_targets
        total_weight = sum(t["weight"] for t in targets)
        roll = self._rng.random() * total_weight

        cumulative = 0
        selected_name = "random"
        for target in targets:
            cumulative += target["weight"]
            if roll <= cumulative:
                selected_name = target["name"]
                break

        # Get position within target region
        try:
            target_type = DriftTarget(selected_name)
        except ValueError:
            target_type = DriftTarget.RANDOM

        position = self._get_position_in_region(selected_name)
        self._drift_count += 1

        return target_type, position

    def _get_position_in_region(self, region_name: str) -> tuple[int, int]:
        """Get random position within a region.

        Args:
            region_name: Name of the region

        Returns:
            (x, y) position
        """
        if region_name == "random" or region_name not in self._regions:
            # Random position anywhere on screen
            x = self._rng.integers(50, self._window_width - 50)
            y = self._rng.integers(50, self._window_height - 50)
            return (x, y)

        region = self._regions[region_name]

        # Random position within region using Gaussian distribution
        # Clustered toward center
        center_x = region.x + region.width // 2
        center_y = region.y + region.height // 2
        sigma_x = region.width / 4
        sigma_y = region.height / 4

        x = self._rng.normal(center_x, sigma_x)
        y = self._rng.normal(center_y, sigma_y)

        # Clamp to region
        x = clamp(x, region.x, region.x + region.width)
        y = clamp(y, region.y, region.y + region.height)

        return (int(x), int(y))

    def get_drift_duration(self) -> float:
        """Get how long to stay at drift position.

        Returns:
            Duration in seconds
        """
        # 0.3 - 2 seconds
        return self._rng.uniform(0.3, 2.0)

    def get_drift_count(self) -> int:
        """Get number of drifts performed.

        Returns:
            Drift count
        """
        return self._drift_count

    def reset_count(self) -> None:
        """Reset drift count."""
        self._drift_count = 0

    def get_idle_movement(self) -> tuple[int, int]:
        """Get small idle movement offset.

        Simulates minor hand tremor/adjustment while waiting.

        Returns:
            (dx, dy) offset in pixels
        """
        # Small movement, 1-5 pixels
        dx = self._rng.integers(-5, 6)
        dy = self._rng.integers(-5, 6)
        return (dx, dy)

    def should_idle_move(self) -> bool:
        """Check if should make small idle movement.

        Returns:
            True if should move slightly
        """
        # 10% chance during idle
        return self._rng.random() < 0.10
