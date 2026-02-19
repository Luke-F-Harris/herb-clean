#!/usr/bin/env python3
"""Test script for LoginHandler - manually test login detection and re-login.

Run from osrs_herblore directory:
    python tests/test_login_handler.py           # Detection only (safe)
    python tests/test_login_handler.py --relogin # Actually perform re-login clicks
"""

import argparse
import logging
import sys
from pathlib import Path

# Add src to path (go up from tests/ to osrs_herblore/, then into src/)
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from vision.screen_capture import ScreenCapture
from vision.template_matcher import TemplateMatcher
from input.mouse_controller import MouseController
from input.bezier_movement import MovementConfig
from input.click_handler import ClickConfig
from safety.login_handler import LoginHandler, LoginConfig, LoginState
from core.config_manager import ConfigManager


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
    parser.add_argument("-c", "--config", type=str, default=None, help="Config file path")
    args = parser.parse_args()

    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)

    logger.info("=" * 50)
    logger.info("LoginHandler Test")
    logger.info("=" * 50)

    # Initialize components
    try:
        config = ConfigManager(args.config)
        logger.info("Config loaded from: %s", config.templates_dir)
    except Exception as e:
        logger.error("Failed to load config: %s", e)
        return 1

    # Screen capture
    screen = ScreenCapture(config.window.get("title", "RuneLite"))
    if not screen.find_window():
        logger.error("Could not find RuneLite window!")
        return 1
    logger.info("Found window at: %s", screen.window_bounds)

    # Template matcher
    template_matcher = TemplateMatcher(
        templates_dir=config.templates_dir,
        confidence_threshold=config.vision.get("confidence_threshold", 0.80),
        multi_scale=config.vision.get("multi_scale", True),
        scale_range=tuple(config.vision.get("scale_range", [0.8, 1.2])),
        scale_steps=config.vision.get("scale_steps", 5),
    )

    # Mouse controller (needed for re-login clicks)
    mouse_cfg = config.mouse
    mouse = MouseController(
        movement_config=MovementConfig(
            speed_range=tuple(mouse_cfg.get("speed_range", [800, 1400])),
        ),
        click_config=ClickConfig(),
    )

    # Login handler
    login_handler = LoginHandler(
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
