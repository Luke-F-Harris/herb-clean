"""Auto-detection of inventory position within RuneLite window."""

import logging
from dataclasses import dataclass
from pathlib import Path
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

    def __init__(self, template_path: Optional[Path] = None):
        """Initialize auto-detector.

        Args:
            template_path: Optional path to inventory template image
        """
        self._logger = logging.getLogger(__name__)
        self._template_path = template_path
        self._template = None

        if template_path and template_path.exists():
            self._template = cv2.imread(str(template_path))
            self._logger.info("Loaded inventory template from %s", template_path)

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
        # Try template-based detection first if available
        if self._template is not None:
            region = self._detect_by_template(screen_image)
            if region:
                return region

        # Try color-based detection with bottom-right priority
        region = self._detect_by_color(screen_image, expected_slot_size)
        if region:
            return region

        return None

    def _detect_by_template(self, screen_image: np.ndarray) -> Optional[InventoryRegion]:
        """Detect inventory using template matching.

        More reliable than color-based detection.

        Args:
            screen_image: BGR image of window

        Returns:
            InventoryRegion or None
        """
        if self._template is None:
            return None

        # Template matching
        result = cv2.matchTemplate(screen_image, self._template, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

        # Need high confidence for template match
        if max_val < 0.70:
            self._logger.warning("Template match confidence too low: %.2f", max_val)
            return None

        x, y = max_loc
        h, w = self._template.shape[:2]

        # Calculate slot dimensions (assuming template is full inventory)
        slot_width = w // 4
        slot_height = h // 7

        region = InventoryRegion(
            x=x,
            y=y,
            slot_width=slot_width,
            slot_height=slot_height,
            cols=4,
            rows=7,
            confidence=max_val,
        )

        self._logger.info(
            "Template-detected inventory at (%d, %d), confidence: %.2f",
            x, y, max_val
        )

        return region

    def _detect_by_color(
        self,
        screen_image: np.ndarray,
        expected_slot_size: tuple[int, int],
    ) -> Optional[InventoryRegion]:
        """Detect inventory by color, prioritizing bottom-right.

        Args:
            screen_image: BGR image of window
            expected_slot_size: Expected slot dimensions

        Returns:
            InventoryRegion or None
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

        candidates = []

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
                # Calculate position score (prefer bottom-right)
                img_h, img_w = screen_image.shape[:2]

                # Normalize positions (0-1)
                norm_x = x / img_w
                norm_y = y / img_h

                # Bonus for being in right half and lower half
                position_bonus = 0
                if norm_x > 0.5:  # Right side
                    position_bonus += 0.2
                if norm_y > 0.3:  # Lower portion
                    position_bonus += 0.1

                final_score = score + position_bonus

                candidates.append({
                    'bounds': (x, y, w, h),
                    'score': final_score,
                    'base_score': score,
                })

        if not candidates:
            self._logger.warning("No region matching inventory dimensions found")
            return None

        # Sort by score, pick best
        best = max(candidates, key=lambda c: c['score'])
        x, y, w, h = best['bounds']

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
            confidence=best['base_score'],
        )

        self._logger.info(
            "Color-detected inventory at (%d, %d), slot size: %dx%d, confidence: %.2f",
            x, y, slot_width, slot_height, best['base_score']
        )

        return region

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

        # At least 25% should be inventory background color
        # (lowered from 30% to handle tab overlays better)
        bg_ratio = np.sum(mask > 0) / (w * h)

        return bg_ratio > 0.25

    def get_smart_default(
        self,
        window_width: int,
        window_height: int,
        slot_width: int = 42,
        slot_height: int = 36,
    ) -> InventoryRegion:
        """Get smart default position based on window size.

        Places inventory in bottom-right, accounting for typical RuneLite layout.

        Args:
            window_width: Window width in pixels
            window_height: Window height in pixels
            slot_width: Inventory slot width
            slot_height: Inventory slot height

        Returns:
            InventoryRegion with calculated position
        """
        # Calculate inventory dimensions
        inv_width = slot_width * 4
        inv_height = slot_height * 7

        # Place in bottom-right with some padding
        # Typical RuneLite: right side panel starts ~70% across
        # Bottom portion starts ~40% down
        x = int(window_width * 0.73)  # Right side
        y = int(window_height * 0.42)  # Below tabs

        # Ensure it fits in window
        x = min(x, window_width - inv_width - 10)
        y = min(y, window_height - inv_height - 10)
        x = max(x, 0)
        y = max(y, 0)

        self._logger.info(
            "Using smart default position at (%d, %d) for %dx%d window",
            x, y, window_width, window_height
        )

        return InventoryRegion(
            x=x,
            y=y,
            slot_width=slot_width,
            slot_height=slot_height,
            cols=4,
            rows=7,
            confidence=0.5,  # Medium confidence for calculated default
        )

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

        # Fall back to manual config if provided
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

        # Smart default based on window size
        h, w = screen_image.shape[:2]
        return self.get_smart_default(w, h)
