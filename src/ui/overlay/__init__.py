"""Transparent click-through overlay for vision debugging.

This module provides a real-time visualization of what the bot "sees":
- Inventory slot states (grimy/clean/empty)
- Template match bounding boxes with confidence
- Current bot state
- Detection statistics

Usage:
    from ui.overlay import OverlayManager, check_pygame_available

    if check_pygame_available():
        overlay = OverlayManager(screen_capture, config)
        overlay.start()
        ...
        overlay.update(detection_data)
        ...
        overlay.stop()
"""

from .detection_data import (
    DetectionData,
    InventorySlotInfo,
    MatchInfo,
    SlotDisplayState,
    WindowBoundsInfo,
    create_detection_data_from_bot,
)
from .overlay_manager import OverlayManager, check_pygame_available
from .overlay_renderer import OverlayRenderer
from .overlay_window import OverlayWindow

__all__ = [
    "DetectionData",
    "InventorySlotInfo",
    "MatchInfo",
    "SlotDisplayState",
    "WindowBoundsInfo",
    "create_detection_data_from_bot",
    "OverlayManager",
    "OverlayRenderer",
    "OverlayWindow",
    "check_pygame_available",
]
