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

    def find_grimy_herb_in_bank(self) -> Optional[MatchResult]:
        """Find grimy herb in bank interface.

        Returns:
            MatchResult with position and dimensions, or None
        """
        screen_image = self.screen.capture_window()
        if screen_image is None:
            return self._cached_state.grimy_herb_location

        for herb_config in self.grimy_templates:
            match = self.matcher.match(screen_image, herb_config["template"])
            if match.found:
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
