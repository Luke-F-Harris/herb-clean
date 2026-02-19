"""Inventory traversal pattern generators."""

import math
from enum import Enum
from typing import Optional

import numpy as np

from utils import create_rng


class TraversalPattern(Enum):
    """Available inventory traversal patterns."""

    ROW_LTR = "row_ltr"
    ROW_RTL = "row_rtl"
    ROW_LTR_BOTTOM = "row_ltr_bottom"
    ROW_RTL_BOTTOM = "row_rtl_bottom"
    COL_TTB = "col_ttb"
    COL_BTT = "col_btt"
    COL_TTB_RIGHT = "col_ttb_right"
    COL_BTT_RIGHT = "col_btt_right"
    ZIGZAG_H = "zigzag_horizontal"
    ZIGZAG_V = "zigzag_vertical"
    SPIRAL_IN = "spiral_inward"
    RANDOM = "random_shuffle"
    WEIGHTED_NEAREST = "weighted_nearest"


class InventoryTraversal:
    """Generate traversal orders for 4x7 inventory grid."""

    ROWS = 7
    COLS = 4

    def __init__(
        self,
        enabled_patterns: Optional[list[str]] = None,
        pattern_weights: Optional[dict[str, float]] = None,
    ):
        """Initialize traversal generator.

        Args:
            enabled_patterns: List of pattern names to enable (all if None)
            pattern_weights: Optional weights for pattern selection
        """
        self._rng = create_rng()

        # Default to all patterns
        all_patterns = [p.value for p in TraversalPattern]
        self._enabled = enabled_patterns if enabled_patterns else all_patterns

        # Validate enabled patterns
        self._enabled = [p for p in self._enabled if p in all_patterns]
        if not self._enabled:
            self._enabled = all_patterns

        # Pattern weights (defaults to equal weighting)
        self._weights = pattern_weights or {}

    def generate_order(
        self,
        pattern: TraversalPattern,
        mouse_pos: Optional[tuple[int, int]] = None,
        slot_positions: Optional[dict[int, tuple[int, int]]] = None,
    ) -> list[int]:
        """Generate slot indices in traversal order.

        Args:
            pattern: Traversal pattern to use
            mouse_pos: Current mouse position (for weighted_nearest)
            slot_positions: Dict of slot index -> (x, y) screen coords (for weighted_nearest)

        Returns:
            List of slot indices in traversal order
        """
        if pattern == TraversalPattern.ROW_LTR:
            return self._row_ltr()
        elif pattern == TraversalPattern.ROW_RTL:
            return self._row_rtl()
        elif pattern == TraversalPattern.ROW_LTR_BOTTOM:
            return self._row_ltr_bottom()
        elif pattern == TraversalPattern.ROW_RTL_BOTTOM:
            return self._row_rtl_bottom()
        elif pattern == TraversalPattern.COL_TTB:
            return self._col_ttb()
        elif pattern == TraversalPattern.COL_BTT:
            return self._col_btt()
        elif pattern == TraversalPattern.COL_TTB_RIGHT:
            return self._col_ttb_right()
        elif pattern == TraversalPattern.COL_BTT_RIGHT:
            return self._col_btt_right()
        elif pattern == TraversalPattern.ZIGZAG_H:
            return self._zigzag_h()
        elif pattern == TraversalPattern.ZIGZAG_V:
            return self._zigzag_v()
        elif pattern == TraversalPattern.SPIRAL_IN:
            return self._spiral_in()
        elif pattern == TraversalPattern.RANDOM:
            return self._random_shuffle()
        elif pattern == TraversalPattern.WEIGHTED_NEAREST:
            return self._weighted_nearest(mouse_pos, slot_positions)
        else:
            return self._row_ltr()

    def random_pattern(self) -> TraversalPattern:
        """Select random enabled pattern.

        Returns:
            Randomly selected pattern from enabled list
        """
        # Build weights array
        weights = []
        for name in self._enabled:
            weights.append(self._weights.get(name, 1.0))

        # Normalize weights
        total = sum(weights)
        probs = [w / total for w in weights]

        # Select pattern
        name = self._rng.choice(self._enabled, p=probs)
        return TraversalPattern(name)

    def _row_ltr(self) -> list[int]:
        """Row-major, left to right, top to bottom."""
        return list(range(self.ROWS * self.COLS))

    def _row_rtl(self) -> list[int]:
        """Row-major, right to left, top to bottom."""
        order = []
        for row in range(self.ROWS):
            for col in range(self.COLS - 1, -1, -1):
                order.append(row * self.COLS + col)
        return order

    def _row_ltr_bottom(self) -> list[int]:
        """Row-major, left to right, bottom to top."""
        order = []
        for row in range(self.ROWS - 1, -1, -1):
            for col in range(self.COLS):
                order.append(row * self.COLS + col)
        return order

    def _row_rtl_bottom(self) -> list[int]:
        """Row-major, right to left, bottom to top."""
        order = []
        for row in range(self.ROWS - 1, -1, -1):
            for col in range(self.COLS - 1, -1, -1):
                order.append(row * self.COLS + col)
        return order

    def _col_ttb(self) -> list[int]:
        """Column-major, top to bottom, left to right."""
        order = []
        for col in range(self.COLS):
            for row in range(self.ROWS):
                order.append(row * self.COLS + col)
        return order

    def _col_btt(self) -> list[int]:
        """Column-major, bottom to top, left to right."""
        order = []
        for col in range(self.COLS):
            for row in range(self.ROWS - 1, -1, -1):
                order.append(row * self.COLS + col)
        return order

    def _col_ttb_right(self) -> list[int]:
        """Column-major, top to bottom, right to left."""
        order = []
        for col in range(self.COLS - 1, -1, -1):
            for row in range(self.ROWS):
                order.append(row * self.COLS + col)
        return order

    def _col_btt_right(self) -> list[int]:
        """Column-major, bottom to top, right to left."""
        order = []
        for col in range(self.COLS - 1, -1, -1):
            for row in range(self.ROWS - 1, -1, -1):
                order.append(row * self.COLS + col)
        return order

    def _zigzag_h(self) -> list[int]:
        """Horizontal zigzag (boustrophedon)."""
        order = []
        for row in range(self.ROWS):
            cols = list(range(self.COLS))
            if row % 2 == 1:
                cols.reverse()
            order.extend(row * self.COLS + c for c in cols)
        return order

    def _zigzag_v(self) -> list[int]:
        """Vertical zigzag."""
        order = []
        for col in range(self.COLS):
            rows = list(range(self.ROWS))
            if col % 2 == 1:
                rows.reverse()
            order.extend(r * self.COLS + col for r in rows)
        return order

    def _spiral_in(self) -> list[int]:
        """Spiral inward from edges (clockwise from top-left)."""
        order = []
        top, bottom = 0, self.ROWS - 1
        left, right = 0, self.COLS - 1

        while top <= bottom and left <= right:
            # Top row: left to right
            for c in range(left, right + 1):
                order.append(top * self.COLS + c)
            top += 1

            # Right column: top to bottom
            for r in range(top, bottom + 1):
                order.append(r * self.COLS + right)
            right -= 1

            # Bottom row: right to left
            if top <= bottom:
                for c in range(right, left - 1, -1):
                    order.append(bottom * self.COLS + c)
                bottom -= 1

            # Left column: bottom to top
            if left <= right:
                for r in range(bottom, top - 1, -1):
                    order.append(r * self.COLS + left)
                left += 1

        return order

    def _random_shuffle(self) -> list[int]:
        """Randomly permute all slot indices."""
        order = list(range(self.ROWS * self.COLS))
        self._rng.shuffle(order)
        return order

    def _weighted_nearest(
        self,
        start_pos: Optional[tuple[int, int]],
        slot_positions: Optional[dict[int, tuple[int, int]]],
    ) -> list[int]:
        """Greedy nearest-neighbor with randomization.

        Prefers slots closer to current position but with randomness.

        Args:
            start_pos: Starting mouse position (x, y)
            slot_positions: Dict of slot index -> (x, y) screen coords

        Returns:
            Slot indices ordered by weighted nearest selection
        """
        # Fallback to random if no position info
        if start_pos is None or slot_positions is None or not slot_positions:
            return self._random_shuffle()

        remaining = set(slot_positions.keys())
        order = []
        current = start_pos

        while remaining:
            # Calculate distances from current position
            distances = {}
            for idx in remaining:
                pos = slot_positions[idx]
                distances[idx] = math.hypot(pos[0] - current[0], pos[1] - current[1])

            # Weight by inverse distance (closer = more likely)
            # Add small epsilon to avoid division by zero
            weights = {idx: 1.0 / (d + 10) for idx, d in distances.items()}
            total = sum(weights.values())

            # Build probability array
            remaining_list = list(remaining)
            probs = [weights[idx] / total for idx in remaining_list]

            # Random weighted selection
            choice = self._rng.choice(remaining_list, p=probs)
            order.append(choice)
            remaining.remove(choice)
            current = slot_positions[choice]

        return order
