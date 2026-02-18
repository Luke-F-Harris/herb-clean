"""Keyboard input handling."""

import time
from typing import Optional

from pynput.keyboard import Key, Controller as KeyboardDriver

import numpy as np


class KeyboardController:
    """Handle keyboard input with human-like timing."""

    def __init__(self):
        """Initialize keyboard controller."""
        self._keyboard = KeyboardDriver()
        self._rng = np.random.default_rng()
        self._stop_flag = False

    def set_stop_flag(self, stop: bool = True) -> None:
        """Set flag to stop input."""
        self._stop_flag = stop

    def press_key(self, key: Key | str, duration: Optional[float] = None) -> bool:
        """Press and release a key.

        Args:
            key: Key to press (pynput Key or character)
            duration: Hold duration in seconds (randomized if None)

        Returns:
            True if completed
        """
        if self._stop_flag:
            return False

        if duration is None:
            # Human-like key press duration: 50-150ms
            duration = self._rng.uniform(0.05, 0.15)

        self._keyboard.press(key)
        time.sleep(duration)
        self._keyboard.release(key)

        return True

    def press_escape(self) -> bool:
        """Press the Escape key (used to close bank)."""
        return self.press_key(Key.esc)

    def press_space(self) -> bool:
        """Press the Space key."""
        return self.press_key(Key.space)

    def press_enter(self) -> bool:
        """Press the Enter key."""
        return self.press_key(Key.enter)

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

        for char in text:
            if self._stop_flag:
                return False

            # Press character
            self._keyboard.press(char)
            time.sleep(self._rng.uniform(0.02, 0.08))
            self._keyboard.release(char)

            # Delay between characters
            delay = base_delay * self._rng.uniform(0.7, 1.3)
            time.sleep(delay)

        return True

    def press_number(self, number: int) -> bool:
        """Press a number key (0-9).

        Args:
            number: Number to press

        Returns:
            True if completed
        """
        if not 0 <= number <= 9:
            return False

        return self.press_key(str(number))

    def press_f_key(self, number: int) -> bool:
        """Press a function key (F1-F12).

        Args:
            number: Function key number (1-12)

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

        return self.press_key(f_keys[number])

    def hold_shift(self) -> None:
        """Press and hold Shift key."""
        self._keyboard.press(Key.shift)

    def release_shift(self) -> None:
        """Release Shift key."""
        self._keyboard.release(Key.shift)

    def shift_click_ready(self) -> "ShiftClickContext":
        """Context manager for shift-clicking.

        Usage:
            with keyboard.shift_click_ready():
                mouse.click()  # This will be a shift-click
        """
        return ShiftClickContext(self)


class ShiftClickContext:
    """Context manager for shift-click operations."""

    def __init__(self, keyboard: KeyboardController):
        self._keyboard = keyboard

    def __enter__(self):
        self._keyboard.hold_shift()
        time.sleep(0.02)  # Small delay to ensure shift is registered
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        time.sleep(0.02)
        self._keyboard.release_shift()
        return False
