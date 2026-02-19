"""Random number generator utilities."""

from typing import Optional

import numpy as np


def create_rng(seed: Optional[int] = None) -> np.random.Generator:
    """Create a numpy random number generator.

    Centralizes RNG creation for consistent initialization across modules.

    Args:
        seed: Optional seed for reproducible random numbers

    Returns:
        NumPy Generator instance
    """
    return np.random.default_rng(seed)
