"""Input driver abstraction layer.

Provides swappable implementations for mouse and keyboard input:
- pynput: Default, works on Windows/Linux/Mac
- ydotool: Linux-only, uses uinput for kernel-level input (less detectable)
"""

from .base import MouseButton, MouseDriverProtocol, KeyboardDriverProtocol
from .factory import DriverFactory, create_mouse_driver, create_keyboard_driver

__all__ = [
    "MouseButton",
    "MouseDriverProtocol",
    "KeyboardDriverProtocol",
    "DriverFactory",
    "create_mouse_driver",
    "create_keyboard_driver",
]
