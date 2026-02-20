"""Pygame overlay window with Win32 click-through support.

This module creates a transparent, always-on-top window that allows
mouse clicks to pass through to the underlying application (RuneLite).
On Windows, this uses WS_EX_LAYERED and WS_EX_TRANSPARENT window styles.
On Linux, the window appears but click-through is not supported.
"""

import logging
import sys
from typing import Optional, Callable

import pygame

from .detection_data import DetectionData


class OverlayWindow:
    """Transparent overlay window that tracks RuneLite position.

    On Windows:
    - Uses WS_EX_LAYERED | WS_EX_TRANSPARENT for click-through
    - Uses HWND_TOPMOST to stay on top

    On Linux:
    - Creates a normal pygame window (for visual testing)
    - Click-through not supported
    """

    # Colorkey for transparency (this exact color becomes transparent)
    TRANSPARENT_COLOR = (255, 0, 255)  # Magenta

    def __init__(
        self,
        get_window_bounds: Callable,
        width: int = 800,
        height: int = 600,
    ):
        """Initialize overlay window.

        Args:
            get_window_bounds: Callable that returns current WindowBounds
            width: Initial window width
            height: Initial window height
        """
        self._logger = logging.getLogger(__name__)
        self._get_window_bounds = get_window_bounds
        self._width = width
        self._height = height
        self._running = False
        self._screen: Optional[pygame.Surface] = None
        self._hwnd: Optional[int] = None
        self._is_windows = sys.platform == "win32"
        self._last_bounds = None

    def initialize(self) -> bool:
        """Initialize pygame and create the overlay window.

        Returns:
            True if initialization successful
        """
        try:
            # Initialize pygame
            pygame.init()

            # Get initial window bounds
            bounds = self._get_window_bounds()
            if bounds:
                self._width = bounds.width
                self._height = bounds.height

            # Create window with no frame
            flags = pygame.NOFRAME

            # Position window before creation on Windows
            if self._is_windows and bounds:
                import os
                os.environ["SDL_VIDEO_WINDOW_POS"] = f"{bounds.x},{bounds.y}"

            self._screen = pygame.display.set_mode(
                (self._width, self._height),
                flags,
            )
            pygame.display.set_caption("Herblore Bot Overlay")

            # Fill with transparent color
            self._screen.fill(self.TRANSPARENT_COLOR)

            # Apply Windows-specific click-through settings
            if self._is_windows:
                self._apply_windows_transparency()

            self._running = True
            self._logger.info(
                "Overlay window initialized: %dx%d, click-through=%s",
                self._width,
                self._height,
                self._is_windows,
            )
            return True

        except Exception as e:
            self._logger.error("Failed to initialize overlay window: %s", e)
            return False

    def _apply_windows_transparency(self) -> None:
        """Apply Windows-specific transparency and click-through settings."""
        try:
            import win32gui
            import win32con
            import win32api

            # Get pygame window handle
            info = pygame.display.get_wm_info()
            self._hwnd = info["window"]

            # Extended window style flags
            GWL_EXSTYLE = -20
            WS_EX_LAYERED = 0x00080000
            WS_EX_TRANSPARENT = 0x00000020
            WS_EX_TOPMOST = 0x00000008

            # Get current extended style
            ex_style = win32gui.GetWindowLong(self._hwnd, GWL_EXSTYLE)

            # Add layered and transparent styles
            new_style = ex_style | WS_EX_LAYERED | WS_EX_TRANSPARENT

            win32gui.SetWindowLong(self._hwnd, GWL_EXSTYLE, new_style)

            # Set color key for transparency (magenta becomes transparent)
            # LWA_COLORKEY = 0x00000001
            win32gui.SetLayeredWindowAttributes(
                self._hwnd,
                win32api.RGB(*self.TRANSPARENT_COLOR),  # Colorkey
                0,  # Alpha (not used with LWA_COLORKEY alone)
                0x00000001,  # LWA_COLORKEY
            )

            # Make window always on top
            HWND_TOPMOST = -1
            SWP_NOMOVE = 0x0002
            SWP_NOSIZE = 0x0001
            SWP_NOACTIVATE = 0x0010

            win32gui.SetWindowPos(
                self._hwnd,
                HWND_TOPMOST,
                0, 0, 0, 0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE,
            )

            self._logger.debug("Windows transparency applied successfully")

        except ImportError:
            self._logger.warning("pywin32 not available, click-through disabled")
        except Exception as e:
            self._logger.error("Failed to apply Windows transparency: %s", e)

    def update_position(self) -> bool:
        """Update overlay position to match RuneLite window.

        Returns:
            True if position was updated, False if window not found
        """
        bounds = self._get_window_bounds()
        if not bounds:
            return False

        # Check if position or size changed
        if self._last_bounds:
            if (
                bounds.x == self._last_bounds.x
                and bounds.y == self._last_bounds.y
                and bounds.width == self._last_bounds.width
                and bounds.height == self._last_bounds.height
            ):
                return True  # No change needed

        self._last_bounds = bounds

        # Resize if needed
        if bounds.width != self._width or bounds.height != self._height:
            self._width = bounds.width
            self._height = bounds.height
            self._screen = pygame.display.set_mode(
                (self._width, self._height),
                pygame.NOFRAME,
            )
            # Reapply transparency after resize
            if self._is_windows:
                self._apply_windows_transparency()

        # Move window to match RuneLite position
        if self._is_windows and self._hwnd:
            try:
                import win32gui

                # SWP_NOSIZE = 0x0001, SWP_NOZORDER = 0x0004, SWP_NOACTIVATE = 0x0010
                win32gui.SetWindowPos(
                    self._hwnd,
                    -1,  # HWND_TOPMOST
                    bounds.x,
                    bounds.y,
                    0, 0,
                    0x0001 | 0x0010,  # SWP_NOSIZE | SWP_NOACTIVATE
                )
            except Exception as e:
                self._logger.debug("Failed to move window: %s", e)

        return True

    def clear(self) -> None:
        """Clear the overlay with transparent color."""
        if self._screen:
            self._screen.fill(self.TRANSPARENT_COLOR)

    def get_surface(self) -> Optional[pygame.Surface]:
        """Get the pygame surface for drawing.

        Returns:
            Pygame surface or None if not initialized
        """
        return self._screen

    def flip(self) -> None:
        """Update the display with current drawing."""
        if self._screen:
            pygame.display.flip()

    def handle_events(self) -> bool:
        """Process pygame events.

        Returns:
            True if window should continue running, False if quit requested
        """
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return False
        return True

    def is_running(self) -> bool:
        """Check if overlay is running."""
        return self._running

    def stop(self) -> None:
        """Stop and clean up overlay window."""
        self._running = False
        try:
            pygame.quit()
        except Exception:
            pass
        self._logger.info("Overlay window stopped")

    @property
    def width(self) -> int:
        """Get current window width."""
        return self._width

    @property
    def height(self) -> int:
        """Get current window height."""
        return self._height

    @property
    def transparent_color(self) -> tuple[int, int, int]:
        """Get the transparent color key."""
        return self.TRANSPARENT_COLOR
