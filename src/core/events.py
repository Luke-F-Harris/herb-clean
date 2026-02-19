"""Event system for anti-detection status tracking."""

import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional


class EventType(Enum):
    """Types of anti-detection events."""

    BREAK_START = "break_start"
    BREAK_END = "break_end"
    DRIFT = "drift"
    SKILL_CHECK = "skill_check"
    FATIGUE_UPDATE = "fatigue_update"
    ATTENTION_LAPSE = "attention_lapse"


@dataclass
class AntiDetectionEvent:
    """An anti-detection event with metadata."""

    event_type: EventType
    timestamp: float = field(default_factory=time.time)
    data: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.timestamp == 0:
            self.timestamp = time.time()

    @property
    def age_seconds(self) -> float:
        """Get event age in seconds."""
        return time.time() - self.timestamp

    def format_time(self) -> str:
        """Format timestamp as MM:SS."""
        minutes = int(self.timestamp // 60) % 60
        seconds = int(self.timestamp % 60)
        return f"{minutes:02d}:{seconds:02d}"


class EventEmitter:
    """Simple event emitter for anti-detection events."""

    def __init__(self, max_history: int = 100):
        """Initialize event emitter.

        Args:
            max_history: Maximum number of events to keep in history
        """
        self._callbacks: list[Callable[[AntiDetectionEvent], None]] = []
        self._history: deque[AntiDetectionEvent] = deque(maxlen=max_history)
        self._current_event: Optional[AntiDetectionEvent] = None

    def subscribe(self, callback: Callable[[AntiDetectionEvent], None]) -> None:
        """Subscribe to events.

        Args:
            callback: Function to call when an event occurs
        """
        self._callbacks.append(callback)

    def unsubscribe(self, callback: Callable[[AntiDetectionEvent], None]) -> None:
        """Unsubscribe from events.

        Args:
            callback: Function to remove from callbacks
        """
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    def emit(self, event: AntiDetectionEvent) -> None:
        """Emit an event to all subscribers.

        Args:
            event: The event to emit
        """
        self._history.append(event)

        # Track current event for ongoing activities (breaks, etc.)
        if event.event_type == EventType.BREAK_START:
            self._current_event = event
        elif event.event_type == EventType.BREAK_END:
            self._current_event = None

        for callback in self._callbacks:
            try:
                callback(event)
            except Exception:
                pass  # Don't let callback errors break the bot

    def emit_break_start(self, break_type: str, duration: float) -> None:
        """Convenience method to emit a break start event.

        Args:
            break_type: "micro" or "long"
            duration: Expected duration in seconds
        """
        self.emit(AntiDetectionEvent(
            event_type=EventType.BREAK_START,
            data={"break_type": break_type, "duration": duration}
        ))

    def emit_break_end(self, break_type: str, actual_duration: float) -> None:
        """Convenience method to emit a break end event.

        Args:
            break_type: "micro" or "long"
            actual_duration: Actual duration in seconds
        """
        self.emit(AntiDetectionEvent(
            event_type=EventType.BREAK_END,
            data={"break_type": break_type, "duration": actual_duration}
        ))

    def emit_drift(self, target: str, duration: float) -> None:
        """Convenience method to emit an attention drift event.

        Args:
            target: Where attention drifted to (e.g., "minimap")
            duration: How long the drift lasted
        """
        self.emit(AntiDetectionEvent(
            event_type=EventType.DRIFT,
            data={"target": target, "duration": duration}
        ))

    def emit_skill_check(self, hover_duration: float) -> None:
        """Convenience method to emit a skill check event.

        Args:
            hover_duration: How long hovered over skill
        """
        self.emit(AntiDetectionEvent(
            event_type=EventType.SKILL_CHECK,
            data={"hover_duration": hover_duration}
        ))

    def emit_fatigue_update(self, level: float, slowdown: float) -> None:
        """Convenience method to emit a fatigue update event.

        Args:
            level: Fatigue level (0-1)
            slowdown: Current slowdown multiplier
        """
        self.emit(AntiDetectionEvent(
            event_type=EventType.FATIGUE_UPDATE,
            data={"level": level, "slowdown": slowdown}
        ))

    def emit_attention_lapse(self, duration: float) -> None:
        """Convenience method to emit an attention lapse event.

        Args:
            duration: Lapse duration in seconds
        """
        self.emit(AntiDetectionEvent(
            event_type=EventType.ATTENTION_LAPSE,
            data={"duration": duration}
        ))

    def get_recent(self, count: int = 10) -> list[AntiDetectionEvent]:
        """Get recent events.

        Args:
            count: Number of events to return

        Returns:
            List of recent events, most recent first
        """
        events = list(self._history)
        events.reverse()
        return events[:count]

    def get_current_event(self) -> Optional[AntiDetectionEvent]:
        """Get the currently active event (e.g., ongoing break).

        Returns:
            Current event or None
        """
        return self._current_event

    def clear_current_event(self) -> None:
        """Clear the current event."""
        self._current_event = None

    def get_event_count(self, event_type: Optional[EventType] = None) -> int:
        """Get count of events by type.

        Args:
            event_type: Filter by type, or None for all

        Returns:
            Event count
        """
        if event_type is None:
            return len(self._history)

        return sum(1 for e in self._history if e.event_type == event_type)
