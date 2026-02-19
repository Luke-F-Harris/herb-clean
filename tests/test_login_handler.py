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
    wait_after_ok_click: tuple[float, float] = (2.0, 4.0)
    wait_after_play_now_click: tuple[float, float] = (2.0, 5.0)
    wait_after_play_click: tuple[float, float] = (3.0, 6.0)
    max_retries: int = 10
    retry_delay: tuple[float, float] = (1.0, 2.0)
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

    def detect_login_state(self) -> LoginState:
        """Detect current login state by checking for UI elements."""
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

        return LoginState.LOGGED_IN

    def is_logged_out(self) -> bool:
        """Check if we're logged out."""
        state = self.detect_login_state()
        return state in (
            LoginState.INACTIVITY_LOGOUT,
            LoginState.PLAY_NOW_SCREEN,
            LoginState.LOGGED_IN_SCREEN,
        )

    def perform_relogin(self) -> bool:
        """Perform the full re-login sequence."""
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
                if not self._click_button(self.config.ok_button_template, "OK"):
                    self._logger.warning("Failed to click OK button")
                else:
                    wait = self._rng.uniform(*self.config.wait_after_ok_click)
                    self._logger.debug("Waiting %.1fs after OK click", wait)
                    time.sleep(wait)

            elif state == LoginState.PLAY_NOW_SCREEN:
                if not self._click_button(self.config.play_now_template, "Play Now"):
                    self._logger.warning("Failed to click Play Now button")
                else:
                    wait = self._rng.uniform(*self.config.wait_after_play_now_click)
                    self._logger.debug("Waiting %.1fs after Play Now click", wait)
                    time.sleep(wait)

            elif state == LoginState.LOGGED_IN_SCREEN:
                if not self._click_button(self.config.play_button_template, "Play"):
                    self._logger.warning("Failed to click Play button")
                else:
                    wait = self._rng.uniform(*self.config.wait_after_play_click)
                    self._logger.debug("Waiting %.1fs after Play click", wait)
                    time.sleep(wait)

            elif state == LoginState.LOGGING_IN:
                wait = self._rng.uniform(*self.config.retry_delay)
                time.sleep(wait)

            else:
                wait = self._rng.uniform(*self.config.retry_delay)
                time.sleep(wait)

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
    state = login_handler.detect_login_state()
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

            success = login_handler.perform_relogin()

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
