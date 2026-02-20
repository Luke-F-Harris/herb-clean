"""Data structures for passing vision detection data to the overlay."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import time


class SlotDisplayState(Enum):
    """Visual state for overlay display."""

    EMPTY = "empty"
    GRIMY = "grimy"
    CLEAN = "clean"
    UNKNOWN = "unknown"


@dataclass
class InventorySlotInfo:
    """Information about a single inventory slot for overlay display."""

    index: int
    row: int
    col: int
    screen_x: int  # Absolute screen X coordinate (center)
    screen_y: int  # Absolute screen Y coordinate (center)
    width: int
    height: int
    state: SlotDisplayState = SlotDisplayState.EMPTY
    item_name: Optional[str] = None
    confidence: float = 0.0


@dataclass
class MatchInfo:
    """Information about a template match for overlay display."""

    label: str
    screen_x: int  # Absolute screen X coordinate (center)
    screen_y: int  # Absolute screen Y coordinate (center)
    width: int
    height: int
    confidence: float
    match_type: str = "template"  # "template", "bank_ui", "herb"


@dataclass
class WindowBoundsInfo:
    """Window bounds information for overlay positioning."""

    x: int
    y: int
    width: int
    height: int


@dataclass
class DetectionData:
    """Complete detection data snapshot for overlay rendering.

    This is passed from the main bot thread to the overlay thread
    via a queue, containing all the information needed to render
    the current vision state.
    """

    timestamp: float = field(default_factory=time.time)
    state_name: str = "idle"  # Current BotState name

    # Window information
    window_bounds: Optional[WindowBoundsInfo] = None

    # Inventory state (28 slots)
    inventory_slots: list[InventorySlotInfo] = field(default_factory=list)

    # Bank UI matches (buttons, etc.)
    bank_matches: list[MatchInfo] = field(default_factory=list)

    # Recent template matches with labels
    recent_matches: list[MatchInfo] = field(default_factory=list)

    # Stats for display
    herbs_cleaned: int = 0
    grimy_count: int = 0
    clean_count: int = 0
    empty_count: int = 0

    @property
    def age_ms(self) -> float:
        """Get age of this detection data in milliseconds."""
        return (time.time() - self.timestamp) * 1000


def create_detection_data_from_bot(
    state_name: str,
    window_bounds,  # WindowBounds from screen_capture
    inventory_slots: list,  # InventorySlot list from inventory_detector
    inventory_config: dict,
    bank_matches: Optional[list] = None,
    recent_matches: Optional[list] = None,
    herbs_cleaned: int = 0,
) -> DetectionData:
    """Create DetectionData from bot components.

    This is a helper function to convert internal bot data structures
    to the overlay-friendly DetectionData format.

    Args:
        state_name: Current bot state name
        window_bounds: WindowBounds from ScreenCapture
        inventory_slots: List of InventorySlot from InventoryDetector
        inventory_config: Inventory config dict with slot dimensions
        bank_matches: Optional list of bank template matches
        recent_matches: Optional list of recent template matches
        herbs_cleaned: Number of herbs cleaned this session

    Returns:
        DetectionData ready for overlay rendering
    """
    # Convert window bounds
    window_info = None
    if window_bounds:
        window_info = WindowBoundsInfo(
            x=window_bounds.x,
            y=window_bounds.y,
            width=window_bounds.width,
            height=window_bounds.height,
        )

    # Convert inventory slots
    slot_width = inventory_config.get("slot_width", 42)
    slot_height = inventory_config.get("slot_height", 36)

    slot_infos = []
    grimy_count = 0
    clean_count = 0
    empty_count = 0

    for slot in inventory_slots:
        # Map SlotState to SlotDisplayState
        if slot.state.value == "grimy":
            display_state = SlotDisplayState.GRIMY
            grimy_count += 1
        elif slot.state.value == "clean":
            display_state = SlotDisplayState.CLEAN
            clean_count += 1
        elif slot.state.value == "empty":
            display_state = SlotDisplayState.EMPTY
            empty_count += 1
        else:
            display_state = SlotDisplayState.UNKNOWN

        # Calculate absolute screen coordinates
        screen_x = slot.x
        screen_y = slot.y
        if window_bounds:
            screen_x += window_bounds.x
            screen_y += window_bounds.y

        slot_infos.append(
            InventorySlotInfo(
                index=slot.index,
                row=slot.row,
                col=slot.col,
                screen_x=screen_x,
                screen_y=screen_y,
                width=slot_width,
                height=slot_height,
                state=display_state,
                item_name=slot.item_name,
            )
        )

    # Convert match info
    bank_match_infos = []
    if bank_matches:
        for match in bank_matches:
            if hasattr(match, "center_x") and match.found:
                bank_match_infos.append(
                    MatchInfo(
                        label=getattr(match, "template_name", "bank_ui"),
                        screen_x=match.center_x,
                        screen_y=match.center_y,
                        width=getattr(match, "width", 32),
                        height=getattr(match, "height", 32),
                        confidence=match.confidence,
                        match_type="bank_ui",
                    )
                )

    recent_match_infos = []
    if recent_matches:
        for match in recent_matches:
            if hasattr(match, "center_x") and match.found:
                recent_match_infos.append(
                    MatchInfo(
                        label=getattr(match, "template_name", "template"),
                        screen_x=match.center_x,
                        screen_y=match.center_y,
                        width=getattr(match, "width", 32),
                        height=getattr(match, "height", 32),
                        confidence=match.confidence,
                        match_type="template",
                    )
                )

    return DetectionData(
        state_name=state_name,
        window_bounds=window_info,
        inventory_slots=slot_infos,
        bank_matches=bank_match_infos,
        recent_matches=recent_match_infos,
        herbs_cleaned=herbs_cleaned,
        grimy_count=grimy_count,
        clean_count=clean_count,
        empty_count=empty_count,
    )
