"""Herblore-specific action types."""
from enum import Enum


class HerbloreActionType(Enum):
    """Specific actions for herblore bot."""

    CLICK_HERB = "click_herb"
    BANK_ACTION = "bank_action"
    OPEN_BANK = "open_bank"
    DEPOSIT = "deposit"
    WITHDRAW = "withdraw"
    CLOSE_BANK = "close_bank"
