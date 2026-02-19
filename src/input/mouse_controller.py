"""Mouse movement orchestration using pynput."""

import time
from typing import Optional, Callable

import numpy as np
from pynput.mouse import Button, Controller as MouseDriver

from utils import create_rng
from .bezier_movement import BezierMovement, MovementConfig
from .click_handler import ClickHandler, ClickConfig, ClickTarget


class MouseController:
    """Orchestrate human-like mouse movement and clicks."""

    def __init__(
        self,
        movement_config: Optional[MovementConfig] = None,
        click_config: Optional[ClickConfig] = None,
        hesitation_chance: float = 0.15,
        hesitation_movements: tuple[int, int] = (1, 3),
        correction_delay: tuple[float, float] = (0.15, 0.35),
        post_click_drift_enabled: bool = True,
        post_click_drift_chance: float = 0.6,
        post_click_drift_distance: tuple[int, int] = (1, 4),
    ):
        """Initialize mouse controller.

        Args:
            movement_config: Bezier movement configuration
            click_config: Click handling configuration
            hesitation_chance: Probability of hesitation movements before clicking
            hesitation_movements: Range of extra movements during hesitation
            correction_delay: Range of delay before correcting a missed click
            post_click_drift_enabled: Whether to enable post-click micro-drift
            post_click_drift_chance: Probability of drift after clicking
            post_click_drift_distance: Range of drift distance in pixels
        """
        self._mouse = MouseDriver()
        self.bezier = BezierMovement(movement_config)
        self.click_handler = ClickHandler(click_config)
        self._stop_flag = False
        self._on_move_callback: Optional[Callable[[int, int], None]] = None
        self._rng = create_rng()

        # Hesitation config
        self._hesitation_chance = hesitation_chance
        self._hesitation_movements = hesitation_movements
        self._correction_delay = correction_delay

        # Post-click drift config
        self._post_click_drift_enabled = post_click_drift_enabled
        self._post_click_drift_chance = post_click_drift_chance
        self._post_click_drift_distance = post_click_drift_distance

    @property
    def position(self) -> tuple[int, int]:
        """Get current mouse position."""
        return self._mouse.position

    def get_position(self) -> tuple[int, int]:
        """Get current mouse position.

        Returns:
            (x, y) tuple of current mouse coordinates
        """
        return self._mouse.position

    def set_stop_flag(self, stop: bool = True) -> None:
        """Set flag to stop current movement."""
        self._stop_flag = stop

    def set_move_callback(self, callback: Optional[Callable[[int, int], None]]) -> None:
        """Set callback for mouse movement (for logging/debugging)."""
        self._on_move_callback = callback

    def move_to(
        self,
        x: int,
        y: int,
        num_points: int = 50,
    ) -> bool:
        """Move mouse to target position with human-like motion.

        Args:
            x: Target x coordinate
            y: Target y coordinate
            num_points: Number of points in movement path

        Returns:
            True if movement completed, False if stopped
        """
        self._stop_flag = False
        start = self.position

        # Generate path
        path = self.bezier.generate_path(start, (x, y), num_points)

        # Calculate timing
        total_time = self.bezier.calculate_movement_time(start, (x, y))
        delays = self.bezier.get_point_delays(path, total_time)

        # Execute movement
        for i, point in enumerate(path):
            if self._stop_flag:
                return False

            self._mouse.position = point

            if self._on_move_callback:
                self._on_move_callback(point[0], point[1])

            if i < len(delays):
                time.sleep(delays[i])

        return True

    def move_and_click(
        self,
        x: int,
        y: int,
        button: Button = Button.left,
    ) -> bool:
        """Move to target and click.

        Args:
            x: Target x coordinate
            y: Target y coordinate
            button: Mouse button to click

        Returns:
            True if completed, False if stopped
        """
        if not self.move_to(x, y):
            return False

        return self.click(button)

    def click(self, button: Button = Button.left) -> bool:
        """Perform a click at current position.

        Args:
            button: Mouse button to click

        Returns:
            True if completed
        """
        if self._stop_flag:
            return False

        # Get randomized duration
        target = ClickTarget(
            center_x=self.position[0],
            center_y=self.position[1],
            width=10,
            height=10,
        )
        result = self.click_handler.calculate_click(target)

        # Press and hold
        self._mouse.press(button)
        time.sleep(result.duration)
        self._mouse.release(button)

        return True

    def _should_hesitate(self) -> bool:
        """Determine if hesitation movements should occur before click."""
        return self._rng.random() < self._hesitation_chance

    def _perform_hesitation(self, target: ClickTarget) -> bool:
        """Perform hesitation movements within target bounds.

        Args:
            target: Click target area

        Returns:
            True if completed, False if stopped
        """
        num_moves = self._rng.integers(
            self._hesitation_movements[0],
            self._hesitation_movements[1] + 1
        )

        for _ in range(num_moves):
            if self._stop_flag:
                return False

            # Generate position within target bounds (inner third)
            hx = target.center_x + self._rng.integers(
                -target.width // 3, target.width // 3 + 1
            )
            hy = target.center_y + self._rng.integers(
                -target.height // 3, target.height // 3 + 1
            )

            # Shorter path for hesitation
            if not self.move_to(int(hx), int(hy), num_points=20):
                return False

            # Brief pause
            time.sleep(self._rng.uniform(0.03, 0.08))

        return True

    def _post_click_drift(self) -> bool:
        """Perform small mouse drift after clicking (natural hand movement).

        Simulates the subtle hand tremor/movement that occurs after clicking,
        making behavior more human-like.

        Returns:
            True if completed, False if stopped
        """
        if not self._post_click_drift_enabled:
            return True

        if self._rng.random() > self._post_click_drift_chance:
            return True

        # Small drift: configurable pixels in random direction
        min_dist, max_dist = self._post_click_drift_distance
        drift_x = self._rng.integers(-max_dist, max_dist + 1)
        drift_y = self._rng.integers(-max_dist, max_dist + 1)

        # Ensure minimum drift distance
        if abs(drift_x) < min_dist and abs(drift_y) < min_dist:
            drift_x = min_dist if drift_x >= 0 else -min_dist

        current = self.position
        target = (current[0] + drift_x, current[1] + drift_y)

        # Very short, slow movement (fewer points = faster)
        return self.move_to(target[0], target[1], num_points=10)

    def click_at_target(
        self,
        target: ClickTarget,
        button: Button = Button.left,
        misclick_rate: float = 0.0,
        slot_row: Optional[int] = None,
        overshoot_undershoot_rate: float = 0.05,
    ) -> tuple[bool, bool]:
        """Move to target and click with randomization.

        Args:
            target: Click target area
            button: Mouse button
            misclick_rate: Probability of misclick
            slot_row: Inventory row (0-6) for row-aware misclick correction
            overshoot_undershoot_rate: Probability of overshooting/undershooting

        Returns:
            (completed, was_misclick) tuple
        """
        # Calculate click position
        click_result = self.click_handler.calculate_click(target)

        # Perform hesitation movements before final click (15% chance)
        if self._should_hesitate():
            if not self._perform_hesitation(target):
                return False, False

        # Check for misclick - only allow actual misses on middle rows
        was_misclick = False
        x, y = click_result.x, click_result.y

        # Only allow misclicks on middle rows (not first or last)
        allow_miss = slot_row is not None and 0 < slot_row < 6

        if allow_miss and self.click_handler.should_misclick(misclick_rate):
            # Actually miss - click outside the target
            offset = self.click_handler.calculate_misclick_offset()
            miss_x = x + offset[0]
            miss_y = y + offset[1]
            was_misclick = True

            # Move to miss position and click
            if not self.move_to(miss_x, miss_y):
                return False, was_misclick

            self._mouse.press(button)
            time.sleep(click_result.duration)
            self._mouse.release(button)

            # Correction: pause (human reaction time), then click correctly
            correction_delay = self._rng.uniform(
                self._correction_delay[0],
                self._correction_delay[1]
            )
            time.sleep(correction_delay)

            # Recalculate correct position and click
            corrected = self.click_handler.calculate_click(target)
            if not self.move_to(corrected.x, corrected.y):
                return False, was_misclick

            self._mouse.press(button)
            time.sleep(corrected.duration)
            self._mouse.release(button)

            # Post-click drift (subtle hand movement)
            self._post_click_drift()

            return True, was_misclick

        # Check for overshoot/undershoot (5% chance by default)
        if self._rng.random() < overshoot_undershoot_rate:
            return self._click_with_overshoot_undershoot(
                target, x, y, click_result.duration, button
            )

        # Normal click (no misclick or not allowed on this row)
        if not self.move_to(x, y):
            return False, was_misclick

        # Perform click
        self._mouse.press(button)
        time.sleep(click_result.duration)
        self._mouse.release(button)

        # Post-click drift (subtle hand movement)
        self._post_click_drift()

        return True, was_misclick

    def _click_with_overshoot_undershoot(
        self,
        target: ClickTarget,
        target_x: int,
        target_y: int,
        click_duration: float,
        button: Button = Button.left,
    ) -> tuple[bool, bool]:
        """Perform click with overshoot or undershoot correction.

        50% chance of overshooting (going past target), 50% undershooting.
        Then corrects to the actual target position.

        Returns:
            (completed, was_misclick) tuple - was_misclick is always False
        """
        current_pos = self.position

        # Calculate direction vector from current to target
        dx = target_x - current_pos[0]
        dy = target_y - current_pos[1]
        distance = (dx**2 + dy**2) ** 0.5

        if distance < 10:
            # Too close, just do normal click
            if not self.move_to(target_x, target_y):
                return False, False
            self._mouse.press(button)
            time.sleep(click_duration)
            self._mouse.release(button)
            self._post_click_drift()
            return True, False

        # Normalize direction
        norm_dx = dx / distance
        norm_dy = dy / distance

        # Decide overshoot (50%) or undershoot (50%)
        is_overshoot = self._rng.random() < 0.5

        if is_overshoot:
            # Go 10-30 pixels past the target
            extra_dist = self._rng.integers(10, 31)
            stop_x = int(target_x + norm_dx * extra_dist)
            stop_y = int(target_y + norm_dy * extra_dist)
        else:
            # Stop 10-25 pixels short of target
            short_dist = self._rng.integers(10, 26)
            stop_x = int(target_x - norm_dx * short_dist)
            stop_y = int(target_y - norm_dy * short_dist)

        # Move to the wrong position
        if not self.move_to(stop_x, stop_y):
            return False, False

        # Brief pause (realizing we're in wrong spot)
        time.sleep(self._rng.uniform(0.05, 0.15))

        # Correct to actual target
        corrected = self.click_handler.calculate_click(target)
        if not self.move_to(corrected.x, corrected.y, num_points=25):
            return False, False

        # Click at correct position
        self._mouse.press(button)
        time.sleep(click_duration)
        self._mouse.release(button)

        # Post-click drift
        self._post_click_drift()

        return True, False

    def right_click(self) -> bool:
        """Perform a right click at current position."""
        return self.click(Button.right)

    def double_click(self, button: Button = Button.left) -> bool:
        """Perform a double click at current position."""
        if self._stop_flag:
            return False

        if not self.click(button):
            return False

        delay = self.click_handler.calculate_double_click_delay()
        time.sleep(delay)

        return self.click(button)

    def drag_to(
        self,
        x: int,
        y: int,
        button: Button = Button.left,
    ) -> bool:
        """Drag from current position to target.

        Args:
            x: Target x coordinate
            y: Target y coordinate
            button: Mouse button to hold

        Returns:
            True if completed
        """
        if self._stop_flag:
            return False

        self._mouse.press(button)
        time.sleep(0.05)  # Small delay before drag

        result = self.move_to(x, y)

        time.sleep(0.05)  # Small delay before release
        self._mouse.release(button)

        return result

    def accidental_drag_to_adjacent(
        self,
        target: ClickTarget,
        slot_row: int,
        slot_col: int,
        slot_width: int,
        slot_height: int,
        button: Button = Button.left,
    ) -> bool:
        """Accidentally drag item toward an adjacent inventory cell.

        Simulates holding the mouse button too long while clicking,
        resulting in an accidental drag toward a neighboring cell.

        Args:
            target: Click target (the item to accidentally drag)
            slot_row: Current slot row (0-6)
            slot_col: Current slot column (0-3)
            slot_width: Width of inventory slot
            slot_height: Height of inventory slot
            button: Mouse button to use

        Returns:
            True if completed
        """
        if self._stop_flag:
            return False

        # Calculate click position within target
        click_result = self.click_handler.calculate_click(target)
        x, y = click_result.x, click_result.y

        # Move to the item
        if not self.move_to(x, y):
            return False

        # Determine possible adjacent directions (avoid going off-grid)
        directions = []
        if slot_col > 0:
            directions.append((-1, 0))  # Left
        if slot_col < 3:
            directions.append((1, 0))   # Right
        if slot_row > 0:
            directions.append((0, -1))  # Up
        if slot_row < 6:
            directions.append((0, 1))   # Down

        if not directions:
            # Shouldn't happen but fallback to normal click
            self._mouse.press(button)
            time.sleep(click_result.duration)
            self._mouse.release(button)
            return True

        # Pick random adjacent direction
        dx, dy = directions[self._rng.integers(0, len(directions))]

        # Calculate drag distance (partial distance toward adjacent cell)
        # Drag 30-70% of the way to the adjacent cell
        drag_ratio = self._rng.uniform(0.3, 0.7)
        drag_x = int(dx * slot_width * drag_ratio)
        drag_y = int(dy * slot_height * drag_ratio)

        # Press and hold (accidentally holding too long)
        self._mouse.press(button)

        # Brief hold before accidental drag starts
        time.sleep(self._rng.uniform(0.08, 0.15))

        # Drag toward adjacent cell
        if not self.move_to(x + drag_x, y + drag_y, num_points=25):
            self._mouse.release(button)
            return False

        # Release (realizing the mistake)
        self._mouse.release(button)

        # Brief pause (human reaction to mistake)
        time.sleep(self._rng.uniform(0.1, 0.25))

        # Move back and click correctly
        if not self.move_to(x, y, num_points=30):
            return False

        self._mouse.press(button)
        time.sleep(click_result.duration)
        self._mouse.release(button)

        # Post-click drift
        self._post_click_drift()

        return True

    def scroll(self, clicks: int) -> bool:
        """Scroll mouse wheel.

        Args:
            clicks: Number of clicks (positive = up, negative = down)

        Returns:
            True if completed
        """
        if self._stop_flag:
            return False

        self._mouse.scroll(0, clicks)
        return True

    def _point_in_target(self, point: tuple[int, int], target: ClickTarget) -> bool:
        """Check if a point is within the target's bounding box.

        Args:
            point: (x, y) coordinates to check
            target: Click target area

        Returns:
            True if point is within target bounds
        """
        half_w = target.width // 2
        half_h = target.height // 2
        return (
            target.center_x - half_w <= point[0] <= target.center_x + half_w
            and target.center_y - half_h <= point[1] <= target.center_y + half_h
        )

    def swift_click_at_target(
        self,
        target: ClickTarget,
        button: Button = Button.left,
        overshoot_undershoot_rate: float = 0.05,
        follow_through_points: int = 8,
    ) -> tuple[bool, bool]:
        """Move toward target and click while passing through it.

        Clicks as soon as the cursor enters the target bounds, then
        continues moving briefly for a natural follow-through motion.
        Includes occasional hesitation and overshoot for realistic variance.

        Args:
            target: Click target area
            button: Mouse button
            overshoot_undershoot_rate: Probability of overshoot/undershoot
            follow_through_points: Points to continue after clicking

        Returns:
            (completed, was_misclick) - was_misclick always False
        """
        # Optional hesitation before approach (15% chance)
        if self._should_hesitate():
            if not self._perform_hesitation(target):
                return False, False

        # Check for overshoot/undershoot (5% chance by default)
        if self._rng.random() < overshoot_undershoot_rate:
            return self._swift_click_with_overshoot(target, button, follow_through_points)

        # Normal swift click path
        return self._execute_swift_click(target, button, follow_through_points)

    def _execute_swift_click(
        self,
        target: ClickTarget,
        button: Button,
        follow_through_points: int,
    ) -> tuple[bool, bool]:
        """Execute the swift click motion.

        Generates a path that goes PAST the target so we click mid-motion
        while passing through, rather than stopping on the target.

        Args:
            target: Click target area
            button: Mouse button
            follow_through_points: Points to continue after clicking

        Returns:
            (completed, was_misclick) tuple
        """
        # Calculate target position
        click_result = self.click_handler.calculate_click(target)
        target_x, target_y = click_result.x, click_result.y

        start = self.position
        dx = target_x - start[0]
        dy = target_y - start[1]
        distance = (dx**2 + dy**2) ** 0.5

        # For very short distances, fall back to normal click behavior
        if distance < 20:
            if not self.move_to(target_x, target_y):
                return False, False
            self._mouse.press(button)
            time.sleep(click_result.duration)
            self._mouse.release(button)
            return True, False

        # Calculate overshoot destination (20-40 pixels past target)
        norm_dx, norm_dy = dx / distance, dy / distance
        overshoot_dist = self._rng.integers(20, 41)
        dest_x = int(target_x + norm_dx * overshoot_dist)
        dest_y = int(target_y + norm_dy * overshoot_dist)

        # Generate path to overshoot point (passing through target)
        path = self.bezier.generate_path(start, (dest_x, dest_y))
        total_time = self.bezier.calculate_movement_time(start, (dest_x, dest_y))
        delays = self.bezier.get_point_delays(path, total_time)

        # Find first point inside target bounds
        click_index = None
        for i, point in enumerate(path):
            if self._point_in_target(point, target):
                click_index = i
                break

        # Fallback: click at roughly 60% of path (should be near target)
        if click_index is None:
            click_index = int(len(path) * 0.6)

        # Move to click point
        for i in range(click_index + 1):
            if self._stop_flag:
                return False, False
            self._mouse.position = path[i]
            if self._on_move_callback:
                self._on_move_callback(path[i][0], path[i][1])
            if i < len(delays):
                time.sleep(delays[i])

        # Click immediately (shorter hold for swift click)
        self._mouse.press(button)
        time.sleep(click_result.duration * 0.6)
        self._mouse.release(button)

        # Follow-through: continue past the target
        end_index = min(click_index + follow_through_points, len(path))
        for i in range(click_index + 1, end_index):
            if self._stop_flag:
                return True, False  # Click already happened
            self._mouse.position = path[i]
            if self._on_move_callback:
                self._on_move_callback(path[i][0], path[i][1])
            if i < len(delays):
                time.sleep(delays[i] * 0.7)  # Slightly faster follow-through

        return True, False

    def _swift_click_with_overshoot(
        self,
        target: ClickTarget,
        button: Button,
        follow_through_points: int,
    ) -> tuple[bool, bool]:
        """Swift click with overshoot/undershoot correction first.

        Args:
            target: Click target area
            button: Mouse button
            follow_through_points: Points to continue after clicking

        Returns:
            (completed, was_misclick) tuple
        """
        # Calculate direction and overshoot position
        click_result = self.click_handler.calculate_click(target)
        target_x, target_y = click_result.x, click_result.y
        current = self.position

        dx = target_x - current[0]
        dy = target_y - current[1]
        distance = (dx**2 + dy**2) ** 0.5

        if distance < 10:
            # Too close, just do normal swift click
            return self._execute_swift_click(target, button, follow_through_points)

        norm_dx, norm_dy = dx / distance, dy / distance

        if self._rng.random() < 0.5:  # Overshoot
            extra = self._rng.integers(10, 31)
            stop_x = int(target_x + norm_dx * extra)
            stop_y = int(target_y + norm_dy * extra)
        else:  # Undershoot
            short = self._rng.integers(10, 26)
            stop_x = int(target_x - norm_dx * short)
            stop_y = int(target_y - norm_dy * short)

        # Move to wrong position
        if not self.move_to(stop_x, stop_y):
            return False, False

        # Brief pause realizing we're wrong
        time.sleep(self._rng.uniform(0.05, 0.15))

        # Now do swift click to correct position
        return self._execute_swift_click(target, button, follow_through_points)
