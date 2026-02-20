"""Input driver validation and startup checks.

Ensures Interception driver is properly installed before bot runs.
"""

import sys
import logging
from typing import Tuple

logger = logging.getLogger(__name__)


class InterceptionNotInstalledError(Exception):
    """Raised when Interception driver is not installed."""
    pass


def validate_interception_installation() -> Tuple[bool, str]:
    """Validate that Interception is fully installed and working.

    Checks:
    1. Running on Windows
    2. interception-python package installed
    3. Interception kernel driver loaded
    4. Can access mouse and keyboard devices

    Returns:
        (success, message) tuple
    """
    # Check 1: Windows only
    if sys.platform != "win32":
        return False, (
            "Interception driver requires Windows.\n"
            "Current platform: " + sys.platform
        )

    # Check 2: Python package installed
    try:
        import interception
    except ImportError:
        return False, (
            "interception-python package not installed.\n\n"
            "Install with:\n"
            "  pip install interception-python"
        )

    # Check 3: Kernel driver loaded (can create context)
    try:
        ctx = interception.interception()
    except Exception as e:
        return False, (
            "Interception kernel driver not loaded.\n\n"
            f"Error: {e}\n\n"
            "Installation steps:\n"
            "1. Download from: https://github.com/oblitum/Interception/releases\n"
            "2. Run as Administrator: install-interception.exe /install\n"
            "3. REBOOT your computer (required for kernel driver)\n"
        )

    # Check 4: Can find devices
    mouse_found = False
    keyboard_found = False

    # Check for keyboard (devices 1-10)
    for device in range(1, 11):
        try:
            hw_id = ctx.get_hardware_id(device)
            if hw_id:
                keyboard_found = True
                break
        except Exception:
            pass

    # Check for mouse (devices 11-20)
    for device in range(11, 21):
        try:
            hw_id = ctx.get_hardware_id(device)
            if hw_id:
                mouse_found = True
                break
        except Exception:
            pass

    if not keyboard_found:
        return False, (
            "Interception cannot find keyboard device.\n"
            "The driver may not be properly installed.\n\n"
            "Try reinstalling:\n"
            "1. Run as Administrator: install-interception.exe /uninstall\n"
            "2. Reboot\n"
            "3. Run as Administrator: install-interception.exe /install\n"
            "4. Reboot again"
        )

    if not mouse_found:
        return False, (
            "Interception cannot find mouse device.\n"
            "The driver may not be properly installed.\n\n"
            "Try reinstalling:\n"
            "1. Run as Administrator: install-interception.exe /uninstall\n"
            "2. Reboot\n"
            "3. Run as Administrator: install-interception.exe /install\n"
            "4. Reboot again"
        )

    return True, "Interception driver validated successfully"


def require_interception() -> None:
    """Require Interception to be installed on Windows, or exit with clear error.

    On Linux/Mac: Skips validation (dev environment uses pynput)
    On Windows: Validates Interception is properly installed

    Call this at bot startup to ensure the driver is ready.

    Raises:
        InterceptionNotInstalledError: If on Windows and Interception is not installed
    """
    # Skip validation on non-Windows (dev environment)
    if sys.platform != "win32":
        logger.warning(
            "Running on %s - using pynput driver (DEV ONLY). "
            "Production requires Windows with Interception.",
            sys.platform
        )
        return

    success, message = validate_interception_installation()

    if success:
        logger.info("Interception driver: OK")
    else:
        logger.error("Interception driver: FAILED")
        raise InterceptionNotInstalledError(
            "\n" + "=" * 60 + "\n"
            "INTERCEPTION DRIVER NOT INSTALLED\n"
            "=" * 60 + "\n\n"
            f"{message}\n\n"
            "The bot requires Interception for undetectable input.\n"
            "=" * 60
        )
