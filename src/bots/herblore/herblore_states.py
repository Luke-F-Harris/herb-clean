"""Herblore bot state machine."""
from enum import Enum
from statemachine import State

from osrs_botlib.core.base_state_machine import BaseBotStateMachine


class BotState(Enum):
    """Herblore bot states."""

    IDLE = "idle"
    ASSESS_STATE = "assess_state"
    BANKING_OPEN = "banking_open"
    BANKING_DEPOSIT = "banking_deposit"
    BANKING_WITHDRAW = "banking_withdraw"
    BANKING_CLOSE = "banking_close"
    CLEANING = "cleaning"
    BREAK_MICRO = "break_micro"
    BREAK_LONG = "break_long"
    EMERGENCY_STOP = "emergency_stop"
    ERROR = "error"
    STOPPED = "stopped"


class HerbCleaningStateMachine(BaseBotStateMachine):
    """State machine for herb cleaning bot."""

    # Herblore-specific states (inherit common states from base)
    banking_open = State()
    banking_deposit = State()
    banking_withdraw = State()
    banking_close = State()
    cleaning = State()

    # Assessment transitions (IDLE always goes through assessment first)
    # Inherit: start_assessment = idle.to(assess_state)

    # From assessment to appropriate state
    assessment_to_banking = assess_state.to(banking_open)
    assessment_to_cleaning = assess_state.to(cleaning)
    assessment_to_deposit = assess_state.to(banking_deposit)
    assessment_to_withdraw = assess_state.to(banking_withdraw)

    # Normal flow transitions
    start_banking = cleaning.to(banking_open)
    deposit_herbs = banking_open.to(banking_deposit)
    withdraw_herbs = banking_deposit.to(banking_withdraw)
    close_bank = banking_withdraw.to(banking_close)
    start_cleaning = banking_close.to(cleaning)

    # Skip deposit if inventory empty
    skip_deposit = banking_open.to(banking_withdraw)

    # Return to cleaning after withdraw
    continue_cleaning = banking_close.to(cleaning)

    # Extend break transitions to include herblore states
    take_micro_break = (
        BaseBotStateMachine.take_micro_break
        | cleaning.to(break_micro)
        | banking_close.to(break_micro)
    )
    take_long_break = (
        BaseBotStateMachine.take_long_break
        | cleaning.to(break_long)
        | banking_close.to(break_long)
    )

    # Extend emergency stop to include herblore states
    emergency = (
        BaseBotStateMachine.emergency
        | banking_open.to(emergency_stop)
        | banking_deposit.to(emergency_stop)
        | banking_withdraw.to(emergency_stop)
        | banking_close.to(emergency_stop)
        | cleaning.to(emergency_stop)
    )

    # Extend error transitions to include herblore states
    handle_error = (
        BaseBotStateMachine.handle_error
        | banking_open.to(error)
        | banking_deposit.to(error)
        | banking_withdraw.to(error)
        | banking_close.to(error)
        | cleaning.to(error)
    )

    def get_current_state(self) -> BotState:
        """Get current state as BotState enum."""
        return BotState(self.current_state.id)

    def is_banking(self) -> bool:
        """Check if currently in a banking state."""
        return self.current_state in (
            self.banking_open,
            self.banking_deposit,
            self.banking_withdraw,
            self.banking_close,
        )
