"""Timing randomization using statistical distributions."""

from dataclasses import dataclass
from enum import Enum
from typing import Optional

import numpy as np

from src.utils import create_rng, gamma_delay


class ActionType(Enum):
    """Types of bot actions for timing purposes."""

    CLICK_HERB = "click_herb"
    BANK_ACTION = "bank_action"
    OPEN_BANK = "open_bank"
    DEPOSIT = "deposit"
    WITHDRAW = "withdraw"
    CLOSE_BANK = "close_bank"


@dataclass
class TimingConfig:
    """Configuration for timing randomization."""

    # Herb cleaning (fast clicking)
    click_herb_mean: float = 250  # ms
    click_herb_std: float = 75
    click_herb_min: float = 150
    click_herb_max: float = 500

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
    """Generate human-like random delays using statistical distributions."""

    def __init__(self, config: Optional[TimingConfig] = None):
        """Initialize timing randomizer.

        Args:
            config: Timing configuration
        """
        self.config = config or TimingConfig()
        self._rng = create_rng()
        self._fatigue_multiplier = 1.0

    def set_fatigue_multiplier(self, multiplier: float) -> None:
        """Set fatigue multiplier for delays.

        Args:
            multiplier: Multiplier >= 1.0 (1.0 = no fatigue)
        """
        self._fatigue_multiplier = max(1.0, multiplier)

    def get_delay(self, action_type: ActionType) -> float:
        """Get randomized delay for an action.

        Uses Gamma distribution for right-skewed, natural timing.

        Args:
            action_type: Type of action

        Returns:
            Delay in seconds
        """
        if action_type == ActionType.CLICK_HERB:
            delay = self._gamma_delay(
                self.config.click_herb_mean,
                self.config.click_herb_std,
                self.config.click_herb_min,
                self.config.click_herb_max,
            )
        elif action_type in (
            ActionType.BANK_ACTION,
            ActionType.OPEN_BANK,
            ActionType.DEPOSIT,
            ActionType.WITHDRAW,
        ):
            delay = self._gamma_delay(
                self.config.bank_action_mean,
                self.config.bank_action_std,
                self.config.bank_action_min,
                self.config.bank_action_max,
            )
        elif action_type == ActionType.CLOSE_BANK:
            delay = self._gamma_delay(
                self.config.after_bank_close,
                self.config.after_bank_close * 0.3,
                self.config.after_bank_close * 0.5,
                self.config.after_bank_close * 2,
            )
        else:
            delay = self._gamma_delay(500, 100, 300, 1000)

        # Apply fatigue
        delay *= self._fatigue_multiplier

        return delay / 1000.0  # Convert to seconds

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

    def get_post_action_delay(self, action_type: ActionType) -> float:
        """Get delay after completing an action.

        Args:
            action_type: Type of action completed

        Returns:
            Delay in seconds
        """
        if action_type == ActionType.OPEN_BANK:
            base = self.config.after_bank_open
        elif action_type == ActionType.DEPOSIT:
            base = self.config.after_deposit
        elif action_type == ActionType.WITHDRAW:
            base = self.config.after_withdraw
        elif action_type == ActionType.CLOSE_BANK:
            base = self.config.after_bank_close
        else:
            base = 200

        # Add random variation (80-120% of base)
        delay = base * self._rng.uniform(0.8, 1.2)

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
        # 5% chance of a think pause
        if self._rng.random() > 0.05:
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
        # 2% chance per action
        return self._rng.random() < 0.02

    def get_micro_pause_duration(self) -> float:
        """Get duration for a micro-pause.

        Returns:
            Duration in seconds
        """
        # 300ms - 1500ms
        duration = self._rng.gamma(2, 200) + 300
        return min(duration, 1500) / 1000.0
