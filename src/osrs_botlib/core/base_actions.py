"""Generic action categories for all bots."""
from enum import Enum


class ActionCategory(Enum):
    """Generic action categories for timing across all bot types."""

    # Skill-specific actions (clicking herb, chopping tree, catching fish, etc.)
    SKILL_ACTION = "skill"

    # Bank operations
    BANK_OPEN = "bank_open"
    BANK_DEPOSIT = "bank_deposit"
    BANK_WITHDRAW = "bank_withdraw"
    BANK_CLOSE = "bank_close"

    # Inventory operations
    INVENTORY_CLICK = "inventory_click"

    # Movement
    CAMERA_MOVE = "camera_move"
    WALK = "walk"

    # UI interactions
    UI_CLICK = "ui_click"
    UI_CLOSE = "ui_close"
