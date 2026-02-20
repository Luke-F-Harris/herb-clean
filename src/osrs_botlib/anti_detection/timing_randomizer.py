"""Timing randomization using statistical distributions."""

from dataclasses import dataclass
from typing import Optional

import numpy as np

from osrs_botlib.utils import create_rng, gamma_delay, gaussian_bounded
from osrs_botlib.core.base_actions import ActionCategory


@dataclass
class TimingConfig:
    """Configuration for timing randomization."""

    # Skill action (clicking herb, chopping tree, catching fish, etc.)
    skill_action_mean: float = 250  # ms
    skill_action_std: float = 75
    skill_action_min: float = 150
    skill_action_max: float = 500

    # Bank actions
    bank_action_mean: float = 800
    bank_action_std: float = 200
    bank_action_min: float = 500
    bank_action_max: float = 1500

    # Post-action delays
    after_bank_open: float = 400
    after_deposit: float = 300
    after_withdraw: float = 300
    after_bank_close: float = 200


class TimingRandomizer:
    """Generate human-like random delays using statistical distributions.

    Implements Markov chain timing correlation:
    - Tracks recent action speeds
    - If recent actions were fast, biases toward slower next action
    - If recent actions were slow, biases toward faster next action
    - Creates natural rhythm variation without pure randomness
    """

    # Markov chain config
    SPEED_HISTORY_SIZE = 5  # Number of recent speeds to track
    CORRELATION_STRENGTH = 0.15  # How strongly to bias based on history

    def __init__(self, config: Optional[TimingConfig] = None):
        """Initialize timing randomizer.

        Args:
            config: Timing configuration
        """
        self.config = config or TimingConfig()
        self._rng = create_rng()
        self._fatigue_multiplier = 1.0

        # Markov chain state: track recent timing history
        self._speed_history: list[float] = []
        self._last_mean_for_action: dict[str, float] = {}

    def set_fatigue_multiplier(self, multiplier: float) -> None:
        """Set fatigue multiplier for delays.

        Args:
            multiplier: Multiplier >= 1.0 (1.0 = no fatigue)
        """
        self._fatigue_multiplier = max(1.0, multiplier)

    def get_delay(self, action_category: ActionCategory) -> float:
        """Get randomized delay for an action.

        Uses Gamma distribution for right-skewed, natural timing.
        Applies Markov chain correlation based on recent timing history.

        Args:
            action_category: Category of action

        Returns:
            Delay in seconds
        """
        if action_category == ActionCategory.SKILL_ACTION:
            delay = self._gamma_delay(
                self.config.skill_action_mean,
                self.config.skill_action_std,
                self.config.skill_action_min,
                self.config.skill_action_max,
            )
            mean = self.config.skill_action_mean
        elif action_category in (
            ActionCategory.BANK_OPEN,
            ActionCategory.BANK_DEPOSIT,
            ActionCategory.BANK_WITHDRAW,
        ):
            delay = self._gamma_delay(
                self.config.bank_action_mean,
                self.config.bank_action_std,
                self.config.bank_action_min,
                self.config.bank_action_max,
            )
            mean = self.config.bank_action_mean
        elif action_category == ActionCategory.BANK_CLOSE:
            delay = self._gamma_delay(
                self.config.after_bank_close,
                self.config.after_bank_close * 0.3,
                self.config.after_bank_close * 0.5,
                self.config.after_bank_close * 2,
            )
            mean = self.config.after_bank_close
        else:
            delay = self._gamma_delay(500, 100, 300, 1000)
            mean = 500

        # Apply Markov timing correlation
        delay = self._apply_timing_correlation(delay, mean, action_category)

        # Apply fatigue
        delay *= self._fatigue_multiplier

        # Record this delay in history
        self._update_speed_history(delay)

        return delay / 1000.0  # Convert to seconds

    def _apply_timing_correlation(
        self, delay: float, mean: float, action_category: ActionCategory
    ) -> float:
        """Apply Markov chain correlation based on recent timing history.

        If recent actions were fast (below mean), bias toward slower.
        If recent actions were slow (above mean), bias toward faster.

        Args:
            delay: Base delay in ms
            mean: Expected mean for this action category
            action_category: Category of action

        Returns:
            Adjusted delay in ms
        """
        if len(self._speed_history) < 2:
            return delay

        # Calculate average of recent delays
        recent_avg = sum(self._speed_history[-self.SPEED_HISTORY_SIZE:]) / min(
            len(self._speed_history), self.SPEED_HISTORY_SIZE
        )

        # Store mean for this action category for reference
        self._last_mean_for_action[action_category.value] = mean

        # Calculate overall average mean across all action types
        if self._last_mean_for_action:
            overall_mean = sum(self._last_mean_for_action.values()) / len(
                self._last_mean_for_action
            )
        else:
            overall_mean = mean

        # Determine bias direction
        if recent_avg < overall_mean * 0.9:
            # Recent actions were fast - bias toward slower
            # Multiply by 1.0 to 1.0 + CORRELATION_STRENGTH
            multiplier = gaussian_bounded(
                self._rng, 1.0, 1.0 + self.CORRELATION_STRENGTH
            )
        elif recent_avg > overall_mean * 1.1:
            # Recent actions were slow - bias toward faster
            # Multiply by 1.0 - CORRELATION_STRENGTH to 1.0
            multiplier = gaussian_bounded(
                self._rng, 1.0 - self.CORRELATION_STRENGTH, 1.0
            )
        else:
            # Recent actions were near average - no bias
            multiplier = 1.0

        return delay * multiplier

    def _update_speed_history(self, delay: float) -> None:
        """Update speed history with new delay.

        Args:
            delay: Delay in ms
        """
        self._speed_history.append(delay)

        # Keep only recent history
        if len(self._speed_history) > self.SPEED_HISTORY_SIZE * 2:
            self._speed_history = self._speed_history[-self.SPEED_HISTORY_SIZE:]

    def reset_history(self) -> None:
        """Reset timing history (call when starting new session)."""
        self._speed_history.clear()
        self._last_mean_for_action.clear()

    def get_speed_history(self) -> list[float]:
        """Get recent speed history for debugging.

        Returns:
            List of recent delays in ms
        """
        return list(self._speed_history)

    def _gamma_delay(
        self, mean: float, std: float, min_val: float, max_val: float
    ) -> float:
        """Generate delay using Gamma distribution.

        Gamma distribution provides natural right-skewed timing
        (occasional longer pauses).

        Args:
            mean: Target mean delay
            std: Target standard deviation
            min_val: Minimum allowed delay
            max_val: Maximum allowed delay

        Returns:
            Delay in milliseconds
        """
        return gamma_delay(self._rng, mean, std, min_val, max_val)

    def get_post_action_delay(self, action_category: ActionCategory) -> float:
        """Get delay after completing an action.

        Args:
            action_category: Category of action completed

        Returns:
            Delay in seconds
        """
        if action_category == ActionCategory.BANK_OPEN:
            base = self.config.after_bank_open
        elif action_category == ActionCategory.BANK_DEPOSIT:
            base = self.config.after_deposit
        elif action_category == ActionCategory.BANK_WITHDRAW:
            base = self.config.after_withdraw
        elif action_category == ActionCategory.BANK_CLOSE:
            base = self.config.after_bank_close
        else:
            base = 200

        # Add random variation (80-120% of base, Gaussian distribution)
        delay = base * gaussian_bounded(self._rng, 0.8, 1.2)

        # Apply fatigue
        delay *= self._fatigue_multiplier

        return delay / 1000.0

    def get_reaction_delay(self) -> float:
        """Get human-like reaction time delay.

        Returns:
            Delay in seconds
        """
        # Human reaction time is typically 200-300ms
        # Using normal distribution centered at 250ms
        delay = self._rng.normal(250, 50)
        delay = max(150, min(500, delay))

        return delay / 1000.0

    def get_think_pause(self) -> float:
        """Get occasional "thinking" pause.

        Simulates momentary distraction or thought.

        Returns:
            Delay in seconds (may be 0)
        """
        # 1% chance of a think pause
        if self._rng.random() > 0.01:
            return 0

        # Think pauses are 500ms - 2000ms
        delay = self._rng.gamma(2, 300) + 500
        delay = min(delay, 2000)

        return delay / 1000.0

    def should_have_micro_pause(self) -> bool:
        """Determine if a micro-pause should occur.

        Returns:
            True if should pause briefly
        """
        # 1% chance per action
        return self._rng.random() < 0.01

    def get_micro_pause_duration(self) -> float:
        """Get duration for a micro-pause.

        Returns:
            Duration in seconds
        """
        # 300ms - 1500ms
        duration = self._rng.gamma(2, 200) + 300
        return min(duration, 1500) / 1000.0
