"""Skill checker - periodically check herblore skill for human-like behavior."""

import logging
import time
from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING

import cv2
import numpy as np

from ..utils import create_rng

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
        self._rng = create_rng()

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
        1. Click skills tab icon
        2. Wait for tab to open
        3. Move mouse to herblore skill position
        4. Hover for 3-8 seconds
        5. Click inventory tab icon
        6. Reset cooldown timer

        Returns:
            True if check completed successfully
        """
        if not self._mouse:
            self._logger.warning("No mouse controller, skipping skill check")
            return False

        self._logger.info("Checking herblore skill (check #%d)", self._check_count + 1)

        # Pre-action delay (thinking pause before checking skill)
        pre_delay = self._rng.uniform(0.2, 0.5)
        time.sleep(pre_delay)

        # Step 1: Click skills tab icon to open skills tab
        skills_tab_pos = self._get_skills_tab_position()
        if skills_tab_pos:
            self._mouse.click_at(skills_tab_pos[0], skills_tab_pos[1])
        else:
            self._logger.warning("Failed to get skills tab position")
            return False

        # Wait for tab animation
        tab_switch_delay = self._rng.uniform(0.15, 0.30)
        time.sleep(tab_switch_delay)

        # Step 2: Move mouse to herblore skill position
        # Herblore is in the skills panel - approximate position relative to panel
        # Skills panel is typically on the right side of the screen
        if self._screen:
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

        # Step 4: Click inventory tab icon to return
        inventory_tab_pos = self._get_inventory_tab_position()
        if inventory_tab_pos:
            self._mouse.click_at(inventory_tab_pos[0], inventory_tab_pos[1])
        else:
            self._logger.warning("Failed to get inventory tab position")
            # Still count as completed since we did check the skill

        # Wait for tab to switch back
        return_delay = self._rng.uniform(0.1, 0.25)
        time.sleep(return_delay)

        # Step 5: Reset cooldown timer
        self._next_check_time = self._schedule_next_check()
        self._check_count += 1

        self._logger.info("Skill check complete, next in %.1f minutes",
                         (self._next_check_time - time.time()) / 60)

        return True

    def _detect_ui_element(
        self,
        template_name: str,
        fallback_x_ratio: float,
        fallback_y_ratio: float,
    ) -> Optional[tuple[int, int]]:
        """Detect a UI element using template matching with fallback.

        Args:
            template_name: Template image filename (e.g., "skills_tab.png")
            fallback_x_ratio: X position as ratio of window width (0.0-1.0)
            fallback_y_ratio: Y position as ratio of window height (0.0-1.0)

        Returns:
            (x, y) window-relative coordinates or None if cannot determine
        """
        if not self._screen:
            return None

        # Try template matching first
        if self._template_matcher:
            screen_image = self._screen.capture_window()
            if screen_image is not None:
                match = self._template_matcher.match(screen_image, template_name)
                if match.found:
                    self._logger.debug(
                        "Template %s found at (%d, %d) with confidence %.2f",
                        template_name, match.center_x, match.center_y, match.confidence
                    )
                    return (match.center_x, match.center_y)

        # Fallback to proportional position
        bounds = self._screen.window_bounds
        if not bounds:
            return None

        fallback_x = int(bounds.width * fallback_x_ratio)
        fallback_y = int(bounds.height * fallback_y_ratio)
        self._logger.debug(
            "Using fallback position for %s: (%d, %d)",
            template_name, fallback_x, fallback_y
        )
        return (fallback_x, fallback_y)

    def _get_herblore_position(self) -> Optional[tuple[int, int]]:
        """Get screen position of herblore skill icon.

        Uses template matching to find the herblore skill icon, with fallback
        to proportional position based on window size.

        Returns:
            (x, y) screen coordinates or None if cannot determine
        """
        if not self._screen:
            return None

        bounds = self._screen.window_bounds
        if not bounds:
            return None

        # Herblore position: 67.1% horizontal, 34.4% vertical (measured from 1208x802)
        pos = self._detect_ui_element("herblore_skill.png", 0.671, 0.344)
        if not pos:
            return None

        # Add window offset to convert to screen coordinates
        screen_x = bounds.x + pos[0]
        screen_y = bounds.y + pos[1]

        # Add small random offset for human-like targeting
        offset_x = self._rng.integers(-8, 9)
        offset_y = self._rng.integers(-5, 6)

        return (screen_x + offset_x, screen_y + offset_y)

    def _get_skills_tab_position(self) -> Optional[tuple[int, int]]:
        """Get screen position of skills tab icon.

        Uses template matching to find the skills tab icon, with fallback
        to proportional position based on window size.

        Returns:
            (x, y) screen coordinates or None if cannot determine
        """
        if not self._screen:
            return None

        bounds = self._screen.window_bounds
        if not bounds:
            return None

        # Skills tab position: 63.4% horizontal, 24.7% vertical (measured from 1208x802)
        pos = self._detect_ui_element("skills_tab.png", 0.634, 0.247)
        if not pos:
            return None

        # Add window offset to convert to screen coordinates
        screen_x = bounds.x + pos[0]
        screen_y = bounds.y + pos[1]

        # Add small random offset for human-like targeting
        offset_x = self._rng.integers(-5, 6)
        offset_y = self._rng.integers(-5, 6)

        return (screen_x + offset_x, screen_y + offset_y)

    def _get_inventory_tab_position(self) -> Optional[tuple[int, int]]:
        """Get screen position of inventory tab icon.

        Uses template matching to find the inventory tab icon, with fallback
        to proportional position based on window size.

        Returns:
            (x, y) screen coordinates or None if cannot determine
        """
        if not self._screen:
            return None

        bounds = self._screen.window_bounds
        if not bounds:
            return None

        # Inventory tab position: 71.6% horizontal, 24.7% vertical (measured from 1208x802)
        pos = self._detect_ui_element("inventory_tab.png", 0.716, 0.247)
        if not pos:
            return None

        # Add window offset to convert to screen coordinates
        screen_x = bounds.x + pos[0]
        screen_y = bounds.y + pos[1]

        # Add small random offset for human-like targeting
        offset_x = self._rng.integers(-5, 6)
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
