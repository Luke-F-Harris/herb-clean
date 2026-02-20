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
    - ydotool: Linux only, uses kernel uinput (less detectable)
    """

    SUPPORTED_DRIVERS = ["pynput", "ydotool"]

    @classmethod
    def create_mouse_driver(
        cls,
        driver_name: str = "pynput",
        config: Optional[Dict[str, Any]] = None,
    ) -> MouseDriverProtocol:
        """Create a mouse driver instance.

        Args:
            driver_name: Driver to use ("pynput" or "ydotool")
            config: Optional driver-specific configuration

        Returns:
            Mouse driver instance

        Raises:
            ValueError: If driver is not supported or unavailable
        """
        config = config or {}

        if driver_name == "pynput":
            return PynputMouseDriver()

        elif driver_name == "ydotool":
            # Check platform
            if sys.platform != "linux":
                raise ValueError("ydotool driver is only available on Linux")

            # Import ydotool driver (lazy to avoid import errors on Windows)
            from .ydotool_driver import YdotoolMouseDriver, check_ydotool_available

            if not check_ydotool_available():
                raise ValueError(
                    "ydotool not available. Ensure ydotool is installed "
                    "and ydotoold is running."
                )

            ydotool_config = config.get("ydotool", {})
            return YdotoolMouseDriver(
                use_xdotool_fallback=ydotool_config.get("use_xdotool_fallback", True),
            )

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
            driver_name: Driver to use ("pynput" or "ydotool")
            config: Optional driver-specific configuration

        Returns:
            Keyboard driver instance

        Raises:
            ValueError: If driver is not supported or unavailable
        """
        config = config or {}

        if driver_name == "pynput":
            return PynputKeyboardDriver()

        elif driver_name == "ydotool":
            if sys.platform != "linux":
                raise ValueError("ydotool driver is only available on Linux")

            from .ydotool_driver import YdotoolKeyboardDriver, check_ydotool_available

            if not check_ydotool_available():
                raise ValueError(
                    "ydotool not available. Ensure ydotool is installed "
                    "and ydotoold is running."
                )

            return YdotoolKeyboardDriver()

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

        if sys.platform == "linux":
            try:
                from .ydotool_driver import check_ydotool_available
                if check_ydotool_available():
                    available.append("ydotool")
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
