"""Mouse movement orchestration using pynput."""

import time
from typing import Optional, Callable

import numpy as np
from pynput.mouse import Button, Controller as MouseDriver

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
        self._rng = np.random.default_rng()

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
    ) -> tuple[bool, bool]:
        """Move to target and click with randomization.

        Args:
            target: Click target area
            button: Mouse button
            misclick_rate: Probability of misclick
            slot_row: Inventory row (0-6) for row-aware misclick correction

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
