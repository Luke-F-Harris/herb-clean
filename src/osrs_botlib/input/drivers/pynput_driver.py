"""Pynput-based input drivers (default implementation)."""

from typing import Tuple, Union

from pynput.mouse import Button as PynputButton, Controller as PynputMouseController
from pynput.keyboard import Key as PynputKey, Controller as PynputKeyboardController

from .base import MouseButton, MouseDriverProtocol, KeyboardDriverProtocol


class PynputMouseDriver:
    """Mouse driver using pynput library.

    This is the default driver, works on Windows/Linux/Mac.
    Uses X11/Win32/Quartz APIs through Python.
    """

    # Map our MouseButton enum to pynput Button
    _BUTTON_MAP = {
        MouseButton.LEFT: PynputButton.left,
        MouseButton.RIGHT: PynputButton.right,
        MouseButton.MIDDLE: PynputButton.middle,
    }

    def __init__(self):
        """Initialize pynput mouse controller."""
        self._mouse = PynputMouseController()

    @property
    def position(self) -> Tuple[int, int]:
        """Get current mouse position."""
        return self._mouse.position

    @position.setter
    def position(self, pos: Tuple[int, int]) -> None:
        """Set mouse position."""
        self._mouse.position = pos

    def press(self, button: MouseButton) -> None:
        """Press a mouse button."""
        pynput_button = self._BUTTON_MAP.get(button, PynputButton.left)
        self._mouse.press(pynput_button)

    def release(self, button: MouseButton) -> None:
        """Release a mouse button."""
        pynput_button = self._BUTTON_MAP.get(button, PynputButton.left)
        self._mouse.release(pynput_button)

    def scroll(self, dx: int, dy: int) -> None:
        """Scroll the mouse wheel."""
        self._mouse.scroll(dx, dy)

    def get_pynput_button(self, button: MouseButton) -> PynputButton:
        """Get the underlying pynput Button for compatibility.

        Args:
            button: Our MouseButton enum

        Returns:
            Corresponding pynput Button
        """
        return self._BUTTON_MAP.get(button, PynputButton.left)


class PynputKeyboardDriver:
    """Keyboard driver using pynput library.

    This is the default driver, works on Windows/Linux/Mac.
    """

    def __init__(self):
        """Initialize pynput keyboard controller."""
        self._keyboard = PynputKeyboardController()

    def press(self, key: Union[str, PynputKey]) -> None:
        """Press a key."""
        self._keyboard.press(key)

    def release(self, key: Union[str, PynputKey]) -> None:
        """Release a key."""
        self._keyboard.release(key)

    @property
    def controller(self) -> PynputKeyboardController:
        """Get the underlying pynput controller for advanced usage."""
        return self._keyboard
