"""Herblore inventory detection."""
import logging
from enum import Enum
from typing import Optional

import numpy as np

from osrs_botlib.vision.base_inventory import (
    BaseInventoryDetector,
    InventorySlot,
    SlotState as BaseSlotState,
)
from osrs_botlib.vision.screen_capture import ScreenCapture
from osrs_botlib.vision.template_matcher import TemplateMatcher


class SlotState(Enum):
    """State of an inventory slot for herblore."""

    EMPTY = "empty"
    GRIMY_HERB = "grimy"
    CLEAN_HERB = "clean"
    UNKNOWN = "unknown"


class HerbInventoryDetector(BaseInventoryDetector):
    """Inventory detector for herblore bot."""

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
        """Initialize herblore inventory detector.

        Args:
            screen_capture: Screen capture instance
            template_matcher: Template matcher instance
            inventory_config: Inventory position config
            grimy_templates: List of grimy herb template configs
            clean_templates: List of clean herb template configs
            auto_detect: Enable auto-detection
            inventory_template_path: Path to inventory template
            traversal_config: Traversal pattern configuration
        """
        super().__init__(
            screen_capture,
            template_matcher,
            inventory_config,
            auto_detect,
            inventory_template_path,
            traversal_config,
        )
        self.grimy_templates = grimy_templates
        self.clean_templates = clean_templates or []
        self._logger = logging.getLogger(__name__)

    def detect_inventory_state(self) -> list[InventorySlot]:
        """Detect state of all inventory slots."""
        # Auto-detect inventory on first run if enabled
        if self._auto_detect and self._detected_region is None:
            self.auto_detect_inventory()

        # Capture inventory region
        inv_image = self.screen.capture_inventory(self.config)
        if inv_image is None:
            return self.slots

        # Update slot states based on template matching
        for slot in self.slots:
            slot.state = BaseSlotState.EMPTY
            slot.item_name = None

            # Extract slot region
            slot_region = self._extract_slot_region(inv_image, slot)
            if slot_region is None:
                continue

            # Check for grimy herbs using template matching
            for herb_config in self.grimy_templates:
                template_name = herb_config["template"]
                match = self.matcher.match(slot_region, template_name)

                if match.found:
                    slot.state = SlotState.GRIMY_HERB
                    slot.item_name = herb_config["name"]
                    break

            # Check for clean herbs
            if slot.state == BaseSlotState.EMPTY:
                for herb_config in self.clean_templates:
                    template_name = herb_config["template"]
                    match = self.matcher.match(slot_region, template_name)

                    if match.found:
                        slot.state = SlotState.CLEAN_HERB
                        slot.item_name = herb_config["name"]
                        break

            # Color-based detection fallback
            if slot.state == BaseSlotState.EMPTY and self._slot_has_content(slot_region):
                if self._detect_grimy_herb_by_color(slot_region):
                    slot.state = SlotState.GRIMY_HERB
                    slot.item_name = "grimy_herb"
                else:
                    slot.state = SlotState.CLEAN_HERB

        return self.slots

    def _detect_grimy_herb_by_color(self, slot_region: np.ndarray) -> bool:
        """Detect if slot contains grimy herb by color analysis."""
        # Grimy herbs have distinctive muddy brown/green colors
        # Convert to HSV for better color detection
        import cv2
        hsv = cv2.cvtColor(slot_region, cv2.COLOR_BGR2HSV)

        # Define color ranges for grimy herbs (muddy brown-green)
        # Hue: 20-60 (yellow-green), Saturation: 30-255, Value: 30-200
        lower_brown = np.array([20, 30, 30])
        upper_brown = np.array([60, 255, 200])

        mask = cv2.inRange(hsv, lower_brown, upper_brown)
        grimy_pixels = np.sum(mask > 0)
        total_pixels = slot_region.shape[0] * slot_region.shape[1]

        # If more than 15% of pixels match grimy herb colors
        return (grimy_pixels / total_pixels) > 0.15

    def has_target_items(self) -> bool:
        """Check if grimy herbs exist."""
        return self.count_grimy_herbs() > 0

    def count_target_items(self) -> int:
        """Count grimy herbs."""
        return self.count_grimy_herbs()

    def get_target_slots(self) -> list[InventorySlot]:
        """Get slots with grimy herbs."""
        return self.get_grimy_slots()

    def count_grimy_herbs(self) -> int:
        """Count grimy herbs in inventory."""
        return sum(1 for slot in self.slots if slot.state == SlotState.GRIMY_HERB)

    def count_clean_herbs(self) -> int:
        """Count clean herbs in inventory."""
        return sum(1 for slot in self.slots if slot.state == SlotState.CLEAN_HERB)

    def get_grimy_slots(self) -> list[InventorySlot]:
        """Get all slots containing grimy herbs."""
        return [slot for slot in self.slots if slot.state == SlotState.GRIMY_HERB]

    def has_grimy_herbs(self) -> bool:
        """Check if inventory has any grimy herbs."""
        return self.count_grimy_herbs() > 0

    def get_next_grimy_slot(
        self,
        allow_regenerate: bool = True,
    ) -> Optional[InventorySlot]:
        """Get next grimy herb slot using traversal pattern."""
        return self.get_next_slot(allow_regenerate)
