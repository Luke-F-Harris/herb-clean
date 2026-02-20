"""Ydotool-based input drivers for Linux.

Ydotool uses Linux uinput for kernel-level input injection,
making it less detectable than userspace solutions like pynput.

Requirements:
- Linux only
- ydotool installed (apt install ydotool)
- ydotoold daemon running (systemctl start ydotool or ydotoold &)
- User in 'input' group (for /dev/uinput access)

Note: ydotool cannot query cursor position. We use xdotool as
fallback for initial position, then track internally.
"""

import logging
import subprocess
import shutil
from typing import Tuple, Optional, Union

from pynput.keyboard import Key as PynputKey

from .base import MouseButton
from .evdev_keycodes import get_evdev_keycode, needs_shift, PYNPUT_TO_EVDEV


logger = logging.getLogger(__name__)


def check_ydotool_available() -> bool:
    """Check if ydotool is available and ydotoold is running.

    Returns:
        True if ydotool can be used
    """
    # Check ydotool binary exists
    if not shutil.which("ydotool"):
        logger.warning("ydotool not found in PATH")
        return False

    # Check ydotoold is running
    result = subprocess.run(
        ["pgrep", "ydotoold"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        logger.warning("ydotoold not running. Start with: ydotoold &")
        return False

    return True


def get_cursor_position_xdotool() -> Optional[Tuple[int, int]]:
    """Get cursor position using xdotool (fallback).

    Returns:
        (x, y) position or None if unavailable
    """
    if not shutil.which("xdotool"):
        return None

    try:
        result = subprocess.run(
            ["xdotool", "getmouselocation", "--shell"],
            capture_output=True,
            text=True,
            timeout=1.0,
        )
        if result.returncode == 0:
            # Parse output like: X=100\nY=200\nSCREEN=0\nWINDOW=12345
            x, y = None, None
            for line in result.stdout.strip().split("\n"):
                if line.startswith("X="):
                    x = int(line[2:])
                elif line.startswith("Y="):
                    y = int(line[2:])
            if x is not None and y is not None:
                return (x, y)
    except (subprocess.TimeoutExpired, ValueError) as e:
        logger.debug("xdotool position query failed: %s", e)

    return None


class YdotoolMouseDriver:
    """Mouse driver using ydotool (Linux kernel-level input).

    Uses uinput for input injection, which is less detectable than
    userspace solutions.

    Position tracking is done internally since ydotool cannot query
    the actual cursor position.
    """

    # ydotool mouse button codes
    # Format: 0xCN for down, 0x8N for up (where N is button number)
    _BUTTON_DOWN = {
        MouseButton.LEFT: "0xC0",
        MouseButton.RIGHT: "0xC1",
        MouseButton.MIDDLE: "0xC2",
    }
    _BUTTON_UP = {
        MouseButton.LEFT: "0x80",
        MouseButton.RIGHT: "0x81",
        MouseButton.MIDDLE: "0x82",
    }

    def __init__(self, use_xdotool_fallback: bool = True):
        """Initialize ydotool mouse driver.

        Args:
            use_xdotool_fallback: Use xdotool to get initial cursor position
        """
        self._cached_position: Tuple[int, int] = (0, 0)
        self._use_xdotool_fallback = use_xdotool_fallback

        # Try to get initial position from xdotool
        if use_xdotool_fallback:
            pos = get_cursor_position_xdotool()
            if pos:
                self._cached_position = pos
                logger.debug("Initial cursor position from xdotool: %s", pos)
            else:
                logger.warning(
                    "Could not get initial cursor position. "
                    "Position tracking will be relative from (0, 0)"
                )

    @property
    def position(self) -> Tuple[int, int]:
        """Get cached mouse position.

        Note: This returns the internally tracked position since ydotool
        cannot query the actual cursor location. If the user moves the
        mouse manually, this will become stale.
        """
        # Optionally refresh from xdotool (expensive, use sparingly)
        if self._use_xdotool_fallback:
            pos = get_cursor_position_xdotool()
            if pos:
                self._cached_position = pos
        return self._cached_position

    @position.setter
    def position(self, pos: Tuple[int, int]) -> None:
        """Move cursor to absolute position.

        Args:
            pos: (x, y) target coordinates
        """
        x, y = int(pos[0]), int(pos[1])
        try:
            subprocess.run(
                ["ydotool", "mousemove", "-a", str(x), str(y)],
                check=True,
                capture_output=True,
            )
            self._cached_position = (x, y)
        except subprocess.CalledProcessError as e:
            logger.error("ydotool mousemove failed: %s", e.stderr)

    def press(self, button: MouseButton) -> None:
        """Press a mouse button (hold down)."""
        code = self._BUTTON_DOWN.get(button, "0xC0")
        try:
            subprocess.run(
                ["ydotool", "click", code],
                check=True,
                capture_output=True,
            )
        except subprocess.CalledProcessError as e:
            logger.error("ydotool click (press) failed: %s", e.stderr)

    def release(self, button: MouseButton) -> None:
        """Release a mouse button."""
        code = self._BUTTON_UP.get(button, "0x80")
        try:
            subprocess.run(
                ["ydotool", "click", code],
                check=True,
                capture_output=True,
            )
        except subprocess.CalledProcessError as e:
            logger.error("ydotool click (release) failed: %s", e.stderr)

    def scroll(self, dx: int, dy: int) -> None:
        """Scroll the mouse wheel.

        Args:
            dx: Horizontal scroll (not well supported by ydotool)
            dy: Vertical scroll (positive = up, negative = down)
        """
        if dy == 0:
            return

        # ydotool scroll: positive = up, negative = down
        # Each unit is one "click" of the wheel
        try:
            subprocess.run(
                ["ydotool", "mousemove", "--wheel", str(dy)],
                check=True,
                capture_output=True,
            )
        except subprocess.CalledProcessError as e:
            logger.error("ydotool scroll failed: %s", e.stderr)

    def refresh_position(self) -> bool:
        """Refresh cached position from xdotool.

        Call this if you suspect the user moved the mouse manually.

        Returns:
            True if position was refreshed
        """
        if self._use_xdotool_fallback:
            pos = get_cursor_position_xdotool()
            if pos:
                self._cached_position = pos
                return True
        return False


class YdotoolKeyboardDriver:
    """Keyboard driver using ydotool (Linux kernel-level input)."""

    def __init__(self):
        """Initialize ydotool keyboard driver."""
        self._shift_held = False

    def press(self, key: Union[str, PynputKey]) -> None:
        """Press a key (hold down).

        Args:
            key: Key to press (string character or pynput Key)
        """
        try:
            keycode = get_evdev_keycode(key)
            # ydotool key format: keycode:state (1=down, 0=up)
            subprocess.run(
                ["ydotool", "key", f"{keycode}:1"],
                check=True,
                capture_output=True,
            )
        except ValueError as e:
            logger.warning("Unknown key for ydotool: %s", e)
        except subprocess.CalledProcessError as e:
            logger.error("ydotool key press failed: %s", e.stderr)

    def release(self, key: Union[str, PynputKey]) -> None:
        """Release a key.

        Args:
            key: Key to release
        """
        try:
            keycode = get_evdev_keycode(key)
            subprocess.run(
                ["ydotool", "key", f"{keycode}:0"],
                check=True,
                capture_output=True,
            )
        except ValueError as e:
            logger.warning("Unknown key for ydotool: %s", e)
        except subprocess.CalledProcessError as e:
            logger.error("ydotool key release failed: %s", e.stderr)

    def type_string(self, text: str) -> None:
        """Type a string using ydotool type command.

        This is more efficient than pressing individual keys.

        Args:
            text: Text to type
        """
        try:
            subprocess.run(
                ["ydotool", "type", "--", text],
                check=True,
                capture_output=True,
            )
        except subprocess.CalledProcessError as e:
            logger.error("ydotool type failed: %s", e.stderr)
