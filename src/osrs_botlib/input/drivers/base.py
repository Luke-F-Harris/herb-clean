"""Base protocols and types for input drivers."""

from enum import Enum
from typing import Protocol, Tuple, Union


class MouseButton(Enum):
    """Mouse button enumeration (driver-agnostic)."""

    LEFT = "left"
    RIGHT = "right"
    MIDDLE = "middle"


class MouseDriverProtocol(Protocol):
    """Protocol for mouse driver implementations.

    All mouse drivers must implement this interface.
    """

    @property
    def position(self) -> Tuple[int, int]:
        """Get current mouse position.

        Returns:
            (x, y) tuple of current cursor coordinates
        """
        ...

    @position.setter
    def position(self, pos: Tuple[int, int]) -> None:
        """Set mouse position (move cursor).

        Args:
            pos: (x, y) tuple of target coordinates
        """
        ...

    def press(self, button: MouseButton) -> None:
        """Press a mouse button (hold down).

        Args:
            button: Button to press
        """
        ...

    def release(self, button: MouseButton) -> None:
        """Release a mouse button.

        Args:
            button: Button to release
        """
        ...

    def scroll(self, dx: int, dy: int) -> None:
        """Scroll the mouse wheel.

        Args:
            dx: Horizontal scroll amount (positive = right)
            dy: Vertical scroll amount (positive = up)
        """
        ...


class KeyboardDriverProtocol(Protocol):
    """Protocol for keyboard driver implementations.

    All keyboard drivers must implement this interface.
    """

    def press(self, key: Union[str, "KeyCode"]) -> None:
        """Press a key (hold down).

        Args:
            key: Key to press (string character or special key)
        """
        ...

    def release(self, key: Union[str, "KeyCode"]) -> None:
        """Release a key.

        Args:
            key: Key to release
        """
        ...


# Type alias for key codes (pynput Key or evdev keycode)
KeyCode = Union[int, "Key"]  # Will be resolved at runtime
