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

    # Jitter (hand tremor near clicks)
    jitter_enabled: bool = True
    jitter_radius: tuple[float, float] = (1.0, 3.0)
    jitter_points: int = 3

    # Curve imperfections
    imperfection_enabled: bool = True
    simple_curve_chance: float = 0.15
    control_point_variance: float = 0.2
    micro_correction_chance: float = 0.3
    micro_correction_magnitude: tuple[float, float] = (2.0, 8.0)

    # Speed variation
    speed_variation_enabled: bool = True
    easing_functions: tuple[str, ...] = ("ease_in_out", "ease_in", "ease_out", "linear", "ease_in_out_back")
    easing_weights: tuple[float, ...] = (0.50, 0.15, 0.15, 0.10, 0.10)
    micro_pause_chance: float = 0.20
    micro_pause_duration: tuple[float, float] = (0.02, 0.08)


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
        Includes optional overshoot and correction, micro-corrections, and jitter.

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

        # Decide whether to use simple quadratic curve or cubic curve
        use_quadratic = (
            self.config.imperfection_enabled
            and self._rng.random() < self.config.simple_curve_chance
        )

        # Check for overshoot
        overshoot_target = None
        if self._rng.random() < self.config.overshoot_chance:
            overshoot_target = self._calculate_overshoot(end_point, dx, dy)

        # Generate Bezier path
        if overshoot_target:
            # Path to overshoot point - always use cubic for overshoot
            control1, control2 = self._generate_control_points(start_point, overshoot_target)
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
        elif use_quadratic:
            # Use simpler quadratic curve with single control point
            control1, _ = self._generate_control_points(start_point, end_point)
            path = self._generate_quadratic_curve(
                start_point, control1, end_point, num_points
            )
        else:
            # Standard cubic curve
            control1, control2 = self._generate_control_points(start_point, end_point)
            path = self._bezier_curve(
                start_point, control1, control2, end_point, num_points
            )

        # Add micro-corrections to mid-path (30% chance)
        if (
            self.config.imperfection_enabled
            and self._rng.random() < self.config.micro_correction_chance
        ):
            path = self.add_micro_corrections(path, end_point)

        # Add jitter near the end (simulates hand tremor)
        path = self.add_jitter_to_path(path, end_point)

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

        # Random offsets based on distance - with extra variance if imperfections enabled
        base_variance = self.config.curve_variance
        if self.config.imperfection_enabled:
            # Add extra variance from config
            base_variance += self._rng.uniform(0, self.config.control_point_variance)

        max_offset = distance * base_variance
        offset1 = self._rng.uniform(-max_offset, max_offset)
        offset2 = self._rng.uniform(-max_offset, max_offset)

        # Occasionally place both control points on same side (more S-curve or C-curve)
        if self.config.imperfection_enabled and self._rng.random() < 0.2:
            # Same side bias
            if offset1 * offset2 < 0:  # Different signs
                offset2 = -offset2  # Make same sign

        # Control point 1 at ~1/3 of path with more t-value variance
        t_variance = 0.15 if self.config.imperfection_enabled else 0.1
        t1 = 0.33 + self._rng.uniform(-t_variance, t_variance)
        control1 = Point(
            start.x + dx * t1 + perp_x * offset1,
            start.y + dy * t1 + perp_y * offset1,
        )

        # Control point 2 at ~2/3 of path
        t2 = 0.67 + self._rng.uniform(-t_variance, t_variance)
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
        easing_func: Optional[callable] = None,
    ) -> list[Point]:
        """Generate points along a cubic Bezier curve.

        Uses variable speed based on selected easing function.
        """
        points = []
        if easing_func is None:
            easing_func = self._get_random_easing_function()

        for i in range(num_points):
            # Variable t for speed variation using selected easing
            linear_t = i / (num_points - 1) if num_points > 1 else 1
            t = easing_func(linear_t)

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

    def _generate_quadratic_curve(
        self,
        p0: Point,
        p1: Point,
        p2: Point,
        num_points: int,
        easing_func: Optional[callable] = None,
    ) -> list[Point]:
        """Generate points along a quadratic Bezier curve.

        Simpler curve with single control point for more natural variation.
        """
        points = []
        if easing_func is None:
            easing_func = self._get_random_easing_function()

        for i in range(num_points):
            linear_t = i / (num_points - 1) if num_points > 1 else 1
            t = easing_func(linear_t)

            # Quadratic Bezier formula
            x = (1 - t) ** 2 * p0.x + 2 * (1 - t) * t * p1.x + t ** 2 * p2.x
            y = (1 - t) ** 2 * p0.y + 2 * (1 - t) * t * p1.y + t ** 2 * p2.y

            points.append(Point(x, y))

        return points

    def _ease_in_out(self, t: float) -> float:
        """Ease-in-out function for natural acceleration/deceleration."""
        if t < 0.5:
            return 2 * t * t
        else:
            return 1 - (-2 * t + 2) ** 2 / 2

    def _ease_in(self, t: float) -> float:
        """Ease-in function (slow start, fast end)."""
        return t * t

    def _ease_out(self, t: float) -> float:
        """Ease-out function (fast start, slow end)."""
        return 1 - (1 - t) * (1 - t)

    def _linear(self, t: float) -> float:
        """Linear easing (constant speed)."""
        return t

    def _ease_in_out_back(self, t: float) -> float:
        """Ease-in-out with slight anticipation/overshoot effect."""
        c1, c2 = 1.70158, 1.70158 * 1.525
        if t < 0.5:
            return (2 * t) ** 2 * ((c2 + 1) * 2 * t - c2) / 2
        return ((2 * t - 2) ** 2 * ((c2 + 1) * (t * 2 - 2) + c2) + 2) / 2

    def _get_random_easing_function(self) -> callable:
        """Randomly select an easing function based on configured weights."""
        if not self.config.speed_variation_enabled:
            return self._ease_in_out

        easing_map = {
            "ease_in_out": self._ease_in_out,
            "ease_in": self._ease_in,
            "ease_out": self._ease_out,
            "linear": self._linear,
            "ease_in_out_back": self._ease_in_out_back,
        }

        functions = list(self.config.easing_functions)
        weights = list(self.config.easing_weights)

        # Normalize weights
        total = sum(weights)
        if total > 0:
            weights = [w / total for w in weights]

        choice = self._rng.choice(functions, p=weights)
        return easing_map.get(choice, self._ease_in_out)

    def add_micro_corrections(self, path: list[Point], end_point: Point) -> list[Point]:
        """Add small mid-path deviations to simulate natural hand adjustments.

        Inserts 1-2 small corrections (2-8 pixels) in the middle portion of the path.
        """
        if not self.config.imperfection_enabled:
            return path

        if len(path) < 10:
            return path

        # Only modify middle 60% of path
        start_idx = len(path) // 5
        end_idx = len(path) * 4 // 5

        # Insert 1-2 corrections
        num_corrections = self._rng.integers(1, 3)
        correction_indices = sorted(
            self._rng.choice(range(start_idx, end_idx), size=min(num_corrections, end_idx - start_idx), replace=False)
        )

        result = list(path)
        for idx in correction_indices:
            if idx >= len(result):
                continue

            # Random deviation magnitude
            magnitude = self._rng.uniform(
                self.config.micro_correction_magnitude[0],
                self.config.micro_correction_magnitude[1]
            )

            # Random angle for deviation
            angle = self._rng.uniform(0, 2 * math.pi)
            dx = magnitude * math.cos(angle)
            dy = magnitude * math.sin(angle)

            # Apply deviation
            result[idx] = Point(result[idx].x + dx, result[idx].y + dy)

            # Add correction back toward path on next point (if exists)
            if idx + 1 < len(result):
                result[idx + 1] = Point(
                    result[idx + 1].x - dx * 0.5,
                    result[idx + 1].y - dy * 0.5
                )

        return result

    def add_jitter_to_path(self, path: list[Point], target_point: Point) -> list[Point]:
        """Add small oscillations near the end of the path to simulate hand tremor.

        Adds small jitter (1-3 pixels) to the last 10-20% of the path.
        Oscillates around target, doesn't drift away.
        """
        if not self.config.jitter_enabled:
            return path

        if len(path) < 5:
            return path

        result = list(path)

        # Apply jitter to last 15% of path
        jitter_start = int(len(path) * 0.85)
        num_jitter_points = min(self.config.jitter_points, len(path) - jitter_start - 1)

        if num_jitter_points <= 0:
            return result

        # Distribute jitter points in the final portion
        jitter_indices = np.linspace(jitter_start, len(path) - 2, num_jitter_points, dtype=int)

        for i, idx in enumerate(jitter_indices):
            if idx >= len(result) - 1:
                continue

            # Oscillate with decreasing magnitude toward end
            decay = 1.0 - (i / num_jitter_points) * 0.5  # Reduce jitter as we approach target
            radius = self._rng.uniform(
                self.config.jitter_radius[0],
                self.config.jitter_radius[1]
            ) * decay

            # Alternate sides for oscillation effect
            angle = (math.pi / 2) if i % 2 == 0 else (-math.pi / 2)

            # Get direction perpendicular to path
            if idx + 1 < len(result):
                dx = result[idx + 1].x - result[idx].x
                dy = result[idx + 1].y - result[idx].y
                length = math.sqrt(dx * dx + dy * dy)
                if length > 0:
                    # Perpendicular offset
                    perp_x = -dy / length
                    perp_y = dx / length
                    result[idx] = Point(
                        result[idx].x + perp_x * radius * (1 if i % 2 == 0 else -1),
                        result[idx].y + perp_y * radius * (1 if i % 2 == 0 else -1)
                    )

        # Ensure final point stays close to target
        if len(result) > 0:
            result[-1] = target_point

        return result

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
        Includes optional micro-pauses for more human-like hesitation.

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

        # Determine if we add a micro-pause this movement
        add_micro_pause = (
            self.config.speed_variation_enabled
            and self._rng.random() < self.config.micro_pause_chance
        )
        micro_pause_index = -1
        micro_pause_duration = 0.0

        if add_micro_pause and num_segments > 5:
            # Place pause in middle 60% of path
            start_range = int(num_segments * 0.2)
            end_range = int(num_segments * 0.8)
            micro_pause_index = self._rng.integers(start_range, end_range)
            micro_pause_duration = self._rng.uniform(
                self.config.micro_pause_duration[0],
                self.config.micro_pause_duration[1]
            )

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

            # Add micro-pause at designated point
            if i == micro_pause_index:
                delay += micro_pause_duration

            delays.append(delay)

        # Normalize to match total time (including micro-pause)
        target_time = total_time + micro_pause_duration
        total_delays = sum(delays)
        if total_delays > 0:
            scale = target_time / total_delays
            delays = [d * scale for d in delays]

        return delays
