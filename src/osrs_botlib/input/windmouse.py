"""WindMouse algorithm - physics-based mouse movement.

This module implements the WindMouse algorithm, a well-known approach for
generating human-like mouse movements using physics simulation. The algorithm
combines two forces:

1. Gravity: A force pulling the mouse toward the target, creating smooth
   approach motion with natural deceleration.

2. Wind: A perpendicular oscillating force that creates curved, organic paths
   with natural overshoot behavior.

The result is mouse movement that exhibits:
- Smooth acceleration and deceleration
- Natural overshoot when approaching targets (momentum-based)
- Curved paths that vary between movements
- Speed variation based on distance to target

References:
- Original WindMouse algorithm by BenLand100
- Fitts's Law integration for target-aware deceleration
"""

import math
from dataclasses import dataclass
from typing import Optional

import numpy as np

from utils import create_rng, gaussian_bounded


@dataclass
class WindMouseConfig:
    """Configuration for WindMouse algorithm."""

    # Physics parameters
    gravity: float = 9.0          # Attraction force toward target (higher = more direct)
    wind: float = 3.0             # Perpendicular oscillating force (higher = more curves)
    target_area: float = 10.0     # Distance at which deceleration begins (pixels)
    max_step: float = 10.0        # Maximum pixels per iteration

    # Additional variation
    wind_change_rate: float = 0.1  # How quickly wind direction changes
    min_wait: float = 2.0          # Minimum delay per step (ms)
    max_wait: float = 10.0         # Maximum delay per step (ms)

    # Fitts's Law integration (optional target-aware deceleration)
    fitts_enabled: bool = True
    fitts_a_coefficient: float = 50.0    # Base time (ms)
    fitts_b_coefficient: float = 150.0   # Scaling factor
    fitts_decel_start: float = 0.8       # Start slowing at 80% of path


@dataclass
class WindMousePoint:
    """A point in a WindMouse path with timing."""

    x: int
    y: int
    delay_ms: float  # Delay before moving to next point


class WindMouse:
    """Generate human-like mouse paths using physics simulation.

    The WindMouse algorithm simulates physical forces acting on the mouse
    cursor to create organic, human-like movement patterns.
    """

    def __init__(
        self,
        config: Optional[WindMouseConfig] = None,
        rng: Optional[np.random.Generator] = None,
    ):
        """Initialize WindMouse.

        Args:
            config: WindMouse configuration
            rng: NumPy random generator (created if not provided)
        """
        self.config = config or WindMouseConfig()
        self._rng = rng or create_rng()

    def generate_path(
        self,
        start: tuple[int, int],
        end: tuple[int, int],
        target_width: float = 10.0,
    ) -> list[WindMousePoint]:
        """Generate a human-like path from start to end.

        Uses physics simulation with gravity (attraction to target) and
        wind (perpendicular oscillation) to create organic movement.

        Args:
            start: Starting (x, y) coordinates
            end: Target (x, y) coordinates
            target_width: Width of the target area (for Fitts's Law)

        Returns:
            List of WindMousePoint with positions and delays
        """
        cfg = self.config

        # Current position (float for precision)
        x = float(start[0])
        y = float(start[1])

        # Target position
        target_x = float(end[0])
        target_y = float(end[1])

        # Velocity components
        vel_x = 0.0
        vel_y = 0.0

        # Wind components (oscillating force)
        wind_x = 0.0
        wind_y = 0.0

        # Path points
        path = [WindMousePoint(int(x), int(y), 0)]

        # Calculate total distance for progress tracking
        initial_distance = math.sqrt((target_x - x) ** 2 + (target_y - y) ** 2)
        if initial_distance < 1:
            return path

        # Main physics loop
        max_iterations = int(initial_distance * 3) + 100  # Safety limit
        iteration = 0

        while iteration < max_iterations:
            iteration += 1

            # Calculate distance to target
            dx = target_x - x
            dy = target_y - y
            distance = math.sqrt(dx * dx + dy * dy)

            # Check if we've reached the target
            if distance < 1:
                break

            # Calculate progress for Fitts's Law deceleration
            progress = 1.0 - (distance / initial_distance)

            # Update wind force (random oscillation)
            wind_x = self._update_wind(wind_x, cfg.wind)
            wind_y = self._update_wind(wind_y, cfg.wind)

            # Calculate gravity force (attraction to target)
            if distance > cfg.target_area:
                # Far from target: stronger gravity, wind has effect
                gravity_factor = cfg.gravity
                wind_factor = 1.0
            else:
                # Near target: weaker gravity, reduced wind for precision
                area_ratio = distance / cfg.target_area
                gravity_factor = cfg.gravity * area_ratio
                wind_factor = area_ratio * area_ratio  # Quadratic reduction

            # Apply forces to velocity
            if distance > 0:
                # Normalize direction to target
                norm_dx = dx / distance
                norm_dy = dy / distance

                # Gravity: pull toward target
                vel_x += norm_dx * gravity_factor
                vel_y += norm_dy * gravity_factor

            # Wind: perpendicular oscillation
            vel_x += wind_x * wind_factor
            vel_y += wind_y * wind_factor

            # Calculate current speed
            speed = math.sqrt(vel_x * vel_x + vel_y * vel_y)

            # Limit maximum speed
            max_speed = self._calculate_max_speed(
                distance, progress, target_width, initial_distance
            )

            if speed > max_speed:
                # Normalize and scale velocity
                vel_x = (vel_x / speed) * max_speed
                vel_y = (vel_y / speed) * max_speed
                speed = max_speed

            # Ensure minimum step size (prevents getting stuck)
            if speed < 0.5 and distance > 1:
                if distance > 0:
                    vel_x = (dx / distance) * 0.5
                    vel_y = (dy / distance) * 0.5
                    speed = 0.5

            # Update position
            x += vel_x
            y += vel_y

            # Calculate delay for this step (Gaussian for natural timing)
            delay_ms = self._calculate_step_delay(distance, speed)

            # Add point to path
            path.append(WindMousePoint(int(round(x)), int(round(y)), delay_ms))

        # Ensure we end exactly at target
        if path[-1].x != end[0] or path[-1].y != end[1]:
            path.append(WindMousePoint(end[0], end[1], cfg.min_wait))

        return path

    def _update_wind(self, current_wind: float, max_wind: float) -> float:
        """Update wind force with random oscillation.

        Args:
            current_wind: Current wind value
            max_wind: Maximum wind magnitude

        Returns:
            New wind value
        """
        # Random walk with mean reversion
        change = gaussian_bounded(
            self._rng,
            -self.config.wind_change_rate * max_wind,
            self.config.wind_change_rate * max_wind,
        )

        # Mean reversion to prevent wind from drifting too far
        new_wind = current_wind + change - current_wind * 0.1

        # Clamp to max wind
        return max(-max_wind, min(max_wind, new_wind))

    def _calculate_max_speed(
        self,
        distance: float,
        progress: float,
        target_width: float,
        initial_distance: float,
    ) -> float:
        """Calculate maximum speed based on distance and Fitts's Law.

        Args:
            distance: Current distance to target
            progress: Progress through movement (0-1)
            target_width: Width of target area
            initial_distance: Total distance of movement

        Returns:
            Maximum speed in pixels per step
        """
        cfg = self.config

        # Base max speed from config
        base_max = cfg.max_step

        # Apply Fitts's Law deceleration near target
        if cfg.fitts_enabled and progress >= cfg.fitts_decel_start:
            # Calculate deceleration factor based on target width
            # Smaller targets = more deceleration
            decel_progress = (progress - cfg.fitts_decel_start) / (1.0 - cfg.fitts_decel_start)

            # Exponential deceleration
            # Wider targets allow faster approach
            width_factor = min(1.0, target_width / 20.0)  # Normalize to reasonable range
            decel_factor = 1.0 - (decel_progress * (1.0 - width_factor) * 0.8)

            base_max *= decel_factor

        # Also slow down when very close to target
        if distance < cfg.target_area:
            proximity_factor = distance / cfg.target_area
            base_max *= max(0.2, proximity_factor)

        return max(0.5, base_max)

    def _calculate_step_delay(self, distance: float, speed: float) -> float:
        """Calculate delay for a movement step.

        Args:
            distance: Distance to target
            speed: Current speed

        Returns:
            Delay in milliseconds
        """
        cfg = self.config

        # Base delay inversely related to speed
        if speed > 0:
            # Faster movement = shorter delays
            base_delay = gaussian_bounded(
                self._rng,
                cfg.min_wait,
                cfg.max_wait,
            )

            # Scale delay based on speed (slower = longer delays)
            speed_factor = cfg.max_step / max(1, speed)
            delay = base_delay * min(2.0, speed_factor)
        else:
            delay = cfg.max_wait

        return max(cfg.min_wait, min(cfg.max_wait * 2, delay))

    def get_path_as_tuples(
        self,
        start: tuple[int, int],
        end: tuple[int, int],
        target_width: float = 10.0,
    ) -> list[tuple[int, int]]:
        """Generate path as simple coordinate tuples.

        Convenience method that returns just coordinates without timing.

        Args:
            start: Starting coordinates
            end: Target coordinates
            target_width: Width of target area

        Returns:
            List of (x, y) coordinate tuples
        """
        path = self.generate_path(start, end, target_width)
        return [(p.x, p.y) for p in path]

    def get_total_time_ms(self, path: list[WindMousePoint]) -> float:
        """Calculate total movement time for a path.

        Args:
            path: List of WindMousePoints

        Returns:
            Total time in milliseconds
        """
        return sum(p.delay_ms for p in path)
