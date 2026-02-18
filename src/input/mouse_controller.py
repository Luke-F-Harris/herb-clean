"""Mouse movement orchestration using pynput."""

import time
from typing import Optional, Callable

from pynput.mouse import Button, Controller as MouseDriver

from .bezier_movement import BezierMovement, MovementConfig
from .click_handler import ClickHandler, ClickConfig, ClickTarget


class MouseController:
    """Orchestrate human-like mouse movement and clicks."""

    def __init__(
        self,
        movement_config: Optional[MovementConfig] = None,
        click_config: Optional[ClickConfig] = None,
    ):
        """Initialize mouse controller.

        Args:
            movement_config: Bezier movement configuration
            click_config: Click handling configuration
        """
        self._mouse = MouseDriver()
        self.bezier = BezierMovement(movement_config)
        self.click_handler = ClickHandler(click_config)
        self._stop_flag = False
        self._on_move_callback: Optional[Callable[[int, int], None]] = None

    @property
    def position(self) -> tuple[int, int]:
        """Get current mouse position."""
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

    def click_at_target(
        self,
        target: ClickTarget,
        button: Button = Button.left,
        misclick_rate: float = 0.0,
    ) -> tuple[bool, bool]:
        """Move to target and click with randomization.

        Args:
            target: Click target area
            button: Mouse button
            misclick_rate: Probability of misclick

        Returns:
            (completed, was_misclick) tuple
        """
        # Calculate click position
        click_result = self.click_handler.calculate_click(target)

        # Check for misclick
        was_misclick = False
        x, y = click_result.x, click_result.y

        if self.click_handler.should_misclick(misclick_rate):
            offset = self.click_handler.calculate_misclick_offset()
            x += offset[0]
            y += offset[1]
            was_misclick = True

        # Move and click
        if not self.move_to(x, y):
            return False, was_misclick

        # Perform click
        self._mouse.press(button)
        time.sleep(click_result.duration)
        self._mouse.release(button)

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
