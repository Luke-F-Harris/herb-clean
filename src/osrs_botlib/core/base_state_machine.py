"""Base state machine for all OSRS bots."""
from typing import Optional
from statemachine import StateMachine, State


class BaseBotStateMachine(StateMachine):
    """Base state machine with common states for all bots.

    Subclasses should add skill-specific states and transitions.
    """

    # Common states (all bots need these)
    idle = State(initial=True)
    assess_state = State()
    error = State()
    emergency_stop = State()
    stopped = State(final=True)
    break_micro = State()
    break_long = State()

    # Common transitions that subclasses can extend
    # Assessment transitions
    start_assessment = idle.to(assess_state)

    # Break transitions (subclasses should add more states to these)
    take_micro_break = idle.to(break_micro)
    take_long_break = idle.to(break_long)
    resume_from_micro = break_micro.to(idle)
    resume_from_long = break_long.to(idle)

    # Emergency stop (subclasses should add more states to this)
    emergency = (
        idle.to(emergency_stop)
        | assess_state.to(emergency_stop)
        | break_micro.to(emergency_stop)
        | break_long.to(emergency_stop)
        | error.to(emergency_stop)
    )

    # Error transitions (subclasses should add more states to this)
    handle_error = (
        idle.to(error)
        | assess_state.to(error)
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
        # Initialize attributes before super().__init__() because it triggers
        # initial state entry which calls on_enter_state
        self._error_message: Optional[str] = None
        self._error_count = 0
        self._state_history: list[str] = []
        super().__init__()

    def on_enter_state(self, state: State) -> None:
        """Called when entering any state."""
        self._state_history.append(state.name)
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

    def is_in_break(self) -> bool:
        """Check if currently in a break state."""
        return self.current_state in (self.break_micro, self.break_long)

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
