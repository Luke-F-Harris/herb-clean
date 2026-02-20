"""Base inventory detector for all bots."""
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import numpy as np

from osrs_botlib.vision.screen_capture import ScreenCapture
from osrs_botlib.vision.template_matcher import TemplateMatcher
from osrs_botlib.vision.inventory_auto_detect import InventoryAutoDetector, InventoryRegion
from osrs_botlib.vision.inventory_traversal import InventoryTraversal, TraversalPattern


class SlotState(Enum):
    """Base state of an inventory slot.

    Subclasses should extend this for skill-specific states.
    """

    EMPTY = "empty"
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


class BaseInventoryDetector(ABC):
    """Base inventory detector with shared functionality.

    Subclasses implement skill-specific item detection.
    """

    def __init__(
        self,
        screen_capture: ScreenCapture,
        template_matcher: TemplateMatcher,
        inventory_config: dict,
        auto_detect: bool = True,
        inventory_template_path: Optional[str] = None,
        traversal_config: Optional[dict] = None,
    ):
        """Initialize inventory detector.

        Args:
            screen_capture: Screen capture instance
            template_matcher: Template matcher instance
            inventory_config: Inventory position config (used as fallback)
            auto_detect: Enable auto-detection of inventory position
            inventory_template_path: Optional path to inventory template image
            traversal_config: Optional traversal pattern configuration
        """
        self._logger = logging.getLogger(__name__)
        self.screen = screen_capture
        self.matcher = template_matcher
        self.config = inventory_config
        self._auto_detect = auto_detect

        # Initialize auto-detector with template if provided
        template_path = None
        if auto_detect and inventory_template_path:
            from pathlib import Path
            template_path = Path(inventory_template_path)

        self._auto_detector = InventoryAutoDetector(template_path) if auto_detect else None
        self._detected_region: Optional[InventoryRegion] = None

        # Pre-calculate slot positions (may be updated by auto-detection)
        self.slots: list[InventorySlot] = self._init_slots()

        # Initialize traversal pattern generator
        trav_cfg = traversal_config or {}
        self._traversal = InventoryTraversal(
            enabled_patterns=trav_cfg.get("enabled_patterns"),
            pattern_weights=trav_cfg.get("pattern_weights"),
        )
        self._current_order: list[int] = []  # Current traversal order
        self._order_index: int = 0  # Position in order
        self._last_item_count: int = 0  # Detect inventory change
        self._current_pattern: Optional[TraversalPattern] = None

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

    @abstractmethod
    def detect_inventory_state(self) -> list[InventorySlot]:
        """Detect state of all inventory slots.

        Subclasses implement skill-specific detection logic.

        Returns:
            List of InventorySlots with updated states
        """
        pass

    @abstractmethod
    def has_target_items(self) -> bool:
        """Check if target items exist (grimy herbs, raw fish, logs, etc.).

        Returns:
            True if target items are present
        """
        pass

    @abstractmethod
    def count_target_items(self) -> int:
        """Count target items in inventory.

        Returns:
            Number of target items
        """
        pass

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
        """Check if a slot region has any content (not empty).

        Args:
            slot_region: Slot image region

        Returns:
            True if slot has content
        """
        # Empty slots have very low variance
        gray = np.mean(slot_region, axis=2)
        variance = np.var(gray)
        return variance > 10.0  # Threshold for "has content"

    def get_next_slot(
        self,
        allow_regenerate: bool = True,
    ) -> Optional[InventorySlot]:
        """Get next slot to process using traversal pattern.

        Args:
            allow_regenerate: Allow regenerating traversal order

        Returns:
            Next slot or None if no slots available
        """
        # Get target slots
        target_slots = self.get_target_slots()
        if not target_slots:
            return None

        current_count = self.count_target_items()

        # Check if inventory changed (new batch)
        if current_count != self._last_item_count:
            if allow_regenerate:
                self._regenerate_traversal_order(target_slots)
            self._last_item_count = current_count

        # Get next slot from order
        if self._current_order and self._order_index < len(self._current_order):
            slot_index = self._current_order[self._order_index]
            self._order_index += 1
            return self.slots[slot_index]

        # Fallback to first target slot
        return target_slots[0] if target_slots else None

    @abstractmethod
    def get_target_slots(self) -> list[InventorySlot]:
        """Get slots containing target items.

        Returns:
            List of slots with target items
        """
        pass

    def _regenerate_traversal_order(
        self,
        target_slots: list[InventorySlot],
    ) -> None:
        """Generate new traversal order for target slots.

        Args:
            target_slots: Slots to traverse
        """
        slot_indices = [slot.index for slot in target_slots]
        self._current_pattern, self._current_order = self._traversal.get_next_order(
            slot_indices
        )
        self._order_index = 0

        self._logger.debug(
            "Generated %s traversal: %s",
            self._current_pattern.value if self._current_pattern else "unknown",
            self._current_order,
        )

    def reset_traversal(self) -> None:
        """Reset traversal state for new inventory."""
        self._current_order = []
        self._order_index = 0
        self._last_item_count = 0

    def get_current_pattern(self) -> Optional[TraversalPattern]:
        """Get current traversal pattern.

        Returns:
            Current pattern or None
        """
        return self._current_pattern

    def is_inventory_full(self) -> bool:
        """Check if inventory is full."""
        return self.count_empty_slots() == 0

    def is_inventory_empty(self) -> bool:
        """Check if inventory is empty."""
        return self.count_empty_slots() == 28

    def count_empty_slots(self) -> int:
        """Count empty slots."""
        return sum(1 for slot in self.slots if slot.state == SlotState.EMPTY)
