"""Status aggregator - collects status from all anti-detection modules."""

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from anti_detection.fatigue_simulator import FatigueSimulator
    from anti_detection.break_scheduler import BreakScheduler
    from anti_detection.timing_randomizer import TimingRandomizer
    from anti_detection.attention_drift import AttentionDrift
    from anti_detection.skill_checker import SkillChecker
    from safety.session_tracker import SessionTracker
    from core.state_machine import HerbCleaningStateMachine


@dataclass
class FatigueStatus:
    """Fatigue module status."""

    level: float = 0.0  # 0-1
    slowdown_multiplier: float = 1.0
    misclick_rate: float = 0.01
    session_minutes: float = 0.0


@dataclass
class BreakStatus:
    """Break scheduler status."""

    next_break_type: str = "micro"
    time_until_next: float = 0.0  # seconds
    micro_count: int = 0
    long_count: int = 0
    total_break_time: float = 0.0  # seconds


@dataclass
class TimingStatus:
    """Timing status (from recent actions)."""

    last_delay_ms: float = 0.0
    avg_delay_ms: float = 0.0
    fatigue_multiplier: float = 1.0


@dataclass
class AttentionStatus:
    """Attention drift status."""

    drift_count: int = 0
    last_target: str = ""
    drift_chance: float = 0.03
    effective_chance: float = 0.03  # With fatigue bonus


@dataclass
class SkillCheckStatus:
    """Skill checker status."""

    check_count: int = 0
    time_until_next: float = 0.0  # seconds
    enabled: bool = True


@dataclass
class SessionStatus:
    """Session status."""

    duration_seconds: float = 0.0
    herbs_cleaned: int = 0
    herbs_per_hour: float = 0.0
    bank_trips: int = 0
    errors: int = 0
    current_state: str = "idle"


@dataclass
class StatusSnapshot:
    """Complete snapshot of all module statuses."""

    timestamp: float = field(default_factory=time.time)
    fatigue: FatigueStatus = field(default_factory=FatigueStatus)
    breaks: BreakStatus = field(default_factory=BreakStatus)
    timing: TimingStatus = field(default_factory=TimingStatus)
    attention: AttentionStatus = field(default_factory=AttentionStatus)
    skill_check: SkillCheckStatus = field(default_factory=SkillCheckStatus)
    session: SessionStatus = field(default_factory=SessionStatus)


class StatusAggregator:
    """Collects status from all anti-detection modules into a single snapshot."""

    def __init__(
        self,
        fatigue: Optional["FatigueSimulator"] = None,
        breaks: Optional["BreakScheduler"] = None,
        timing: Optional["TimingRandomizer"] = None,
        attention: Optional["AttentionDrift"] = None,
        skill_checker: Optional["SkillChecker"] = None,
        session: Optional["SessionTracker"] = None,
        state_machine: Optional["HerbCleaningStateMachine"] = None,
    ):
        """Initialize status aggregator.

        Args:
            fatigue: Fatigue simulator instance
            breaks: Break scheduler instance
            timing: Timing randomizer instance
            attention: Attention drift instance
            skill_checker: Skill checker instance
            session: Session tracker instance
            state_machine: State machine instance
        """
        self._fatigue = fatigue
        self._breaks = breaks
        self._timing = timing
        self._attention = attention
        self._skill_checker = skill_checker
        self._session = session
        self._state_machine = state_machine

        # Track timing for display
        self._last_delay_ms: float = 0.0
        self._delay_history: list[float] = []
        self._max_delay_history = 50

    def record_delay(self, delay_ms: float) -> None:
        """Record a timing delay for status tracking.

        Args:
            delay_ms: Delay in milliseconds
        """
        self._last_delay_ms = delay_ms
        self._delay_history.append(delay_ms)
        if len(self._delay_history) > self._max_delay_history:
            self._delay_history = self._delay_history[-self._max_delay_history:]

    def get_snapshot(self) -> StatusSnapshot:
        """Get complete status snapshot from all modules.

        Returns:
            StatusSnapshot with all module statuses
        """
        snapshot = StatusSnapshot()

        # Fatigue status
        if self._fatigue:
            fatigue_level = self._fatigue.get_fatigue_level()
            snapshot.fatigue = FatigueStatus(
                level=fatigue_level,
                slowdown_multiplier=self._fatigue.get_slowdown_multiplier(),
                misclick_rate=self._fatigue.get_misclick_rate(),
                session_minutes=self._fatigue.get_session_duration(),
            )

        # Break status
        if self._breaks:
            break_type, time_until = self._breaks.time_until_next_break()
            snapshot.breaks = BreakStatus(
                next_break_type=break_type.value,
                time_until_next=time_until,
                micro_count=self._breaks.get_break_count(
                    __import__("src.anti_detection.break_scheduler", fromlist=["BreakType"]).BreakType.MICRO
                ) if hasattr(self._breaks, "get_break_count") else 0,
                long_count=self._breaks.get_break_count(
                    __import__("src.anti_detection.break_scheduler", fromlist=["BreakType"]).BreakType.LONG
                ) if hasattr(self._breaks, "get_break_count") else 0,
                total_break_time=self._breaks.get_total_break_time(),
            )

        # Timing status
        fatigue_mult = 1.0
        if self._timing and hasattr(self._timing, "_fatigue_multiplier"):
            fatigue_mult = self._timing._fatigue_multiplier

        avg_delay = 0.0
        if self._delay_history:
            avg_delay = sum(self._delay_history) / len(self._delay_history)

        snapshot.timing = TimingStatus(
            last_delay_ms=self._last_delay_ms,
            avg_delay_ms=avg_delay,
            fatigue_multiplier=fatigue_mult,
        )

        # Attention status
        if self._attention:
            fatigue_level = snapshot.fatigue.level if self._fatigue else 0.0
            base_chance = self._attention.config.drift_chance
            effective_chance = base_chance + (fatigue_level * 0.03)

            snapshot.attention = AttentionStatus(
                drift_count=self._attention.get_drift_count(),
                last_target="",  # Updated by events
                drift_chance=base_chance,
                effective_chance=effective_chance,
            )

        # Skill check status
        if self._skill_checker:
            snapshot.skill_check = SkillCheckStatus(
                check_count=self._skill_checker.get_check_count(),
                time_until_next=self._skill_checker.time_until_next_check(),
                enabled=self._skill_checker.config.enabled,
            )

        # Session status
        if self._session:
            stats = self._session.get_stats()
            current_state = "idle"
            if self._state_machine:
                current_state = self._state_machine.get_current_state().value

            snapshot.session = SessionStatus(
                duration_seconds=self._session.get_session_duration(),
                herbs_cleaned=stats.herbs_cleaned,
                herbs_per_hour=stats.herbs_per_hour,
                bank_trips=stats.bank_trips,
                errors=stats.errors,
                current_state=current_state,
            )

        return snapshot

    def format_session_time(self) -> str:
        """Format session duration as HH:MM:SS or MM:SS.

        Returns:
            Formatted time string
        """
        if not self._session:
            return "00:00"

        duration = self._session.get_session_duration()
        hours = int(duration // 3600)
        minutes = int((duration % 3600) // 60)
        seconds = int(duration % 60)

        if hours > 0:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"
