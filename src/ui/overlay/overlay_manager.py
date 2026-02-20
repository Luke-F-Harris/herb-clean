"""Overlay manager - handles threading and lifecycle."""

import logging
import queue
import threading
import time
from typing import Optional, Callable

from .detection_data import DetectionData
from .overlay_window import OverlayWindow
from .overlay_renderer import OverlayRenderer


class OverlayManager:
    """Manages the overlay window in a separate thread.

    The overlay runs in its own daemon thread to avoid blocking
    the main bot loop. Detection data is passed via a thread-safe
    queue.

    Usage:
        overlay = OverlayManager(screen_capture)
        overlay.start()
        ...
        overlay.update(detection_data)
        ...
        overlay.stop()
    """

    def __init__(
        self,
        screen_capture,  # ScreenCapture instance
        config: Optional[dict] = None,
    ):
        """Initialize overlay manager.

        Args:
            screen_capture: ScreenCapture instance for window tracking
            config: Optional overlay configuration dict
        """
        self._logger = logging.getLogger(__name__)
        self._screen = screen_capture
        self._config = config or {}

        # Thread-safe queue for passing data
        self._data_queue: queue.Queue[DetectionData] = queue.Queue(maxsize=5)

        # Thread management
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._lock = threading.Lock()

        # Components (initialized in thread)
        self._window: Optional[OverlayWindow] = None
        self._renderer: Optional[OverlayRenderer] = None

        # Render settings
        self._fps_limit = self._config.get("fps_limit", 30)
        self._frame_time = 1.0 / self._fps_limit

        # Latest data for rendering
        self._latest_data: Optional[DetectionData] = None

    def start(self) -> bool:
        """Start the overlay thread.

        Returns:
            True if started successfully
        """
        with self._lock:
            if self._running:
                self._logger.warning("Overlay already running")
                return True

            self._running = True
            self._thread = threading.Thread(
                target=self._run_loop,
                name="OverlayThread",
                daemon=True,
            )
            self._thread.start()
            self._logger.info("Overlay thread started")
            return True

    def stop(self) -> None:
        """Stop the overlay thread."""
        with self._lock:
            if not self._running:
                return

            self._running = False

        # Wait for thread to finish (with timeout)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)

        self._logger.info("Overlay thread stopped")

    def update(self, data: DetectionData) -> None:
        """Update overlay with new detection data.

        This is called from the main bot thread. Data is passed
        via a thread-safe queue to the overlay thread.

        Args:
            data: New detection data to display
        """
        try:
            # Non-blocking put, drop old data if queue is full
            try:
                self._data_queue.put_nowait(data)
            except queue.Full:
                # Remove old data and add new
                try:
                    self._data_queue.get_nowait()
                except queue.Empty:
                    pass
                self._data_queue.put_nowait(data)
        except Exception as e:
            self._logger.debug("Failed to queue overlay data: %s", e)

    def is_running(self) -> bool:
        """Check if overlay is running."""
        return self._running

    def _run_loop(self) -> None:
        """Main overlay thread loop."""
        try:
            # Initialize components in this thread
            if not self._initialize():
                self._running = False
                return

            last_frame_time = time.time()

            while self._running:
                frame_start = time.time()

                # Process pygame events
                if not self._window.handle_events():
                    self._running = False
                    break

                # Get latest data from queue
                self._drain_queue()

                # Update window position to track RuneLite
                self._window.update_position()

                # Render if we have data
                if self._latest_data:
                    surface = self._window.get_surface()
                    if surface:
                        self._renderer.render(
                            surface,
                            self._latest_data,
                            self._window.transparent_color,
                        )
                        self._window.flip()

                # Frame rate limiting
                elapsed = time.time() - frame_start
                if elapsed < self._frame_time:
                    time.sleep(self._frame_time - elapsed)

        except Exception as e:
            self._logger.error("Overlay thread error: %s", e)
        finally:
            self._cleanup()

    def _initialize(self) -> bool:
        """Initialize overlay components.

        Returns:
            True if initialization successful
        """
        try:
            # Create window
            self._window = OverlayWindow(
                get_window_bounds=lambda: self._screen.window_bounds,
            )

            if not self._window.initialize():
                return False

            # Create renderer
            self._renderer = OverlayRenderer(config=self._config)
            if not self._renderer.initialize():
                return False

            self._logger.info("Overlay components initialized")
            return True

        except Exception as e:
            self._logger.error("Failed to initialize overlay: %s", e)
            return False

    def _drain_queue(self) -> None:
        """Get latest data from queue, discarding old entries."""
        latest = None
        while True:
            try:
                latest = self._data_queue.get_nowait()
            except queue.Empty:
                break

        if latest:
            self._latest_data = latest

    def _cleanup(self) -> None:
        """Clean up overlay resources."""
        if self._window:
            self._window.stop()
            self._window = None
        self._renderer = None


def check_pygame_available() -> bool:
    """Check if pygame is available.

    Returns:
        True if pygame can be imported
    """
    try:
        import pygame
        return True
    except ImportError:
        return False
