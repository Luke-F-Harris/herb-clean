"""Organic easing functions that generate unique, human-like speed profiles.

This module replaces mathematically perfect easing functions (like t^2, sin(t*pi))
with procedurally generated curves that are unique for every movement. This prevents
detection systems from fingerprinting patterns based on known mathematical constants.

Key concepts:
- Perturbed basis functions: Instead of t^2, use t^2 + noise(t)
- Smooth perturbations: Multi-octave noise that creates organic wobble
- Micro-drift: Simulates gradual hand fatigue/recovery
"""

import math
from dataclasses import dataclass
from typing import Optional

import numpy as np


@dataclass
class OrganicEasingConfig:
    """Configuration for organic easing generation."""

    enabled: bool = True

    # Base shape variation
    inflection_range: tuple[float, float] = (0.35, 0.65)  # Where speed peaks
    power_range: tuple[float, float] = (1.5, 2.5)  # Curve steepness
    amplitude_range: tuple[float, float] = (0.85, 1.0)  # Strength variation

    # Perturbation noise
    perturbation_strength_range: tuple[float, float] = (0.03, 0.08)
    noise_octaves: int = 3  # Layers of variation

    # Drift
    drift_rate_range: tuple[float, float] = (-0.05, 0.05)
    drift_curve_range: tuple[float, float] = (0.5, 2.0)


class OrganicEasing:
    """Generate unique, non-repeatable easing curves that mimic human movement.

    Unlike mathematical easing functions that produce identical curves every time,
    this class generates procedurally unique curves for each movement. Each curve
    has its own "personality" with different inflection points, acceleration rates,
    and subtle perturbations.
    """

    def __init__(self, rng: np.random.Generator, config: Optional[OrganicEasingConfig] = None):
        """Initialize the organic easing generator.

        Args:
            rng: NumPy random generator for reproducible randomness
            config: Configuration for easing parameters
        """
        self._rng = rng
        self.config = config or OrganicEasingConfig()

    def _generate_movement_params(self, movement_distance: float) -> dict:
        """Generate unique parameters for a specific movement.

        Args:
            movement_distance: Distance in pixels (affects curve characteristics)

        Returns:
            Dictionary of parameters unique to this movement
        """
        cfg = self.config

        # Inflection point: where acceleration peaks
        inflection = self._rng.uniform(*cfg.inflection_range)

        # Asymmetric rise/fall powers (avoids perfect quadratic)
        rise_power = self._rng.uniform(*cfg.power_range)
        fall_power = self._rng.uniform(*cfg.power_range)

        # Overall amplitude variation
        amplitude = self._rng.uniform(*cfg.amplitude_range)

        # Generate noise octaves with random frequencies/amplitudes/phases
        noise_octaves = []
        for i in range(cfg.noise_octaves):
            octave = {
                'freq': self._rng.uniform(1.5 + i * 1.5, 3.0 + i * 2.0),
                'amp': self._rng.uniform(0.01, 0.04) / (i + 1),  # Decreasing amplitude
                'phase': self._rng.uniform(0, 2 * math.pi),
            }
            noise_octaves.append(octave)

        # Perturbation strength
        perturbation_strength = self._rng.uniform(*cfg.perturbation_strength_range)

        # Drift parameters
        drift_rate = self._rng.uniform(*cfg.drift_rate_range)
        drift_curve = self._rng.uniform(*cfg.drift_curve_range)

        # Distance-based adjustments
        # Short movements: more erratic, larger relative perturbations
        # Long movements: smoother, smaller relative perturbations
        distance_factor = min(1.0, max(0.3, 100 / max(movement_distance, 1)))
        perturbation_strength *= (0.5 + 0.5 * distance_factor)

        return {
            'inflection': inflection,
            'rise_power': rise_power,
            'fall_power': fall_power,
            'amplitude': amplitude,
            'noise_octaves': noise_octaves,
            'perturbation_strength': perturbation_strength,
            'drift_rate': drift_rate,
            'drift_curve': drift_curve,
        }

    def _organic_base(self, t: float, params: dict) -> float:
        """Calculate organic base shape (randomized polynomial blend).

        Instead of perfect sin(t*pi), uses asymmetric power curves with
        shifted inflection point.

        Args:
            t: Progress through movement (0 to 1)
            params: Movement parameters

        Returns:
            Base easing value (roughly 0 to 1)
        """
        inflection = params['inflection']
        rise_power = params['rise_power']
        fall_power = params['fall_power']
        amplitude = params['amplitude']

        if t < inflection:
            # Rising phase with random power
            normalized = t / inflection
            base = normalized ** rise_power
        else:
            # Falling phase with different power
            normalized = (t - inflection) / (1 - inflection)
            base = 1 - (normalized ** fall_power)

        return base * amplitude

    def _smooth_perturbation(self, t: float, params: dict) -> float:
        """Add continuous, non-repeating perturbation.

        Uses multiple octaves of smooth waves at different frequencies
        to create organic wobble without sharp changes.

        Args:
            t: Progress through movement (0 to 1)
            params: Movement parameters

        Returns:
            Perturbation value (small, typically -0.08 to 0.08)
        """
        value = 0.0
        for octave in params['noise_octaves']:
            frequency = octave['freq']
            amplitude = octave['amp']
            phase = octave['phase']

            # Smooth wave with random characteristics
            value += amplitude * math.sin(t * frequency * math.pi + phase)

        return value * params['perturbation_strength'] * 10  # Scale up for effect

    def _micro_drift(self, t: float, params: dict) -> float:
        """Simulate gradual hand fatigue/recovery drift.

        Creates a gradual offset that accumulates over the movement,
        modeling the natural tendency for hands to drift slightly.

        Args:
            t: Progress through movement (0 to 1)
            params: Movement parameters

        Returns:
            Drift value (typically -0.05 to 0.05)
        """
        drift_rate = params['drift_rate']
        drift_curve = params['drift_curve']

        return drift_rate * (t ** drift_curve)

    def generate_easing_function(self, movement_distance: float = 100) -> callable:
        """Create a unique easing function for a specific movement.

        Each call returns a NEW function with different characteristics.
        The function is not mathematically perfect - it has organic variation.

        Args:
            movement_distance: Distance in pixels (affects curve characteristics)

        Returns:
            An easing function that maps t (0-1) to eased t (0-1)
        """
        # Generate unique parameters for this movement
        params = self._generate_movement_params(movement_distance)

        def organic_ease(t: float) -> float:
            # Handle edge cases
            if t <= 0:
                return 0.0
            if t >= 1:
                return 1.0

            # Base shape (rough approximation of slow-fast-slow)
            base = self._organic_base(t, params)

            # Add smooth perturbations
            perturbation = self._smooth_perturbation(t, params)

            # Add micro-drift
            drift = self._micro_drift(t, params)

            # Combine components
            # Scale to roughly match expected easing range (0 at start, 1 at end)
            result = t + (base - t) * 0.3 + perturbation + drift

            # Clamp to valid range
            return max(0.0, min(1.0, result))

        return organic_ease

    def generate_base_profile(self, num_segments: int, movement_distance: float = 100) -> list[float]:
        """Generate an organic base speed profile for a movement.

        Replaces the perfect sin(progress * pi) base curve used in
        _generate_speed_profile with a unique organic curve.

        Args:
            num_segments: Number of path segments
            movement_distance: Distance in pixels

        Returns:
            List of base speed factors (0 to 1, representing slow to fast)
        """
        params = self._generate_movement_params(movement_distance)

        profile = []
        for i in range(num_segments):
            t = i / num_segments if num_segments > 0 else 0

            # Generate organic base value (replaces sin(t * pi))
            base = self._organic_base(t, params)

            # Add perturbation for variation
            perturbation = self._smooth_perturbation(t, params)

            # Combine
            value = base + perturbation

            # Ensure valid range (0.05 minimum to prevent infinite delays)
            profile.append(max(0.05, min(1.0, value)))

        return profile

    def generate_easing_params_for_speed_profile(self, movement_distance: float = 100) -> dict:
        """Generate parameters for use in _generate_speed_profile.

        Returns parameters that can be used to replace the fixed mathematical
        functions in the speed profile generation.

        Args:
            movement_distance: Distance in pixels

        Returns:
            Dictionary with organic parameters for speed profile generation
        """
        params = self._generate_movement_params(movement_distance)

        return {
            # Replace fixed asymmetry with organic value
            'asymmetry': self._rng.uniform(-0.2, 0.2),

            # Organic inflection affects where peak speed occurs
            'peak_shift': params['inflection'] - 0.5,

            # Powers for asymmetric acceleration/deceleration
            'accel_power': params['rise_power'],
            'decel_power': params['fall_power'],

            # Amplitude variation
            'amplitude': params['amplitude'],

            # Perturbation function
            'perturbation_params': params,
        }

    def apply_organic_base(self, progress: float, profile_params: dict) -> float:
        """Calculate organic base value for a specific progress point.

        Used as a drop-in replacement for sin(progress * pi) in speed profiles.

        Args:
            progress: Progress through movement (0 to 1)
            profile_params: Parameters from generate_easing_params_for_speed_profile

        Returns:
            Base speed factor (0 to 1)
        """
        params = profile_params['perturbation_params']

        # Calculate organic base
        base = self._organic_base(progress, params)

        # Add perturbation
        perturbation = self._smooth_perturbation(progress, params)

        # Combine and clamp
        return max(0.05, min(1.0, base + perturbation))
