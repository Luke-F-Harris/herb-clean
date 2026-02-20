#!/usr/bin/env python3
"""OSRS Herb Cleaning Bot - Entry Point.

DISCLAIMER: Botting violates OSRS Terms of Service and can result in
permanent account bans. This code is for educational purposes only.
"""

import argparse
import logging
import sys
from pathlib import Path

from core.bot_controller import BotController


def setup_logging(verbose: bool = False, log_file: str | None = None) -> None:
    """Configure logging.

    Args:
        verbose: Enable debug logging
        log_file: Optional file to log to
    """
    level = logging.DEBUG if verbose else logging.INFO
    format_str = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]

    if log_file:
        handlers.append(logging.FileHandler(log_file))

    logging.basicConfig(
        level=level,
        format=format_str,
        handlers=handlers,
    )


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="OSRS Herb Cleaning Bot (Educational)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
DISCLAIMER:
  Botting violates OSRS Terms of Service and can result in permanent
  account bans. Jagex employs sophisticated behavioral analysis.
  No bot is truly undetectable. Use at your own risk.

CONTROLS:
  F12 - Emergency stop (immediately halts all bot actions)

SETUP:
  1. Open RuneLite with GPU plugin enabled
  2. Stand next to a bank booth/chest
  3. Have grimy herbs in your bank
  4. Capture template images for your herbs (see config/templates/)
  5. Run this script
        """,
    )

    parser.add_argument(
        "-c", "--config",
        type=str,
        default=None,
        help="Path to config file (default: config/default_config.yaml)",
    )

    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose/debug logging",
    )

    parser.add_argument(
        "-l", "--log-file",
        type=str,
        default=None,
        help="Log to file in addition to stdout",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Test configuration without running bot",
    )

    parser.add_argument(
        "--status-ui",
        action="store_true",
        help="Enable Rich terminal UI for real-time anti-detection status",
    )

    parser.add_argument(
        "--overlay",
        action="store_true",
        help="Enable transparent overlay for vision debugging (Windows click-through)",
    )

    return parser.parse_args()


def validate_environment() -> list[str]:
    """Validate that required dependencies and environment are available.

    Returns:
        List of warning/error messages
    """
    issues = []

    # Check platform-specific dependencies
    if sys.platform == "win32":
        try:
            import win32gui
        except ImportError:
            issues.append("pywin32 not found - required for Windows. Run: pip install pywin32")
    else:
        # Check for xdotool (Linux window detection)
        try:
            import subprocess
            result = subprocess.run(["which", "xdotool"], capture_output=True)
            if result.returncode != 0:
                issues.append("xdotool not found - required for Linux. Run: sudo apt install xdotool")
        except Exception:
            issues.append("Could not check for xdotool")

    # Check required Python packages
    required_packages = [
        ("numpy", "numpy"),
        ("cv2", "opencv-python"),
        ("yaml", "PyYAML"),
        ("mss", "mss"),
        ("pynput", "pynput"),
        ("statemachine", "python-statemachine"),
        ("PIL", "Pillow"),
    ]

    for module_name, package_name in required_packages:
        try:
            __import__(module_name)
        except ImportError:
            issues.append(f"Missing package: {package_name}")

    return issues


def main() -> int:
    """Main entry point.

    Returns:
        Exit code
    """
    args = parse_args()
    setup_logging(args.verbose, args.log_file)

    logger = logging.getLogger(__name__)

    # Banner
    logger.info("=" * 50)
    logger.info("OSRS Herb Cleaning Bot")
    logger.info("Press F12 at any time for emergency stop")
    logger.info("=" * 50)

    # Validate environment
    issues = validate_environment()
    if issues:
        for issue in issues:
            logger.warning("Environment issue: %s", issue)

        if any("Missing package" in i for i in issues):
            logger.error("Missing required packages. Run: pip install -r requirements.txt")
            return 1

    # Dry run - just validate config
    if args.dry_run:
        logger.info("Dry run mode - validating configuration...")
        try:
            controller = BotController(args.config, overlay_enabled=False)
            logger.info("Configuration valid!")
            logger.info("Templates dir: %s", controller.config.templates_dir)
            logger.info("Emergency stop key: %s", controller.config.safety.get("emergency_stop_key"))
            logger.info("Max session hours: %s", controller.config.safety.get("max_session_hours"))
            return 0
        except Exception as e:
            logger.error("Configuration error: %s", e)
            return 1

    # Run bot
    status_display = None
    try:
        # Check pygame availability if overlay requested
        if args.overlay:
            try:
                import pygame
                logger.info("Overlay mode enabled")
            except ImportError:
                logger.warning("Pygame not installed, overlay disabled. Run: pip install pygame")
                args.overlay = False

        controller = BotController(args.config, overlay_enabled=args.overlay)

        # Start status UI if requested
        if args.status_ui:
            try:
                from ui.status_display import StatusDisplay, check_rich_available

                if check_rich_available():
                    status_display = StatusDisplay(
                        aggregator=controller.status_aggregator,
                        events=controller.events,
                    )
                    if status_display.start():
                        logger.info("Status UI enabled")
                    else:
                        logger.warning("Status UI failed to start, continuing without it")
                        status_display = None
                else:
                    logger.warning("Rich library not installed, status UI disabled. Run: pip install rich")
            except ImportError as e:
                logger.warning("Could not import status display: %s", e)

        controller.start()
        return 0

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        return 0

    except FileNotFoundError as e:
        logger.error("File not found: %s", e)
        return 1

    except RuntimeError as e:
        logger.error("Runtime error: %s", e)
        return 1

    except Exception as e:
        logger.exception("Unexpected error: %s", e)
        return 1

    finally:
        if status_display:
            status_display.stop()


if __name__ == "__main__":
    sys.exit(main())
