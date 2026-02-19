"""Statistical distribution utilities."""

import numpy as np


def gamma_delay(
    rng: np.random.Generator,
    mean: float,
    std: float,
    min_val: float,
    max_val: float,
) -> float:
    """Generate delay using Gamma distribution.

    Gamma distribution provides natural right-skewed timing
    (occasional longer pauses), which better simulates human behavior.

    Args:
        rng: NumPy random generator
        mean: Target mean delay
        std: Target standard deviation
        min_val: Minimum allowed delay
        max_val: Maximum allowed delay

    Returns:
        Delay value clamped to [min_val, max_val]
    """
    # Calculate Gamma parameters from mean and std
    # For Gamma: mean = k*theta, var = k*theta^2
    # So: k = (mean/std)^2, theta = std^2/mean
    variance = std * std
    k = (mean * mean) / variance  # shape
    theta = variance / mean  # scale

    delay = rng.gamma(k, theta)

    # Clamp to bounds
    return max(min_val, min(max_val, delay))
