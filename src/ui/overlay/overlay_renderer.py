"""Overlay rendering logic for drawing detection visualizations."""

import logging
from typing import Optional

import pygame

from .detection_data import DetectionData, SlotDisplayState, MatchInfo, InventorySlotInfo


class OverlayRenderer:
    """Renders detection data onto the overlay surface.

    Color scheme:
    - Grimy herbs: Red (255, 100, 100)
    - Clean herbs: Green (100, 255, 100)
    - Bank UI: Blue (100, 150, 255)
    - High confidence (>0.9): Bright green
    - Low confidence (<0.8): Orange
    """

    # Colors (RGB)
    COLOR_GRIMY = (255, 100, 100)
    COLOR_CLEAN = (100, 255, 100)
    COLOR_EMPTY = (80, 80, 80)
    COLOR_BANK_UI = (100, 150, 255)
    COLOR_TEMPLATE = (255, 200, 100)
    COLOR_STATE_BG = (40, 40, 40)
    COLOR_STATE_TEXT = (255, 255, 255)
    COLOR_CONFIDENCE_HIGH = (100, 255, 100)
    COLOR_CONFIDENCE_MED = (255, 200, 100)
    COLOR_CONFIDENCE_LOW = (255, 100, 100)
    COLOR_LABEL_BG = (20, 20, 20)
    COLOR_LABEL_TEXT = (255, 255, 255)

    def __init__(self, config: Optional[dict] = None):
        """Initialize renderer.

        Args:
            config: Optional overlay configuration
        """
        self._logger = logging.getLogger(__name__)
        self._config = config or {}
        self._font: Optional[pygame.font.Font] = None
        self._small_font: Optional[pygame.font.Font] = None
        self._initialized = False

    def initialize(self) -> bool:
        """Initialize pygame fonts.

        Returns:
            True if initialization successful
        """
        try:
            pygame.font.init()
            self._font = pygame.font.SysFont("consolas", 14)
            self._small_font = pygame.font.SysFont("consolas", 11)
            self._initialized = True
            return True
        except Exception as e:
            self._logger.error("Failed to initialize fonts: %s", e)
            return False

    def render(
        self,
        surface: pygame.Surface,
        data: DetectionData,
        transparent_color: tuple[int, int, int],
        clear_surface: bool = True,
    ) -> None:
        """Render detection data onto surface.

        Args:
            surface: Pygame surface to draw on
            data: Detection data to visualize
            transparent_color: Color to use for transparent areas
            clear_surface: Whether to clear the surface before rendering (default True).
                          Set to False when rendering as an overlay on existing content.
        """
        if not self._initialized:
            self.initialize()

        # Clear with transparent color (only if requested)
        if clear_surface:
            surface.fill(transparent_color)

        if not data.window_bounds:
            return

        # Get window offset for coordinate conversion
        wx = data.window_bounds.x
        wy = data.window_bounds.y

        # Draw components based on config
        if self._config.get("show_inventory", True):
            self._draw_inventory(surface, data, wx, wy)

        if self._config.get("show_bank", True):
            self._draw_bank_matches(surface, data, wx, wy)

        if self._config.get("show_state", True):
            self._draw_state_indicator(surface, data)

        if self._config.get("show_confidence", True):
            self._draw_recent_matches(surface, data, wx, wy)

    def _draw_inventory(
        self,
        surface: pygame.Surface,
        data: DetectionData,
        wx: int,
        wy: int,
    ) -> None:
        """Draw inventory slot states.

        Args:
            surface: Surface to draw on
            data: Detection data
            wx: Window X offset
            wy: Window Y offset
        """
        for slot in data.inventory_slots:
            # Convert absolute screen coords to surface-relative coords
            x = slot.screen_x - wx - slot.width // 2
            y = slot.screen_y - wy - slot.height // 2

            # Skip if outside bounds
            if x < 0 or y < 0:
                continue

            # Choose color based on state
            if slot.state == SlotDisplayState.GRIMY:
                color = self.COLOR_GRIMY
            elif slot.state == SlotDisplayState.CLEAN:
                color = self.COLOR_CLEAN
            elif slot.state == SlotDisplayState.EMPTY:
                color = self.COLOR_EMPTY
            else:
                color = self.COLOR_EMPTY

            # Draw slot outline (thicker for non-empty)
            thickness = 3 if slot.state != SlotDisplayState.EMPTY else 1

            rect = pygame.Rect(x, y, slot.width, slot.height)
            pygame.draw.rect(surface, color, rect, thickness)

            # Draw slot index for debugging (small number in corner)
            if self._small_font and slot.state != SlotDisplayState.EMPTY:
                # Draw confidence/item indicator
                if slot.item_name:
                    short_name = slot.item_name[:3].upper()
                    text = self._small_font.render(short_name, True, color)
                    text_rect = text.get_rect(topleft=(x + 2, y + 2))

                    # Background for readability
                    bg_rect = text_rect.inflate(4, 2)
                    pygame.draw.rect(surface, self.COLOR_LABEL_BG, bg_rect)
                    surface.blit(text, text_rect)

    def _draw_bank_matches(
        self,
        surface: pygame.Surface,
        data: DetectionData,
        wx: int,
        wy: int,
    ) -> None:
        """Draw bank UI match boxes.

        Args:
            surface: Surface to draw on
            data: Detection data
            wx: Window X offset
            wy: Window Y offset
        """
        for match in data.bank_matches:
            # Convert absolute screen coords to surface-relative
            x = match.screen_x - wx - match.width // 2
            y = match.screen_y - wy - match.height // 2

            if x < 0 or y < 0:
                continue

            # Draw bounding box
            rect = pygame.Rect(x, y, match.width, match.height)
            pygame.draw.rect(surface, self.COLOR_BANK_UI, rect, 2)

            # Draw label with confidence
            if self._small_font:
                label = f"{match.label} ({match.confidence:.0%})"
                text = self._small_font.render(label, True, self.COLOR_BANK_UI)
                text_rect = text.get_rect(midbottom=(x + match.width // 2, y - 2))

                # Background
                bg_rect = text_rect.inflate(4, 2)
                pygame.draw.rect(surface, self.COLOR_LABEL_BG, bg_rect)
                surface.blit(text, text_rect)

            # Draw confidence bar below
            self._draw_confidence_bar(surface, x, y + match.height + 2, match.width, match.confidence)

    def _draw_recent_matches(
        self,
        surface: pygame.Surface,
        data: DetectionData,
        wx: int,
        wy: int,
    ) -> None:
        """Draw recent template match visualizations.

        Args:
            surface: Surface to draw on
            data: Detection data
            wx: Window X offset
            wy: Window Y offset
        """
        for match in data.recent_matches:
            # Convert absolute screen coords to surface-relative
            x = match.screen_x - wx - match.width // 2
            y = match.screen_y - wy - match.height // 2

            if x < 0 or y < 0:
                continue

            # Choose color based on confidence
            if match.confidence >= 0.9:
                color = self.COLOR_CONFIDENCE_HIGH
            elif match.confidence >= 0.8:
                color = self.COLOR_CONFIDENCE_MED
            else:
                color = self.COLOR_CONFIDENCE_LOW

            # Draw bounding box
            rect = pygame.Rect(x, y, match.width, match.height)
            pygame.draw.rect(surface, color, rect, 2)

            # Draw label
            if self._small_font:
                label = f"{match.label}"
                text = self._small_font.render(label, True, color)
                text_rect = text.get_rect(midbottom=(x + match.width // 2, y - 2))

                bg_rect = text_rect.inflate(4, 2)
                pygame.draw.rect(surface, self.COLOR_LABEL_BG, bg_rect)
                surface.blit(text, text_rect)

    def _draw_state_indicator(
        self,
        surface: pygame.Surface,
        data: DetectionData,
    ) -> None:
        """Draw current state indicator in top-left corner.

        Args:
            surface: Surface to draw on
            data: Detection data
        """
        if not self._font:
            return

        # State text
        state_text = data.state_name.upper().replace("_", " ")

        # Stats text
        stats_text = f"G:{data.grimy_count} C:{data.clean_count} | Cleaned:{data.herbs_cleaned}"

        # Render texts
        state_render = self._font.render(state_text, True, self.COLOR_STATE_TEXT)
        stats_render = self._small_font.render(stats_text, True, self.COLOR_STATE_TEXT) if self._small_font else None

        # Calculate box size
        padding = 8
        line_spacing = 4
        box_width = max(state_render.get_width(), stats_render.get_width() if stats_render else 0) + padding * 2
        box_height = state_render.get_height() + padding * 2
        if stats_render:
            box_height += stats_render.get_height() + line_spacing

        # Draw background
        bg_rect = pygame.Rect(10, 10, box_width, box_height)
        pygame.draw.rect(surface, self.COLOR_STATE_BG, bg_rect)
        pygame.draw.rect(surface, self._get_state_color(data.state_name), bg_rect, 2)

        # Draw state text
        surface.blit(state_render, (10 + padding, 10 + padding))

        # Draw stats text
        if stats_render:
            surface.blit(
                stats_render,
                (10 + padding, 10 + padding + state_render.get_height() + line_spacing),
            )

    def _draw_confidence_bar(
        self,
        surface: pygame.Surface,
        x: int,
        y: int,
        width: int,
        confidence: float,
    ) -> None:
        """Draw a confidence bar.

        Args:
            surface: Surface to draw on
            x: X position
            y: Y position
            width: Bar width
            confidence: Confidence value (0-1)
        """
        bar_height = 4
        filled_width = int(width * confidence)

        # Choose color based on confidence
        if confidence >= 0.9:
            color = self.COLOR_CONFIDENCE_HIGH
        elif confidence >= 0.8:
            color = self.COLOR_CONFIDENCE_MED
        else:
            color = self.COLOR_CONFIDENCE_LOW

        # Draw background
        bg_rect = pygame.Rect(x, y, width, bar_height)
        pygame.draw.rect(surface, self.COLOR_EMPTY, bg_rect)

        # Draw filled portion
        if filled_width > 0:
            filled_rect = pygame.Rect(x, y, filled_width, bar_height)
            pygame.draw.rect(surface, color, filled_rect)

    def _get_state_color(self, state_name: str) -> tuple[int, int, int]:
        """Get border color for state indicator.

        Args:
            state_name: Current state name

        Returns:
            RGB color tuple
        """
        state_colors = {
            "cleaning": self.COLOR_CLEAN,
            "banking_open": self.COLOR_BANK_UI,
            "banking_deposit": self.COLOR_BANK_UI,
            "banking_withdraw": self.COLOR_BANK_UI,
            "banking_close": self.COLOR_BANK_UI,
            "error": self.COLOR_CONFIDENCE_LOW,
            "emergency_stop": (255, 0, 0),
            "break_micro": (150, 150, 255),
            "break_long": (150, 150, 255),
        }
        return state_colors.get(state_name, self.COLOR_STATE_TEXT)
