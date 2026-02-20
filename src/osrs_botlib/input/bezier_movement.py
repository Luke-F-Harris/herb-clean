"""Human-like mouse movement using Bezier curves."""

import math
import time
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from utils import create_rng, gaussian_bounded
from .organic_easing import OrganicEasing, OrganicEasingConfig
from .windmouse import WindMouse, WindMouseConfig


@dataclass
class MovementConfig:
    """Configuration for mouse movement."""

    speed_range: tuple[float, float] = (800, 1400)  # pixels per second
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

    # Multi-segment curves (more control points for complex paths)
    multi_segment_chance: float = 0.25  # Chance to use 3-4 control points
    max_control_points: int = 4  # Maximum control points (2-4)

    # Speed variation
    speed_variation_enabled: bool = True
    easing_functions: tuple[str, ...] = ("ease_in_out", "ease_in", "ease_out", "linear", "ease_in_out_back")
    easing_weights: tuple[float, ...] = (0.50, 0.15, 0.15, 0.10, 0.10)
    micro_pause_chance: float = 0.25
    micro_pause_duration: tuple[float, float] = (0.03, 0.12)

    # Exaggerated speed variation (more noticeable accel/decel)
    min_speed_factor: float = 0.2   # Slowest parts are 5x slower
    max_speed_factor: float = 1.5   # Fastest parts are 1.5x faster
    burst_chance: float = 0.15      # Chance of sudden speed burst
    burst_speed_multiplier: float = 1.8
    burst_duration_ratio: float = 0.15

    # Organic easing (replaces mathematical easing functions)
    organic_easing_config: OrganicEasingConfig = field(default_factory=OrganicEasingConfig)

    # WindMouse integration (physics-based alternative to Bezier)
    windmouse_enabled: bool = False
    windmouse_chance: float = 0.0  # Probability of using WindMouse vs Bezier
    windmouse_config: WindMouseConfig = field(default_factory=WindMouseConfig)

    # Fitts's Law deceleration (explicit target-aware slowdown)
    fitts_enabled: bool = True
    fitts_a_coefficient: float = 50.0    # Base time (ms)
    fitts_b_coefficient: float = 150.0   # Scaling factor
    fitts_decel_start: float = 0.8       # Start slowing at 80% of path


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
        self._rng = create_rng()
        self._organic_easing = OrganicEasing(self._rng, self.config.organic_easing_config)
        self._windmouse = WindMouse(self.config.windmouse_config, self._rng)

    def generate_path(
        self,
        start: tuple[int, int],
        end: tuple[int, int],
        num_points: int = 50,
        target_width: float = 10.0,
    ) -> list[tuple[int, int]]:
        """Generate a human-like path between two points.

        Uses cubic Bezier curves with randomized control points.
        Includes optional overshoot and correction, micro-corrections, and jitter.
        May use WindMouse algorithm instead based on configuration.

        Args:
            start: Starting (x, y) coordinates
            end: Target (x, y) coordinates
            num_points: Number of points in the path
            target_width: Width of target area (for Fitts's Law)

        Returns:
            List of (x, y) coordinates forming the path
        """
        # Check if we should use WindMouse instead of Bezier
        if (
            self.config.windmouse_enabled
            and self._rng.random() < self.config.windmouse_chance
        ):
            return self._windmouse.get_path_as_tuples(start, end, target_width)

        start_point = Point(float(start[0]), float(start[1]))
        end_point = Point(float(end[0]), float(end[1]))

        # Calculate distance and direction
        dx = end_point.x - start_point.x
        dy = end_point.y - start_point.y
        distance = math.sqrt(dx * dx + dy * dy)

        if distance < 1:
            return [end]

        # Decide curve type:
        # - Quadratic (1 control point): 15% chance - simpler curves
        # - Cubic (2 control points): default - standard curves
        # - Multi-segment (3 control points): rare - only for medium movements
        use_quadratic = (
            self.config.imperfection_enabled
            and self._rng.random() < self.config.simple_curve_chance
        )

        # Multi-segment curves: only for medium-distance movements (80-250px)
        # Very long movements (>250px) should use simple curves to avoid wild paths
        multi_segment_chance = self.config.multi_segment_chance
        if distance > 250:
            multi_segment_chance = 0  # Never use multi-segment for very long moves
        elif distance > 150:
            multi_segment_chance *= 0.5  # Reduce chance for longer moves

        use_multi_segment = (
            self.config.imperfection_enabled
            and not use_quadratic
            and 80 < distance < 300  # Only for medium movements
            and self._rng.random() < multi_segment_chance
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
        elif use_multi_segment:
            # Use 3-4 control points for more complex, organic curves
            num_controls = self._rng.integers(3, self.config.max_control_points + 1)
            controls = self._generate_multi_control_points(start_point, end_point, num_controls)
            path = self._generate_multi_segment_curve(
                start_point, end_point, controls, num_points
            )
        elif use_quadratic:
            # Use simpler quadratic curve with single control point
            control1, _ = self._generate_control_points(start_point, end_point)
            path = self._generate_quadratic_curve(
                start_point, control1, end_point, num_points
            )
        else:
            # Standard cubic curve (2 control points)
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

        IMPORTANT: Avoids symmetric placement to prevent bot-like curves.
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
            # Add extra variance from config (Gaussian for natural distribution)
            base_variance += gaussian_bounded(
                self._rng, 0, self.config.control_point_variance
            )

        # Scale down variance for longer movements to prevent wild curves
        # Short movements (< 100px): full variance
        # Long movements (> 300px): reduced to 60% variance
        if distance > 100:
            distance_scale = max(0.6, 1.0 - (distance - 100) / 500)
            base_variance *= distance_scale

        max_offset = distance * base_variance

        # Generate asymmetric offsets - avoid mirror symmetry (Gaussian for natural clusters)
        offset1 = gaussian_bounded(self._rng, -max_offset, max_offset)

        # Make offset2 intentionally different magnitude (not just opposite sign)
        # This breaks the symmetry that makes curves look bot-like
        offset2_magnitude = gaussian_bounded(self._rng, 0.3, 1.0) * max_offset
        offset2_sign = 1 if self._rng.random() < 0.5 else -1

        # 40% chance: same side (C-curve), 60% chance: different sides (S-curve)
        if self._rng.random() < 0.4:
            # Same side - makes a C-curve
            offset2 = offset2_sign * offset2_magnitude * (1 if offset1 >= 0 else -1)
        else:
            # Different sides - makes an S-curve, but asymmetric magnitude
            offset2 = offset2_sign * offset2_magnitude * (-1 if offset1 >= 0 else 1)

        # ASYMMETRIC t-values: avoid 0.33/0.67 symmetry
        # Use different base positions and variances for each control point
        t_variance = 0.15 if self.config.imperfection_enabled else 0.1

        # First control point: anywhere from 0.2 to 0.45 (biased toward start)
        # Gaussian distribution clusters control points naturally
        t1_base = gaussian_bounded(self._rng, 0.25, 0.40)
        t1 = t1_base + gaussian_bounded(self._rng, -t_variance, t_variance)
        t1 = max(0.15, min(0.50, t1))  # Clamp to valid range

        # Second control point: anywhere from 0.55 to 0.85 (biased toward end)
        # Use different variance to break symmetry
        t2_base = gaussian_bounded(self._rng, 0.60, 0.80)
        t2 = t2_base + gaussian_bounded(self._rng, -t_variance * 0.7, t_variance * 1.3)
        t2 = max(0.50, min(0.90, t2))  # Clamp to valid range

        control1 = Point(
            start.x + dx * t1 + perp_x * offset1,
            start.y + dy * t1 + perp_y * offset1,
        )

        control2 = Point(
            start.x + dx * t2 + perp_x * offset2,
            start.y + dy * t2 + perp_y * offset2,
        )

        return control1, control2

    def _generate_multi_control_points(
        self, start: Point, end: Point, num_controls: int = 3
    ) -> list[Point]:
        """Generate 3-4 control points for more complex curves.

        Creates more organic, human-like paths by using higher-order
        Bezier curves or chained segments.

        Args:
            start: Starting point
            end: Ending point
            num_controls: Number of control points (3 or 4)

        Returns:
            List of control points
        """
        dx = end.x - start.x
        dy = end.y - start.y
        distance = math.sqrt(dx * dx + dy * dy)

        if distance < 1:
            return [start, end]

        # Perpendicular direction
        perp_x = -dy / distance
        perp_y = dx / distance

        base_variance = self.config.curve_variance
        if self.config.imperfection_enabled:
            base_variance += gaussian_bounded(
                self._rng, 0, self.config.control_point_variance
            )

        # Scale down variance for longer movements (same as standard control points)
        if distance > 100:
            distance_scale = max(0.6, 1.0 - (distance - 100) / 500)
            base_variance *= distance_scale

        # Further reduce variance for multi-control to prevent wild curves
        base_variance *= 0.7

        max_offset = distance * base_variance
        controls = []

        # Generate t-values that are intentionally irregular (Gaussian for natural clustering)
        if num_controls == 3:
            # Three control points at irregular intervals
            t_values = [
                gaussian_bounded(self._rng, 0.18, 0.32),
                gaussian_bounded(self._rng, 0.42, 0.58),
                gaussian_bounded(self._rng, 0.68, 0.82),
            ]
        else:  # 4 control points
            t_values = [
                gaussian_bounded(self._rng, 0.12, 0.25),
                gaussian_bounded(self._rng, 0.32, 0.45),
                gaussian_bounded(self._rng, 0.55, 0.68),
                gaussian_bounded(self._rng, 0.75, 0.88),
            ]

        # Generate offsets with varying magnitudes (Gaussian for natural clusters)
        prev_offset = 0
        for i, t in enumerate(t_values):
            # Vary magnitude for each control point
            magnitude = gaussian_bounded(self._rng, 0.3, 1.0) * max_offset

            # Alternate sides with some randomness
            if i == 0:
                offset = magnitude * (1 if self._rng.random() < 0.5 else -1)
            else:
                # 70% chance to be on opposite side from previous
                if self._rng.random() < 0.7:
                    offset = -magnitude if prev_offset > 0 else magnitude
                else:
                    offset = magnitude if prev_offset > 0 else -magnitude

            prev_offset = offset

            control = Point(
                start.x + dx * t + perp_x * offset,
                start.y + dy * t + perp_y * offset,
            )
            controls.append(control)

        return controls

    def _calculate_overshoot(self, target: Point, dx: float, dy: float) -> Point:
        """Calculate overshoot point past target."""
        distance = math.sqrt(dx * dx + dy * dy)
        if distance < 1:
            return target

        # Normalize direction
        dir_x = dx / distance
        dir_y = dy / distance

        # Random overshoot distance (Gaussian for natural variance)
        overshoot_dist = gaussian_bounded(
            self._rng,
            self.config.overshoot_distance[0],
            self.config.overshoot_distance[1],
        )

        # Add some perpendicular drift (Gaussian)
        perp_drift = gaussian_bounded(self._rng, -5, 5)

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

        Points are distributed uniformly along the curve parameter.
        Easing is NOT applied here - it's applied to timing in get_point_delays().
        This prevents point clustering that causes teleporting.
        """
        # Note: easing_func parameter is kept for API compatibility but ignored
        # Easing is now applied to timing, not point distribution
        points = []

        for i in range(num_points):
            # Use linear t for uniform point distribution
            t = i / (num_points - 1) if num_points > 1 else 1

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

        Points are distributed uniformly along the curve parameter.
        Easing is NOT applied here - it's applied to timing in get_point_delays().
        """
        # Note: easing_func parameter is kept for API compatibility but ignored
        points = []

        for i in range(num_points):
            # Use linear t for uniform point distribution
            t = i / (num_points - 1) if num_points > 1 else 1

            # Quadratic Bezier formula
            x = (1 - t) ** 2 * p0.x + 2 * (1 - t) * t * p1.x + t ** 2 * p2.x
            y = (1 - t) ** 2 * p0.y + 2 * (1 - t) * t * p1.y + t ** 2 * p2.y

            points.append(Point(x, y))

        return points

    def _generate_multi_segment_curve(
        self,
        start: Point,
        end: Point,
        controls: list[Point],
        num_points: int,
        easing_func: Optional[callable] = None,
    ) -> list[Point]:
        """Generate a curve through multiple control points using chained cubic segments.

        Instead of a single high-order Bezier, chains multiple cubic segments
        for smoother, more controllable paths with 3-4 control points.

        Args:
            start: Starting point
            end: Ending point
            controls: List of 3-4 control points
            num_points: Total points in output path
            easing_func: Optional easing function

        Returns:
            List of points forming the path
        """
        if easing_func is None:
            # Calculate distance for organic easing
            dx = end.x - start.x
            dy = end.y - start.y
            distance = math.sqrt(dx * dx + dy * dy)
            easing_func = self._get_random_easing_function(distance)

        if len(controls) < 2:
            # Fall back to standard cubic
            c1, c2 = self._generate_control_points(start, end)
            return self._bezier_curve(start, c1, c2, end, num_points, easing_func)

        # Create waypoints: start -> controls -> end
        waypoints = [start] + controls + [end]

        # Generate smooth path through waypoints using Catmull-Rom style interpolation
        # We'll create cubic Bezier segments between each pair of waypoints
        all_points = []
        num_segments = len(waypoints) - 1
        points_per_segment = num_points // num_segments

        for i in range(num_segments):
            p0 = waypoints[i]
            p3 = waypoints[i + 1]

            # Calculate control points for this segment based on neighboring waypoints
            # This creates smooth transitions between segments
            if i == 0:
                # First segment: use direction toward next waypoint
                dx = waypoints[i + 1].x - p0.x
                dy = waypoints[i + 1].y - p0.y
                p1 = Point(p0.x + dx * 0.33, p0.y + dy * 0.33)
            else:
                # Use tangent from previous waypoint
                prev = waypoints[i - 1]
                dx = p3.x - prev.x
                dy = p3.y - prev.y
                p1 = Point(p0.x + dx * 0.15, p0.y + dy * 0.15)

            if i == num_segments - 1:
                # Last segment: use direction from previous waypoint
                dx = p3.x - waypoints[i].x
                dy = p3.y - waypoints[i].y
                p2 = Point(p3.x - dx * 0.33, p3.y - dy * 0.33)
            else:
                # Use tangent toward next waypoint
                next_wp = waypoints[i + 2]
                dx = next_wp.x - p0.x
                dy = next_wp.y - p0.y
                p2 = Point(p3.x - dx * 0.15, p3.y - dy * 0.15)

            # Add some randomness to control points (Gaussian for natural variance)
            variance = 0.1
            p1 = Point(
                p1.x + gaussian_bounded(self._rng, -variance, variance) * abs(p3.x - p0.x),
                p1.y + gaussian_bounded(self._rng, -variance, variance) * abs(p3.y - p0.y),
            )
            p2 = Point(
                p2.x + gaussian_bounded(self._rng, -variance, variance) * abs(p3.x - p0.x),
                p2.y + gaussian_bounded(self._rng, -variance, variance) * abs(p3.y - p0.y),
            )

            # Generate this segment
            segment_points = points_per_segment if i < num_segments - 1 else num_points - len(all_points)
            segment = self._bezier_curve(p0, p1, p2, p3, segment_points, easing_func)

            # Avoid duplicate points at segment boundaries
            if all_points:
                all_points.extend(segment[1:])
            else:
                all_points.extend(segment)

        return all_points

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

    def _get_random_easing_function(self, distance: float = 100) -> callable:
        """Get a unique organic easing function for this movement.

        Each call returns a completely unique easing function with different
        characteristics. No mathematical constants are used - the curve is
        procedurally generated to be undetectable.

        Args:
            distance: Movement distance in pixels (affects curve characteristics)

        Returns:
            A unique easing function for this movement
        """
        if self.config.organic_easing_config.enabled:
            # Generate completely unique easing for each movement
            return self._organic_easing.generate_easing_function(distance)

        # Fallback to legacy mathematical easing if organic is disabled
        if not self.config.speed_variation_enabled:
            return self._ease_in_out

        easing_map = {
            "ease_in_out": self._ease_in_out,
            "ease_in": self._ease_in,
            "ease_out": self._ease_out,
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

            # Random deviation magnitude (Gaussian for natural distribution)
            magnitude = gaussian_bounded(
                self._rng,
                self.config.micro_correction_magnitude[0],
                self.config.micro_correction_magnitude[1],
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
            radius = gaussian_bounded(
                self._rng,
                self.config.jitter_radius[0],
                self.config.jitter_radius[1],
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

        # Random speed within range (Gaussian for natural variance)
        speed = gaussian_bounded(
            self._rng,
            self.config.speed_range[0],
            self.config.speed_range[1],
        )

        # Add some minimum time for very short distances
        min_time = 0.05
        return max(min_time, distance / speed)

    def get_point_delays(
        self,
        path: list[tuple[int, int]],
        total_time: float,
        target_width: float = 10.0,
    ) -> list[float]:
        """Calculate delays between path points for natural movement.

        Uses continuous, gradual speed variation throughout the movement.
        Speed is NEVER constant - always smoothly accelerating or decelerating.

        The speed profile combines:
        1. Base curve (slow-fast-slow pattern for natural mouse movement)
        2. Medium frequency waves (gradual speed oscillations)
        3. Low frequency drift (overall speed tendency shifts)
        4. Per-point micro-variation (tiny random fluctuations)
        5. Fitts's Law deceleration (target-aware slowdown in final approach)

        Args:
            path: List of path points
            total_time: Total movement time in seconds
            target_width: Width of target area for Fitts's Law deceleration

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
            micro_pause_duration = gaussian_bounded(
                self._rng,
                self.config.micro_pause_duration[0],
                self.config.micro_pause_duration[1],
            )

        # Calculate distances between consecutive points
        # This handles natural curve geometry variations (curves bend more in some places)
        distances = []
        for i in range(num_segments):
            dx = path[i + 1][0] - path[i][0]
            dy = path[i + 1][1] - path[i][1]
            distances.append(math.sqrt(dx * dx + dy * dy))

        total_distance = sum(distances)

        # Generate the continuous speed profile (creates slow-fast-slow pattern)
        speed_factors = self._generate_speed_profile(num_segments)

        for i in range(num_segments):
            # Base delay proportional to distance (handles curve geometry)
            if total_distance > 0:
                proportion = distances[i] / total_distance
                base_delay = total_time * proportion
            else:
                base_delay = total_time / num_segments

            # Apply speed profile for natural acceleration/deceleration
            delay = base_delay / speed_factors[i]

            # Add micro-pause at designated point
            if i == micro_pause_index:
                delay += micro_pause_duration

            delays.append(delay)

        # Apply Fitts's Law deceleration in final approach
        if self.config.fitts_enabled and total_distance > 0:
            delays = self._apply_fitts_deceleration(
                delays, total_distance, target_width
            )

        # Normalize to match total time (including micro-pause)
        target_time = total_time + micro_pause_duration
        total_delays = sum(delays)
        if total_delays > 0:
            scale = target_time / total_delays
            delays = [d * scale for d in delays]

        return delays

    def _apply_fitts_deceleration(
        self,
        delays: list[float],
        distance: float,
        target_width: float,
    ) -> list[float]:
        """Apply Fitts's Law deceleration to delays in final approach.

        Fitts's Law: MT = a + b * log2(D/W + 1)
        Smaller targets require more careful (slower) final approach.

        Args:
            delays: Original delay list
            distance: Total movement distance
            target_width: Width of target area

        Returns:
            Modified delays with Fitts's Law deceleration applied
        """
        if len(delays) == 0:
            return delays

        num_segments = len(delays)
        decel_start_idx = int(num_segments * self.config.fitts_decel_start)

        # Calculate expected slowdown based on Fitts's Law
        # MT = a + b * log2(D/W + 1)
        if target_width > 0:
            index_of_difficulty = math.log2(distance / target_width + 1)
        else:
            index_of_difficulty = math.log2(distance / 10 + 1)

        # Smaller targets = higher difficulty = more deceleration
        # Normalize difficulty to a multiplier (1.0 to 2.0 range)
        decel_strength = 1.0 + min(1.0, index_of_difficulty / 5.0)

        result = list(delays)
        for i in range(decel_start_idx, num_segments):
            # Calculate progress through deceleration phase
            decel_progress = (i - decel_start_idx) / max(1, num_segments - decel_start_idx)

            # Exponential deceleration (slower and slower)
            # Higher decel_strength = more pronounced slowdown
            decel_factor = 1.0 + (decel_strength - 1.0) * (decel_progress ** 1.5)

            result[i] *= decel_factor

        return result

    def _generate_speed_profile(self, num_segments: int, movement_distance: float = 100) -> list[float]:
        """Generate a continuous speed profile with gradual variations.

        Creates organic speed changes that:
        - Start slow, accelerate, then decelerate to stop
        - Have continuous medium-frequency oscillations
        - Include gradual drift in overall speed tendency
        - Never maintain constant speed for more than 2-3 points
        - Use procedurally generated curves (no mathematical constants)

        Args:
            num_segments: Number of path segments
            movement_distance: Distance in pixels (affects organic curve)

        Returns:
            List of speed factors (higher = faster movement)
        """
        min_factor = self.config.min_speed_factor
        max_factor = self.config.max_speed_factor
        factor_range = max_factor - min_factor

        # Use organic easing for base curve if enabled
        use_organic = self.config.organic_easing_config.enabled

        if not self.config.speed_variation_enabled:
            if use_organic:
                # Use organic base even without variation
                organic_profile = self._organic_easing.generate_base_profile(
                    num_segments, movement_distance
                )
                return [
                    min_factor + factor_range * base
                    for base in organic_profile
                ]
            else:
                # Legacy: basic ease-in-out with sin()
                return [
                    min_factor + factor_range * math.sin(i / num_segments * math.pi)
                    for i in range(num_segments)
                ]

        # Generate organic parameters for this movement's speed profile
        if use_organic:
            profile_params = self._organic_easing.generate_easing_params_for_speed_profile(
                movement_distance
            )
            asymmetry = profile_params['asymmetry']
        else:
            # Legacy: fixed asymmetry range
            asymmetry = self._rng.uniform(-0.15, 0.15)

        # Secondary waves: medium frequency oscillations (2-4 cycles)
        # These add variation on top of the base curve (Gaussian for natural clustering)
        num_waves = self._rng.integers(2, 5)
        wave_amplitudes = [gaussian_bounded(self._rng, 0.08, 0.20) for _ in range(num_waves)]
        wave_phases = [gaussian_bounded(self._rng, 0, 2 * math.pi) for _ in range(num_waves)]
        wave_frequencies = [gaussian_bounded(self._rng, 1.5, 4.0) for _ in range(num_waves)]

        # Drift: gradual shift in overall speed (like hand fatigue/recovery)
        drift_direction = self._rng.choice([-1, 1])
        drift_strength = gaussian_bounded(self._rng, 0.0, 0.15)

        # Generate smooth noise for micro-variation using cumulative random walk
        noise = self._generate_smooth_noise(num_segments, smoothness=0.85)

        speed_factors = []

        for i in range(num_segments):
            progress = i / num_segments

            # 1. Base curve: organic or legacy
            if use_organic:
                # Use organic base (no mathematical constants)
                base = self._organic_easing.apply_organic_base(progress, profile_params)
            else:
                # Legacy: asymmetric slow-fast-slow using sin()
                adjusted_progress = progress + asymmetry * math.sin(progress * math.pi)
                adjusted_progress = max(0, min(1, adjusted_progress))
                base = math.sin(adjusted_progress * math.pi)

            # 2. Secondary waves: medium frequency oscillations
            wave_sum = 0
            for w in range(num_waves):
                wave_sum += wave_amplitudes[w] * math.sin(
                    wave_frequencies[w] * progress * math.pi + wave_phases[w]
                )

            # 3. Drift: gradual overall speed shift
            drift = drift_direction * drift_strength * progress

            # 4. Smooth noise: micro-variation
            noise_contribution = noise[i] * 0.12

            # Combine all components
            combined = base + wave_sum + drift + noise_contribution

            # Ensure we stay in valid range [0, 1] before scaling
            combined = max(0.05, min(1.0, combined))

            # Scale to actual speed factor range
            speed_factor = min_factor + factor_range * combined

            speed_factors.append(speed_factor)

        return speed_factors

    def _generate_smooth_noise(self, length: int, smoothness: float = 0.8) -> list[float]:
        """Generate smooth random noise using exponential moving average.

        Creates noise that varies gradually, not abruptly. Uses Gaussian
        distribution for more natural clustering around zero.

        Args:
            length: Number of noise values to generate
            smoothness: How smooth (0 = random, 1 = very smooth)

        Returns:
            List of noise values in range [-1, 1]
        """
        noise = []
        current = gaussian_bounded(self._rng, -1, 1)

        for _ in range(length):
            # Blend current value with new random value (Gaussian for natural distribution)
            target = gaussian_bounded(self._rng, -1, 1)
            current = smoothness * current + (1 - smoothness) * target
            noise.append(current)

        return noise
