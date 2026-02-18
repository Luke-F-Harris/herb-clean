"""Human-like mouse movement using Bezier curves."""

import math
import time
from dataclasses import dataclass
from typing import Optional

import numpy as np


@dataclass
class MovementConfig:
    """Configuration for mouse movement."""

    speed_range: tuple[float, float] = (200, 400)  # pixels per second
    overshoot_chance: float = 0.30
    overshoot_distance: tuple[int, int] = (5, 15)
    curve_variance: float = 0.3


@dataclass
class Point:
    """2D point."""

    x: float
    y: float


class BezierMovement:
    """Generate human-like mouse movement paths using Bezier curves."""

    def __init__(self, config: Optional[MovementConfig] = None):
        """Initialize Bezier movement generator.

        Args:
            config: Movement configuration
        """
        self.config = config or MovementConfig()
        self._rng = np.random.default_rng()

    def generate_path(
        self,
        start: tuple[int, int],
        end: tuple[int, int],
        num_points: int = 50,
    ) -> list[tuple[int, int]]:
        """Generate a human-like path between two points.

        Uses cubic Bezier curves with randomized control points.
        Includes optional overshoot and correction.

        Args:
            start: Starting (x, y) coordinates
            end: Target (x, y) coordinates
            num_points: Number of points in the path

        Returns:
            List of (x, y) coordinates forming the path
        """
        start_point = Point(float(start[0]), float(start[1]))
        end_point = Point(float(end[0]), float(end[1]))

        # Calculate distance and direction
        dx = end_point.x - start_point.x
        dy = end_point.y - start_point.y
        distance = math.sqrt(dx * dx + dy * dy)

        if distance < 1:
            return [end]

        # Generate control points for cubic Bezier
        control1, control2 = self._generate_control_points(start_point, end_point)

        # Check for overshoot
        overshoot_target = None
        if self._rng.random() < self.config.overshoot_chance:
            overshoot_target = self._calculate_overshoot(end_point, dx, dy)

        # Generate Bezier path
        if overshoot_target:
            # Path to overshoot point
            path1 = self._bezier_curve(
                start_point, control1, control2, overshoot_target, num_points // 2
            )
            # Correction path back to target
            correction_control1, correction_control2 = self._generate_control_points(
                overshoot_target, end_point
            )
            path2 = self._bezier_curve(
                overshoot_target,
                correction_control1,
                correction_control2,
                end_point,
                num_points // 2,
            )
            path = path1 + path2[1:]  # Avoid duplicate point
        else:
            path = self._bezier_curve(
                start_point, control1, control2, end_point, num_points
            )

        # Convert to integer coordinates
        return [(int(round(p.x)), int(round(p.y))) for p in path]

    def _generate_control_points(
        self, start: Point, end: Point
    ) -> tuple[Point, Point]:
        """Generate randomized control points for Bezier curve.

        Control points are placed perpendicular to the line
        between start and end, with random offsets.
        """
        dx = end.x - start.x
        dy = end.y - start.y
        distance = math.sqrt(dx * dx + dy * dy)

        # Perpendicular direction
        perp_x = -dy / distance if distance > 0 else 0
        perp_y = dx / distance if distance > 0 else 0

        # Random offsets based on distance
        max_offset = distance * self.config.curve_variance
        offset1 = self._rng.uniform(-max_offset, max_offset)
        offset2 = self._rng.uniform(-max_offset, max_offset)

        # Control point 1 at ~1/3 of path
        t1 = 0.33 + self._rng.uniform(-0.1, 0.1)
        control1 = Point(
            start.x + dx * t1 + perp_x * offset1,
            start.y + dy * t1 + perp_y * offset1,
        )

        # Control point 2 at ~2/3 of path
        t2 = 0.67 + self._rng.uniform(-0.1, 0.1)
        control2 = Point(
            start.x + dx * t2 + perp_x * offset2,
            start.y + dy * t2 + perp_y * offset2,
        )

        return control1, control2

    def _calculate_overshoot(self, target: Point, dx: float, dy: float) -> Point:
        """Calculate overshoot point past target."""
        distance = math.sqrt(dx * dx + dy * dy)
        if distance < 1:
            return target

        # Normalize direction
        dir_x = dx / distance
        dir_y = dy / distance

        # Random overshoot distance
        overshoot_dist = self._rng.uniform(
            self.config.overshoot_distance[0], self.config.overshoot_distance[1]
        )

        # Add some perpendicular drift
        perp_drift = self._rng.uniform(-5, 5)

        return Point(
            target.x + dir_x * overshoot_dist - dir_y * perp_drift,
            target.y + dir_y * overshoot_dist + dir_x * perp_drift,
        )

    def _bezier_curve(
        self,
        p0: Point,
        p1: Point,
        p2: Point,
        p3: Point,
        num_points: int,
    ) -> list[Point]:
        """Generate points along a cubic Bezier curve.

        Uses variable speed: slow at start and end, faster in middle.
        """
        points = []

        for i in range(num_points):
            # Variable t for speed variation (ease-in-out)
            linear_t = i / (num_points - 1) if num_points > 1 else 1
            t = self._ease_in_out(linear_t)

            # Cubic Bezier formula
            x = (
                (1 - t) ** 3 * p0.x
                + 3 * (1 - t) ** 2 * t * p1.x
                + 3 * (1 - t) * t ** 2 * p2.x
                + t ** 3 * p3.x
            )
            y = (
                (1 - t) ** 3 * p0.y
                + 3 * (1 - t) ** 2 * t * p1.y
                + 3 * (1 - t) * t ** 2 * p2.y
                + t ** 3 * p3.y
            )

            points.append(Point(x, y))

        return points

    def _ease_in_out(self, t: float) -> float:
        """Ease-in-out function for natural acceleration/deceleration."""
        if t < 0.5:
            return 2 * t * t
        else:
            return 1 - (-2 * t + 2) ** 2 / 2

    def calculate_movement_time(
        self, start: tuple[int, int], end: tuple[int, int]
    ) -> float:
        """Calculate movement time based on distance and speed.

        Args:
            start: Starting coordinates
            end: Target coordinates

        Returns:
            Movement time in seconds
        """
        dx = end[0] - start[0]
        dy = end[1] - start[1]
        distance = math.sqrt(dx * dx + dy * dy)

        # Random speed within range
        speed = self._rng.uniform(
            self.config.speed_range[0], self.config.speed_range[1]
        )

        # Add some minimum time for very short distances
        min_time = 0.05
        return max(min_time, distance / speed)

    def get_point_delays(
        self,
        path: list[tuple[int, int]],
        total_time: float,
    ) -> list[float]:
        """Calculate delays between path points for natural movement.

        Uses variable timing: slower at start/end, faster in middle.

        Args:
            path: List of path points
            total_time: Total movement time in seconds

        Returns:
            List of delays between consecutive points
        """
        if len(path) < 2:
            return []

        num_segments = len(path) - 1
        delays = []

        for i in range(num_segments):
            # Variable speed along path
            progress = i / num_segments
            # Slower at start and end
            speed_factor = 0.5 + 0.5 * math.sin(progress * math.pi)
            speed_factor = max(0.3, speed_factor)  # Minimum speed

            base_delay = total_time / num_segments
            delay = base_delay / speed_factor

            # Add small random variation
            delay *= self._rng.uniform(0.9, 1.1)
            delays.append(delay)

        # Normalize to match total time
        total_delays = sum(delays)
        if total_delays > 0:
            scale = total_time / total_delays
            delays = [d * scale for d in delays]

        return delays
