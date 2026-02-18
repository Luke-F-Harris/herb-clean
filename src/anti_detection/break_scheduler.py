"""Break scheduling - micro and long breaks for human-like behavior."""

import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Callable

import numpy as np


class BreakType(Enum):
    """Types of breaks."""

    MICRO = "micro"
    LONG = "long"
    SESSION_END = "session_end"


@dataclass
class BreakConfig:
    """Configuration for break scheduling."""

    # Micro breaks (seconds)
    micro_interval: tuple[float, float] = (480, 900)  # 8-15 minutes
    micro_duration: tuple[float, float] = (2, 10)

    # Long breaks (seconds)
    long_interval: tuple[float, float] = (2700, 5400)  # 45-90 minutes
    long_duration: tuple[float, float] = (60, 300)  # 1-5 minutes


@dataclass
class ScheduledBreak:
    """A scheduled break."""

    break_type: BreakType
    scheduled_time: float  # Unix timestamp
    duration: float  # seconds
    completed: bool = False


class BreakScheduler:
    """Schedule and manage breaks for human-like behavior."""

    def __init__(self, config: Optional[BreakConfig] = None):
        """Initialize break scheduler.

        Args:
            config: Break configuration
        """
        self.config = config or BreakConfig()
        self._rng = np.random.default_rng()
        self._session_start: Optional[float] = None
        self._next_micro_break: Optional[ScheduledBreak] = None
        self._next_long_break: Optional[ScheduledBreak] = None
        self._break_history: list[ScheduledBreak] = []
        self._on_break_callback: Optional[Callable[[BreakType, float], None]] = None

    def set_break_callback(
        self, callback: Optional[Callable[[BreakType, float], None]]
    ) -> None:
        """Set callback for when breaks occur.

        Args:
            callback: Function(break_type, duration) called on break
        """
        self._on_break_callback = callback

    def start_session(self) -> None:
        """Start a new session and schedule initial breaks."""
        self._session_start = time.time()
        self._break_history = []
        self._schedule_next_micro_break()
        self._schedule_next_long_break()

    def _schedule_next_micro_break(self) -> None:
        """Schedule the next micro break."""
        interval = self._rng.uniform(
            self.config.micro_interval[0], self.config.micro_interval[1]
        )
        duration = self._rng.uniform(
            self.config.micro_duration[0], self.config.micro_duration[1]
        )

        self._next_micro_break = ScheduledBreak(
            break_type=BreakType.MICRO,
            scheduled_time=time.time() + interval,
            duration=duration,
        )

    def _schedule_next_long_break(self) -> None:
        """Schedule the next long break."""
        interval = self._rng.uniform(
            self.config.long_interval[0], self.config.long_interval[1]
        )
        duration = self._rng.uniform(
            self.config.long_duration[0], self.config.long_duration[1]
        )

        self._next_long_break = ScheduledBreak(
            break_type=BreakType.LONG,
            scheduled_time=time.time() + interval,
            duration=duration,
        )

    def check_break_needed(self) -> Optional[ScheduledBreak]:
        """Check if a break is due.

        Returns:
            ScheduledBreak if break is due, None otherwise
        """
        current_time = time.time()

        # Long breaks take priority
        if self._next_long_break and current_time >= self._next_long_break.scheduled_time:
            return self._next_long_break

        if self._next_micro_break and current_time >= self._next_micro_break.scheduled_time:
            return self._next_micro_break

        return None

    def execute_break(self, scheduled_break: ScheduledBreak) -> float:
        """Execute a scheduled break.

        Args:
            scheduled_break: The break to execute

        Returns:
            Actual break duration in seconds
        """
        # Add some variation to duration
        actual_duration = scheduled_break.duration * self._rng.uniform(0.8, 1.2)

        if self._on_break_callback:
            self._on_break_callback(scheduled_break.break_type, actual_duration)

        # Sleep for break duration
        time.sleep(actual_duration)

        # Mark completed and record
        scheduled_break.completed = True
        self._break_history.append(scheduled_break)

        # Schedule next break
        if scheduled_break.break_type == BreakType.MICRO:
            self._schedule_next_micro_break()
        elif scheduled_break.break_type == BreakType.LONG:
            self._schedule_next_long_break()
            # Also push back micro break after long break
            self._schedule_next_micro_break()

        return actual_duration

    def time_until_next_break(self) -> tuple[BreakType, float]:
        """Get time until next break.

        Returns:
            (break_type, seconds_until) tuple
        """
        current_time = time.time()

        micro_time = float("inf")
        long_time = float("inf")

        if self._next_micro_break:
            micro_time = self._next_micro_break.scheduled_time - current_time

        if self._next_long_break:
            long_time = self._next_long_break.scheduled_time - current_time

        if long_time <= micro_time:
            return BreakType.LONG, max(0, long_time)
        else:
            return BreakType.MICRO, max(0, micro_time)

    def get_break_count(self, break_type: Optional[BreakType] = None) -> int:
        """Get number of breaks taken.

        Args:
            break_type: Filter by type, or None for all

        Returns:
            Number of breaks
        """
        if break_type is None:
            return len(self._break_history)

        return sum(1 for b in self._break_history if b.break_type == break_type)

    def get_total_break_time(self) -> float:
        """Get total time spent on breaks.

        Returns:
            Total break time in seconds
        """
        return sum(b.duration for b in self._break_history)

    def force_micro_break(self) -> float:
        """Force an immediate micro break.

        Returns:
            Break duration in seconds
        """
        duration = self._rng.uniform(
            self.config.micro_duration[0], self.config.micro_duration[1]
        )

        forced_break = ScheduledBreak(
            break_type=BreakType.MICRO,
            scheduled_time=time.time(),
            duration=duration,
        )

        return self.execute_break(forced_break)

    def skip_next_break(self, break_type: BreakType) -> None:
        """Skip the next scheduled break and reschedule.

        Args:
            break_type: Type of break to skip
        """
        if break_type == BreakType.MICRO:
            self._schedule_next_micro_break()
        elif break_type == BreakType.LONG:
            self._schedule_next_long_break()

    def get_status(self) -> dict:
        """Get current break scheduler status.

        Returns:
            Dict with scheduler metrics
        """
        break_type, time_until = self.time_until_next_break()

        return {
            "session_duration_minutes": (time.time() - (self._session_start or time.time())) / 60,
            "next_break_type": break_type.value,
            "time_until_next_break_seconds": time_until,
            "micro_breaks_taken": self.get_break_count(BreakType.MICRO),
            "long_breaks_taken": self.get_break_count(BreakType.LONG),
            "total_break_time_seconds": self.get_total_break_time(),
        }
