"""Factory for creating input drivers."""

import logging
import sys
from typing import Optional, Dict, Any

from .base import MouseDriverProtocol, KeyboardDriverProtocol


logger = logging.getLogger(__name__)


class DriverFactory:
    """Factory for creating mouse and keyboard drivers.

    Production (Windows): Uses Interception for kernel-level input.
    Development (Linux): Uses pynput for testing.
    """

    @classmethod
    def create_mouse_driver(
        cls,
        driver_name: str = "interception",
        config: Optional[Dict[str, Any]] = None,
    ) -> MouseDriverProtocol:
        """Create a mouse driver instance.

        On Windows: Creates Interception driver (required)
        On Linux: Creates pynput driver (for dev testing only)

        Args:
            driver_name: Driver name (auto-selected based on platform)
            config: Optional driver-specific configuration

        Returns:
            Mouse driver instance
        """
        if sys.platform == "win32":
            # Windows: Interception required
            from .interception_driver import InterceptionMouseDriver
            logger.info("Using Interception mouse driver (kernel-level)")
            return InterceptionMouseDriver()
        else:
            # Linux/Mac: pynput for development testing
            from .pynput_driver import PynputMouseDriver
            logger.warning(
                "Using pynput mouse driver (DEV ONLY - not for production)"
            )
            return PynputMouseDriver()

    @classmethod
    def create_keyboard_driver(
        cls,
        driver_name: str = "interception",
        config: Optional[Dict[str, Any]] = None,
    ) -> KeyboardDriverProtocol:
        """Create a keyboard driver instance.

        On Windows: Creates Interception driver (required)
        On Linux: Creates pynput driver (for dev testing only)

        Args:
            driver_name: Driver name (auto-selected based on platform)
            config: Optional driver-specific configuration

        Returns:
            Keyboard driver instance
        """
        if sys.platform == "win32":
            # Windows: Interception required
            from .interception_driver import InterceptionKeyboardDriver
            logger.info("Using Interception keyboard driver (kernel-level)")
            return InterceptionKeyboardDriver()
        else:
            # Linux/Mac: pynput for development testing
            from .pynput_driver import PynputKeyboardDriver
            logger.warning(
                "Using pynput keyboard driver (DEV ONLY - not for production)"
            )
            return PynputKeyboardDriver()


# Convenience functions
def create_mouse_driver(
    driver_name: str = "interception",
    config: Optional[Dict[str, Any]] = None,
) -> MouseDriverProtocol:
    """Create a mouse driver. See DriverFactory.create_mouse_driver."""
    return DriverFactory.create_mouse_driver(driver_name, config)


def create_keyboard_driver(
    driver_name: str = "interception",
    config: Optional[Dict[str, Any]] = None,
) -> KeyboardDriverProtocol:
    """Create a keyboard driver. See DriverFactory.create_keyboard_driver."""
    return DriverFactory.create_keyboard_driver(driver_name, config)
