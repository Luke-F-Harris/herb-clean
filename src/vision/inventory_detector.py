"""Inventory slot detection and classification."""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import numpy as np

from .screen_capture import ScreenCapture
from .template_matcher import TemplateMatcher
from .inventory_auto_detect import InventoryAutoDetector, InventoryRegion
from .inventory_traversal import InventoryTraversal, TraversalPattern


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
        clean_templates: Optional[list[dict]] = None,
        auto_detect: bool = True,
        inventory_template_path: Optional[str] = None,
        traversal_config: Optional[dict] = None,
    ):
        """Initialize inventory detector.

        Args:
            screen_capture: Screen capture instance
            template_matcher: Template matcher instance
            inventory_config: Inventory position config (used as fallback)
            grimy_templates: List of grimy herb template configs
            clean_templates: List of clean herb template configs
            auto_detect: Enable auto-detection of inventory position
            inventory_template_path: Optional path to inventory template image
            traversal_config: Optional traversal pattern configuration
        """
        self._logger = logging.getLogger(__name__)
        self.screen = screen_capture
        self.matcher = template_matcher
        self.config = inventory_config
        self.grimy_templates = grimy_templates
        self.clean_templates = clean_templates or []
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
        self._last_grimy_count: int = 0  # Detect inventory change
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

            # Check for grimy herbs using template matching (primary method)
            for herb_config in self.grimy_templates:
                template_name = herb_config["template"]
                match = self.matcher.match(slot_region, template_name)

                if match.found:
                    slot.state = SlotState.GRIMY_HERB
                    slot.item_name = herb_config["name"]
                    break

            # Check for clean herbs using template matching
            if slot.state == SlotState.EMPTY:
                for herb_config in self.clean_templates:
                    template_name = herb_config["template"]
                    match = self.matcher.match(slot_region, template_name)

                    if match.found:
                        slot.state = SlotState.CLEAN_HERB
                        slot.item_name = herb_config["name"]
                        break

            # If template matching failed for both, check if slot has content
            if slot.state == SlotState.EMPTY and self._slot_has_content(slot_region):
                # Use color-based detection to distinguish grimy from clean
                if self._detect_grimy_herb_by_color(slot_region):
                    slot.state = SlotState.GRIMY_HERB
                    slot.item_name = "grimy_herb"  # Generic name when detected by color
                else:
                    # Has content but not grimy colors = likely clean herb or other item
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
        # Lowered threshold for better detection
        return std > 15

    def _detect_grimy_herb_by_color(self, slot_region: np.ndarray) -> bool:
        """Detect grimy herbs using color-based detection.

        Grimy herbs have distinctive DARK green/brown colors in HSV space.
        Clean herbs are brighter/more saturated, so we specifically look for
        the darker, muddier colors that characterize grimy herbs.

        Args:
            slot_region: BGR image of inventory slot

        Returns:
            True if region likely contains a grimy herb
        """
        import cv2

        # Convert to HSV for better color detection
        hsv = cv2.cvtColor(slot_region, cv2.COLOR_BGR2HSV)

        # Grimy herbs have DARK greenish-brown colors (lower value/brightness)
        # Clean herbs are brighter/more saturated, so we exclude high values
        # Dark/muted green range (grimy herb leaf parts - darker than clean herbs)
        lower_dark_green = np.array([25, 30, 30])
        upper_dark_green = np.array([85, 255, 150])  # Cap value at 150 to exclude bright greens

        # Brown range (grimy/dirty parts - distinctive to grimy herbs)
        lower_brown = np.array([10, 40, 30])
        upper_brown = np.array([25, 255, 180])

        # Create masks
        mask_dark_green = cv2.inRange(hsv, lower_dark_green, upper_dark_green)
        mask_brown = cv2.inRange(hsv, lower_brown, upper_brown)

        total_pixels = slot_region.shape[0] * slot_region.shape[1]

        # Calculate percentage of each color
        dark_green_pixels = np.count_nonzero(mask_dark_green)
        brown_pixels = np.count_nonzero(mask_brown)

        dark_green_pct = dark_green_pixels / total_pixels
        brown_pct = brown_pixels / total_pixels

        # Grimy herbs should have BOTH dark green AND brown pixels
        # Clean herbs are mostly bright green without brown
        # Require at least 5% dark green AND 3% brown for grimy detection
        has_dark_green = dark_green_pct > 0.05
        has_brown = brown_pct > 0.03

        # Must have both characteristics to be considered grimy
        return has_dark_green and has_brown

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

    def get_next_grimy_slot(
        self,
        mouse_pos: Optional[tuple[int, int]] = None,
    ) -> Optional[InventorySlot]:
        """Get next slot using current traversal pattern.

        Args:
            mouse_pos: Current mouse position (used for weighted_nearest pattern)

        Returns:
            Next grimy slot in traversal order, or None if no more
        """
        grimy = self.get_grimy_slots()
        grimy_count = len(grimy)

        # Detect inventory change (new herbs withdrawn or herbs cleaned)
        # Regenerate traversal when count increases (new inventory)
        if grimy_count > self._last_grimy_count or self._order_index >= len(self._current_order):
            self._regenerate_traversal_order(grimy, mouse_pos)

        self._last_grimy_count = grimy_count

        # Return next slot in traversal order that still has a grimy herb
        grimy_indices = {s.index for s in grimy}
        while self._order_index < len(self._current_order):
            idx = self._current_order[self._order_index]
            self._order_index += 1
            if idx in grimy_indices:
                return self.slots[idx]

        return None  # No more grimy slots

    def _regenerate_traversal_order(
        self,
        grimy_slots: list,
        mouse_pos: Optional[tuple[int, int]] = None,
    ) -> None:
        """Generate new traversal order for current inventory.

        Args:
            grimy_slots: List of slots containing grimy herbs
            mouse_pos: Current mouse position for weighted_nearest
        """
        self._current_pattern = self._traversal.random_pattern()

        # Build slot positions dict for weighted_nearest pattern
        slot_positions = None
        if self._current_pattern == TraversalPattern.WEIGHTED_NEAREST:
            slot_positions = {}
            bounds = self.screen.window_bounds
            for slot in grimy_slots:
                if bounds:
                    slot_positions[slot.index] = (bounds.x + slot.x, bounds.y + slot.y)
                else:
                    slot_positions[slot.index] = (slot.x, slot.y)

        # Generate full traversal order
        full_order = self._traversal.generate_order(
            self._current_pattern,
            mouse_pos=mouse_pos,
            slot_positions=slot_positions,
        )

        # Filter to only include indices that have grimy herbs
        grimy_indices = {s.index for s in grimy_slots}
        self._current_order = [i for i in full_order if i in grimy_indices]
        self._order_index = 0

        self._logger.debug(
            "New traversal pattern: %s, order: %s",
            self._current_pattern.value,
            self._current_order[:5],
        )

    def reset_traversal(self) -> None:
        """Reset traversal state for a new inventory."""
        self._current_order = []
        self._order_index = 0
        self._last_grimy_count = 0
        self._current_pattern = None

    def get_current_pattern(self) -> Optional[TraversalPattern]:
        """Get the current traversal pattern being used."""
        return self._current_pattern

    def is_inventory_full(self) -> bool:
        """Check if inventory is full."""
        return self.count_empty_slots() == 0

    def is_inventory_empty(self) -> bool:
        """Check if inventory is empty."""
        return self.count_empty_slots() == 28

    def has_grimy_herbs(self) -> bool:
        """Check if inventory has any grimy herbs."""
        return self.count_grimy_herbs() > 0
