"""Herblore session tracking."""
import logging
from dataclasses import dataclass
from typing import Optional

from osrs_botlib.safety.base_session import (
    BaseSessionStats,
    BaseSessionTracker,
    SessionConfig,
)


@dataclass
class HerbloreSessionStats(BaseSessionStats):
    """Statistics for herblore bot session."""

    herbs_cleaned: int = 0

    # Derived stats
    herbs_per_hour: float = 0.0
    avg_clean_time_ms: float = 0.0


class HerbSessionTracker(BaseSessionTracker):
    """Session tracker for herblore bot."""

    def __init__(self, config: Optional[SessionConfig] = None):
        """Initialize herblore session tracker.

        Args:
            config: Session configuration
        """
        self._clean_times: list[float] = []  # For averaging
        super().__init__(config)

    def _create_stats(self) -> HerbloreSessionStats:
        """Create herblore stats object."""
        return HerbloreSessionStats()

    def get_primary_metric(self) -> int:
        """Get main metric (herbs cleaned)."""
        return self._stats.herbs_cleaned

    def record_item_processed(self, process_time_ms: float) -> None:
        """Record a herb being cleaned.

        Args:
            process_time_ms: Time to clean in milliseconds
        """
        self._stats.herbs_cleaned += 1
        self._clean_times.append(process_time_ms)

        # Keep rolling window of clean times
        if len(self._clean_times) > 1000:
            self._clean_times = self._clean_times[-500:]

    def record_herb_cleaned(self, clean_time_ms: float) -> None:
        """Record a herb being cleaned (alias for consistency).

        Args:
            clean_time_ms: Time to clean in milliseconds
        """
        self.record_item_processed(clean_time_ms)

    def _calculate_derived_stats(self) -> None:
        """Calculate derived statistics."""
        duration_hours = self.get_session_duration() / 3600

        if duration_hours > 0:
            self._stats.herbs_per_hour = self._stats.herbs_cleaned / duration_hours

        if self._clean_times:
            self._stats.avg_clean_time_ms = sum(self._clean_times) / len(self._clean_times)

        self._stats.total_active_time = self.get_active_time()

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

    def log_stats(self) -> None:
        """Log current statistics."""
        self._last_log_time = self._stats.start_time if self._stats.start_time else 0
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
