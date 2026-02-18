"""Bot state machine using python-statemachine."""

from enum import Enum
from typing import Optional

from statemachine import StateMachine, State


class BotState(Enum):
    """Bot states."""

    IDLE = "idle"
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


class HerbCleaningStateMachine(StateMachine):
    """State machine for herb cleaning bot."""

    # States
    idle = State(initial=True)
    banking_open = State()
    banking_deposit = State()
    banking_withdraw = State()
    banking_close = State()
    cleaning = State()
    break_micro = State()
    break_long = State()
    emergency_stop = State()
    error = State()
    stopped = State(final=True)

    # Normal flow transitions
    start_banking = idle.to(banking_open) | cleaning.to(banking_open)
    deposit_herbs = banking_open.to(banking_deposit)
    withdraw_herbs = banking_deposit.to(banking_withdraw)
    close_bank = banking_withdraw.to(banking_close)
    start_cleaning = banking_close.to(cleaning)

    # Skip deposit if inventory empty
    skip_deposit = banking_open.to(banking_withdraw)

    # Return to cleaning after withdraw
    continue_cleaning = banking_close.to(cleaning)

    # Break transitions (can happen from most states)
    take_micro_break = (
        idle.to(break_micro)
        | cleaning.to(break_micro)
        | banking_close.to(break_micro)
    )
    take_long_break = (
        idle.to(break_long)
        | cleaning.to(break_long)
        | banking_close.to(break_long)
    )

    # Return from breaks
    resume_from_micro = break_micro.to(idle)
    resume_from_long = break_long.to(idle)

    # Emergency stop (from any state)
    emergency = (
        idle.to(emergency_stop)
        | banking_open.to(emergency_stop)
        | banking_deposit.to(emergency_stop)
        | banking_withdraw.to(emergency_stop)
        | banking_close.to(emergency_stop)
        | cleaning.to(emergency_stop)
        | break_micro.to(emergency_stop)
        | break_long.to(emergency_stop)
        | error.to(emergency_stop)
    )

    # Error transitions
    handle_error = (
        idle.to(error)
        | banking_open.to(error)
        | banking_deposit.to(error)
        | banking_withdraw.to(error)
        | banking_close.to(error)
        | cleaning.to(error)
    )

    # Recovery from error
    recover = error.to(idle)

    # Normal stop
    stop = (
        idle.to(stopped)
        | emergency_stop.to(stopped)
        | error.to(stopped)
        | break_micro.to(stopped)
        | break_long.to(stopped)
    )

    def __init__(self):
        """Initialize state machine."""
        super().__init__()
        self._error_message: Optional[str] = None
        self._error_count = 0
        self._state_history: list[str] = []

    def on_enter_state(self, state: State) -> None:
        """Called when entering any state."""
        self._state_history.append(state.id)
        # Keep history limited
        if len(self._state_history) > 100:
            self._state_history = self._state_history[-50:]

    def on_enter_error(self) -> None:
        """Called when entering error state."""
        self._error_count += 1

    def on_enter_emergency_stop(self) -> None:
        """Called when entering emergency stop state."""
        pass

    def set_error(self, message: str) -> None:
        """Set error message.

        Args:
            message: Error description
        """
        self._error_message = message

    def get_error(self) -> Optional[str]:
        """Get last error message."""
        return self._error_message

    def get_error_count(self) -> int:
        """Get total error count."""
        return self._error_count

    def get_state_history(self) -> list[str]:
        """Get recent state history."""
        return self._state_history.copy()

    def get_current_state(self) -> BotState:
        """Get current state as BotState enum."""
        return BotState(self.current_state.id)

    def is_in_break(self) -> bool:
        """Check if currently in a break state."""
        return self.current_state in (self.break_micro, self.break_long)

    def is_banking(self) -> bool:
        """Check if currently in a banking state."""
        return self.current_state in (
            self.banking_open,
            self.banking_deposit,
            self.banking_withdraw,
            self.banking_close,
        )

    def is_stopped(self) -> bool:
        """Check if bot is stopped."""
        return self.current_state in (self.emergency_stop, self.stopped, self.error)

    def can_transition_to(self, target_state: str) -> bool:
        """Check if transition to target state is valid.

        Args:
            target_state: Target state name

        Returns:
            True if transition is valid
        """
        # Get all possible transitions from current state
        for transition in self.current_state.transitions:
            for state in transition.destinations:
                if state.id == target_state:
                    return True
        return False
