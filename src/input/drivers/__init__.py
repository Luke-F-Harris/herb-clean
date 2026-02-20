"""Input driver abstraction layer.

Production (Windows): Uses Interception kernel driver for undetectable input.
Development (Linux): Uses pynput for testing only.

Interception is REQUIRED for production use. The bot will not run on Windows
without the Interception driver properly installed.
"""

from .base import MouseButton, MouseDriverProtocol, KeyboardDriverProtocol
from .factory import DriverFactory, create_mouse_driver, create_keyboard_driver
from .validation import require_interception, InterceptionNotInstalledError

__all__ = [
    "MouseButton",
    "MouseDriverProtocol",
    "KeyboardDriverProtocol",
    "DriverFactory",
    "create_mouse_driver",
    "create_keyboard_driver",
    "require_interception",
    "InterceptionNotInstalledError",
]
