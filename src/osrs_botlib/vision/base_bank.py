"""Base bank detector for all bots."""
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

import numpy as np

from osrs_botlib.vision.screen_capture import ScreenCapture
from osrs_botlib.vision.template_matcher import TemplateMatcher, MatchResult

logger = logging.getLogger(__name__)


@dataclass
class BankState:
    """Current state of bank interface."""

    is_open: bool = False
    booth_location: Optional[MatchResult] = None
    deposit_button: Optional[MatchResult] = None
    close_button: Optional[MatchResult] = None


class BaseBankDetector(ABC):
    """Base bank detector with shared functionality.

    Subclasses implement skill-specific item finding in bank.
    """

    def __init__(
        self,
        screen_capture: ScreenCapture,
        template_matcher: TemplateMatcher,
        bank_config: dict,
    ):
        """Initialize bank detector.

        Args:
            screen_capture: Screen capture instance
            template_matcher: Template matcher instance
            bank_config: Bank template config
        """
        self.screen = screen_capture
        self.matcher = template_matcher
        self.config = bank_config
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
        """Detect bank item grid using quad-anchor triangulation.

        Uses up to 4 anchor buttons to calculate the exact bank region:
        - Top-left: Menu button
        - Top-right: Close button
        - Bottom-left: Insert button
        - Bottom-center: Deposit button

        Returns:
            Tuple of (x, y, width, height) for bank item region, or None
        """
        # Detect all anchor buttons
        close_match = self.matcher.match(
            screen_image, self.config.get("close_button_template", "bank_close.png")
        )
        deposit_match = self.matcher.match(
            screen_image, self.config.get("deposit_all_template", "deposit_all.png")
        )
        insert_match = self.matcher.match(
            screen_image, self.config.get("insert_button_template", "bank_insert.png")
        )
        menu_match = self.matcher.match(
            screen_image, self.config.get("menu_button_template", "bank_menu.png")
        )

        # Method 1: Quad-anchor (most reliable)
        if menu_match.found and close_match.found and insert_match.found and deposit_match.found:
            left_corner_x = insert_match.x + insert_match.width
            left_corner_y = menu_match.y + menu_match.height

            right_corner_x = close_match.x
            right_corner_y = close_match.y + close_match.height

            bottom_left_y = insert_match.y
            bottom_right_y = deposit_match.y

            margin = 5
            left = left_corner_x + margin
            top = max(left_corner_y, right_corner_y) + margin
            right = right_corner_x - margin
            bottom = min(bottom_left_y, bottom_right_y) - margin

            return (
                max(0, left),
                max(0, top),
                max(0, right - left),
                max(0, bottom - top)
            )

        # Method 2: Triple-anchor
        if menu_match.found and close_match.found and insert_match.found:
            left_corner_x = insert_match.x + insert_match.width
            left_corner_y = menu_match.y + menu_match.height

            right_corner_x = close_match.x
            right_corner_y = close_match.y + close_match.height

            margin = 5
            left = left_corner_x + margin
            top = max(left_corner_y, right_corner_y) + margin
            right = right_corner_x - margin
            bottom = insert_match.y - margin

            return (
                max(0, left),
                max(0, top),
                max(0, right - left),
                max(0, bottom - top)
            )

        # Method 3: Dual-anchor with close and deposit
        if close_match.found and deposit_match.found:
            dx = close_match.center_x - deposit_match.center_x
            dy = deposit_match.center_y - close_match.center_y

            panel_width = int(dx * 2.2)

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

        # Method 4: Dual-anchor with menu and insert
        if menu_match.found and insert_match.found:
            left = max(menu_match.x + menu_match.width, insert_match.x + insert_match.width) + 5
            top = menu_match.y + menu_match.height + 5
            bottom = insert_match.y - 5

            height = bottom - top
            width = int(height * 1.1)

            return (
                max(0, left),
                max(0, top),
                width,
                max(0, bottom - top)
            )

        # Method 5: Single anchor fallback
        if close_match.found:
            button_scale = close_match.width / 21.0

            offset_x = int(510 * button_scale)
            offset_y = int(50 * button_scale)
            bank_width = int(480 * button_scale)
            bank_height = int(460 * button_scale)

            x = max(0, close_match.x - offset_x)
            y = max(0, close_match.y + offset_y)

            return (x, y, bank_width, bank_height)

        if deposit_match.found:
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

    @abstractmethod
    def find_target_item_in_bank(self) -> Optional[MatchResult]:
        """Find skill-specific item in bank (grimy herbs, raw fish, logs, etc.).

        Subclasses implement item-specific detection logic.

        Returns:
            MatchResult with position and dimensions, or None
        """
        pass

    def is_bank_open(self) -> bool:
        """Check if bank interface is currently open."""
        return self.detect_bank_state().is_open

    def _to_screen_coords(self, match: MatchResult) -> MatchResult:
        """Convert match result to absolute screen coordinates.

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
