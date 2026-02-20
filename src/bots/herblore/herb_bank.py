"""Herblore bank detection."""
import logging
from typing import Optional

from osrs_botlib.vision.base_bank import BaseBankDetector
from osrs_botlib.vision.screen_capture import ScreenCapture
from osrs_botlib.vision.template_matcher import TemplateMatcher, MatchResult

logger = logging.getLogger(__name__)


class HerbBankDetector(BaseBankDetector):
    """Bank detector for herblore bot."""

    def __init__(
        self,
        screen_capture: ScreenCapture,
        template_matcher: TemplateMatcher,
        bank_config: dict,
        grimy_templates: list[dict],
    ):
        """Initialize herblore bank detector.

        Args:
            screen_capture: Screen capture instance
            template_matcher: Template matcher instance
            bank_config: Bank template config
            grimy_templates: List of grimy herb template configs
        """
        super().__init__(screen_capture, template_matcher, bank_config)
        self.grimy_templates = grimy_templates

    def find_target_item_in_bank(self) -> Optional[MatchResult]:
        """Find grimy herb in bank interface."""
        return self.find_grimy_herb_in_bank()

    def find_grimy_herb_in_bank(self) -> Optional[MatchResult]:
        """Find grimy herb in bank interface.

        Uses direct template matching on all herb templates.

        Returns:
            MatchResult with position and dimensions, or None
        """
        screen_image = self.screen.capture_window()
        if screen_image is None:
            return None

        # Get bank item region to restrict search area
        bank_region = self._get_bank_item_region(screen_image)

        if bank_region:
            # Crop image to bank item area only
            x, y, width, height = bank_region
            cropped_image = screen_image[y:y+height, x:x+width]
            search_image = cropped_image
            offset_x = x
            offset_y = y
            logger.debug(f"Bank region detected: {bank_region}")
        else:
            # Fallback: search full image if bank region not detected
            search_image = screen_image
            offset_x = 0
            offset_y = 0
            logger.debug("Bank region not detected, searching full image")

        # Direct template matching on ALL herbs
        best_match = None
        best_confidence = 0.0
        best_template = None

        for herb_config in self.grimy_templates:
            template_name = herb_config["template"]
            # Use bottom-region matching for bank items (avoids stack numbers)
            match = self.matcher.match_bottom_region(
                search_image,
                template_name,
                region_percentage=0.70
            )

            logger.debug(
                f"{template_name}: conf={match.confidence:.3f}, found={match.found}"
            )

            if match.found and match.confidence > best_confidence:
                logger.debug(f"New best: {template_name} ({match.confidence:.3f})")
                best_match = match
                best_confidence = match.confidence
                best_template = template_name

        if best_match:
            logger.debug(
                f"Final match: {best_template} at ({best_match.center_x}, "
                f"{best_match.center_y}) conf={best_confidence:.3f}"
            )
            # Adjust coordinates to account for cropped region
            best_match.x += offset_x
            best_match.y += offset_y
            best_match.center_x += offset_x
            best_match.center_y += offset_y

            return self._to_screen_coords(best_match)

        logger.debug("No herb match found above threshold")
        return None
