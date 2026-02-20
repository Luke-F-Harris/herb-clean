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


def gaussian_bounded(
    rng: np.random.Generator,
    min_val: float,
    max_val: float,
    mean: float = None,
    std: float = None,
) -> float:
    """Generate a value using truncated Gaussian distribution.

    Unlike uniform distribution (instantly detectable as bot behavior),
    Gaussian distribution creates a bell curve that matches human behavior.
    Values cluster around the mean with occasional outliers.

    Args:
        rng: NumPy random generator
        min_val: Minimum allowed value
        max_val: Maximum allowed value
        mean: Target mean (defaults to midpoint of range)
        std: Standard deviation (defaults to ~1/6 of range for 99.7% coverage)

    Returns:
        Value clamped to [min_val, max_val] with Gaussian distribution
    """
    # Default mean to midpoint of range
    if mean is None:
        mean = (min_val + max_val) / 2

    # Default std to ~1/6 of range (3 sigma = 99.7% within bounds naturally)
    if std is None:
        std = (max_val - min_val) / 6

    # Generate Gaussian value and clamp to bounds
    value = rng.normal(mean, std)
    return max(min_val, min(max_val, value))
