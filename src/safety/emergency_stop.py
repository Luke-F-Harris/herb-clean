"""Emergency stop functionality with hotkey listener."""

import logging
import os
import threading
import time
from typing import Callable, Optional

from pynput import keyboard


logger = logging.getLogger(__name__)

# Signal file used by emergency_stop_helper.py for ydotool mode
SIGNAL_FILE = "/tmp/osrs_herblore_stop_signal"


class EmergencyStop:
    """Emergency stop handler with F12 hotkey.

    Supports two modes:
    - pynput mode (default): Uses pynput keyboard listener
    - ydotool mode: Polls a signal file written by emergency_stop_helper.py
    """

    def __init__(
        self,
        stop_key: str = "f12",
        on_stop_callback: Optional[Callable[[], None]] = None,
        use_signal_file: bool = False,
        poll_interval: float = 0.1,
    ):
        """Initialize emergency stop.

        Args:
            stop_key: Key to trigger emergency stop
            on_stop_callback: Function to call on emergency stop
            use_signal_file: Use signal file polling instead of pynput listener
                            (for ydotool mode where pynput listener may not work)
            poll_interval: How often to check signal file (seconds)
        """
        self._stop_key = self._parse_key(stop_key)
        self._on_stop_callback = on_stop_callback
        self._is_stopped = False
        self._listener: Optional[keyboard.Listener] = None
        self._lock = threading.Lock()

        # Signal file polling (for ydotool mode)
        self._use_signal_file = use_signal_file
        self._poll_interval = poll_interval
        self._poll_thread: Optional[threading.Thread] = None
        self._polling = False

    def _parse_key(self, key_str: str) -> keyboard.Key:
        """Parse key string to pynput Key.

        Args:
            key_str: Key name (e.g., "f12", "escape")

        Returns:
            pynput Key object
        """
        key_map = {
            "f1": keyboard.Key.f1,
            "f2": keyboard.Key.f2,
            "f3": keyboard.Key.f3,
            "f4": keyboard.Key.f4,
            "f5": keyboard.Key.f5,
            "f6": keyboard.Key.f6,
            "f7": keyboard.Key.f7,
            "f8": keyboard.Key.f8,
            "f9": keyboard.Key.f9,
            "f10": keyboard.Key.f10,
            "f11": keyboard.Key.f11,
            "f12": keyboard.Key.f12,
            "escape": keyboard.Key.esc,
            "esc": keyboard.Key.esc,
            "pause": keyboard.Key.pause,
        }

        return key_map.get(key_str.lower(), keyboard.Key.f12)

    def _on_key_press(self, key: keyboard.Key) -> None:
        """Handle key press events.

        Args:
            key: Pressed key
        """
        if key == self._stop_key:
            self.trigger_stop()

    def trigger_stop(self) -> None:
        """Trigger emergency stop."""
        with self._lock:
            if self._is_stopped:
                return

            self._is_stopped = True

            if self._on_stop_callback:
                # Run callback in separate thread to avoid blocking
                threading.Thread(
                    target=self._on_stop_callback,
                    daemon=True,
                ).start()

    def start_listening(self) -> None:
        """Start listening for emergency stop key."""
        if self._use_signal_file:
            self._start_signal_polling()
        else:
            self._start_keyboard_listener()

    def _start_keyboard_listener(self) -> None:
        """Start pynput keyboard listener."""
        if self._listener is not None:
            return

        self._listener = keyboard.Listener(on_press=self._on_key_press)
        self._listener.start()
        logger.debug("Started keyboard listener for emergency stop")

    def _start_signal_polling(self) -> None:
        """Start signal file polling thread."""
        if self._polling:
            return

        # Clear any existing signal file
        self._clear_signal_file()

        self._polling = True
        self._poll_thread = threading.Thread(
            target=self._poll_signal_file,
            daemon=True,
        )
        self._poll_thread.start()
        logger.info(
            "Started signal file polling for emergency stop. "
            "Run 'python tools/emergency_stop_helper.py' in another terminal."
        )

    def _poll_signal_file(self) -> None:
        """Poll signal file for stop signal."""
        while self._polling:
            if os.path.exists(SIGNAL_FILE):
                try:
                    with open(SIGNAL_FILE, "r") as f:
                        content = f.read().strip()
                    if content == "1":
                        logger.info("Emergency stop signal detected from file")
                        self.trigger_stop()
                        # Clear signal file after processing
                        self._clear_signal_file()
                except (IOError, OSError) as e:
                    logger.debug("Error reading signal file: %s", e)

            time.sleep(self._poll_interval)

    def _clear_signal_file(self) -> None:
        """Clear the signal file."""
        try:
            if os.path.exists(SIGNAL_FILE):
                os.remove(SIGNAL_FILE)
        except OSError:
            pass

    def stop_listening(self) -> None:
        """Stop listening for emergency stop key."""
        # Stop keyboard listener
        if self._listener is not None:
            self._listener.stop()
            self._listener = None

        # Stop signal polling
        self._polling = False
        if self._poll_thread is not None:
            self._poll_thread.join(timeout=1.0)
            self._poll_thread = None

        # Clean up signal file
        self._clear_signal_file()

    def is_stopped(self) -> bool:
        """Check if emergency stop was triggered.

        Returns:
            True if stopped
        """
        with self._lock:
            return self._is_stopped

    def reset(self) -> None:
        """Reset emergency stop state."""
        with self._lock:
            self._is_stopped = False

    def set_callback(self, callback: Optional[Callable[[], None]]) -> None:
        """Set or update the stop callback.

        Args:
            callback: Function to call on emergency stop
        """
        self._on_stop_callback = callback

    def __enter__(self):
        """Context manager entry."""
        self.start_listening()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop_listening()
        return False
