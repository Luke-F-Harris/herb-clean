"""Interception-based input drivers for Windows.

Interception is a Windows kernel-level driver for input injection,
similar to ydotool on Linux. It intercepts input at the driver level,
making it harder to detect than userspace solutions.

Requirements:
- Windows only
- Interception driver installed: https://github.com/oblitum/Interception
- interception-python package: pip install interception-python

Installation:
1. Download Interception installer from:
   https://github.com/oblitum/Interception/releases
2. Run install-interception.exe /install
3. Reboot
4. pip install interception-python
"""

import logging
import time
from typing import Tuple, Optional

from .base import MouseButton


logger = logging.getLogger(__name__)


def check_interception_available() -> bool:
    """Check if Interception is available.

    Returns:
        True if Interception can be used
    """
    try:
        import interception
        # Try to create a context to verify driver is loaded
        ctx = interception.interception()
        # Check if we can get devices
        ctx.get_hardware_id(1)
        return True
    except ImportError:
        logger.warning(
            "interception-python not installed. "
            "Install with: pip install interception-python"
        )
        return False
    except Exception as e:
        logger.warning(
            "Interception driver not loaded: %s. "
            "Install from: https://github.com/oblitum/Interception/releases",
            e
        )
        return False


class InterceptionMouseDriver:
    """Mouse driver using Interception (Windows kernel-level input).

    Uses the Interception driver for low-level input injection that
    bypasses standard Windows input APIs.
    """

    # Interception mouse button flags
    _BUTTON_DOWN = {
        MouseButton.LEFT: 0x001,    # INTERCEPTION_MOUSE_LEFT_BUTTON_DOWN
        MouseButton.RIGHT: 0x004,   # INTERCEPTION_MOUSE_RIGHT_BUTTON_DOWN
        MouseButton.MIDDLE: 0x010,  # INTERCEPTION_MOUSE_MIDDLE_BUTTON_DOWN
    }
    _BUTTON_UP = {
        MouseButton.LEFT: 0x002,    # INTERCEPTION_MOUSE_LEFT_BUTTON_UP
        MouseButton.RIGHT: 0x008,   # INTERCEPTION_MOUSE_RIGHT_BUTTON_UP
        MouseButton.MIDDLE: 0x020,  # INTERCEPTION_MOUSE_MIDDLE_BUTTON_UP
    }

    def __init__(self):
        """Initialize Interception mouse driver."""
        try:
            import interception
            self._interception = interception
        except ImportError as e:
            raise RuntimeError(
                "interception-python not installed. "
                "Install with: pip install interception-python"
            ) from e

        self._ctx = interception.interception()
        self._mouse_device = self._find_mouse_device()

        if self._mouse_device is None:
            raise RuntimeError("No mouse device found for Interception")

        # Cache position (Interception uses relative movement by default)
        self._cached_position: Tuple[int, int] = self._get_cursor_position()

    def _find_mouse_device(self) -> Optional[int]:
        """Find the first mouse device.

        Returns:
            Device ID or None
        """
        # Interception device IDs: 1-10 are keyboards, 11-20 are mice
        for device in range(11, 21):
            try:
                hw_id = self._ctx.get_hardware_id(device)
                if hw_id:
                    logger.debug("Found mouse device %d: %s", device, hw_id)
                    return device
            except Exception:
                pass
        return None

    def _get_cursor_position(self) -> Tuple[int, int]:
        """Get current cursor position using Windows API.

        Returns:
            (x, y) position
        """
        try:
            import ctypes
            from ctypes import wintypes

            class POINT(ctypes.Structure):
                _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]

            point = POINT()
            ctypes.windll.user32.GetCursorPos(ctypes.byref(point))
            return (point.x, point.y)
        except Exception:
            return (0, 0)

    @property
    def position(self) -> Tuple[int, int]:
        """Get current mouse position."""
        # Refresh from Windows API for accuracy
        self._cached_position = self._get_cursor_position()
        return self._cached_position

    @position.setter
    def position(self, pos: Tuple[int, int]) -> None:
        """Move cursor to absolute position.

        Args:
            pos: (x, y) target coordinates
        """
        x, y = int(pos[0]), int(pos[1])

        # Create mouse stroke for absolute movement
        stroke = self._interception.mouse_stroke(
            state=0,
            flags=0x8001,  # INTERCEPTION_MOUSE_MOVE_ABSOLUTE | INTERCEPTION_MOUSE_VIRTUAL_DESKTOP
            rolling=0,
            x=int(x * 65535 / self._get_screen_width()),
            y=int(y * 65535 / self._get_screen_height()),
            information=0,
        )

        self._ctx.send(self._mouse_device, stroke)
        self._cached_position = (x, y)

    def _get_screen_width(self) -> int:
        """Get primary screen width."""
        try:
            import ctypes
            return ctypes.windll.user32.GetSystemMetrics(0)
        except Exception:
            return 1920

    def _get_screen_height(self) -> int:
        """Get primary screen height."""
        try:
            import ctypes
            return ctypes.windll.user32.GetSystemMetrics(1)
        except Exception:
            return 1080

    def press(self, button: MouseButton) -> None:
        """Press a mouse button (hold down)."""
        state = self._BUTTON_DOWN.get(button, 0x001)
        stroke = self._interception.mouse_stroke(
            state=state,
            flags=0,
            rolling=0,
            x=0,
            y=0,
            information=0,
        )
        self._ctx.send(self._mouse_device, stroke)

    def release(self, button: MouseButton) -> None:
        """Release a mouse button."""
        state = self._BUTTON_UP.get(button, 0x002)
        stroke = self._interception.mouse_stroke(
            state=state,
            flags=0,
            rolling=0,
            x=0,
            y=0,
            information=0,
        )
        self._ctx.send(self._mouse_device, stroke)

    def scroll(self, dx: int, dy: int) -> None:
        """Scroll the mouse wheel.

        Args:
            dx: Horizontal scroll (not commonly supported)
            dy: Vertical scroll (positive = up, negative = down)
        """
        if dy == 0:
            return

        # INTERCEPTION_MOUSE_WHEEL = 0x400
        stroke = self._interception.mouse_stroke(
            state=0x400,
            flags=0,
            rolling=dy * 120,  # Standard wheel delta
            x=0,
            y=0,
            information=0,
        )
        self._ctx.send(self._mouse_device, stroke)


class InterceptionKeyboardDriver:
    """Keyboard driver using Interception (Windows kernel-level input)."""

    def __init__(self):
        """Initialize Interception keyboard driver."""
        try:
            import interception
            self._interception = interception
        except ImportError as e:
            raise RuntimeError(
                "interception-python not installed. "
                "Install with: pip install interception-python"
            ) from e

        self._ctx = interception.interception()
        self._keyboard_device = self._find_keyboard_device()

        if self._keyboard_device is None:
            raise RuntimeError("No keyboard device found for Interception")

    def _find_keyboard_device(self) -> Optional[int]:
        """Find the first keyboard device.

        Returns:
            Device ID or None
        """
        # Interception device IDs: 1-10 are keyboards
        for device in range(1, 11):
            try:
                hw_id = self._ctx.get_hardware_id(device)
                if hw_id:
                    logger.debug("Found keyboard device %d: %s", device, hw_id)
                    return device
            except Exception:
                pass
        return None

    def _get_scan_code(self, key) -> int:
        """Convert key to scan code.

        Args:
            key: pynput Key or character

        Returns:
            Scan code
        """
        # Import here to avoid circular dependency
        from pynput.keyboard import Key as PynputKey

        # Virtual key to scan code mapping (common keys)
        # These are hardware scan codes, not virtual key codes
        SCAN_CODES = {
            PynputKey.esc: 0x01,
            PynputKey.f1: 0x3B,
            PynputKey.f2: 0x3C,
            PynputKey.f3: 0x3D,
            PynputKey.f4: 0x3E,
            PynputKey.f5: 0x3F,
            PynputKey.f6: 0x40,
            PynputKey.f7: 0x41,
            PynputKey.f8: 0x42,
            PynputKey.f9: 0x43,
            PynputKey.f10: 0x44,
            PynputKey.f11: 0x57,
            PynputKey.f12: 0x58,
            PynputKey.backspace: 0x0E,
            PynputKey.tab: 0x0F,
            PynputKey.enter: 0x1C,
            PynputKey.shift: 0x2A,
            PynputKey.shift_l: 0x2A,
            PynputKey.shift_r: 0x36,
            PynputKey.ctrl: 0x1D,
            PynputKey.ctrl_l: 0x1D,
            PynputKey.ctrl_r: 0x1D,  # Extended
            PynputKey.alt: 0x38,
            PynputKey.alt_l: 0x38,
            PynputKey.alt_r: 0x38,  # Extended
            PynputKey.space: 0x39,
            PynputKey.caps_lock: 0x3A,
        }

        if key in SCAN_CODES:
            return SCAN_CODES[key]

        # Character to scan code (US keyboard layout)
        CHAR_SCAN_CODES = {
            'a': 0x1E, 'b': 0x30, 'c': 0x2E, 'd': 0x20, 'e': 0x12,
            'f': 0x21, 'g': 0x22, 'h': 0x23, 'i': 0x17, 'j': 0x24,
            'k': 0x25, 'l': 0x26, 'm': 0x32, 'n': 0x31, 'o': 0x18,
            'p': 0x19, 'q': 0x10, 'r': 0x13, 's': 0x1F, 't': 0x14,
            'u': 0x16, 'v': 0x2F, 'w': 0x11, 'x': 0x2D, 'y': 0x15,
            'z': 0x2C,
            '1': 0x02, '2': 0x03, '3': 0x04, '4': 0x05, '5': 0x06,
            '6': 0x07, '7': 0x08, '8': 0x09, '9': 0x0A, '0': 0x0B,
        }

        if isinstance(key, str) and len(key) == 1:
            code = CHAR_SCAN_CODES.get(key.lower())
            if code:
                return code

        logger.warning("Unknown key for Interception: %s", key)
        return 0x00

    def press(self, key) -> None:
        """Press a key (hold down)."""
        scan_code = self._get_scan_code(key)
        if scan_code == 0:
            return

        stroke = self._interception.key_stroke(
            code=scan_code,
            state=0,  # Key down
            information=0,
        )
        self._ctx.send(self._keyboard_device, stroke)

    def release(self, key) -> None:
        """Release a key."""
        scan_code = self._get_scan_code(key)
        if scan_code == 0:
            return

        stroke = self._interception.key_stroke(
            code=scan_code,
            state=1,  # Key up
            information=0,
        )
        self._ctx.send(self._keyboard_device, stroke)
