"""Auto-detection of inventory position within RuneLite window."""

import logging
from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np


@dataclass
class InventoryRegion:
    """Detected inventory region."""

    x: int  # Relative to window
    y: int
    slot_width: int
    slot_height: int
    cols: int = 4
    rows: int = 7
    confidence: float = 0.0


class InventoryAutoDetector:
    """Auto-detect inventory position in RuneLite."""

    # OSRS inventory has distinctive brown/tan color
    # HSV range for inventory background
    INVENTORY_BG_LOWER = np.array([10, 20, 40])
    INVENTORY_BG_UPPER = np.array([25, 80, 100])

    def __init__(self):
        """Initialize auto-detector."""
        self._logger = logging.getLogger(__name__)

    def detect_inventory_region(
        self,
        screen_image: np.ndarray,
        expected_slot_size: tuple[int, int] = (42, 36),
    ) -> Optional[InventoryRegion]:
        """Auto-detect inventory region in window screenshot.

        Args:
            screen_image: BGR image of RuneLite window
            expected_slot_size: (width, height) of inventory slots

        Returns:
            InventoryRegion or None if not found
        """
        # Convert to HSV for color-based detection
        hsv = cv2.cvtColor(screen_image, cv2.COLOR_BGR2HSV)

        # Create mask for inventory background color
        mask = cv2.inRange(hsv, self.INVENTORY_BG_LOWER, self.INVENTORY_BG_UPPER)

        # Apply morphological operations to clean up mask
        kernel = np.ones((5, 5), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

        # Find contours
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if not contours:
            self._logger.warning("No inventory-colored regions found")
            return None

        # Look for rectangular region that matches inventory dimensions
        # Inventory is 4 cols x 7 rows
        expected_width = expected_slot_size[0] * 4
        expected_height = expected_slot_size[1] * 7

        best_match = None
        best_score = 0

        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)

            # Check if size is close to expected inventory size
            width_ratio = min(w, expected_width) / max(w, expected_width)
            height_ratio = min(h, expected_height) / max(h, expected_height)

            # Must be reasonably close to 4:7 aspect ratio
            aspect_ratio = w / h if h > 0 else 0
            expected_aspect = expected_width / expected_height
            aspect_score = min(aspect_ratio, expected_aspect) / max(aspect_ratio, expected_aspect)

            # Combined score
            score = width_ratio * height_ratio * aspect_score

            # Minimum thresholds
            if score > 0.7 and w > 100 and h > 150:
                if score > best_score:
                    best_score = score
                    best_match = (x, y, w, h)

        if best_match is None:
            self._logger.warning("No region matching inventory dimensions found")
            return None

        x, y, w, h = best_match

        # Calculate slot dimensions
        slot_width = w // 4
        slot_height = h // 7

        region = InventoryRegion(
            x=x,
            y=y,
            slot_width=slot_width,
            slot_height=slot_height,
            cols=4,
            rows=7,
            confidence=best_score,
        )

        self._logger.info(
            "Detected inventory at (%d, %d), slot size: %dx%d, confidence: %.2f",
            x, y, slot_width, slot_height, best_score
        )

        return region

    def detect_inventory_by_slots(
        self,
        screen_image: np.ndarray,
    ) -> Optional[InventoryRegion]:
        """Detect inventory by finding individual slot borders.

        More robust method that looks for the grid pattern.

        Args:
            screen_image: BGR image of RuneLite window

        Returns:
            InventoryRegion or None if not found
        """
        # Convert to grayscale
        gray = cv2.cvtColor(screen_image, cv2.COLOR_BGR2GRAY)

        # Detect edges
        edges = cv2.Canny(gray, 50, 150)

        # Find horizontal and vertical lines
        horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (25, 1))
        vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 25))

        horizontal_lines = cv2.morphologyEx(edges, cv2.MORPH_OPEN, horizontal_kernel)
        vertical_lines = cv2.morphologyEx(edges, cv2.MORPH_OPEN, vertical_kernel)

        # Combine
        grid = cv2.add(horizontal_lines, vertical_lines)

        # Find contours in grid
        contours, _ = cv2.findContours(grid, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # Look for grid pattern with 4 columns
        # This is more complex and may require tuning
        # For now, fall back to color-based detection
        return None

    def verify_inventory_region(
        self,
        screen_image: np.ndarray,
        region: InventoryRegion,
    ) -> bool:
        """Verify that detected region is actually the inventory.

        Args:
            screen_image: BGR image of window
            region: Region to verify

        Returns:
            True if verification passes
        """
        # Extract region
        x, y = region.x, region.y
        w = region.slot_width * region.cols
        h = region.slot_height * region.rows

        if y + h > screen_image.shape[0] or x + w > screen_image.shape[1]:
            return False

        inventory_img = screen_image[y:y+h, x:x+w]

        # Check color distribution
        hsv = cv2.cvtColor(inventory_img, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, self.INVENTORY_BG_LOWER, self.INVENTORY_BG_UPPER)

        # At least 30% should be inventory background color
        bg_ratio = np.sum(mask > 0) / (w * h)

        return bg_ratio > 0.30

    def detect_with_fallback(
        self,
        screen_image: np.ndarray,
        manual_config: Optional[dict] = None,
    ) -> InventoryRegion:
        """Detect inventory with fallback to manual config.

        Args:
            screen_image: BGR image of window
            manual_config: Manual config to use as fallback

        Returns:
            InventoryRegion (auto-detected or from config)
        """
        # Try auto-detection
        region = self.detect_inventory_region(screen_image)

        if region and self.verify_inventory_region(screen_image, region):
            self._logger.info("Successfully auto-detected inventory")
            return region

        # Fall back to manual config
        if manual_config:
            self._logger.info("Using manual inventory config")
            return InventoryRegion(
                x=manual_config.get("x", 563),
                y=manual_config.get("y", 208),
                slot_width=manual_config.get("slot_width", 42),
                slot_height=manual_config.get("slot_height", 36),
                cols=manual_config.get("cols", 4),
                rows=manual_config.get("rows", 7),
                confidence=1.0,
            )

        # Default fallback (common RuneLite position)
        self._logger.warning("Using default inventory position")
        return InventoryRegion(
            x=563,
            y=208,
            slot_width=42,
            slot_height=36,
            cols=4,
            rows=7,
            confidence=0.0,
        )
