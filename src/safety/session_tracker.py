"""Session tracking and statistics."""

import json
import logging
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np

from utils import create_rng, gaussian_bounded


@dataclass
class SessionStats:
    """Statistics for a bot session."""

    start_time: float = 0.0
    end_time: float = 0.0
    herbs_cleaned: int = 0
    bank_trips: int = 0
    micro_breaks: int = 0
    long_breaks: int = 0
    errors: int = 0
    misclicks: int = 0
    attention_drifts: int = 0

    # Timing stats
    total_active_time: float = 0.0
    total_break_time: float = 0.0

    # Derived stats
    herbs_per_hour: float = 0.0
    avg_clean_time_ms: float = 0.0


@dataclass
class SessionConfig:
    """Configuration for session tracking."""

    # Variable session length (Gaussian distribution within range)
    max_session_hours_range: tuple[float, float] = (4.0, 6.0)
    max_session_hours_std: float = 0.5  # Standard deviation in hours

    # Legacy fixed session length (used if range is None or equal)
    max_session_hours: float = 4.0

    stats_log_interval: float = 60.0  # seconds
    log_file: Optional[Path] = None


class SessionTracker:
    """Track session runtime and statistics."""

    def __init__(self, config: Optional[SessionConfig] = None):
        """Initialize session tracker.

        Args:
            config: Session configuration
        """
        self.config = config or SessionConfig()
        self._stats = SessionStats()
        self._is_running = False
        self._last_log_time = 0.0
        self._clean_times: list[float] = []  # For averaging
        self._logger = logging.getLogger(__name__)
        self._rng = create_rng()
        self._current_max_hours: float = self.config.max_session_hours

    def start_session(self) -> None:
        """Start a new session.

        Selects a variable session length using Gaussian distribution
        within the configured range.
        """
        self._stats = SessionStats(start_time=time.time())
        self._is_running = True
        self._last_log_time = time.time()
        self._clean_times = []

        # Determine session length for this session (variable, Gaussian)
        min_hours, max_hours = self.config.max_session_hours_range
        if min_hours < max_hours:
            # Variable session length with Gaussian distribution
            mean_hours = (min_hours + max_hours) / 2
            self._current_max_hours = gaussian_bounded(
                self._rng,
                min_hours,
                max_hours,
                mean=mean_hours,
                std=self.config.max_session_hours_std,
            )
        else:
            # Fixed session length (legacy behavior)
            self._current_max_hours = self.config.max_session_hours

        self._logger.info(
            "Session started at %s (max duration: %.1f hours)",
            datetime.now().isoformat(),
            self._current_max_hours,
        )

    def end_session(self) -> SessionStats:
        """End the current session.

        Returns:
            Final session statistics
        """
        self._stats.end_time = time.time()
        self._is_running = False
        self._calculate_derived_stats()

        self._logger.info(
            "Session ended. Duration: %.1f minutes, Herbs cleaned: %d",
            self.get_session_duration() / 60,
            self._stats.herbs_cleaned,
        )

        # Save stats if log file configured
        if self.config.log_file:
            self._save_stats()

        return self._stats

    def record_herb_cleaned(self, clean_time_ms: float) -> None:
        """Record a herb being cleaned.

        Args:
            clean_time_ms: Time to clean in milliseconds
        """
        self._stats.herbs_cleaned += 1
        self._clean_times.append(clean_time_ms)

        # Keep rolling window of clean times
        if len(self._clean_times) > 1000:
            self._clean_times = self._clean_times[-500:]

    def record_bank_trip(self) -> None:
        """Record a bank trip."""
        self._stats.bank_trips += 1

    def record_micro_break(self, duration: float) -> None:
        """Record a micro break.

        Args:
            duration: Break duration in seconds
        """
        self._stats.micro_breaks += 1
        self._stats.total_break_time += duration

    def record_long_break(self, duration: float) -> None:
        """Record a long break.

        Args:
            duration: Break duration in seconds
        """
        self._stats.long_breaks += 1
        self._stats.total_break_time += duration

    def record_error(self) -> None:
        """Record an error."""
        self._stats.errors += 1

    def record_misclick(self) -> None:
        """Record a misclick."""
        self._stats.misclicks += 1

    def record_attention_drift(self) -> None:
        """Record an attention drift."""
        self._stats.attention_drifts += 1

    def get_session_duration(self) -> float:
        """Get current session duration in seconds.

        Returns:
            Duration in seconds
        """
        if not self._stats.start_time:
            return 0

        end = self._stats.end_time or time.time()
        return end - self._stats.start_time

    def get_active_time(self) -> float:
        """Get active (non-break) time in seconds.

        Returns:
            Active time in seconds
        """
        total = self.get_session_duration()
        return total - self._stats.total_break_time

    def should_end_session(self) -> bool:
        """Check if session should end due to max time.

        Returns:
            True if session should end
        """
        max_seconds = self._current_max_hours * 3600
        return self.get_session_duration() >= max_seconds

    def get_time_remaining(self) -> float:
        """Get time remaining in session.

        Returns:
            Time remaining in seconds
        """
        max_seconds = self._current_max_hours * 3600
        elapsed = self.get_session_duration()
        return max(0, max_seconds - elapsed)

    def get_current_max_hours(self) -> float:
        """Get the maximum session length for this session.

        Returns:
            Max session length in hours
        """
        return self._current_max_hours

    def _calculate_derived_stats(self) -> None:
        """Calculate derived statistics."""
        duration_hours = self.get_session_duration() / 3600

        if duration_hours > 0:
            self._stats.herbs_per_hour = self._stats.herbs_cleaned / duration_hours

        if self._clean_times:
            self._stats.avg_clean_time_ms = sum(self._clean_times) / len(self._clean_times)

        self._stats.total_active_time = self.get_active_time()

    def get_stats(self) -> SessionStats:
        """Get current statistics.

        Returns:
            Current session stats
        """
        self._calculate_derived_stats()
        return self._stats

    def should_log_stats(self) -> bool:
        """Check if it's time to log stats.

        Returns:
            True if should log
        """
        elapsed = time.time() - self._last_log_time
        return elapsed >= self.config.stats_log_interval

    def log_stats(self) -> None:
        """Log current statistics."""
        self._last_log_time = time.time()
        stats = self.get_stats()

        self._logger.info(
            "Stats: Herbs=%d (%.0f/hr), Banks=%d, Breaks=%d/%d, Errors=%d",
            stats.herbs_cleaned,
            stats.herbs_per_hour,
            stats.bank_trips,
            stats.micro_breaks,
            stats.long_breaks,
            stats.errors,
        )

    def _save_stats(self) -> None:
        """Save statistics to log file."""
        if not self.config.log_file:
            return

        log_path = Path(self.config.log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        stats_dict = asdict(self._stats)
        stats_dict["timestamp"] = datetime.now().isoformat()

        # Append to log file
        with open(log_path, "a") as f:
            f.write(json.dumps(stats_dict) + "\n")

    def get_status_string(self) -> str:
        """Get formatted status string.

        Returns:
            Human-readable status
        """
        stats = self.get_stats()
        duration = self.get_session_duration()

        return (
            f"Session: {duration / 60:.1f}min | "
            f"Herbs: {stats.herbs_cleaned} ({stats.herbs_per_hour:.0f}/hr) | "
            f"Banks: {stats.bank_trips} | "
            f"Breaks: {stats.micro_breaks}M/{stats.long_breaks}L | "
            f"Errors: {stats.errors}"
        )

    @property
    def is_running(self) -> bool:
        """Check if session is running."""
        return self._is_running
