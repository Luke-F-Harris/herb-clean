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
        """Detect the bank item grid region to restrict search area.

        Returns:
            Tuple of (x, y, width, height) for bank item region, or None
        """
        # Find close button or deposit button to locate bank interface
        close_match = self.matcher.match(
            screen_image, self.config.get("close_button_template", "bank_close.png")
        )
        deposit_match = self.matcher.match(
            screen_image, self.config.get("deposit_all_template", "deposit_all.png")
        )

        if not (close_match.found or deposit_match.found):
            return None

        # Use close button as primary anchor (top-right of bank)
        if close_match.found:
            # Bank close button is at top-right of bank interface
            # Item grid is below and to the left
            # Typical OSRS bank: ~900px wide, ~550px tall for item area
            close_x = close_match.x
            close_y = close_match.y

            # Calculate bank item region
            # Grid starts about 50px below title bar, extends left about 850px
            x = max(0, close_x - 900)
            y = max(0, close_y - 20)
            width = min(950, screen_image.shape[1] - x)
            height = min(600, screen_image.shape[0] - y)

            return (x, y, width, height)

        # Fallback: use deposit button as anchor (bottom of bank)
        elif deposit_match.found:
            # Deposit button is at bottom of bank interface
            # Item grid is above
            deposit_x = deposit_match.x
            deposit_y = deposit_match.y

            # Grid is centered above deposit button
            x = max(0, deposit_x - 400)
            y = max(0, deposit_y - 600)
            width = min(900, screen_image.shape[1] - x)
            height = min(550, deposit_y - y)

            return (x, y, width, height)

        return None

    def find_grimy_herb_in_bank(self) -> Optional[MatchResult]:
        """Find grimy herb in bank interface.

        Uses bottom-region matching to avoid stack number interference.
        Only searches within the bank item grid to prevent false positives.

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

        for herb_config in self.grimy_templates:
            # Use bottom-region matching for bank items (avoids stack numbers)
            match = self.matcher.match_bottom_region(
                search_image,
                herb_config["template"],
                region_percentage=0.65  # Use bottom 65% of item
            )

            if match.found:
                # Adjust coordinates to account for cropped region
                match.x += offset_x
                match.y += offset_y
                match.center_x += offset_x
                match.center_y += offset_y

                match_result = self._to_screen_coords(match)
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
