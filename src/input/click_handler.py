"""Click position and timing randomization."""

from dataclasses import dataclass
from typing import Optional

import numpy as np

from ..utils import create_rng, clamp


@dataclass
class ClickConfig:
    """Configuration for click handling."""

    position_sigma_ratio: float = 6  # sigma = width / this value
    duration_mean: float = 100  # ms
    duration_min: float = 50
    duration_max: float = 200


@dataclass
class ClickTarget:
    """Target area for clicking."""

    center_x: int
    center_y: int
    width: int
    height: int


@dataclass
class ClickResult:
    """Result of click position/timing calculation."""

    x: int
    y: int
    duration: float  # seconds


class ClickHandler:
    """Handle click position and timing randomization."""

    def __init__(self, config: Optional[ClickConfig] = None):
        """Initialize click handler.

        Args:
            config: Click configuration
        """
        self.config = config or ClickConfig()
        self._rng = create_rng()

    def calculate_click(self, target: ClickTarget) -> ClickResult:
        """Calculate randomized click position and duration.

        Position uses Gaussian distribution centered on target.
        Duration uses Gamma distribution for natural variation.

        Args:
            target: Target area for clicking

        Returns:
            ClickResult with position and duration
        """
        # Calculate position using Gaussian distribution
        x, y = self._randomize_position(target)

        # Calculate duration using Gamma distribution
        duration = self._randomize_duration()

        return ClickResult(x=x, y=y, duration=duration)

    def _randomize_position(self, target: ClickTarget) -> tuple[int, int]:
        """Generate randomized click position within target.

        Uses Gaussian distribution clustered toward center.
        """
        # Calculate sigma based on target size
        sigma_x = target.width / self.config.position_sigma_ratio
        sigma_y = target.height / self.config.position_sigma_ratio

        # Generate position with Gaussian distribution
        x = self._rng.normal(target.center_x, sigma_x)
        y = self._rng.normal(target.center_y, sigma_y)

        # Clamp to target bounds
        half_width = target.width / 2
        half_height = target.height / 2

        x = clamp(x, target.center_x - half_width, target.center_x + half_width)
        y = clamp(y, target.center_y - half_height, target.center_y + half_height)

        return int(round(x)), int(round(y))

    def _randomize_duration(self) -> float:
        """Generate randomized click duration using Gamma distribution.

        Returns:
            Duration in seconds
        """
        # Gamma distribution parameters
        # Shape (k) and scale (theta) chosen to give right-skewed distribution
        shape = 2.0
        scale = self.config.duration_mean / (shape * 2)  # Adjust for mean

        duration_ms = self._rng.gamma(shape, scale) * 2

        # Clamp to min/max
        duration_ms = max(self.config.duration_min, min(self.config.duration_max, duration_ms))

        return duration_ms / 1000.0  # Convert to seconds

    def calculate_double_click_delay(self) -> float:
        """Calculate delay between double-click presses.

        Returns:
            Delay in seconds
        """
        # Human double-click typically 100-300ms apart
        delay_ms = self._rng.uniform(100, 250)
        return delay_ms / 1000.0

    def should_misclick(self, misclick_rate: float) -> bool:
        """Determine if this should be a misclick.

        Args:
            misclick_rate: Probability of misclick (0-1)

        Returns:
            True if should misclick
        """
        return self._rng.random() < misclick_rate

    def calculate_misclick_offset(self) -> tuple[int, int]:
        """Calculate offset for a misclick.

        Returns:
            (dx, dy) offset in pixels
        """
        # Misclicks typically nearby but wrong slot
        angle = self._rng.uniform(0, 2 * np.pi)
        distance = self._rng.uniform(20, 50)

        dx = int(distance * np.cos(angle))
        dy = int(distance * np.sin(angle))

        return dx, dy

    def create_target_from_slot(
        self, slot_x: int, slot_y: int, slot_width: int = 42, slot_height: int = 36
    ) -> ClickTarget:
        """Create a click target from inventory slot info.

        Args:
            slot_x: Slot center x
            slot_y: Slot center y
            slot_width: Slot width
            slot_height: Slot height

        Returns:
            ClickTarget for the slot
        """
        return ClickTarget(
            center_x=slot_x,
            center_y=slot_y,
            width=slot_width,
            height=slot_height,
        )
