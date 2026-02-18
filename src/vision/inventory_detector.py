"""Inventory slot detection and classification."""

from dataclasses import dataclass
from enum import Enum
from typing import Optional

import numpy as np

from .screen_capture import ScreenCapture
from .template_matcher import TemplateMatcher
from .inventory_auto_detect import InventoryAutoDetector, InventoryRegion


class SlotState(Enum):
    """State of an inventory slot."""

    EMPTY = "empty"
    GRIMY_HERB = "grimy"
    CLEAN_HERB = "clean"
    UNKNOWN = "unknown"


@dataclass
class InventorySlot:
    """Represents a single inventory slot."""

    index: int  # 0-27
    row: int  # 0-6
    col: int  # 0-3
    x: int  # Screen x (center)
    y: int  # Screen y (center)
    state: SlotState = SlotState.EMPTY
    item_name: Optional[str] = None


class InventoryDetector:
    """Detect inventory state and item positions."""

    def __init__(
        self,
        screen_capture: ScreenCapture,
        template_matcher: TemplateMatcher,
        inventory_config: dict,
        grimy_templates: list[dict],
        auto_detect: bool = True,
    ):
        """Initialize inventory detector.

        Args:
            screen_capture: Screen capture instance
            template_matcher: Template matcher instance
            inventory_config: Inventory position config (used as fallback)
            grimy_templates: List of grimy herb template configs
            auto_detect: Enable auto-detection of inventory position
        """
        self.screen = screen_capture
        self.matcher = template_matcher
        self.config = inventory_config
        self.grimy_templates = grimy_templates
        self._auto_detect = auto_detect
        self._auto_detector = InventoryAutoDetector() if auto_detect else None
        self._detected_region: Optional[InventoryRegion] = None

        # Pre-calculate slot positions (may be updated by auto-detection)
        self.slots: list[InventorySlot] = self._init_slots()

    def _init_slots(self) -> list[InventorySlot]:
        """Initialize inventory slot positions."""
        slots = []
        inv = self.config

        for row in range(inv.get("rows", 7)):
            for col in range(inv.get("cols", 4)):
                index = row * inv.get("cols", 4) + col
                # Calculate center of slot
                x = inv.get("x", 563) + col * inv.get("slot_width", 42) + inv.get("slot_width", 42) // 2
                y = inv.get("y", 208) + row * inv.get("slot_height", 36) + inv.get("slot_height", 36) // 2

                slots.append(
                    InventorySlot(
                        index=index,
                        row=row,
                        col=col,
                        x=x,
                        y=y,
                    )
                )

        return slots

    def update_inventory_region(self, region: InventoryRegion) -> None:
        """Update inventory region and recalculate slot positions.

        Args:
            region: New inventory region
        """
        self.config = {
            "x": region.x,
            "y": region.y,
            "slot_width": region.slot_width,
            "slot_height": region.slot_height,
            "cols": region.cols,
            "rows": region.rows,
        }
        self._detected_region = region
        self.slots = self._init_slots()

    def auto_detect_inventory(self) -> bool:
        """Auto-detect inventory position in current window.

        Returns:
            True if detection successful
        """
        if not self._auto_detector:
            return False

        screen_image = self.screen.capture_window()
        if screen_image is None:
            return False

        region = self._auto_detector.detect_with_fallback(screen_image, self.config)

        if region.confidence > 0.5:
            self.update_inventory_region(region)
            return True

        return False

    def get_slot_screen_coords(self, slot_index: int) -> tuple[int, int]:
        """Get screen coordinates for a slot.

        Args:
            slot_index: Slot index (0-27)

        Returns:
            (x, y) screen coordinates
        """
        if slot_index < 0 or slot_index >= len(self.slots):
            raise ValueError(f"Invalid slot index: {slot_index}")

        slot = self.slots[slot_index]
        bounds = self.screen.window_bounds

        if bounds:
            return (bounds.x + slot.x, bounds.y + slot.y)
        return (slot.x, slot.y)

    def detect_inventory_state(self) -> list[InventorySlot]:
        """Detect state of all inventory slots.

        Returns:
            List of InventorySlots with updated states
        """
        # Auto-detect inventory on first run if enabled
        if self._auto_detect and self._detected_region is None:
            self.auto_detect_inventory()

        # Capture inventory region
        inv_image = self.screen.capture_inventory(self.config)
        if inv_image is None:
            return self.slots

        # Update slot states based on template matching
        for slot in self.slots:
            slot.state = SlotState.EMPTY
            slot.item_name = None

            # Extract slot region
            slot_region = self._extract_slot_region(inv_image, slot)
            if slot_region is None:
                continue

            # Check for grimy herbs
            for herb_config in self.grimy_templates:
                template_name = herb_config["template"]
                match = self.matcher.match(slot_region, template_name)

                if match.found:
                    slot.state = SlotState.GRIMY_HERB
                    slot.item_name = herb_config["name"]
                    break

            # If not grimy and not empty, might be clean herb
            if slot.state == SlotState.EMPTY:
                # Check if slot has content (simple color variance check)
                if self._slot_has_content(slot_region):
                    slot.state = SlotState.CLEAN_HERB

        return self.slots

    def _extract_slot_region(
        self, inv_image: np.ndarray, slot: InventorySlot
    ) -> Optional[np.ndarray]:
        """Extract a single slot region from inventory image."""
        inv = self.config
        # Calculate slot bounds relative to inventory image
        x1 = slot.col * inv["slot_width"]
        y1 = slot.row * inv["slot_height"]
        x2 = x1 + inv["slot_width"]
        y2 = y1 + inv["slot_height"]

        if x2 > inv_image.shape[1] or y2 > inv_image.shape[0]:
            return None

        return inv_image[y1:y2, x1:x2]

    def _slot_has_content(self, slot_region: np.ndarray) -> bool:
        """Check if slot region has item content.

        Uses color variance to detect if slot is not empty.
        Empty slots have low variance (uniform background).
        """
        # Calculate standard deviation of colors
        std = np.std(slot_region)
        # Threshold determined empirically
        return std > 25

    def count_grimy_herbs(self) -> int:
        """Count number of grimy herbs in inventory."""
        return sum(1 for slot in self.slots if slot.state == SlotState.GRIMY_HERB)

    def count_clean_herbs(self) -> int:
        """Count number of clean herbs in inventory."""
        return sum(1 for slot in self.slots if slot.state == SlotState.CLEAN_HERB)

    def count_empty_slots(self) -> int:
        """Count number of empty slots."""
        return sum(1 for slot in self.slots if slot.state == SlotState.EMPTY)

    def get_grimy_slots(self) -> list[InventorySlot]:
        """Get list of slots containing grimy herbs."""
        return [slot for slot in self.slots if slot.state == SlotState.GRIMY_HERB]

    def get_next_grimy_slot(self) -> Optional[InventorySlot]:
        """Get the first slot with a grimy herb."""
        for slot in self.slots:
            if slot.state == SlotState.GRIMY_HERB:
                return slot
        return None

    def is_inventory_full(self) -> bool:
        """Check if inventory is full."""
        return self.count_empty_slots() == 0

    def is_inventory_empty(self) -> bool:
        """Check if inventory is empty."""
        return self.count_empty_slots() == 28

    def has_grimy_herbs(self) -> bool:
        """Check if inventory has any grimy herbs."""
        return self.count_grimy_herbs() > 0
