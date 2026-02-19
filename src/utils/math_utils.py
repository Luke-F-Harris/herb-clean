"""Math and geometry utilities."""

import math
from typing import Tuple, Union


def clamp(value: Union[int, float], min_val: Union[int, float], max_val: Union[int, float]) -> Union[int, float]:
    """Clamp a value to a range.

    Args:
        value: Value to clamp
        min_val: Minimum allowed value
        max_val: Maximum allowed value

    Returns:
        Value clamped to [min_val, max_val]
    """
    return max(min_val, min(max_val, value))


def clamp_point(
    x: Union[int, float],
    y: Union[int, float],
    bounds: Tuple[Union[int, float], Union[int, float], Union[int, float], Union[int, float]],
) -> Tuple[Union[int, float], Union[int, float]]:
    """Clamp a 2D point to rectangular bounds.

    Args:
        x: X coordinate
        y: Y coordinate
        bounds: (min_x, min_y, max_x, max_y) bounds tuple

    Returns:
        (x, y) clamped to bounds
    """
    min_x, min_y, max_x, max_y = bounds
    return (
        clamp(x, min_x, max_x),
        clamp(y, min_y, max_y),
    )


def distance(x1: Union[int, float], y1: Union[int, float], x2: Union[int, float], y2: Union[int, float]) -> float:
    """Calculate Euclidean distance between two points.

    Args:
        x1: First point X
        y1: First point Y
        x2: Second point X
        y2: Second point Y

    Returns:
        Distance between points
    """
    dx = x2 - x1
    dy = y2 - y1
    return math.sqrt(dx * dx + dy * dy)
