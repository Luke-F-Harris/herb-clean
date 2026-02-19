"""Login handler - detects logout and performs re-login sequence."""

import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Optional

import numpy as np

if TYPE_CHECKING:
    from ..vision.screen_capture import ScreenCapture
    from ..vision.template_matcher import TemplateMatcher
    from ..input.mouse_controller import MouseController
    from ..input.click_handler import ClickTarget


class LoginState(Enum):
    """Possible login states."""

    LOGGED_IN = "logged_in"  # In-game, playing
    INACTIVITY_LOGOUT = "inactivity_logout"  # Disconnected dialog shown
    PLAY_NOW_SCREEN = "play_now_screen"  # Welcome screen with Play Now
    LOGGED_IN_SCREEN = "logged_in_screen"  # Account select with Click Here To Play
    LOGGING_IN = "logging_in"  # Loading/connecting
    UNKNOWN = "unknown"


@dataclass
class LoginConfig:
    """Configuration for login handling."""

    # Wait times after button clicks (seconds)
    wait_after_ok_click: tuple[float, float] = (2.0, 4.0)
    wait_after_play_now_click: tuple[float, float] = (2.0, 5.0)
    wait_after_play_click: tuple[float, float] = (3.0, 6.0)

    # Detection retry settings
    max_retries: int = 10
    retry_delay: tuple[float, float] = (1.0, 2.0)

    # Template names
    ok_button_template: str = "inactivity_logout_ok_button.png"
    play_now_template: str = "play_now_button.png"
    play_button_template: str = "logged_in_play_button.png"


class LoginHandler:
    """Handles logout detection and re-login sequence."""

    def __init__(
        self,
        screen: "ScreenCapture",
        template_matcher: "TemplateMatcher",
        mouse: "MouseController",
        config: Optional[LoginConfig] = None,
    ):
        """Initialize login handler.

        Args:
            screen: Screen capture instance
            template_matcher: Template matcher instance
            mouse: Mouse controller instance
            config: Login configuration
        """
        self._logger = logging.getLogger(__name__)
        self._screen = screen
        self._template_matcher = template_matcher
        self._mouse = mouse
        self.config = config or LoginConfig()
        self._rng = np.random.default_rng()

        # Track login attempts
        self._login_attempts = 0
        self._last_logout_time: Optional[float] = None

    def detect_login_state(self) -> LoginState:
        """Detect current login state by checking for UI elements.

        Returns:
            Current LoginState
        """
        screen_image = self._screen.capture_window()
        if screen_image is None:
            return LoginState.UNKNOWN

        # Check for inactivity logout dialog (OK button visible)
        ok_match = self._template_matcher.match(
            screen_image, self.config.ok_button_template
        )
        if ok_match.found:
            self._logger.debug("Detected: Inactivity logout dialog")
            return LoginState.INACTIVITY_LOGOUT

        # Check for Play Now screen
        play_now_match = self._template_matcher.match(
            screen_image, self.config.play_now_template
        )
        if play_now_match.found:
            self._logger.debug("Detected: Play Now screen")
            return LoginState.PLAY_NOW_SCREEN

        # Check for logged in screen (Click Here To Play)
        play_match = self._template_matcher.match(
            screen_image, self.config.play_button_template
        )
        if play_match.found:
            self._logger.debug("Detected: Logged in screen")
            return LoginState.LOGGED_IN_SCREEN

        # If none of the login screens are visible, assume logged in
        return LoginState.LOGGED_IN

    def is_logged_out(self) -> bool:
        """Check if we're logged out.

        Returns:
            True if any logout state is detected
        """
        state = self.detect_login_state()
        return state in (
            LoginState.INACTIVITY_LOGOUT,
            LoginState.PLAY_NOW_SCREEN,
            LoginState.LOGGED_IN_SCREEN,
        )

    def perform_relogin(self) -> bool:
        """Perform the full re-login sequence.

        Sequence:
        1. If inactivity logout -> click OK
        2. If play now screen -> click Play Now
        3. If logged in screen -> click Click Here To Play
        4. Wait for game to load

        Returns:
            True if successfully logged back in
        """
        self._login_attempts += 1
        self._last_logout_time = time.time()
        self._logger.info("Starting re-login sequence (attempt #%d)", self._login_attempts)

        for attempt in range(self.config.max_retries):
            state = self.detect_login_state()
            self._logger.debug("Login state: %s (attempt %d)", state.value, attempt + 1)

            if state == LoginState.LOGGED_IN:
                self._logger.info("Successfully logged back in!")
                return True

            elif state == LoginState.INACTIVITY_LOGOUT:
                if not self._click_ok_button():
                    self._logger.warning("Failed to click OK button")
                else:
                    # Wait for screen transition
                    wait = self._rng.uniform(*self.config.wait_after_ok_click)
                    self._logger.debug("Waiting %.1fs after OK click", wait)
                    time.sleep(wait)

            elif state == LoginState.PLAY_NOW_SCREEN:
                if not self._click_play_now_button():
                    self._logger.warning("Failed to click Play Now button")
                else:
                    # Wait for screen transition
                    wait = self._rng.uniform(*self.config.wait_after_play_now_click)
                    self._logger.debug("Waiting %.1fs after Play Now click", wait)
                    time.sleep(wait)

            elif state == LoginState.LOGGED_IN_SCREEN:
                if not self._click_play_button():
                    self._logger.warning("Failed to click Play button")
                else:
                    # Wait for game to load
                    wait = self._rng.uniform(*self.config.wait_after_play_click)
                    self._logger.debug("Waiting %.1fs after Play click", wait)
                    time.sleep(wait)

            elif state == LoginState.LOGGING_IN:
                # Just wait for loading
                wait = self._rng.uniform(*self.config.retry_delay)
                time.sleep(wait)

            else:
                # Unknown state, wait and retry
                wait = self._rng.uniform(*self.config.retry_delay)
                time.sleep(wait)

        self._logger.error("Re-login failed after %d attempts", self.config.max_retries)
        return False

    def _click_ok_button(self) -> bool:
        """Click the OK button on inactivity logout dialog.

        Returns:
            True if click completed
        """
        screen_image = self._screen.capture_window()
        if screen_image is None:
            return False

        match = self._template_matcher.match(
            screen_image, self.config.ok_button_template
        )
        if not match.found:
            return False

        # Get screen coordinates
        bounds = self._screen.window_bounds
        if not bounds:
            return False

        screen_x = bounds.x + match.center_x
        screen_y = bounds.y + match.center_y

        self._logger.info("Clicking OK button at (%d, %d)", screen_x, screen_y)

        # Click with some randomization
        self._click_with_variation(screen_x, screen_y, match.width, match.height)
        return True

    def _click_play_now_button(self) -> bool:
        """Click the Play Now button.

        Returns:
            True if click completed
        """
        screen_image = self._screen.capture_window()
        if screen_image is None:
            return False

        match = self._template_matcher.match(
            screen_image, self.config.play_now_template
        )
        if not match.found:
            return False

        bounds = self._screen.window_bounds
        if not bounds:
            return False

        screen_x = bounds.x + match.center_x
        screen_y = bounds.y + match.center_y

        self._logger.info("Clicking Play Now button at (%d, %d)", screen_x, screen_y)

        self._click_with_variation(screen_x, screen_y, match.width, match.height)
        return True

    def _click_play_button(self) -> bool:
        """Click the Click Here To Play button.

        Returns:
            True if click completed
        """
        screen_image = self._screen.capture_window()
        if screen_image is None:
            return False

        match = self._template_matcher.match(
            screen_image, self.config.play_button_template
        )
        if not match.found:
            return False

        bounds = self._screen.window_bounds
        if not bounds:
            return False

        screen_x = bounds.x + match.center_x
        screen_y = bounds.y + match.center_y

        self._logger.info("Clicking Play button at (%d, %d)", screen_x, screen_y)

        self._click_with_variation(screen_x, screen_y, match.width, match.height)
        return True

    def _click_with_variation(
        self, center_x: int, center_y: int, width: int, height: int
    ) -> None:
        """Click at position with human-like variation.

        Args:
            center_x: Center X coordinate
            center_y: Center Y coordinate
            width: Button width for offset bounds
            height: Button height for offset bounds
        """
        # Add small random offset within button bounds
        offset_x = self._rng.integers(-width // 4, width // 4 + 1)
        offset_y = self._rng.integers(-height // 4, height // 4 + 1)

        target_x = center_x + offset_x
        target_y = center_y + offset_y

        # Move and click
        self._mouse.move_to(target_x, target_y)

        # Small delay before click (human-like)
        time.sleep(self._rng.uniform(0.1, 0.3))

        self._mouse.click()

    def get_login_attempts(self) -> int:
        """Get number of login attempts this session.

        Returns:
            Login attempt count
        """
        return self._login_attempts

    def get_last_logout_time(self) -> Optional[float]:
        """Get timestamp of last detected logout.

        Returns:
            Unix timestamp or None
        """
        return self._last_logout_time

    def reset_stats(self) -> None:
        """Reset login statistics."""
        self._login_attempts = 0
        self._last_logout_time = None
