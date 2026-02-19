"""Rich terminal display for anti-detection status."""

import logging
import threading
import time
from typing import TYPE_CHECKING, Optional

try:
    from rich.console import Console
    from rich.live import Live
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    from rich.layout import Layout
    from rich.progress import BarColumn, Progress, TextColumn
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

if TYPE_CHECKING:
    from core.status_aggregator import StatusAggregator
    from core.events import EventEmitter, AntiDetectionEvent


def format_time_short(seconds: float) -> str:
    """Format seconds as M:SS or H:MM:SS."""
    if seconds < 0:
        return "0:00"

    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)

    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def format_percent(value: float) -> str:
    """Format a 0-1 value as percentage."""
    return f"{value * 100:.0f}%"


class StatusDisplay:
    """Rich terminal display for real-time anti-detection status."""

    def __init__(
        self,
        aggregator: "StatusAggregator",
        events: Optional["EventEmitter"] = None,
        refresh_rate: float = 4.0,
    ):
        """Initialize status display.

        Args:
            aggregator: Status aggregator for collecting module statuses
            events: Event emitter for recent events
            refresh_rate: Display refresh rate in Hz
        """
        self._logger = logging.getLogger(__name__)
        self._aggregator = aggregator
        self._events = events
        self._refresh_rate = refresh_rate

        self._console: Optional["Console"] = None
        self._live: Optional["Live"] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None

        # Track last drift target from events
        self._last_drift_target = ""
        self._current_event_text = ""
        self._current_event_remaining = 0.0

        # Subscribe to events if available
        if events:
            events.subscribe(self._on_event)

    def _on_event(self, event: "AntiDetectionEvent") -> None:
        """Handle incoming events.

        Args:
            event: The event that occurred
        """
        from core.events import EventType

        if event.event_type == EventType.DRIFT:
            self._last_drift_target = event.data.get("target", "")
        elif event.event_type == EventType.BREAK_START:
            break_type = event.data.get("break_type", "micro")
            duration = event.data.get("duration", 0)
            self._current_event_text = f"{break_type.upper()} BREAK"
            self._current_event_remaining = duration
        elif event.event_type == EventType.BREAK_END:
            self._current_event_text = ""
            self._current_event_remaining = 0

    def is_available(self) -> bool:
        """Check if Rich is available.

        Returns:
            True if Rich library is installed
        """
        return RICH_AVAILABLE

    def start(self) -> bool:
        """Start the status display.

        Returns:
            True if started successfully
        """
        if not RICH_AVAILABLE:
            self._logger.warning("Rich library not available, status UI disabled")
            return False

        if self._running:
            return True

        self._console = Console()
        self._running = True
        self._thread = threading.Thread(target=self._run_display, daemon=True)
        self._thread.start()

        return True

    def stop(self) -> None:
        """Stop the status display."""
        self._running = False
        if self._live:
            try:
                self._live.stop()
            except Exception:
                pass
        if self._thread:
            self._thread.join(timeout=1.0)

    def _run_display(self) -> None:
        """Run the display loop in a background thread."""
        if not self._console:
            return

        try:
            with Live(
                self._render(),
                console=self._console,
                refresh_per_second=self._refresh_rate,
                screen=False,
            ) as live:
                self._live = live
                while self._running:
                    try:
                        live.update(self._render())
                    except Exception as e:
                        self._logger.debug("Display render error: %s", e)
                    time.sleep(1.0 / self._refresh_rate)
        except Exception as e:
            self._logger.error("Status display error: %s", e)
            self._running = False

    def _render(self) -> Panel:
        """Render the complete status display.

        Returns:
            Rich Panel containing the status display
        """
        snapshot = self._aggregator.get_snapshot()

        # Create the main layout table
        main_table = Table.grid(padding=(0, 1))
        main_table.add_column(ratio=1)

        # Header row
        header = self._render_header(snapshot)
        main_table.add_row(header)

        # Status row
        status = self._render_status_bar(snapshot)
        main_table.add_row(status)

        # Main content (2x2 grid of panels)
        content = self._render_content_grid(snapshot)
        main_table.add_row(content)

        # Current event row
        event_panel = self._render_current_event(snapshot)
        main_table.add_row(event_panel)

        # Recent events row
        events_panel = self._render_recent_events()
        main_table.add_row(events_panel)

        return Panel(
            main_table,
            title="[bold cyan]OSRS Herb Bot - Anti-Detection Status[/]",
            border_style="cyan",
        )

    def _render_header(self, snapshot) -> Table:
        """Render the header row."""
        table = Table.grid(expand=True)
        table.add_column(justify="left", ratio=1)
        table.add_column(justify="right", ratio=1)

        session_time = format_time_short(snapshot.session.duration_seconds)

        table.add_row(
            f"[bold]Session:[/] {session_time}",
            f"[bold]State:[/] [yellow]{snapshot.session.current_state.upper()}[/]",
        )

        return table

    def _render_status_bar(self, snapshot) -> Table:
        """Render the status bar with herbs count."""
        table = Table.grid(expand=True)
        table.add_column(justify="center")

        herbs = snapshot.session.herbs_cleaned
        rate = snapshot.session.herbs_per_hour

        table.add_row(
            f"[green bold]Herbs: {herbs:,}[/] @ [cyan]{rate:,.0f}/hr[/]"
        )

        return table

    def _render_content_grid(self, snapshot) -> Table:
        """Render the main 2x2 content grid."""
        grid = Table.grid(expand=True, padding=(0, 1))
        grid.add_column(ratio=1)
        grid.add_column(ratio=1)

        # Row 1: Fatigue | Breaks
        fatigue_panel = self._render_fatigue_panel(snapshot)
        breaks_panel = self._render_breaks_panel(snapshot)
        grid.add_row(fatigue_panel, breaks_panel)

        # Row 2: Timing | Attention
        timing_panel = self._render_timing_panel(snapshot)
        attention_panel = self._render_attention_panel(snapshot)
        grid.add_row(timing_panel, attention_panel)

        # Row 3: Skill Check
        skill_panel = self._render_skill_panel(snapshot)
        grid.add_row(skill_panel, "")

        return grid

    def _render_fatigue_panel(self, snapshot) -> Panel:
        """Render fatigue status panel."""
        fatigue = snapshot.fatigue
        level = fatigue.level

        # Create progress bar for fatigue level
        filled = int(level * 8)
        empty = 8 - filled
        bar = "[green]" + "█" * filled + "[/][dim]░[/]" * empty

        table = Table.grid(padding=(0, 1))
        table.add_column()
        table.add_column()

        table.add_row("Level:", f"{bar} {format_percent(level)}")
        table.add_row("Slowdown:", f"[yellow]{fatigue.slowdown_multiplier:.2f}x[/]")

        return Panel(table, title="[bold]FATIGUE[/]", border_style="yellow")

    def _render_breaks_panel(self, snapshot) -> Panel:
        """Render breaks status panel."""
        breaks = snapshot.breaks

        time_until = format_time_short(breaks.time_until_next)
        total_time = format_time_short(breaks.total_break_time)

        table = Table.grid(padding=(0, 1))
        table.add_column()
        table.add_column()

        table.add_row("Next:", f"[cyan]{breaks.next_break_type}[/] in {time_until}")
        table.add_row(
            "Count:",
            f"Micro: [green]{breaks.micro_count}[/] | Long: [blue]{breaks.long_count}[/]"
        )
        table.add_row("Total:", total_time)

        return Panel(table, title="[bold]BREAKS[/]", border_style="blue")

    def _render_timing_panel(self, snapshot) -> Panel:
        """Render timing status panel."""
        timing = snapshot.timing

        table = Table.grid(padding=(0, 1))
        table.add_column()
        table.add_column()

        table.add_row("Last:", f"[cyan]{timing.last_delay_ms:.0f}ms[/]")
        table.add_row("Avg:", f"{timing.avg_delay_ms:.0f}ms")
        table.add_row("Fatigue mult:", f"{timing.fatigue_multiplier:.2f}x")

        return Panel(table, title="[bold]TIMING[/]", border_style="magenta")

    def _render_attention_panel(self, snapshot) -> Panel:
        """Render attention drift status panel."""
        attention = snapshot.attention

        # Show fatigue bonus
        fatigue_bonus = attention.effective_chance - attention.drift_chance
        bonus_text = f" [dim](+{fatigue_bonus*100:.1f}%)[/]" if fatigue_bonus > 0 else ""

        table = Table.grid(padding=(0, 1))
        table.add_column()
        table.add_column()

        table.add_row("Drifts:", f"[green]{attention.drift_count}[/]")
        if self._last_drift_target:
            table.add_row("Last:", f"[cyan]{self._last_drift_target}[/]")
        table.add_row(
            "Chance:",
            f"{attention.effective_chance*100:.1f}%{bonus_text}"
        )

        return Panel(table, title="[bold]ATTENTION[/]", border_style="green")

    def _render_skill_panel(self, snapshot) -> Panel:
        """Render skill check status panel."""
        skill = snapshot.skill_check

        time_until = format_time_short(skill.time_until_next)
        status = "[green]Enabled[/]" if skill.enabled else "[red]Disabled[/]"

        table = Table.grid(padding=(0, 1))
        table.add_column()
        table.add_column()

        table.add_row("Checks:", f"[cyan]{skill.check_count}[/]")
        table.add_row("Next:", time_until)
        table.add_row("Status:", status)

        return Panel(table, title="[bold]SKILL CHECK[/]", border_style="cyan")

    def _render_current_event(self, snapshot) -> Panel:
        """Render current ongoing event (e.g., break in progress)."""
        if self._events:
            current = self._events.get_current_event()
            if current:
                from core.events import EventType

                if current.event_type == EventType.BREAK_START:
                    break_type = current.data.get("break_type", "micro")
                    duration = current.data.get("duration", 0)
                    elapsed = current.age_seconds
                    remaining = max(0, duration - elapsed)

                    # Progress bar
                    progress = elapsed / duration if duration > 0 else 1.0
                    filled = int(progress * 20)
                    bar = "█" * filled + "░" * (20 - filled)

                    return Panel(
                        f"[yellow bold]► {break_type.upper()} BREAK[/] "
                        f"[{bar}] "
                        f"[cyan]{remaining:.1f}s remaining[/]",
                        title="[bold]CURRENT EVENT[/]",
                        border_style="yellow",
                    )

        return Panel(
            "[dim]No active event[/]",
            title="[bold]CURRENT EVENT[/]",
            border_style="dim",
        )

    def _render_recent_events(self) -> Panel:
        """Render recent events list."""
        if not self._events:
            return Panel("[dim]No events[/]", title="[bold]Recent Events[/]")

        events = self._events.get_recent(5)
        if not events:
            return Panel("[dim]No events yet[/]", title="[bold]Recent Events[/]")

        lines = []
        session_start = time.time()
        if self._aggregator._session:
            session_start = time.time() - self._aggregator._session.get_session_duration()

        for event in events:
            # Format timestamp relative to session start
            event_time = event.timestamp - session_start
            time_str = format_time_short(event_time)

            # Format event description
            from core.events import EventType

            if event.event_type == EventType.DRIFT:
                target = event.data.get("target", "unknown")
                duration = event.data.get("duration", 0)
                desc = f"Attention drift → [cyan]{target}[/] ({duration:.1f}s)"
            elif event.event_type == EventType.BREAK_END:
                break_type = event.data.get("break_type", "micro")
                duration = event.data.get("duration", 0)
                desc = f"[blue]{break_type.capitalize()} break[/] completed ({duration:.1f}s)"
            elif event.event_type == EventType.BREAK_START:
                break_type = event.data.get("break_type", "micro")
                desc = f"[yellow]{break_type.capitalize()} break[/] started"
            elif event.event_type == EventType.SKILL_CHECK:
                hover = event.data.get("hover_duration", 0)
                desc = f"[green]Skill check[/] performed ({hover:.1f}s hover)"
            elif event.event_type == EventType.ATTENTION_LAPSE:
                duration = event.data.get("duration", 0)
                desc = f"[dim]Attention lapse[/] ({duration:.1f}s)"
            else:
                desc = f"{event.event_type.value}"

            lines.append(f"[dim]{time_str}[/]  {desc}")

        return Panel(
            "\n".join(lines),
            title="[bold]Recent Events[/]",
            border_style="dim",
        )


def check_rich_available() -> bool:
    """Check if Rich library is available.

    Returns:
        True if Rich is installed
    """
    return RICH_AVAILABLE
