"""Factory for creating input drivers."""

import logging
import sys
from typing import Optional, Dict, Any

from .base import MouseButton, MouseDriverProtocol, KeyboardDriverProtocol
from .pynput_driver import PynputMouseDriver, PynputKeyboardDriver


logger = logging.getLogger(__name__)


class DriverFactory:
    """Factory for creating mouse and keyboard drivers.

    Supports multiple driver backends:
    - pynput: Default, cross-platform (Windows/Linux/Mac)
    - interception: Windows only, uses kernel driver (less detectable)

    Note: ydotool (Linux kernel-level) was removed since this project
    runs on Windows only.
    """

    SUPPORTED_DRIVERS = ["pynput", "interception"]

    @classmethod
    def create_mouse_driver(
        cls,
        driver_name: str = "pynput",
        config: Optional[Dict[str, Any]] = None,
    ) -> MouseDriverProtocol:
        """Create a mouse driver instance.

        Args:
            driver_name: Driver to use ("pynput" or "interception")
            config: Optional driver-specific configuration

        Returns:
            Mouse driver instance

        Raises:
            ValueError: If driver is not supported or unavailable
        """
        config = config or {}

        if driver_name == "pynput":
            return PynputMouseDriver()

        elif driver_name == "interception":
            # Check platform
            if sys.platform != "win32":
                raise ValueError("interception driver is only available on Windows")

            # Import interception driver (lazy to avoid import errors on Linux)
            from .interception_driver import (
                InterceptionMouseDriver,
                check_interception_available,
            )

            if not check_interception_available():
                raise ValueError(
                    "Interception not available. Install the driver from:\n"
                    "https://github.com/oblitum/Interception/releases\n"
                    "Then: pip install interception-python"
                )

            return InterceptionMouseDriver()

        else:
            raise ValueError(
                f"Unknown driver: {driver_name}. "
                f"Supported: {cls.SUPPORTED_DRIVERS}"
            )

    @classmethod
    def create_keyboard_driver(
        cls,
        driver_name: str = "pynput",
        config: Optional[Dict[str, Any]] = None,
    ) -> KeyboardDriverProtocol:
        """Create a keyboard driver instance.

        Args:
            driver_name: Driver to use ("pynput" or "interception")
            config: Optional driver-specific configuration

        Returns:
            Keyboard driver instance

        Raises:
            ValueError: If driver is not supported or unavailable
        """
        config = config or {}

        if driver_name == "pynput":
            return PynputKeyboardDriver()

        elif driver_name == "interception":
            if sys.platform != "win32":
                raise ValueError("interception driver is only available on Windows")

            from .interception_driver import (
                InterceptionKeyboardDriver,
                check_interception_available,
            )

            if not check_interception_available():
                raise ValueError(
                    "Interception not available. Install the driver from:\n"
                    "https://github.com/oblitum/Interception/releases\n"
                    "Then: pip install interception-python"
                )

            return InterceptionKeyboardDriver()

        else:
            raise ValueError(
                f"Unknown driver: {driver_name}. "
                f"Supported: {cls.SUPPORTED_DRIVERS}"
            )

    @classmethod
    def get_available_drivers(cls) -> list:
        """Get list of available drivers on current platform.

        Returns:
            List of driver names that can be used
        """
        available = ["pynput"]  # Always available

        if sys.platform == "win32":
            try:
                from .interception_driver import check_interception_available
                if check_interception_available():
                    available.append("interception")
            except ImportError:
                pass

        return available


# Convenience functions
def create_mouse_driver(
    driver_name: str = "pynput",
    config: Optional[Dict[str, Any]] = None,
) -> MouseDriverProtocol:
    """Create a mouse driver. See DriverFactory.create_mouse_driver."""
    return DriverFactory.create_mouse_driver(driver_name, config)


def create_keyboard_driver(
    driver_name: str = "pynput",
    config: Optional[Dict[str, Any]] = None,
) -> KeyboardDriverProtocol:
    """Create a keyboard driver. See DriverFactory.create_keyboard_driver."""
    return DriverFactory.create_keyboard_driver(driver_name, config)
