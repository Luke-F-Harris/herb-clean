"""Bank interface detection."""

from dataclasses import dataclass
from typing import Optional

import numpy as np

from .screen_capture import ScreenCapture
from .template_matcher import TemplateMatcher, MatchResult


@dataclass
class BankState:
    """Current state of bank interface."""

    is_open: bool = False
    booth_location: Optional[MatchResult] = None
    deposit_button: Optional[MatchResult] = None
    close_button: Optional[MatchResult] = None
    grimy_herb_location: Optional[MatchResult] = None


class BankDetector:
    """Detect bank interface elements."""

    def __init__(
        self,
        screen_capture: ScreenCapture,
        template_matcher: TemplateMatcher,
        bank_config: dict,
        grimy_templates: list[dict],
    ):
        """Initialize bank detector.

        Args:
            screen_capture: Screen capture instance
            template_matcher: Template matcher instance
            bank_config: Bank template config
            grimy_templates: List of grimy herb template configs
        """
        self.screen = screen_capture
        self.matcher = template_matcher
        self.config = bank_config
        self.grimy_templates = grimy_templates
        self._cached_state = BankState()

    def detect_bank_state(self) -> BankState:
        """Detect current bank interface state.

        Returns:
            BankState with detected elements
        """
        screen_image = self.screen.capture_window()
        if screen_image is None:
            return self._cached_state

        state = BankState()

        # Check if bank is open by looking for deposit/close buttons
        deposit_match = self.matcher.match(
            screen_image, self.config.get("deposit_all_template", "deposit_all.png")
        )
        close_match = self.matcher.match(
            screen_image, self.config.get("close_button_template", "bank_close.png")
        )

        # Bank is open if we find the deposit or close buttons
        if deposit_match.found or close_match.found:
            state.is_open = True

            if deposit_match.found:
                state.deposit_button = self._to_screen_coords(deposit_match)

            if close_match.found:
                state.close_button = self._to_screen_coords(close_match)

            # Look for grimy herbs in bank
            for herb_config in self.grimy_templates:
                herb_match = self.matcher.match(screen_image, herb_config["template"])
                if herb_match.found:
                    state.grimy_herb_location = self._to_screen_coords(herb_match)
                    break
        else:
            state.is_open = False

        self._cached_state = state
        return state

    def find_bank_booth(self) -> Optional[MatchResult]:
        """Find bank booth location in game view.

        Returns:
            MatchResult with position and dimensions, or None
        """
        screen_image = self.screen.capture_window()
        if screen_image is None:
            return None

        # Try booth template
        booth_match = self.matcher.match(
            screen_image, self.config.get("booth_template", "bank_booth.png")
        )

        if booth_match.found:
            match_result = self._to_screen_coords(booth_match)
            self._cached_state.booth_location = match_result
            return match_result

        # Try chest template as alternative
        chest_match = self.matcher.match(
            screen_image, self.config.get("chest_template", "bank_chest.png")
        )

        if chest_match.found:
            match_result = self._to_screen_coords(chest_match)
            self._cached_state.booth_location = match_result
            return match_result

        return self._cached_state.booth_location

    def find_deposit_button(self) -> Optional[MatchResult]:
        """Find deposit-all button.

        Returns:
            MatchResult with position and dimensions, or None
        """
        screen_image = self.screen.capture_window()
        if screen_image is None:
            return self._cached_state.deposit_button

        match = self.matcher.match(
            screen_image, self.config.get("deposit_all_template", "deposit_all.png")
        )

        if match.found:
            match_result = self._to_screen_coords(match)
            self._cached_state.deposit_button = match_result
            return match_result

        return None

    def find_close_button(self) -> Optional[MatchResult]:
        """Find bank close button.

        Returns:
            MatchResult with position and dimensions, or None
        """
        screen_image = self.screen.capture_window()
        if screen_image is None:
            return self._cached_state.close_button

        match = self.matcher.match(
            screen_image, self.config.get("close_button_template", "bank_close.png")
        )

        if match.found:
            match_result = self._to_screen_coords(match)
            self._cached_state.close_button = match_result
            return match_result

        return None

    def _get_bank_item_region(self, screen_image: np.ndarray) -> Optional[tuple[int, int, int, int]]:
        """Detect bank item grid using dual-anchor triangulation.

        Uses both close button (top-right) and deposit button (bottom-center)
        to calculate the actual bank region without relying on unreliable
        template matching scale factors.

        Returns:
            Tuple of (x, y, width, height) for bank item region, or None
        """
        close_match = self.matcher.match(
            screen_image, self.config.get("close_button_template", "bank_close.png")
        )
        deposit_match = self.matcher.match(
            screen_image, self.config.get("deposit_all_template", "deposit_all.png")
        )

        # Method 1: Dual-anchor (most reliable)
        if close_match.found and deposit_match.found:
            # Close button is at top-right, deposit is at bottom-center
            # The horizontal distance from deposit center to close center
            # tells us half the panel width
            dx = close_match.center_x - deposit_match.center_x
            dy = deposit_match.center_y - close_match.center_y

            # Panel width is roughly 2x the horizontal offset
            panel_width = int(dx * 2.2)  # Close is slightly right of center

            # Item grid is inset from panel edges
            # Left edge = close_x - panel_width + small_margin
            # Top edge = close_y + button_height
            # Width/height = derived from dy (vertical span)

            item_grid_left = close_match.x - panel_width + 20
            item_grid_top = close_match.y + close_match.height + 10
            item_grid_width = panel_width - 40
            item_grid_height = dy - close_match.height - 60

            return (
                max(0, item_grid_left),
                max(0, item_grid_top),
                min(item_grid_width, screen_image.shape[1] - item_grid_left),
                min(item_grid_height, screen_image.shape[0] - item_grid_top)
            )

        # Method 2: Single anchor fallback with FIXED offsets (no scale multiplication)
        # Use the detected button SIZE as the scale indicator, not template scale
        if close_match.found:
            # The close button size tells us the UI scale
            # Standard close button is ~21x21 at 1080p
            button_scale = close_match.width / 21.0

            offset_x = int(510 * button_scale)
            offset_y = int(50 * button_scale)
            bank_width = int(480 * button_scale)
            bank_height = int(460 * button_scale)

            x = max(0, close_match.x - offset_x)
            y = max(0, close_match.y + offset_y)

            return (x, y, bank_width, bank_height)

        # Method 3: Deposit button only fallback
        if deposit_match.found:
            # Use deposit button size as scale indicator
            # Standard deposit button is ~35 pixels wide at 1080p
            button_scale = deposit_match.width / 35.0

            offset_x = int(240 * button_scale)
            offset_y = int(520 * button_scale)
            bank_width = int(480 * button_scale)
            bank_height = int(460 * button_scale)

            x = max(0, deposit_match.x - offset_x)
            y = max(0, deposit_match.y - offset_y)
            height = min(bank_height, deposit_match.y - y)

            return (x, y, bank_width, height)

        return None

    def find_grimy_herb_in_bank(self) -> Optional[MatchResult]:
        """Find grimy herb in bank interface.

        Uses hybrid color + template matching approach:
        1. Pre-filter candidates using color histogram similarity
        2. Run template matching only on top candidates
        3. Use bottom-region matching to avoid stack number interference

        This significantly improves accuracy for visually similar herbs.

        Returns:
            MatchResult with position and dimensions, or None
        """
        screen_image = self.screen.capture_window()
        if screen_image is None:
            return self._cached_state.grimy_herb_location

        # Get bank item region to restrict search area
        bank_region = self._get_bank_item_region(screen_image)

        if bank_region:
            # Crop image to bank item area only
            x, y, width, height = bank_region
            cropped_image = screen_image[y:y+height, x:x+width]
            search_image = cropped_image
            offset_x = x
            offset_y = y
        else:
            # Fallback: search full image if bank region not detected
            search_image = screen_image
            offset_x = 0
            offset_y = 0

        # Extract all template names for color pre-filtering
        template_names = [herb_config["template"] for herb_config in self.grimy_templates]

        # Pre-filter using color histogram (get top 3 candidates)
        color_candidates = self.matcher.filter_templates_by_color(
            search_image,
            template_names,
            top_k=3
        )

        # Try template matching on color-filtered candidates only
        best_match = None
        best_confidence = 0.0

        for template_name, color_similarity in color_candidates:
            # Use bottom-region matching for bank items (avoids stack numbers)
            # Using 70% - balance between avoiding text and keeping enough template data
            match = self.matcher.match_bottom_region(
                search_image,
                template_name,
                region_percentage=0.70  # Use bottom 70% of item to avoid stack text
            )

            if match.found and match.confidence > best_confidence:
                best_match = match
                best_confidence = match.confidence

        if best_match:
            # Adjust coordinates to account for cropped region
            best_match.x += offset_x
            best_match.y += offset_y
            best_match.center_x += offset_x
            best_match.center_y += offset_y

            match_result = self._to_screen_coords(best_match)
            self._cached_state.grimy_herb_location = match_result
            return match_result

        return None

    def is_bank_open(self) -> bool:
        """Check if bank interface is currently open."""
        return self.detect_bank_state().is_open

    def _to_screen_coords(self, match: MatchResult) -> MatchResult:
        """Convert match result to absolute screen coordinates.

        Modifies the MatchResult in-place to convert window-relative
        coordinates to absolute screen coordinates.

        Args:
            match: MatchResult with window-relative coordinates

        Returns:
            Same MatchResult with screen-absolute coordinates
        """
        bounds = self.screen.window_bounds
        if bounds:
            match.x += bounds.x
            match.y += bounds.y
            match.center_x += bounds.x
            match.center_y += bounds.y
        return match
