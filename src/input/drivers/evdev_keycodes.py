"""Evdev keycode mappings for ydotool keyboard input.

These codes match the Linux kernel's input event codes.
See: /usr/include/linux/input-event-codes.h
"""

from pynput.keyboard import Key as PynputKey


# Evdev keycodes for common keys
# These are used by ydotool for keyboard input
EVDEV_KEYCODES = {
    # Letters (lowercase)
    "a": 30,
    "b": 48,
    "c": 46,
    "d": 32,
    "e": 18,
    "f": 33,
    "g": 34,
    "h": 35,
    "i": 23,
    "j": 36,
    "k": 37,
    "l": 38,
    "m": 50,
    "n": 49,
    "o": 24,
    "p": 25,
    "q": 16,
    "r": 19,
    "s": 31,
    "t": 20,
    "u": 22,
    "v": 47,
    "w": 17,
    "x": 45,
    "y": 21,
    "z": 44,
    # Numbers
    "0": 11,
    "1": 2,
    "2": 3,
    "3": 4,
    "4": 5,
    "5": 6,
    "6": 7,
    "7": 8,
    "8": 9,
    "9": 10,
    # Special characters
    " ": 57,  # Space
    "\n": 28,  # Enter
    "\t": 15,  # Tab
    "-": 12,
    "=": 13,
    "[": 26,
    "]": 27,
    "\\": 43,
    ";": 39,
    "'": 40,
    "`": 41,
    ",": 51,
    ".": 52,
    "/": 53,
}

# Pynput Key to evdev keycode mapping
PYNPUT_TO_EVDEV = {
    PynputKey.esc: 1,
    PynputKey.f1: 59,
    PynputKey.f2: 60,
    PynputKey.f3: 61,
    PynputKey.f4: 62,
    PynputKey.f5: 63,
    PynputKey.f6: 64,
    PynputKey.f7: 65,
    PynputKey.f8: 66,
    PynputKey.f9: 67,
    PynputKey.f10: 68,
    PynputKey.f11: 87,
    PynputKey.f12: 88,
    PynputKey.backspace: 14,
    PynputKey.tab: 15,
    PynputKey.enter: 28,
    PynputKey.shift: 42,  # Left shift
    PynputKey.shift_l: 42,
    PynputKey.shift_r: 54,
    PynputKey.ctrl: 29,  # Left ctrl
    PynputKey.ctrl_l: 29,
    PynputKey.ctrl_r: 97,
    PynputKey.alt: 56,  # Left alt
    PynputKey.alt_l: 56,
    PynputKey.alt_r: 100,
    PynputKey.caps_lock: 58,
    PynputKey.space: 57,
    PynputKey.up: 103,
    PynputKey.down: 108,
    PynputKey.left: 105,
    PynputKey.right: 106,
    PynputKey.home: 102,
    PynputKey.end: 107,
    PynputKey.page_up: 104,
    PynputKey.page_down: 109,
    PynputKey.insert: 110,
    PynputKey.delete: 111,
    PynputKey.pause: 119,
}


def get_evdev_keycode(key) -> int:
    """Get evdev keycode for a key.

    Args:
        key: Either a string character or pynput Key

    Returns:
        Evdev keycode integer

    Raises:
        ValueError: If key is not mapped
    """
    if isinstance(key, str):
        if len(key) == 1:
            code = EVDEV_KEYCODES.get(key.lower())
            if code is not None:
                return code
        raise ValueError(f"Unknown character: {key}")

    # Check if it's a pynput Key
    code = PYNPUT_TO_EVDEV.get(key)
    if code is not None:
        return code

    raise ValueError(f"Unknown key: {key}")


def needs_shift(char: str) -> bool:
    """Check if a character requires shift key.

    Args:
        char: Single character

    Returns:
        True if shift is needed
    """
    # Uppercase letters
    if char.isupper():
        return True

    # Shift symbols
    shift_chars = set('~!@#$%^&*()_+{}|:"<>?')
    return char in shift_chars
