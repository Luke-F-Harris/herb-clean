"""Keyboard input handling with enhanced anti-detection."""

import time
from typing import Optional, Dict, Any

from pynput.keyboard import Key

import numpy as np

from utils import create_rng
from .drivers import create_keyboard_driver


class KeyboardController:
    """Handle keyboard input with human-like timing.

    Supports multiple input drivers:
    - pynput (default): Cross-platform, uses Python library
    - ydotool: Linux-only, uses kernel uinput (less detectable)
    """

    def __init__(
        self,
        driver_name: str = "pynput",
        driver_config: Optional[Dict[str, Any]] = None,
    ):
        """Initialize keyboard controller.

        Args:
            driver_name: Input driver to use ("pynput" or "ydotool")
            driver_config: Driver-specific configuration
        """
        self._driver = create_keyboard_driver(driver_name, driver_config)
        self._driver_name = driver_name
        self._rng = create_rng()
        self._stop_flag = False
        self._last_key_time = 0.0

    def set_stop_flag(self, stop: bool = True) -> None:
        """Set flag to stop input."""
        self._stop_flag = stop

    def press_key(
        self,
        key: Key | str,
        duration: Optional[float] = None,
        pre_delay: bool = True,
    ) -> bool:
        """Press and release a key with randomized timing.

        Args:
            key: Key to press (pynput Key or character)
            duration: Hold duration in seconds (randomized if None)
            pre_delay: Add delay before keypress (simulates hand movement)

        Returns:
            True if completed
        """
        if self._stop_flag:
            return False

        # Pre-key delay (simulates moving hand from mouse to keyboard)
        if pre_delay:
            pre_delay_time = self._get_pre_key_delay()
            time.sleep(pre_delay_time)

        # Key press duration (time key is held down)
        if duration is None:
            duration = self._get_key_duration()

        # Press and hold
        self._driver.press(key)
        time.sleep(duration)
        self._driver.release(key)

        self._last_key_time = time.time()

        return True

    @property
    def driver_name(self) -> str:
        """Get the name of the current input driver."""
        return self._driver_name

    def _get_key_duration(self) -> float:
        """Get randomized key hold duration.

        Uses gamma distribution for natural variance.

        Returns:
            Duration in seconds
        """
        # Gamma distribution: shape=2, scale tuned for 60-120ms mean
        duration = self._rng.gamma(2.0, 0.03)

        # Clamp to reasonable bounds (30-200ms)
        duration = max(0.03, min(0.20, duration))

        return duration

    def _get_pre_key_delay(self) -> float:
        """Get delay before pressing key (hand travel time).

        Simulates moving hand from mouse to keyboard.

        Returns:
            Delay in seconds
        """
        # Check time since last key
        time_since_last = time.time() - self._last_key_time

        # If recent keypress, shorter delay (hand already near keyboard)
        if time_since_last < 2.0:
            # Quick successive keypresses: 50-150ms
            return self._rng.uniform(0.05, 0.15)
        else:
            # Hand movement from mouse: 150-400ms
            # Using gamma for right-skewed distribution
            delay = self._rng.gamma(2.0, 0.08) + 0.15
            return min(0.40, delay)

    def press_escape(self, pre_delay: bool = True) -> bool:
        """Press the Escape key (used to close bank).

        Args:
            pre_delay: Add delay before keypress

        Returns:
            True if completed
        """
        return self.press_key(Key.esc, pre_delay=pre_delay)

    def press_space(self, pre_delay: bool = True) -> bool:
        """Press the Space key.

        Args:
            pre_delay: Add delay before keypress

        Returns:
            True if completed
        """
        return self.press_key(Key.space, pre_delay=pre_delay)

    def press_enter(self, pre_delay: bool = True) -> bool:
        """Press the Enter key.

        Args:
            pre_delay: Add delay before keypress

        Returns:
            True if completed
        """
        return self.press_key(Key.enter, pre_delay=pre_delay)

    def type_text(self, text: str, wpm: float = 60) -> bool:
        """Type text with human-like timing.

        Args:
            text: Text to type
            wpm: Words per minute (for timing)

        Returns:
            True if completed
        """
        if self._stop_flag:
            return False

        # Calculate base delay from WPM (assuming 5 chars per word)
        chars_per_second = (wpm * 5) / 60
        base_delay = 1.0 / chars_per_second

        for i, char in enumerate(text):
            if self._stop_flag:
                return False

            # First character has pre-delay
            if i == 0:
                pre_delay = self._get_pre_key_delay()
                time.sleep(pre_delay)

            # Variable key press duration
            press_duration = self._get_key_duration()

            # Press character
            self._driver.press(char)
            time.sleep(press_duration)
            self._driver.release(char)

            # Delay between characters (varied)
            if i < len(text) - 1:
                delay = base_delay * self._rng.uniform(0.6, 1.4)
                time.sleep(delay)

        self._last_key_time = time.time()
        return True

    def press_number(self, number: int, pre_delay: bool = True) -> bool:
        """Press a number key (0-9).

        Args:
            number: Number to press
            pre_delay: Add delay before keypress

        Returns:
            True if completed
        """
        if not 0 <= number <= 9:
            return False

        return self.press_key(str(number), pre_delay=pre_delay)

    def press_f_key(self, number: int, pre_delay: bool = True) -> bool:
        """Press a function key (F1-F12).

        Args:
            number: Function key number (1-12)
            pre_delay: Add delay before keypress

        Returns:
            True if completed
        """
        if not 1 <= number <= 12:
            return False

        f_keys = {
            1: Key.f1, 2: Key.f2, 3: Key.f3, 4: Key.f4,
            5: Key.f5, 6: Key.f6, 7: Key.f7, 8: Key.f8,
            9: Key.f9, 10: Key.f10, 11: Key.f11, 12: Key.f12,
        }

        return self.press_key(f_keys[number], pre_delay=pre_delay)

    def hold_shift(self) -> None:
        """Press and hold Shift key."""
        # Small delay before holding (hand positioning)
        time.sleep(self._rng.uniform(0.01, 0.03))
        self._driver.press(Key.shift)

    def release_shift(self) -> None:
        """Release Shift key."""
        # Small delay before release
        time.sleep(self._rng.uniform(0.01, 0.03))
        self._driver.release(Key.shift)

    def shift_click_ready(self) -> "ShiftClickContext":
        """Context manager for shift-clicking.

        Usage:
            with keyboard.shift_click_ready():
                mouse.click()  # This will be a shift-click
        """
        return ShiftClickContext(self)

    def get_inter_key_delay(self) -> float:
        """Get delay between different key actions.

        For sequences like: key1, pause, key2

        Returns:
            Delay in seconds
        """
        # 100-300ms between different key actions
        return self._rng.gamma(2.0, 0.06) + 0.10


class ShiftClickContext:
    """Context manager for shift-click operations."""

    def __init__(self, keyboard: KeyboardController):
        self._keyboard = keyboard
        self._rng = create_rng()

    def __enter__(self):
        self._keyboard.hold_shift()
        # Randomized delay to ensure shift is registered
        time.sleep(self._rng.uniform(0.02, 0.05))
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Randomized delay before release
        time.sleep(self._rng.uniform(0.02, 0.05))
        self._keyboard.release_shift()
        return False
