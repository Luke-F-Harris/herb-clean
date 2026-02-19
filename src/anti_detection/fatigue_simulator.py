"""Fatigue simulation - gradual performance degradation over time."""

import time
from dataclasses import dataclass
from typing import Optional

import numpy as np

from src.utils import create_rng


@dataclass
class FatigueConfig:
    """Configuration for fatigue simulation."""

    onset_minutes: float = 30  # When fatigue starts
    max_slowdown_percent: float = 50  # Maximum slowdown
    misclick_rate_start: float = 0.01  # Initial misclick rate
    misclick_rate_max: float = 0.05  # Maximum misclick rate


class FatigueSimulator:
    """Simulate human fatigue with performance degradation."""

    def __init__(self, config: Optional[FatigueConfig] = None):
        """Initialize fatigue simulator.

        Args:
            config: Fatigue configuration
        """
        self.config = config or FatigueConfig()
        self._rng = create_rng()
        self._session_start: Optional[float] = None
        self._last_break_time: Optional[float] = None

    def start_session(self) -> None:
        """Start a new session (reset fatigue)."""
        self._session_start = time.time()
        self._last_break_time = time.time()

    def record_break(self, duration: float) -> None:
        """Record that a break was taken.

        Breaks reduce accumulated fatigue.

        Args:
            duration: Break duration in seconds
        """
        self._last_break_time = time.time()

        # Longer breaks reduce fatigue more
        # A 5-minute break essentially resets fatigue
        recovery = min(1.0, duration / 300)

        if self._session_start:
            # Move session start forward to simulate recovery
            current = time.time()
            elapsed = current - self._session_start
            recovered_time = elapsed * recovery
            self._session_start = current - (elapsed - recovered_time)

    def get_session_duration(self) -> float:
        """Get current session duration in minutes.

        Returns:
            Session duration in minutes
        """
        if not self._session_start:
            return 0

        return (time.time() - self._session_start) / 60

    def get_time_since_break(self) -> float:
        """Get time since last break in minutes.

        Returns:
            Time since break in minutes
        """
        if not self._last_break_time:
            return self.get_session_duration()

        return (time.time() - self._last_break_time) / 60

    def get_fatigue_level(self) -> float:
        """Get current fatigue level (0-1).

        0 = no fatigue, 1 = maximum fatigue

        Returns:
            Fatigue level
        """
        session_minutes = self.get_session_duration()

        if session_minutes < self.config.onset_minutes:
            return 0.0

        # Fatigue increases logarithmically after onset
        # Reaches ~0.7 at 2 hours, ~0.85 at 3 hours, ~0.95 at 4 hours
        time_past_onset = session_minutes - self.config.onset_minutes
        fatigue = 1 - np.exp(-time_past_onset / 60)

        # Add some random variation
        fatigue *= self._rng.uniform(0.9, 1.1)

        return min(1.0, max(0.0, fatigue))

    def get_slowdown_multiplier(self) -> float:
        """Get timing slowdown multiplier based on fatigue.

        Returns:
            Multiplier >= 1.0 (1.0 = no slowdown)
        """
        fatigue = self.get_fatigue_level()
        max_slowdown = self.config.max_slowdown_percent / 100

        # Linear interpolation
        slowdown = 1.0 + (fatigue * max_slowdown)

        # Add random variation
        slowdown *= self._rng.uniform(0.95, 1.05)

        return slowdown

    def get_misclick_rate(self) -> float:
        """Get current misclick probability.

        Returns:
            Misclick rate (0-1)
        """
        fatigue = self.get_fatigue_level()

        # Interpolate between start and max rates
        rate_range = self.config.misclick_rate_max - self.config.misclick_rate_start
        rate = self.config.misclick_rate_start + (fatigue * rate_range)

        return rate

    def should_take_break(self, micro_interval: tuple[float, float]) -> bool:
        """Check if fatigue indicates a break should happen.

        Args:
            micro_interval: (min, max) minutes for micro-break interval

        Returns:
            True if break recommended
        """
        time_since_break = self.get_time_since_break()

        # Check against interval with some randomness
        interval = self._rng.uniform(micro_interval[0], micro_interval[1])

        return time_since_break >= interval

    def get_accuracy_modifier(self) -> float:
        """Get accuracy modifier for movements/clicks.

        Higher fatigue = less precise movements.

        Returns:
            Modifier (1.0 = normal, >1.0 = less accurate)
        """
        fatigue = self.get_fatigue_level()

        # Accuracy degrades up to 30% at max fatigue
        modifier = 1.0 + (fatigue * 0.3)

        return modifier

    def should_have_attention_lapse(self) -> bool:
        """Check if fatigue causes an attention lapse.

        Returns:
            True if attention lapsed
        """
        fatigue = self.get_fatigue_level()

        # Chance increases with fatigue (0-5%)
        lapse_chance = fatigue * 0.05

        return self._rng.random() < lapse_chance

    def get_attention_lapse_duration(self) -> float:
        """Get duration of attention lapse.

        Returns:
            Duration in seconds
        """
        # 1-5 seconds
        return self._rng.uniform(1, 5)

    def get_status(self) -> dict:
        """Get current fatigue status.

        Returns:
            Dict with fatigue metrics
        """
        return {
            "session_minutes": self.get_session_duration(),
            "time_since_break_minutes": self.get_time_since_break(),
            "fatigue_level": self.get_fatigue_level(),
            "slowdown_multiplier": self.get_slowdown_multiplier(),
            "misclick_rate": self.get_misclick_rate(),
            "accuracy_modifier": self.get_accuracy_modifier(),
        }
