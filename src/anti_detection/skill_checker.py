"""Skill checker - periodically check herblore skill for human-like behavior."""

import logging
import time
from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from ..input.keyboard_controller import KeyboardController
    from ..input.mouse_controller import MouseController
    from ..vision.screen_capture import ScreenCapture
    from ..vision.template_matcher import TemplateMatcher


@dataclass
class SkillCheckConfig:
    """Configuration for skill checking."""

    enabled: bool = True
    cooldown_interval: tuple[float, float] = (600, 900)  # 10-15 minutes
    hover_duration: tuple[float, float] = (3.0, 8.0)  # 3-8 seconds


class SkillChecker:
    """Periodically check herblore skill to simulate human curiosity."""

    def __init__(
        self,
        config: Optional[SkillCheckConfig] = None,
        keyboard: Optional["KeyboardController"] = None,
        mouse: Optional["MouseController"] = None,
        screen: Optional["ScreenCapture"] = None,
        template_matcher: Optional["TemplateMatcher"] = None,
    ):
        """Initialize skill checker.

        Args:
            config: Skill check configuration
            keyboard: Keyboard controller for tab switching
            mouse: Mouse controller for hovering
            screen: Screen capture for getting window bounds
            template_matcher: Template matcher for finding UI elements
        """
        self._logger = logging.getLogger(__name__)
        self.config = config or SkillCheckConfig()
        self._keyboard = keyboard
        self._mouse = mouse
        self._screen = screen
        self._template_matcher = template_matcher
        self._rng = np.random.default_rng()

        # Track when next check should occur
        self._next_check_time = self._schedule_next_check()
        self._check_count = 0

    def _schedule_next_check(self) -> float:
        """Schedule the next skill check.

        Returns:
            Unix timestamp for next check
        """
        interval = self._rng.uniform(
            self.config.cooldown_interval[0],
            self.config.cooldown_interval[1]
        )
        return time.time() + interval

    def should_check(self) -> bool:
        """Check if it's time to check the skill.

        Returns:
            True if skill check should be performed
        """
        if not self.config.enabled:
            return False

        return time.time() >= self._next_check_time

    def perform_skill_check(self) -> bool:
        """Perform a skill check by opening skills tab and hovering over herblore.

        Steps:
        1. Press F2 (skills tab)
        2. Wait for tab to open
        3. Move mouse to herblore skill position
        4. Hover for 3-8 seconds
        5. Press F3 (inventory tab)
        6. Reset cooldown timer

        Returns:
            True if check completed successfully
        """
        if not self._keyboard:
            self._logger.warning("No keyboard controller, skipping skill check")
            return False

        self._logger.info("Checking herblore skill (check #%d)", self._check_count + 1)

        # Pre-action delay (thinking pause before checking skill)
        pre_delay = self._rng.uniform(0.2, 0.5)
        time.sleep(pre_delay)

        # Step 1: Press F2 to open skills tab
        if not self._keyboard.press_f_key(2, pre_delay=True):
            self._logger.warning("Failed to press F2")
            return False

        # Wait for tab animation
        tab_switch_delay = self._rng.uniform(0.15, 0.30)
        time.sleep(tab_switch_delay)

        # Step 2: Move mouse to herblore skill position
        # Herblore is in the skills panel - approximate position relative to panel
        # Skills panel is typically on the right side of the screen
        if self._mouse and self._screen:
            herblore_pos = self._get_herblore_position()
            if herblore_pos:
                self._mouse.move_to(herblore_pos[0], herblore_pos[1])

        # Step 3: Hover for random duration (3-8 seconds)
        hover_duration = self._rng.uniform(
            self.config.hover_duration[0],
            self.config.hover_duration[1]
        )
        self._logger.debug("Hovering over herblore skill for %.1fs", hover_duration)

        # During hover, occasionally make small idle movements
        self._perform_hover_with_idle_movements(hover_duration)

        # Step 4: Press F3 to return to inventory tab
        if not self._keyboard.press_f_key(3, pre_delay=True):
            self._logger.warning("Failed to press F3")
            # Still count as completed since we did check the skill
            pass

        # Wait for tab to switch back
        return_delay = self._rng.uniform(0.1, 0.25)
        time.sleep(return_delay)

        # Step 5: Reset cooldown timer
        self._next_check_time = self._schedule_next_check()
        self._check_count += 1

        self._logger.info("Skill check complete, next in %.1f minutes",
                         (self._next_check_time - time.time()) / 60)

        return True

    def _get_herblore_position(self) -> Optional[tuple[int, int]]:
        """Get screen position of herblore skill icon.

        The skills tab has a 3x8 grid layout. Herblore is skill #16 (row 5, col 1).
        Position is relative to the skills panel which is on the right side.

        Returns:
            (x, y) screen coordinates or None if cannot determine
        """
        if not self._screen:
            return None

        bounds = self._screen.window_bounds
        if not bounds:
            return None

        # Skills panel is on the right side of the game window
        # Standard fixed-size client: 765x503
        # Skills panel starts around x=550, y=210
        # Each skill icon is approximately 58x32 pixels in a 3-column layout
        # Herblore is row 5 (0-indexed), column 0

        # Skills panel position (relative to window)
        panel_x = 550
        panel_y = 210

        # Skill slot dimensions
        skill_width = 58
        skill_height = 32

        # Herblore position: row 5, column 0 (0-indexed)
        # Skills are ordered: Attack, Strength, Defence, Ranged, Prayer, Magic,
        # Runecraft, Construction, Hitpoints, Agility, Herblore, ...
        # Row 0: Attack, Hitpoints, Mining
        # Row 1: Strength, Agility, Smithing
        # Row 2: Defence, Herblore, Fishing
        # Herblore is row 2, column 1

        herblore_row = 2
        herblore_col = 1

        # Calculate center of herblore skill
        skill_x = panel_x + (herblore_col * skill_width) + (skill_width // 2)
        skill_y = panel_y + (herblore_row * skill_height) + (skill_height // 2)

        # Add window offset
        screen_x = bounds.x + skill_x
        screen_y = bounds.y + skill_y

        # Add small random offset for human-like targeting
        offset_x = self._rng.integers(-8, 9)
        offset_y = self._rng.integers(-5, 6)

        return (screen_x + offset_x, screen_y + offset_y)

    def _perform_hover_with_idle_movements(self, duration: float) -> None:
        """Hover at current position with occasional idle movements.

        Args:
            duration: Total hover duration in seconds
        """
        start_time = time.time()
        end_time = start_time + duration

        while time.time() < end_time:
            remaining = end_time - time.time()
            if remaining <= 0:
                break

            # Wait for a portion of the remaining time
            wait_time = min(self._rng.uniform(0.5, 1.5), remaining)
            time.sleep(wait_time)

            # Occasionally make tiny idle movement (10% chance)
            if self._mouse and self._rng.random() < 0.10:
                dx = self._rng.integers(-3, 4)
                dy = self._rng.integers(-3, 4)
                current_pos = self._mouse.get_position()
                self._mouse.move_to(current_pos[0] + dx, current_pos[1] + dy)

    def get_check_count(self) -> int:
        """Get number of skill checks performed.

        Returns:
            Check count
        """
        return self._check_count

    def time_until_next_check(self) -> float:
        """Get time until next skill check.

        Returns:
            Seconds until next check
        """
        return max(0, self._next_check_time - time.time())

    def reset(self) -> None:
        """Reset the skill checker state."""
        self._next_check_time = self._schedule_next_check()
        self._check_count = 0

    def get_status(self) -> dict:
        """Get current skill checker status.

        Returns:
            Dict with status information
        """
        return {
            "enabled": self.config.enabled,
            "check_count": self._check_count,
            "time_until_next_check_seconds": self.time_until_next_check(),
            "next_check_time": self._next_check_time,
        }
