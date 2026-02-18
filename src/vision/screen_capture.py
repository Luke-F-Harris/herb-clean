"""Screen capture using mss with RuneLite window detection (Windows-compatible)."""

import sys
from dataclasses import dataclass
from typing import Optional

import mss
import numpy as np
from PIL import Image


@dataclass
class WindowBounds:
    """Window position and size."""

    x: int
    y: int
    width: int
    height: int


class ScreenCapture:
    """Capture screenshots from RuneLite window."""

    def __init__(self, window_title: str = "RuneLite"):
        """Initialize screen capture.

        Args:
            window_title: Title of the RuneLite window to find
        """
        self.window_title = window_title
        self._sct = mss.mss()
        self._window_bounds: Optional[WindowBounds] = None
        self._hwnd: Optional[int] = None  # Windows window handle

    def find_window(self) -> Optional[WindowBounds]:
        """Find RuneLite window bounds.

        Uses Windows API (win32gui) on Windows.

        Returns:
            WindowBounds or None if not found
        """
        if sys.platform == "win32":
            return self._find_window_windows()
        else:
            return self._find_window_linux()

    def _find_window_windows(self) -> Optional[WindowBounds]:
        """Find window using Windows API (win32gui).

        Returns:
            WindowBounds or None if not found
        """
        try:
            import win32gui
            import win32con
        except ImportError:
            raise RuntimeError(
                "pywin32 is required for Windows. Install with: pip install pywin32"
            )

        # Find all windows with matching title
        def callback(hwnd, windows):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if self.window_title.lower() in title.lower():
                    windows.append(hwnd)
            return True

        windows = []
        win32gui.EnumWindows(callback, windows)

        if not windows:
            return None

        # Use first matching window
        self._hwnd = windows[0]

        # Get window rect (includes borders/title bar)
        rect = win32gui.GetWindowRect(self._hwnd)

        # Get client rect (actual drawable area)
        try:
            client_rect = win32gui.GetClientRect(self._hwnd)
            # Convert client coordinates to screen coordinates
            client_top_left = win32gui.ClientToScreen(self._hwnd, (0, 0))

            self._window_bounds = WindowBounds(
                x=client_top_left[0],
                y=client_top_left[1],
                width=client_rect[2],
                height=client_rect[3],
            )
        except Exception:
            # Fallback to window rect
            self._window_bounds = WindowBounds(
                x=rect[0],
                y=rect[1],
                width=rect[2] - rect[0],
                height=rect[3] - rect[1],
            )

        return self._window_bounds

    def _find_window_linux(self) -> Optional[WindowBounds]:
        """Find window using xdotool (Linux).

        Returns:
            WindowBounds or None if not found
        """
        try:
            import subprocess
        except ImportError:
            return None

        try:
            # Find window ID by name
            result = subprocess.run(
                ["xdotool", "search", "--name", self.window_title],
                capture_output=True,
                text=True,
                timeout=5,
            )

            if result.returncode != 0 or not result.stdout.strip():
                return None

            # Get first matching window
            window_id = result.stdout.strip().split("\n")[0]

            # Get window geometry
            result = subprocess.run(
                ["xdotool", "getwindowgeometry", "--shell", window_id],
                capture_output=True,
                text=True,
                timeout=5,
            )

            if result.returncode != 0:
                return None

            # Parse geometry output
            geometry = {}
            for line in result.stdout.strip().split("\n"):
                if "=" in line:
                    key, value = line.split("=", 1)
                    geometry[key] = int(value)

            self._window_bounds = WindowBounds(
                x=geometry.get("X", 0),
                y=geometry.get("Y", 0),
                width=geometry.get("WIDTH", 800),
                height=geometry.get("HEIGHT", 600),
            )

            return self._window_bounds

        except (subprocess.TimeoutExpired, FileNotFoundError, ValueError):
            return None

    def capture_window(self, refresh_bounds: bool = False) -> Optional[np.ndarray]:
        """Capture the RuneLite window.

        Args:
            refresh_bounds: If True, re-find window position

        Returns:
            BGR numpy array of the window, or None if capture failed
        """
        if refresh_bounds or self._window_bounds is None:
            if not self.find_window():
                return None

        bounds = self._window_bounds
        monitor = {
            "left": bounds.x,
            "top": bounds.y,
            "width": bounds.width,
            "height": bounds.height,
        }

        try:
            screenshot = self._sct.grab(monitor)
            # Convert BGRA to BGR
            img = np.array(screenshot)
            return img[:, :, :3]
        except Exception:
            return None

    def capture_region(
        self, x: int, y: int, width: int, height: int, relative: bool = True
    ) -> Optional[np.ndarray]:
        """Capture a specific region.

        Args:
            x: X coordinate
            y: Y coordinate
            width: Region width
            height: Region height
            relative: If True, coordinates are relative to window

        Returns:
            BGR numpy array of the region, or None if capture failed
        """
        if relative:
            if self._window_bounds is None:
                if not self.find_window():
                    return None
            x += self._window_bounds.x
            y += self._window_bounds.y

        monitor = {"left": x, "top": y, "width": width, "height": height}

        try:
            screenshot = self._sct.grab(monitor)
            img = np.array(screenshot)
            return img[:, :, :3]
        except Exception:
            return None

    def capture_inventory(self, config: dict) -> Optional[np.ndarray]:
        """Capture the inventory region based on config.

        Args:
            config: Inventory config with x, y, slot_width, slot_height, cols, rows

        Returns:
            BGR numpy array of inventory region
        """
        inv = config
        width = inv["slot_width"] * inv["cols"]
        height = inv["slot_height"] * inv["rows"]
        return self.capture_region(inv["x"], inv["y"], width, height)

    @property
    def window_bounds(self) -> Optional[WindowBounds]:
        """Get current window bounds."""
        return self._window_bounds

    def close(self) -> None:
        """Clean up resources."""
        self._sct.close()
