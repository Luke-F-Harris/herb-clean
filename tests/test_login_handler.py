#!/usr/bin/env python3
"""Test script for LoginHandler - manually test login detection and re-login.

Run from osrs_herblore directory:
    python tests/test_login_handler.py           # Detection only (safe)
    python tests/test_login_handler.py --relogin # Actually perform re-login clicks
"""

import argparse
import logging
import sys
import time
from pathlib import Path

import numpy as np
import yaml

# Add src to path (go up to project root, then into src)
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from vision.screen_capture import ScreenCapture
from vision.template_matcher import TemplateMatcher
from input.mouse_controller import MouseController
from input.bezier_movement import MovementConfig
from input.click_handler import ClickConfig


# Inline LoginState enum to avoid relative import issues
from enum import Enum
from dataclasses import dataclass
from typing import Optional


class LoginState(Enum):
    """Possible login states."""
    LOGGED_IN = "logged_in"
    INACTIVITY_LOGOUT = "inactivity_logout"
    PLAY_NOW_SCREEN = "play_now_screen"
    LOGGED_IN_SCREEN = "logged_in_screen"
    LOGGING_IN = "logging_in"
    UNKNOWN = "unknown"


@dataclass
class LoginConfig:
    """Configuration for login handling."""
    # Polling settings - check every interval until state changes or timeout
    poll_interval: float = 1.0  # Check every 1 second
    state_change_timeout: float = 30.0  # Max wait for state to change (server connection can be slow)

    max_retries: int = 10

    # Template names
    ok_button_template: str = "inactivity_logout_ok_button.png"
    play_now_template: str = "play_now_button.png"
    play_button_template: str = "logged_in_play_button.png"


class LoginHandlerTest:
    """Test version of LoginHandler that avoids relative imports."""

    def __init__(
        self,
        screen: ScreenCapture,
        template_matcher: TemplateMatcher,
        mouse: MouseController,
        config: Optional[LoginConfig] = None,
    ):
        self._logger = logging.getLogger(__name__)
        self._screen = screen
        self._template_matcher = template_matcher
        self._mouse = mouse
        self.config = config or LoginConfig()
        self._rng = np.random.default_rng()
        self._login_attempts = 0
        self._last_logout_time: Optional[float] = None

    def detect_login_state(self, save_debug: bool = False) -> LoginState:
        """Detect current login state by checking for UI elements."""
        screen_image = self._screen.capture_window()
        if screen_image is None:
            self._logger.warning("Could not capture screen!")
            return LoginState.UNKNOWN

        # Optionally save screenshot for debugging
        if save_debug:
            import cv2
            debug_path = project_root / "tests" / "debug_output" / "login_state_screen.png"
            debug_path.parent.mkdir(parents=True, exist_ok=True)
            cv2.imwrite(str(debug_path), screen_image)
            self._logger.info("Saved debug screenshot to: %s", debug_path)

        # Check for inactivity logout dialog (OK button visible)
        ok_match = self._template_matcher.match(
            screen_image, self.config.ok_button_template
        )
        self._logger.debug("OK button match: found=%s, confidence=%.3f",
                          ok_match.found, ok_match.confidence)
        if ok_match.found:
            self._logger.info("Detected: Inactivity logout dialog (conf=%.3f)", ok_match.confidence)
            return LoginState.INACTIVITY_LOGOUT

        # Check for Play Now screen
        play_now_match = self._template_matcher.match(
            screen_image, self.config.play_now_template
        )
        self._logger.debug("Play Now match: found=%s, confidence=%.3f",
                          play_now_match.found, play_now_match.confidence)
        if play_now_match.found:
            self._logger.info("Detected: Play Now screen (conf=%.3f)", play_now_match.confidence)
            return LoginState.PLAY_NOW_SCREEN

        # Check for logged in screen (Click Here To Play)
        play_match = self._template_matcher.match(
            screen_image, self.config.play_button_template
        )
        self._logger.debug("Play button match: found=%s, confidence=%.3f",
                          play_match.found, play_match.confidence)
        if play_match.found:
            self._logger.info("Detected: Logged in screen (conf=%.3f)", play_match.confidence)
            return LoginState.LOGGED_IN_SCREEN

        self._logger.debug("No login screens detected - assuming LOGGED_IN")
        return LoginState.LOGGED_IN

    def is_logged_out(self) -> bool:
        """Check if we're logged out."""
        state = self.detect_login_state()
        return state in (
            LoginState.INACTIVITY_LOGOUT,
            LoginState.PLAY_NOW_SCREEN,
            LoginState.LOGGED_IN_SCREEN,
        )

    def _wait_for_state_change(
        self,
        current_state: LoginState,
        save_debug: bool = False
    ) -> LoginState:
        """Poll until state changes from current_state or timeout.

        For LOGGED_IN state, requires 3 consecutive confirmations to avoid
        false positives during loading screens where no templates match.

        Args:
            current_state: The state we're waiting to change from
            save_debug: Whether to save debug screenshots

        Returns:
            The new state (may be same as current if timeout)
        """
        start_time = time.time()
        poll_count = 0
        logged_in_confirmations = 0
        REQUIRED_CONFIRMATIONS = 3  # Need 3 consecutive LOGGED_IN to confirm

        while (time.time() - start_time) < self.config.state_change_timeout:
            poll_count += 1
            time.sleep(self.config.poll_interval)

            new_state = self.detect_login_state(save_debug=save_debug)
            elapsed = time.time() - start_time

            if new_state != current_state:
                # State changed - but if it's LOGGED_IN, we need to confirm
                if new_state == LoginState.LOGGED_IN:
                    logged_in_confirmations += 1
                    self._logger.debug(
                        "LOGGED_IN detected (%d/%d confirmations, %.1fs elapsed)",
                        logged_in_confirmations, REQUIRED_CONFIRMATIONS, elapsed
                    )
                    if logged_in_confirmations >= REQUIRED_CONFIRMATIONS:
                        self._logger.info(
                            "State confirmed: %s -> %s (after %.1fs, %d polls)",
                            current_state.value, new_state.value, elapsed, poll_count
                        )
                        return new_state
                    # Not enough confirmations yet, keep polling
                    continue
                else:
                    # Valid new state (not LOGGED_IN), return immediately
                    logged_in_confirmations = 0  # Reset counter
                    self._logger.info(
                        "State changed: %s -> %s (after %.1fs, %d polls)",
                        current_state.value, new_state.value, elapsed, poll_count
                    )
                    return new_state
            else:
                # Still in same state
                logged_in_confirmations = 0  # Reset if we go back to current state
                self._logger.debug(
                    "Still in state %s (%.1fs elapsed, poll %d)",
                    current_state.value, elapsed, poll_count
                )

        self._logger.warning(
            "Timeout waiting for state change from %s (%.1fs)",
            current_state.value, self.config.state_change_timeout
        )
        return self.detect_login_state(save_debug=save_debug)

    def perform_relogin(self, save_debug: bool = False) -> bool:
        """Perform the full re-login sequence."""
        self._login_attempts += 1
        self._last_logout_time = time.time()
        self._logger.info("Starting re-login sequence (attempt #%d)", self._login_attempts)

        for attempt in range(self.config.max_retries):
            # Detect current state
            state = self.detect_login_state(save_debug=save_debug)
            self._logger.info("Login state: %s (attempt %d/%d)", state.value, attempt + 1, self.config.max_retries)

            if state == LoginState.LOGGED_IN:
                self._logger.info("Successfully logged back in!")
                return True

            elif state == LoginState.INACTIVITY_LOGOUT:
                if not self._click_button(self.config.ok_button_template, "OK"):
                    self._logger.warning("Failed to click OK button")
                else:
                    # Poll until state changes from INACTIVITY_LOGOUT
                    self._wait_for_state_change(LoginState.INACTIVITY_LOGOUT, save_debug)

            elif state == LoginState.PLAY_NOW_SCREEN:
                if not self._click_button(self.config.play_now_template, "Play Now"):
                    self._logger.warning("Failed to click Play Now button")
                else:
                    # Poll until state changes from PLAY_NOW_SCREEN
                    # This waits through the "Connecting to server..." loading
                    self._wait_for_state_change(LoginState.PLAY_NOW_SCREEN, save_debug)

            elif state == LoginState.LOGGED_IN_SCREEN:
                if not self._click_button(self.config.play_button_template, "Play"):
                    self._logger.warning("Failed to click Play button")
                else:
                    # Poll until state changes from LOGGED_IN_SCREEN
                    self._wait_for_state_change(LoginState.LOGGED_IN_SCREEN, save_debug)

            elif state == LoginState.LOGGING_IN:
                # Already in a loading state, just poll for change
                self._wait_for_state_change(LoginState.LOGGING_IN, save_debug)

            else:
                # Unknown state, wait a bit and retry
                time.sleep(self.config.poll_interval)

        self._logger.error("Re-login failed after %d attempts", self.config.max_retries)
        return False

    def _click_button(self, template_name: str, button_name: str) -> bool:
        """Click a button found by template matching."""
        screen_image = self._screen.capture_window()
        if screen_image is None:
            return False

        match = self._template_matcher.match(screen_image, template_name)
        if not match.found:
            return False

        bounds = self._screen.window_bounds
        if not bounds:
            return False

        screen_x = bounds.x + match.center_x
        screen_y = bounds.y + match.center_y

        self._logger.info("Clicking %s button at (%d, %d)", button_name, screen_x, screen_y)

        # Add small random offset
        offset_x = self._rng.integers(-match.width // 4, match.width // 4 + 1)
        offset_y = self._rng.integers(-match.height // 4, match.height // 4 + 1)

        target_x = screen_x + offset_x
        target_y = screen_y + offset_y

        self._mouse.move_to(target_x, target_y)
        time.sleep(self._rng.uniform(0.1, 0.3))
        self._mouse.click()

        return True


def load_config():
    """Load configuration from YAML file."""
    config_path = project_root / "config" / "default_config.yaml"
    if not config_path.exists():
        print(f"Config not found: {config_path}")
        return {}
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def setup_logging(verbose: bool = False) -> None:
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Test LoginHandler")
    parser.add_argument("-v", "--verbose", action="store_true", help="Debug logging")
    parser.add_argument("--relogin", action="store_true", help="Actually perform re-login (clicks mouse)")
    parser.add_argument("--debug", action="store_true", help="Save debug screenshots to tests/debug_output/")
    args = parser.parse_args()

    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)

    logger.info("=" * 50)
    logger.info("LoginHandler Test")
    logger.info("=" * 50)

    # Load config
    config = load_config()
    if not config:
        return 1

    window_cfg = config.get("window", {})
    vision_cfg = config.get("vision", {})
    mouse_cfg = config.get("mouse", {})

    templates_dir = project_root / "config" / "templates"
    logger.info("Templates dir: %s", templates_dir)

    # Screen capture
    screen = ScreenCapture(window_cfg.get("title", "RuneLite"))
    if not screen.find_window():
        logger.error("Could not find RuneLite window!")
        return 1
    logger.info("Found window at: %s", screen.window_bounds)

    # Template matcher
    template_matcher = TemplateMatcher(
        templates_dir=templates_dir,
        confidence_threshold=vision_cfg.get("confidence_threshold", 0.80),
        multi_scale=vision_cfg.get("multi_scale", True),
        scale_range=tuple(vision_cfg.get("scale_range", [0.8, 1.2])),
        scale_steps=vision_cfg.get("scale_steps", 5),
    )

    # Mouse controller
    mouse = MouseController(
        movement_config=MovementConfig(
            speed_range=tuple(mouse_cfg.get("speed_range", [800, 1400])),
        ),
        click_config=ClickConfig(),
    )

    # Login handler
    login_handler = LoginHandlerTest(
        screen=screen,
        template_matcher=template_matcher,
        mouse=mouse,
        config=LoginConfig(),
    )

    # Detect current state
    logger.info("-" * 40)
    state = login_handler.detect_login_state(save_debug=args.debug)
    logger.info("Current login state: %s", state.value)
    logger.info("Is logged out: %s", login_handler.is_logged_out())

    # Show what would happen
    if state == LoginState.LOGGED_IN:
        logger.info("You are logged in - no action needed")
    elif state == LoginState.INACTIVITY_LOGOUT:
        logger.info("Detected: Inactivity logout dialog (OK button visible)")
    elif state == LoginState.PLAY_NOW_SCREEN:
        logger.info("Detected: Play Now screen (welcome screen)")
    elif state == LoginState.LOGGED_IN_SCREEN:
        logger.info("Detected: Account select screen (Click Here To Play)")
    elif state == LoginState.UNKNOWN:
        logger.warning("Could not determine login state")

    # Perform re-login if requested
    if args.relogin:
        if state == LoginState.LOGGED_IN:
            logger.info("Already logged in, nothing to do")
        else:
            logger.info("-" * 40)
            logger.info("Performing re-login sequence...")
            logger.warning("This will move your mouse!")

            success = login_handler.perform_relogin(save_debug=args.debug)

            if success:
                logger.info("Re-login successful!")
            else:
                logger.error("Re-login failed after %d attempts", login_handler.config.max_retries)
                return 1
    else:
        if login_handler.is_logged_out():
            logger.info("-" * 40)
            logger.info("Run with --relogin to actually perform the login sequence")

    return 0


if __name__ == "__main__":
    sys.exit(main())
