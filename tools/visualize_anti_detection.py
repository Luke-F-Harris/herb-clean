"""Anti-Detection Mechanics Visualization.

Pre-computes a 90-minute simulated session with all anti-detection mechanics active:
- TimingRandomizer: Gamma-distributed delays
- FatigueSimulator: Gradual performance degradation
- BreakScheduler: Micro and long breaks
- AttentionDrift: Random attention movements
- SkillChecker: Periodic skill inspection

Uses time compression to make long waits watchable:
- Short delays (<2s): Normal speed
- Medium delays (2-30s): 15x compression
- Long delays (>30s): 60x compression (5-min break -> 5 seconds)

OPTIMIZED VERSION:
- Binary search for current event lookup
- Pre-computed histogram data
- Cached timeline surface
- Only stores notable events (not 16k actions)
- Incremental counter updates
"""

import argparse
import bisect
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

import numpy as np
import pygame
import yaml


# =============================================================================
# Configuration Loading
# =============================================================================


class SimpleConfigManager:
    """Minimal config manager that loads YAML without complex dependencies."""

    DEFAULT_CONFIG_PATH = Path(__file__).parent.parent / "config" / "default_config.yaml"

    def __init__(self, config_path: str | Path | None = None):
        self.config_path = Path(config_path) if config_path else self.DEFAULT_CONFIG_PATH
        self._config: dict = {}
        if self.config_path.exists():
            with open(self.config_path, "r") as f:
                self._config = yaml.safe_load(f) or {}

    def get(self, key: str, default=None):
        keys = key.split(".")
        value = self._config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value


# =============================================================================
# Data Classes
# =============================================================================


class EventType(Enum):
    """Types of simulated events."""
    BREAK_MICRO = "break_micro"
    BREAK_LONG = "break_long"
    DRIFT = "drift"
    SKILL_CHECK = "skill_check"


class CompressionTier(Enum):
    """Time compression tiers."""
    NONE = 0       # < 2s: normal speed
    MEDIUM = 1     # 2-30s: 15x compression
    HEAVY = 2      # > 30s: 60x compression


@dataclass
class SimulatedEvent:
    """A single notable event in the simulation timeline."""
    event_type: EventType
    start_time: float
    end_time: float
    data: dict = field(default_factory=dict)
    compression_tier: CompressionTier = CompressionTier.NONE


@dataclass
class DriftRegion:
    """Screen region for drift target."""
    name: str
    x: int
    y: int
    width: int
    height: int
    color: tuple[int, int, int]


# =============================================================================
# Simulation Engine (Optimized)
# =============================================================================


class AntiDetectionSimulator:
    """Pre-computes a simulated session with all anti-detection mechanics.

    OPTIMIZED: Only stores notable events (breaks, drifts, skill checks).
    Actions are aggregated into statistics, not stored individually.
    """

    DRIFT_REGIONS = {
        "minimap": DriftRegion("minimap", 850, 30, 150, 150, (100, 200, 100)),
        "chat": DriftRegion("chat", 20, 500, 480, 150, (100, 150, 200)),
        "skills_tab": DriftRegion("skills_tab", 850, 200, 180, 200, (200, 150, 255)),
        "random": DriftRegion("random", 400, 300, 200, 200, (150, 150, 150)),
    }

    def __init__(self, config: SimpleConfigManager, session_duration_minutes: float = 90):
        self.config = config
        self.session_duration = session_duration_minutes * 60
        self._rng = np.random.default_rng()
        self._load_config()

        # Notable events only (not actions)
        self.events: list[SimulatedEvent] = []
        self.event_start_times: list[float] = []  # For binary search

        # Pre-computed statistics
        self.delay_histogram: np.ndarray = None  # Pre-computed histogram counts
        self.histogram_bins = np.linspace(0, 800, 25)
        self.fatigue_samples: list[tuple[float, float]] = []

        # Summary counts (computed incrementally during playback)
        self.total_actions = 0
        self.total_drifts = 0
        self.total_skill_checks = 0
        self.micro_break_count = 0
        self.long_break_count = 0

        # Drift target distribution
        self.drift_target_counts: dict[str, int] = {}

        # Action timing samples for histogram (sampled, not all)
        self.delay_samples: np.ndarray = None

    def _load_config(self):
        """Load configuration values from config manager."""
        timing = self.config.get("timing", {}) or {}
        self.timing_mean = timing.get("click_herb_mean", 250) / 1000
        self.timing_std = timing.get("click_herb_std", 75) / 1000

        fatigue = self.config.get("fatigue", {}) or {}
        self.fatigue_onset_minutes = fatigue.get("onset_minutes", 30)
        self.fatigue_max_slowdown = fatigue.get("max_slowdown_percent", 50) / 100

        breaks = self.config.get("breaks", {}) or {}
        micro = breaks.get("micro", {}) or {}
        long_cfg = breaks.get("long", {}) or {}
        self.micro_interval = tuple(micro.get("interval", [480, 900]))
        self.micro_duration = tuple(micro.get("duration", [2, 10]))
        self.long_interval = tuple(long_cfg.get("interval", [2700, 5400]))
        self.long_duration = tuple(long_cfg.get("duration", [60, 300]))

        attention = self.config.get("attention", {}) or {}
        self.drift_chance = attention.get("drift_chance", 0.03)
        self.drift_targets = attention.get("drift_targets", [
            {"name": "minimap", "weight": 3},
            {"name": "chat", "weight": 2},
            {"name": "random", "weight": 1},
        ])

        skill_check = self.config.get("skill_check", {}) or {}
        self.skill_check_enabled = skill_check.get("enabled", True)
        self.skill_check_interval = tuple(skill_check.get("cooldown_interval", [600, 900]))
        self.skill_check_hover = tuple(skill_check.get("hover_duration", [3.0, 8.0]))

    def _get_compression_tier(self, duration: float) -> CompressionTier:
        if duration < 2.0:
            return CompressionTier.NONE
        elif duration < 30.0:
            return CompressionTier.MEDIUM
        else:
            return CompressionTier.HEAVY

    def _gamma_delay(self, mean: float, std: float) -> float:
        variance = std * std
        k = (mean * mean) / variance
        theta = variance / mean
        return self._rng.gamma(k, theta)

    def _compute_fatigue(self, session_minutes: float) -> float:
        if session_minutes < self.fatigue_onset_minutes:
            return 0.0
        time_past_onset = session_minutes - self.fatigue_onset_minutes
        fatigue = 1 - np.exp(-time_past_onset / 60)
        return min(1.0, max(0.0, fatigue))

    def _select_drift_target(self) -> str:
        total_weight = sum(t["weight"] for t in self.drift_targets)
        roll = self._rng.random() * total_weight
        cumulative = 0
        for target in self.drift_targets:
            cumulative += target["weight"]
            if roll <= cumulative:
                return target["name"]
        return "random"

    def simulate(self):
        """Run the full simulation."""
        print(f"Simulating {self.session_duration / 60:.1f} minute session...")

        self.events = []
        self.event_start_times = []
        self.fatigue_samples = []
        self.drift_target_counts = {}

        current_time = 0.0
        action_count = 0
        delay_samples_list = []

        next_micro_break = current_time + self._rng.uniform(*self.micro_interval)
        next_long_break = current_time + self._rng.uniform(*self.long_interval)
        next_skill_check = current_time + self._rng.uniform(*self.skill_check_interval)

        while current_time < self.session_duration:
            session_minutes = current_time / 60

            # Sample fatigue every 30 seconds
            if len(self.fatigue_samples) == 0 or current_time - self.fatigue_samples[-1][0] >= 30:
                fatigue = self._compute_fatigue(session_minutes)
                self.fatigue_samples.append((current_time, fatigue))

            # Long break
            if current_time >= next_long_break:
                break_duration = self._rng.uniform(*self.long_duration)
                event = SimulatedEvent(
                    event_type=EventType.BREAK_LONG,
                    start_time=current_time,
                    end_time=current_time + break_duration,
                    data={"duration": break_duration},
                    compression_tier=self._get_compression_tier(break_duration),
                )
                self.events.append(event)
                self.event_start_times.append(current_time)
                self.long_break_count += 1
                current_time += break_duration
                next_long_break = current_time + self._rng.uniform(*self.long_interval)
                next_micro_break = current_time + self._rng.uniform(*self.micro_interval)
                continue

            # Micro break
            if current_time >= next_micro_break:
                break_duration = self._rng.uniform(*self.micro_duration)
                event = SimulatedEvent(
                    event_type=EventType.BREAK_MICRO,
                    start_time=current_time,
                    end_time=current_time + break_duration,
                    data={"duration": break_duration},
                    compression_tier=self._get_compression_tier(break_duration),
                )
                self.events.append(event)
                self.event_start_times.append(current_time)
                self.micro_break_count += 1
                current_time += break_duration
                next_micro_break = current_time + self._rng.uniform(*self.micro_interval)
                continue

            # Skill check
            if self.skill_check_enabled and current_time >= next_skill_check:
                hover_duration = self._rng.uniform(*self.skill_check_hover)
                total_duration = 1.0 + hover_duration + 0.5
                event = SimulatedEvent(
                    event_type=EventType.SKILL_CHECK,
                    start_time=current_time,
                    end_time=current_time + total_duration,
                    data={"hover_duration": hover_duration, "total_duration": total_duration},
                    compression_tier=self._get_compression_tier(total_duration),
                )
                self.events.append(event)
                self.event_start_times.append(current_time)
                self.total_skill_checks += 1
                current_time += total_duration
                next_skill_check = current_time + self._rng.uniform(*self.skill_check_interval)
                continue

            # Attention drift
            fatigue = self._compute_fatigue(session_minutes)
            drift_chance = self.drift_chance + (fatigue * 0.03)
            if self._rng.random() < drift_chance:
                target = self._select_drift_target()
                drift_duration = self._rng.uniform(0.3, 2.0)
                event = SimulatedEvent(
                    event_type=EventType.DRIFT,
                    start_time=current_time,
                    end_time=current_time + drift_duration,
                    data={"target": target, "duration": drift_duration},
                    compression_tier=CompressionTier.NONE,
                )
                self.events.append(event)
                self.event_start_times.append(current_time)
                self.total_drifts += 1
                self.drift_target_counts[target] = self.drift_target_counts.get(target, 0) + 1
                current_time += drift_duration
                continue

            # Regular action (NOT stored as event, just statistics)
            slowdown = 1.0 + (fatigue * self.fatigue_max_slowdown)
            delay = self._gamma_delay(self.timing_mean, self.timing_std) * slowdown
            delay_samples_list.append(delay * 1000)
            current_time += delay
            action_count += 1

        # Final fatigue sample
        self.fatigue_samples.append((current_time, self._compute_fatigue(current_time / 60)))

        self.total_actions = action_count

        # Pre-compute histogram from all delay samples
        self.delay_samples = np.array(delay_samples_list)
        self.delay_histogram, _ = np.histogram(self.delay_samples, bins=self.histogram_bins)

        print(f"Simulation complete:")
        print(f"  - {action_count} actions (histogram pre-computed)")
        print(f"  - {len(self.events)} notable events stored")
        print(f"  - {self.micro_break_count} micro + {self.long_break_count} long breaks")
        print(f"  - {self.total_drifts} attention drifts")
        print(f"  - {self.total_skill_checks} skill checks")


# =============================================================================
# Visualization (Optimized)
# =============================================================================


class AntiDetectionVisualizer:
    """Pygame visualization for anti-detection mechanics.

    OPTIMIZED:
    - Binary search for current event (O(log n) instead of O(n))
    - Pre-rendered timeline surface
    - Cached panel data
    - No per-frame list comprehensions
    """

    WINDOW_WIDTH = 1400
    WINDOW_HEIGHT = 900
    CANVAS_WIDTH = 1050
    CANVAS_HEIGHT = 700
    PANEL_WIDTH = 350
    PANEL_HEIGHT = 140
    STATUS_HEIGHT = 50
    TIMELINE_HEIGHT = 50

    COLOR_BG = (25, 25, 30)
    COLOR_CANVAS_BG = (35, 35, 45)
    COLOR_PANEL_BG = (40, 40, 50)
    COLOR_TEXT = (220, 220, 220)
    COLOR_TEXT_DIM = (150, 150, 150)
    COLOR_ACCENT = (100, 180, 255)
    COLOR_MICRO_BREAK = (100, 150, 255)
    COLOR_LONG_BREAK = (255, 100, 100)
    COLOR_DRIFT = (255, 200, 100)
    COLOR_SKILL_CHECK = (200, 150, 255)
    COLOR_FATIGUE = (255, 150, 100)

    def __init__(self, simulator: AntiDetectionSimulator):
        self.sim = simulator

        self.screen: Optional[pygame.Surface] = None
        self.clock: Optional[pygame.time.Clock] = None
        self.font: Optional[pygame.font.Font] = None
        self.font_large: Optional[pygame.font.Font] = None
        self.font_small: Optional[pygame.font.Font] = None

        self.sim_time = 0.0
        self.paused = False
        self.speed = 1.0
        self.skip_requested = False

        # Cached state
        self._current_event: Optional[SimulatedEvent] = None
        self._current_event_index = -1
        self._last_lookup_time = -1.0

        # Pre-rendered surfaces
        self._timeline_surface: Optional[pygame.Surface] = None
        self._histogram_surface: Optional[pygame.Surface] = None

        # Cached counters (updated incrementally)
        self._cached_drift_count = 0
        self._cached_skill_check_count = 0
        self._cached_break_count = 0
        self._last_counted_index = -1
        self._cached_drift_targets: dict[str, int] = {}
        self._cached_last_drift_target = "none"

        self.drift_regions = simulator.DRIFT_REGIONS

    def init_pygame(self):
        """Initialize pygame display."""
        pygame.init()
        pygame.display.set_caption("Anti-Detection Mechanics Visualization")
        self.screen = pygame.display.set_mode((self.WINDOW_WIDTH, self.WINDOW_HEIGHT))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("monospace", 16)
        self.font_large = pygame.font.SysFont("monospace", 20, bold=True)
        self.font_small = pygame.font.SysFont("monospace", 12)

        # Pre-render static surfaces
        self._render_timeline_surface()
        self._render_histogram_surface()

    def _render_timeline_surface(self):
        """Pre-render the timeline with all events."""
        bar_w = self.WINDOW_WIDTH - 100
        bar_h = 20

        self._timeline_surface = pygame.Surface((bar_w, bar_h), pygame.SRCALPHA)
        self._timeline_surface.fill((50, 50, 60))

        max_time = self.sim.session_duration

        for event in self.sim.events:
            event_x = int((event.start_time / max_time) * bar_w)
            event_w = max(1, int((event.end_time - event.start_time) / max_time * bar_w))

            if event.event_type == EventType.BREAK_MICRO:
                color = self.COLOR_MICRO_BREAK
            elif event.event_type == EventType.BREAK_LONG:
                color = self.COLOR_LONG_BREAK
            elif event.event_type == EventType.DRIFT:
                color = self.COLOR_DRIFT
            elif event.event_type == EventType.SKILL_CHECK:
                color = self.COLOR_SKILL_CHECK
            else:
                continue

            pygame.draw.rect(self._timeline_surface, color, (event_x, 0, event_w, bar_h))

    def _render_histogram_surface(self):
        """Pre-render the histogram (final state)."""
        width = self.PANEL_WIDTH
        height = self.PANEL_HEIGHT

        self._histogram_surface = pygame.Surface((width, height), pygame.SRCALPHA)

        counts = self.sim.delay_histogram
        max_count = max(counts.max(), 1)

        bar_width = width // len(counts)
        for i, count in enumerate(counts):
            bar_height = int((count / max_count) * (height - 40))
            bar_x = i * bar_width
            bar_y = height - 10 - bar_height

            if self.sim.histogram_bins[i] < 200:
                color = (100, 255, 150)
            elif self.sim.histogram_bins[i] < 400:
                color = (255, 255, 100)
            else:
                color = (255, 150, 100)

            pygame.draw.rect(self._histogram_surface, color, (bar_x, bar_y, bar_width - 2, bar_height))

    def _get_current_event(self) -> Optional[SimulatedEvent]:
        """Get current event using binary search (O(log n))."""
        if self.sim_time == self._last_lookup_time:
            return self._current_event

        self._last_lookup_time = self.sim_time

        # Binary search for event containing current time
        idx = bisect.bisect_right(self.sim.event_start_times, self.sim_time) - 1

        if idx >= 0 and idx < len(self.sim.events):
            event = self.sim.events[idx]
            if event.start_time <= self.sim_time < event.end_time:
                self._current_event = event
                self._current_event_index = idx
                return event

        self._current_event = None
        self._current_event_index = -1
        return None

    def _update_cached_counters(self):
        """Update cached counters incrementally based on current time."""
        # Find how many events have passed
        idx = bisect.bisect_right(self.sim.event_start_times, self.sim_time) - 1

        if idx <= self._last_counted_index:
            # Time went backwards (restart), reset counters
            if self.sim_time < 1.0:
                self._cached_drift_count = 0
                self._cached_skill_check_count = 0
                self._cached_break_count = 0
                self._last_counted_index = -1
                self._cached_drift_targets = {}
                self._cached_last_drift_target = "none"
            return

        # Count new events since last update
        for i in range(self._last_counted_index + 1, idx + 1):
            if i >= len(self.sim.events):
                break
            event = self.sim.events[i]
            if event.start_time > self.sim_time:
                break

            if event.event_type == EventType.DRIFT:
                self._cached_drift_count += 1
                target = event.data.get("target", "random")
                self._cached_drift_targets[target] = self._cached_drift_targets.get(target, 0) + 1
                self._cached_last_drift_target = target
            elif event.event_type == EventType.SKILL_CHECK:
                self._cached_skill_check_count += 1
            elif event.event_type in (EventType.BREAK_MICRO, EventType.BREAK_LONG):
                self._cached_break_count += 1

        self._last_counted_index = idx

    def _format_time(self, seconds: float) -> str:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes:02d}:{secs:02d}"

    def _draw_panel_background(self, x: int, y: int, width: int, height: int, title: str):
        pygame.draw.rect(self.screen, self.COLOR_PANEL_BG, (x, y, width, height))
        pygame.draw.rect(self.screen, self.COLOR_ACCENT, (x, y, width, height), 1)
        title_surface = self.font.render(title, True, self.COLOR_ACCENT)
        self.screen.blit(title_surface, (x + 10, y + 5))

    def _draw_histogram(self, x: int, y: int, width: int, height: int, current_delay: float):
        """Draw histogram using pre-rendered surface."""
        self.screen.blit(self._histogram_surface, (x, y))

        # Draw current delay marker
        if 0 < current_delay < 800:
            marker_x = x + int((current_delay / 800) * width)
            pygame.draw.line(self.screen, (255, 50, 50), (marker_x, y + 30), (marker_x, y + height - 10), 2)

        # Labels
        text = f"Current: {current_delay:.0f}ms | Total: {self.sim.total_actions}"
        self.screen.blit(self.font_small.render(text, True, self.COLOR_TEXT), (x + 10, y + height - 25))

    def _draw_fatigue_graph(self, x: int, y: int, width: int, height: int):
        """Draw fatigue graph using pre-computed samples."""
        # Find samples up to current time using binary search
        sample_times = [s[0] for s in self.sim.fatigue_samples]
        idx = bisect.bisect_right(sample_times, self.sim_time)
        samples = self.sim.fatigue_samples[:idx]

        if len(samples) < 2:
            current_fatigue = 0
        else:
            graph_x = x + 40
            graph_y = y + 25
            graph_w = width - 50
            graph_h = height - 50

            pygame.draw.line(self.screen, self.COLOR_TEXT_DIM, (graph_x, graph_y), (graph_x, graph_y + graph_h), 1)
            pygame.draw.line(self.screen, self.COLOR_TEXT_DIM, (graph_x, graph_y + graph_h), (graph_x + graph_w, graph_y + graph_h), 1)

            for level in [0, 0.5, 1.0]:
                ly = graph_y + graph_h - int(level * graph_h)
                self.screen.blit(self.font_small.render(f"{level:.1f}", True, self.COLOR_TEXT_DIM), (x + 5, ly - 6))

            max_time = self.sim.session_duration
            points = []
            for t, f in samples:
                px = graph_x + int((t / max_time) * graph_w)
                py = graph_y + graph_h - int(f * graph_h)
                points.append((px, py))

            if len(points) >= 2:
                pygame.draw.lines(self.screen, self.COLOR_FATIGUE, False, points, 2)

            current_fatigue = samples[-1][1]

        slowdown = 1.0 + (current_fatigue * self.sim.fatigue_max_slowdown)
        text = f"Level: {current_fatigue:.2f} | Mult: {slowdown:.2f}x"
        self.screen.blit(self.font_small.render(text, True, self.COLOR_TEXT), (x + 10, y + height - 20))

    def _draw_break_timeline(self, x: int, y: int, width: int, height: int):
        """Draw break scheduler timeline."""
        bar_y = y + 50
        bar_h = 20
        pygame.draw.rect(self.screen, (50, 50, 60), (x + 10, bar_y, width - 20, bar_h))

        max_time = self.sim.session_duration

        # Only draw break events (small list)
        for event in self.sim.events:
            if event.event_type not in (EventType.BREAK_MICRO, EventType.BREAK_LONG):
                continue

            marker_x = x + 10 + int((event.start_time / max_time) * (width - 20))
            marker_w = max(2, int((event.end_time - event.start_time) / max_time * (width - 20)))

            if event.event_type == EventType.BREAK_MICRO:
                color = self.COLOR_MICRO_BREAK
            else:
                color = self.COLOR_LONG_BREAK

            if event.start_time > self.sim_time:
                color = tuple(c // 3 for c in color)

            pygame.draw.rect(self.screen, color, (marker_x, bar_y, marker_w, bar_h))

        # Current position
        current_x = x + 10 + int((self.sim_time / max_time) * (width - 20))
        pygame.draw.line(self.screen, (255, 255, 255), (current_x, bar_y - 5), (current_x, bar_y + bar_h + 5), 2)

        # Find next break using binary search
        idx = bisect.bisect_right(self.sim.event_start_times, self.sim_time)
        next_break = None
        for i in range(idx, len(self.sim.events)):
            if self.sim.events[i].event_type in (EventType.BREAK_MICRO, EventType.BREAK_LONG):
                next_break = self.sim.events[i]
                break

        if next_break:
            time_until = next_break.start_time - self.sim_time
            break_type = "micro" if next_break.event_type == EventType.BREAK_MICRO else "long"
            text = f"Next: {break_type} in {self._format_time(time_until)}"
        else:
            text = "No more breaks"

        self.screen.blit(self.font_small.render(text, True, self.COLOR_TEXT), (x + 10, y + height - 25))

        # Legend
        pygame.draw.rect(self.screen, self.COLOR_MICRO_BREAK, (x + 10, y + 25, 15, 15))
        self.screen.blit(self.font_small.render("Micro", True, self.COLOR_TEXT_DIM), (x + 30, y + 25))
        pygame.draw.rect(self.screen, self.COLOR_LONG_BREAK, (x + 90, y + 25, 15, 15))
        self.screen.blit(self.font_small.render("Long", True, self.COLOR_TEXT_DIM), (x + 110, y + 25))

    def _draw_attention_drift_panel(self, x: int, y: int, width: int, height: int):
        """Draw attention drift panel using cached counters."""
        self._update_cached_counters()

        text1 = f"Drifts: {self._cached_drift_count}"
        text2 = f"Last: {self._cached_last_drift_target}"
        self.screen.blit(self.font.render(text1, True, self.COLOR_TEXT), (x + 10, y + 30))
        self.screen.blit(self.font.render(text2, True, self.COLOR_DRIFT), (x + 10, y + 55))

        # Mini bar chart
        bar_y = y + 85
        bar_total_w = width - 20
        if self._cached_drift_count > 0:
            bar_x = x + 10
            for target, count in sorted(self._cached_drift_targets.items()):
                bar_w = int((count / self._cached_drift_count) * bar_total_w)
                color = self.drift_regions.get(target, DriftRegion("", 0, 0, 0, 0, (150, 150, 150))).color
                pygame.draw.rect(self.screen, color, (bar_x, bar_y, bar_w, 15))
                bar_x += bar_w

        # Labels
        label_y = y + 105
        for i, (target, count) in enumerate(sorted(self._cached_drift_targets.items())):
            if i >= 4:  # Max 4 labels
                break
            color = self.drift_regions.get(target, DriftRegion("", 0, 0, 0, 0, (150, 150, 150))).color
            pygame.draw.rect(self.screen, color, (x + 10 + i * 80, label_y, 10, 10))
            self.screen.blit(self.font_small.render(f"{target[:6]}", True, self.COLOR_TEXT_DIM), (x + 25 + i * 80, label_y))

    def _draw_skill_checker_panel(self, x: int, y: int, width: int, height: int):
        """Draw skill checker panel."""
        self._update_cached_counters()

        text1 = f"Checks: {self._cached_skill_check_count}"
        self.screen.blit(self.font.render(text1, True, self.COLOR_TEXT), (x + 10, y + 30))

        # Find next skill check
        idx = bisect.bisect_right(self.sim.event_start_times, self.sim_time)
        next_check = None
        for i in range(idx, len(self.sim.events)):
            if self.sim.events[i].event_type == EventType.SKILL_CHECK:
                next_check = self.sim.events[i]
                break

        if next_check:
            time_until = next_check.start_time - self.sim_time
            text2 = f"Next: {self._format_time(time_until)}"
            self.screen.blit(self.font.render(text2, True, self.COLOR_SKILL_CHECK), (x + 10, y + 55))
        else:
            self.screen.blit(self.font.render("No more checks", True, self.COLOR_TEXT_DIM), (x + 10, y + 55))

        # Active skill check progress
        current_event = self._get_current_event()
        if current_event and current_event.event_type == EventType.SKILL_CHECK:
            progress = (self.sim_time - current_event.start_time) / (current_event.end_time - current_event.start_time)
            bar_w = int(progress * (width - 20))
            pygame.draw.rect(self.screen, self.COLOR_SKILL_CHECK, (x + 10, y + 85, bar_w, 20))
            pygame.draw.rect(self.screen, self.COLOR_ACCENT, (x + 10, y + 85, width - 20, 20), 1)
            self.screen.blit(self.font_small.render("Checking skill...", True, self.COLOR_TEXT), (x + 10, y + 110))

    def _draw_main_canvas(self, x: int, y: int, width: int, height: int):
        """Draw main visualization canvas."""
        pygame.draw.rect(self.screen, self.COLOR_CANVAS_BG, (x, y, width, height))
        pygame.draw.rect(self.screen, self.COLOR_ACCENT, (x, y, width, height), 1)

        current_event = self._get_current_event()

        # Draw drift regions
        for name, region in self.drift_regions.items():
            rect = pygame.Rect(x + region.x, y + region.y, region.width, region.height)
            color = tuple(c // 4 for c in region.color)

            if current_event and current_event.event_type == EventType.DRIFT:
                if current_event.data.get("target") == name:
                    color = region.color

            pygame.draw.rect(self.screen, color, rect, 2)
            self.screen.blit(self.font_small.render(name, True, color), (rect.x + 5, rect.y + 5))

        # Cursor position
        cursor_x = x + width // 2
        cursor_y = y + height // 2

        if current_event:
            if current_event.event_type == EventType.DRIFT:
                target = current_event.data.get("target", "random")
                if target in self.drift_regions:
                    region = self.drift_regions[target]
                    cursor_x = x + region.x + region.width // 2
                    cursor_y = y + region.y + region.height // 2
            elif current_event.event_type == EventType.SKILL_CHECK:
                cursor_x = x + 900
                cursor_y = y + 250

        pygame.draw.circle(self.screen, (255, 100, 100), (cursor_x, cursor_y), 10)
        pygame.draw.circle(self.screen, (255, 255, 255), (cursor_x - 3, cursor_y - 3), 3)

        # Event overlay
        if current_event:
            overlay_text = ""
            overlay_color = self.COLOR_TEXT

            if current_event.event_type == EventType.BREAK_MICRO:
                overlay_text = f"MICRO BREAK ({current_event.data['duration']:.1f}s)"
                overlay_color = self.COLOR_MICRO_BREAK
            elif current_event.event_type == EventType.BREAK_LONG:
                overlay_text = f"LONG BREAK ({current_event.data['duration']:.1f}s)"
                overlay_color = self.COLOR_LONG_BREAK
            elif current_event.event_type == EventType.DRIFT:
                overlay_text = f"ATTENTION DRIFT: {current_event.data['target']}"
                overlay_color = self.COLOR_DRIFT
            elif current_event.event_type == EventType.SKILL_CHECK:
                overlay_text = "SKILL CHECK"
                overlay_color = self.COLOR_SKILL_CHECK

            if overlay_text:
                text_surface = self.font_large.render(overlay_text, True, overlay_color)
                text_rect = text_surface.get_rect(center=(x + width // 2, y + height // 2 - 50))
                bg_rect = text_rect.inflate(20, 10)
                pygame.draw.rect(self.screen, (0, 0, 0), bg_rect)
                pygame.draw.rect(self.screen, overlay_color, bg_rect, 2)
                self.screen.blit(text_surface, text_rect)

    def _draw_status_bar(self, x: int, y: int, width: int, height: int):
        """Draw status bar."""
        pygame.draw.rect(self.screen, self.COLOR_PANEL_BG, (x, y, width, height))

        time_text = f"Sim Time: {self._format_time(self.sim_time)} / {self._format_time(self.sim.session_duration)}"
        self.screen.blit(self.font.render(time_text, True, self.COLOR_TEXT), (10, y + 15))

        speed_text = f"Speed: {self.speed:.1f}x"
        self.screen.blit(self.font.render(speed_text, True, self.COLOR_ACCENT), (250, y + 15))

        current_event = self._get_current_event()
        if current_event:
            comp_text = ""
            comp_color = self.COLOR_TEXT_DIM
            if current_event.compression_tier == CompressionTier.MEDIUM:
                comp_text = "15x COMPRESSION"
                comp_color = (255, 200, 100)
            elif current_event.compression_tier == CompressionTier.HEAVY:
                comp_text = "60x COMPRESSION"
                comp_color = (255, 100, 100)

            if comp_text:
                self.screen.blit(self.font.render(comp_text, True, comp_color), (400, y + 15))

        if self.paused:
            pause_surface = self.font_large.render("PAUSED", True, (255, 255, 100))
            self.screen.blit(pause_surface, (600, y + 12))

        if current_event:
            action_text = f"Event: {current_event.event_type.value}"
            self.screen.blit(self.font.render(action_text, True, self.COLOR_TEXT_DIM), (750, y + 15))

    def _draw_timeline_scrubber(self, x: int, y: int, width: int, height: int):
        """Draw timeline using pre-rendered surface."""
        pygame.draw.rect(self.screen, self.COLOR_PANEL_BG, (x, y, width, height))

        bar_x = x + 50
        bar_y = y + 15
        bar_w = width - 100

        # Blit pre-rendered timeline
        self.screen.blit(self._timeline_surface, (bar_x, bar_y))

        # Current position marker
        max_time = self.sim.session_duration
        current_x = bar_x + int((self.sim_time / max_time) * bar_w)
        pygame.draw.line(self.screen, (255, 255, 255), (current_x, bar_y - 3), (current_x, bar_y + 23), 3)

        # Time labels
        self.screen.blit(self.font_small.render("0:00", True, self.COLOR_TEXT_DIM), (bar_x - 30, bar_y + 3))
        end_label = self._format_time(max_time)
        self.screen.blit(self.font_small.render(end_label, True, self.COLOR_TEXT_DIM), (bar_x + bar_w + 5, bar_y + 3))

        hint = "SPACE: Pause | S: Skip | +/-: Speed | R: Restart | ENTER: New Sim | Q: Quit"
        self.screen.blit(self.font_small.render(hint, True, self.COLOR_TEXT_DIM), (x + 10, y + 38))

    def _update_time(self, dt: float):
        """Update simulation time with compression."""
        if self.paused:
            return

        current_event = self._get_current_event()
        time_step = dt * self.speed

        if current_event:
            if current_event.compression_tier == CompressionTier.MEDIUM:
                time_step *= 15
            elif current_event.compression_tier == CompressionTier.HEAVY:
                time_step *= 60

            if self.skip_requested and current_event.compression_tier != CompressionTier.NONE:
                self.sim_time = current_event.end_time
                self.skip_requested = False
                return

        self.sim_time += time_step

        if self.sim_time >= self.sim.session_duration:
            self.sim_time = 0
            self._reset_caches()

    def _reset_caches(self):
        """Reset cached counters on restart."""
        self._cached_drift_count = 0
        self._cached_skill_check_count = 0
        self._cached_break_count = 0
        self._last_counted_index = -1
        self._cached_drift_targets = {}
        self._cached_last_drift_target = "none"
        self._last_lookup_time = -1.0

    def run(self) -> bool:
        """Run the visualization loop."""
        self.init_pygame()

        running = True
        run_again = False
        last_time = pygame.time.get_ticks() / 1000

        while running:
            current_time = pygame.time.get_ticks() / 1000
            dt = current_time - last_time
            last_time = current_time

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_q, pygame.K_ESCAPE):
                        running = False
                    elif event.key == pygame.K_RETURN:
                        running = False
                        run_again = True
                    elif event.key == pygame.K_SPACE:
                        self.paused = not self.paused
                    elif event.key == pygame.K_s:
                        self.skip_requested = True
                    elif event.key == pygame.K_r:
                        self.sim_time = 0
                        self._reset_caches()
                    elif event.key in (pygame.K_PLUS, pygame.K_EQUALS):
                        self.speed = min(5.0, self.speed + 0.5)
                    elif event.key == pygame.K_MINUS:
                        self.speed = max(0.25, self.speed - 0.5)
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    mx, my = event.pos
                    timeline_y = self.WINDOW_HEIGHT - self.TIMELINE_HEIGHT
                    if timeline_y <= my <= self.WINDOW_HEIGHT:
                        bar_x = 50
                        bar_w = self.WINDOW_WIDTH - 100
                        if bar_x <= mx <= bar_x + bar_w:
                            ratio = (mx - bar_x) / bar_w
                            self.sim_time = ratio * self.sim.session_duration
                            self._reset_caches()
                            # Rebuild counters up to new time
                            self._update_cached_counters()

            self._update_time(dt)
            self.screen.fill(self.COLOR_BG)

            self._draw_status_bar(0, 0, self.WINDOW_WIDTH, self.STATUS_HEIGHT)

            canvas_y = self.STATUS_HEIGHT
            self._draw_main_canvas(0, canvas_y, self.CANVAS_WIDTH, self.CANVAS_HEIGHT)

            panel_x = self.CANVAS_WIDTH
            panel_y = self.STATUS_HEIGHT

            self._draw_panel_background(panel_x, panel_y, self.PANEL_WIDTH, self.PANEL_HEIGHT, "TIMING RANDOMIZER")
            current_event = self._get_current_event()
            current_delay = 0
            if current_event and current_event.event_type == EventType.DRIFT:
                # Show approximate delay during drift
                current_delay = self.sim.timing_mean * 1000
            self._draw_histogram(panel_x, panel_y, self.PANEL_WIDTH, self.PANEL_HEIGHT, current_delay)

            panel_y += self.PANEL_HEIGHT
            self._draw_panel_background(panel_x, panel_y, self.PANEL_WIDTH, self.PANEL_HEIGHT, "FATIGUE SIMULATOR")
            self._draw_fatigue_graph(panel_x, panel_y, self.PANEL_WIDTH, self.PANEL_HEIGHT)

            panel_y += self.PANEL_HEIGHT
            self._draw_panel_background(panel_x, panel_y, self.PANEL_WIDTH, self.PANEL_HEIGHT, "BREAK SCHEDULER")
            self._draw_break_timeline(panel_x, panel_y, self.PANEL_WIDTH, self.PANEL_HEIGHT)

            panel_y += self.PANEL_HEIGHT
            self._draw_panel_background(panel_x, panel_y, self.PANEL_WIDTH, self.PANEL_HEIGHT, "ATTENTION DRIFT")
            self._draw_attention_drift_panel(panel_x, panel_y, self.PANEL_WIDTH, self.PANEL_HEIGHT)

            panel_y += self.PANEL_HEIGHT
            self._draw_panel_background(panel_x, panel_y, self.PANEL_WIDTH, self.PANEL_HEIGHT, "SKILL CHECKER")
            self._draw_skill_checker_panel(panel_x, panel_y, self.PANEL_WIDTH, self.PANEL_HEIGHT)

            timeline_y = self.WINDOW_HEIGHT - self.TIMELINE_HEIGHT
            self._draw_timeline_scrubber(0, timeline_y, self.WINDOW_WIDTH, self.TIMELINE_HEIGHT)

            pygame.display.flip()
            self.clock.tick(60)

        pygame.quit()
        return run_again


def main():
    parser = argparse.ArgumentParser(description="Visualize anti-detection mechanics")
    parser.add_argument("-c", "--config", type=str, default=None, help="Path to config file")
    parser.add_argument("--duration", type=float, default=90, help="Session duration in minutes (default: 90)")
    args = parser.parse_args()

    print("Anti-Detection Mechanics Visualization (Optimized)")
    print("=" * 50)

    config = SimpleConfigManager(args.config)
    run_count = 0

    while True:
        run_count += 1
        print(f"\n=== Simulation #{run_count} ===")

        simulator = AntiDetectionSimulator(config, session_duration_minutes=args.duration)
        simulator.simulate()

        visualizer = AntiDetectionVisualizer(simulator)

        print("\nControls:")
        print("  SPACE  - Pause/Resume")
        print("  S      - Skip current long delay")
        print("  +/-    - Adjust speed (0.25x - 5x)")
        print("  R      - Restart from beginning")
        print("  ENTER  - Generate new simulation")
        print("  Q/ESC  - Quit")
        print("\nClick on timeline to jump to any point.")
        print("\nStarting visualization...")

        run_again = visualizer.run()
        if not run_again:
            break

    print("\nDone!")


if __name__ == "__main__":
    main()
