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
"""

import argparse
import sys
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
    DELAY = "delay"                # TimingRandomizer delay
    BREAK_MICRO = "break_micro"    # Micro break
    BREAK_LONG = "break_long"      # Long break
    DRIFT = "drift"                # Attention drift
    SKILL_CHECK = "skill_check"    # Skill check sequence
    FATIGUE_SAMPLE = "fatigue"     # Fatigue level sample
    ACTION = "action"              # Regular cleaning action


class CompressionTier(Enum):
    """Time compression tiers."""
    NONE = 0       # < 2s: normal speed
    MEDIUM = 1     # 2-30s: 15x compression
    HEAVY = 2      # > 30s: 60x compression


@dataclass
class SimulatedEvent:
    """A single event in the simulation timeline."""
    event_type: EventType
    start_time: float  # simulated seconds from session start
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
# Simulation Engine
# =============================================================================


class AntiDetectionSimulator:
    """Pre-computes a simulated session with all anti-detection mechanics."""

    # Default drift regions (relative to canvas)
    DRIFT_REGIONS = {
        "minimap": DriftRegion("minimap", 850, 30, 150, 150, (100, 200, 100)),
        "chat": DriftRegion("chat", 20, 500, 480, 150, (100, 150, 200)),
        "skills_tab": DriftRegion("skills_tab", 850, 200, 180, 200, (200, 150, 255)),
        "random": DriftRegion("random", 400, 300, 200, 200, (150, 150, 150)),
    }

    def __init__(self, config: SimpleConfigManager, session_duration_minutes: float = 90):
        """Initialize simulator.

        Args:
            config: Configuration manager
            session_duration_minutes: Session length to simulate
        """
        self.config = config
        self.session_duration = session_duration_minutes * 60  # Convert to seconds
        self._rng = np.random.default_rng()

        # Load configuration values
        self._load_config()

        # Events timeline
        self.events: list[SimulatedEvent] = []

        # Statistics tracking
        self.delay_samples: list[float] = []
        self.fatigue_samples: list[tuple[float, float]] = []  # (time, level)
        self.break_events: list[SimulatedEvent] = []
        self.drift_events: list[SimulatedEvent] = []
        self.skill_check_events: list[SimulatedEvent] = []

    def _load_config(self):
        """Load configuration values from config manager."""
        # Timing config
        timing = self.config.get("timing", {}) or {}
        self.timing_mean = timing.get("click_herb_mean", 250) / 1000  # Convert to seconds
        self.timing_std = timing.get("click_herb_std", 75) / 1000

        # Fatigue config
        fatigue = self.config.get("fatigue", {}) or {}
        self.fatigue_onset_minutes = fatigue.get("onset_minutes", 30)
        self.fatigue_max_slowdown = fatigue.get("max_slowdown_percent", 50) / 100

        # Break config
        breaks = self.config.get("breaks", {}) or {}
        micro = breaks.get("micro", {}) or {}
        long_cfg = breaks.get("long", {}) or {}
        self.micro_interval = tuple(micro.get("interval", [480, 900]))
        self.micro_duration = tuple(micro.get("duration", [2, 10]))
        self.long_interval = tuple(long_cfg.get("interval", [2700, 5400]))
        self.long_duration = tuple(long_cfg.get("duration", [60, 300]))

        # Attention drift config
        attention = self.config.get("attention", {}) or {}
        self.drift_chance = attention.get("drift_chance", 0.03)
        self.drift_targets = attention.get("drift_targets", [
            {"name": "minimap", "weight": 3},
            {"name": "chat", "weight": 2},
            {"name": "random", "weight": 1},
        ])

        # Skill check config
        skill_check = self.config.get("skill_check", {}) or {}
        self.skill_check_enabled = skill_check.get("enabled", True)
        self.skill_check_interval = tuple(skill_check.get("cooldown_interval", [600, 900]))
        self.skill_check_hover = tuple(skill_check.get("hover_duration", [3.0, 8.0]))

    def _get_compression_tier(self, duration: float) -> CompressionTier:
        """Determine compression tier for a duration."""
        if duration < 2.0:
            return CompressionTier.NONE
        elif duration < 30.0:
            return CompressionTier.MEDIUM
        else:
            return CompressionTier.HEAVY

    def _gamma_delay(self, mean: float, std: float) -> float:
        """Generate delay using Gamma distribution (same as TimingRandomizer)."""
        variance = std * std
        k = (mean * mean) / variance  # shape
        theta = variance / mean  # scale
        return self._rng.gamma(k, theta)

    def _compute_fatigue(self, session_minutes: float) -> float:
        """Compute fatigue level at given session time.

        Uses the same logarithmic formula as FatigueSimulator.
        """
        if session_minutes < self.fatigue_onset_minutes:
            return 0.0

        time_past_onset = session_minutes - self.fatigue_onset_minutes
        fatigue = 1 - np.exp(-time_past_onset / 60)
        return min(1.0, max(0.0, fatigue))

    def _select_drift_target(self) -> str:
        """Select a drift target based on weights."""
        total_weight = sum(t["weight"] for t in self.drift_targets)
        roll = self._rng.random() * total_weight

        cumulative = 0
        for target in self.drift_targets:
            cumulative += target["weight"]
            if roll <= cumulative:
                return target["name"]
        return "random"

    def simulate(self):
        """Run the full simulation and populate events list."""
        print(f"Simulating {self.session_duration / 60:.1f} minute session...")

        self.events = []
        self.delay_samples = []
        self.fatigue_samples = []
        self.break_events = []
        self.drift_events = []
        self.skill_check_events = []

        current_time = 0.0
        action_count = 0

        # Schedule initial breaks
        next_micro_break = current_time + self._rng.uniform(*self.micro_interval)
        next_long_break = current_time + self._rng.uniform(*self.long_interval)
        next_skill_check = current_time + self._rng.uniform(*self.skill_check_interval)
        last_break_time = 0.0

        while current_time < self.session_duration:
            session_minutes = current_time / 60

            # Sample fatigue periodically (every 30 seconds of sim time)
            if len(self.fatigue_samples) == 0 or current_time - self.fatigue_samples[-1][0] >= 30:
                fatigue = self._compute_fatigue(session_minutes)
                self.fatigue_samples.append((current_time, fatigue))

            # Check for long break (priority)
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
                self.break_events.append(event)
                current_time += break_duration
                next_long_break = current_time + self._rng.uniform(*self.long_interval)
                next_micro_break = current_time + self._rng.uniform(*self.micro_interval)
                last_break_time = current_time
                continue

            # Check for micro break
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
                self.break_events.append(event)
                current_time += break_duration
                next_micro_break = current_time + self._rng.uniform(*self.micro_interval)
                last_break_time = current_time
                continue

            # Check for skill check
            if self.skill_check_enabled and current_time >= next_skill_check:
                hover_duration = self._rng.uniform(*self.skill_check_hover)
                # Full skill check sequence: ~1s click + hover + ~0.5s return
                total_duration = 1.0 + hover_duration + 0.5
                event = SimulatedEvent(
                    event_type=EventType.SKILL_CHECK,
                    start_time=current_time,
                    end_time=current_time + total_duration,
                    data={"hover_duration": hover_duration, "total_duration": total_duration},
                    compression_tier=self._get_compression_tier(total_duration),
                )
                self.events.append(event)
                self.skill_check_events.append(event)
                current_time += total_duration
                next_skill_check = current_time + self._rng.uniform(*self.skill_check_interval)
                continue

            # Check for attention drift (3% chance per action)
            fatigue = self._compute_fatigue(session_minutes)
            drift_chance = self.drift_chance + (fatigue * 0.03)  # Increases with fatigue
            if self._rng.random() < drift_chance:
                target = self._select_drift_target()
                drift_duration = self._rng.uniform(0.3, 2.0)
                event = SimulatedEvent(
                    event_type=EventType.DRIFT,
                    start_time=current_time,
                    end_time=current_time + drift_duration,
                    data={"target": target, "duration": drift_duration},
                    compression_tier=self._get_compression_tier(drift_duration),
                )
                self.events.append(event)
                self.drift_events.append(event)
                current_time += drift_duration
                continue

            # Regular action with delay
            # Apply fatigue slowdown
            slowdown = 1.0 + (fatigue * self.fatigue_max_slowdown)
            delay = self._gamma_delay(self.timing_mean, self.timing_std) * slowdown
            self.delay_samples.append(delay * 1000)  # Store in ms for histogram

            event = SimulatedEvent(
                event_type=EventType.ACTION,
                start_time=current_time,
                end_time=current_time + delay,
                data={"delay_ms": delay * 1000, "fatigue": fatigue, "action_num": action_count},
                compression_tier=CompressionTier.NONE,  # Actions are always quick
            )
            self.events.append(event)
            current_time += delay
            action_count += 1

        # Final fatigue sample
        self.fatigue_samples.append((current_time, self._compute_fatigue(current_time / 60)))

        print(f"Simulation complete:")
        print(f"  - {action_count} actions")
        print(f"  - {len(self.break_events)} breaks ({sum(1 for b in self.break_events if b.event_type == EventType.BREAK_MICRO)} micro, {sum(1 for b in self.break_events if b.event_type == EventType.BREAK_LONG)} long)")
        print(f"  - {len(self.drift_events)} attention drifts")
        print(f"  - {len(self.skill_check_events)} skill checks")
        print(f"  - {len(self.fatigue_samples)} fatigue samples")


# =============================================================================
# Visualization
# =============================================================================


class AntiDetectionVisualizer:
    """Pygame visualization for anti-detection mechanics."""

    # Layout constants (1400x900 window)
    WINDOW_WIDTH = 1400
    WINDOW_HEIGHT = 900
    CANVAS_WIDTH = 1050
    CANVAS_HEIGHT = 700
    PANEL_WIDTH = 350
    PANEL_HEIGHT = 140
    STATUS_HEIGHT = 50
    TIMELINE_HEIGHT = 50

    # Colors
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
    COLOR_DELAY = (100, 255, 150)
    COLOR_PROGRESS = (80, 200, 120)

    def __init__(self, simulator: AntiDetectionSimulator):
        """Initialize visualizer.

        Args:
            simulator: Pre-computed simulation
        """
        self.sim = simulator

        # Pygame state
        self.screen: Optional[pygame.Surface] = None
        self.clock: Optional[pygame.time.Clock] = None
        self.font: Optional[pygame.font.Font] = None
        self.font_large: Optional[pygame.font.Font] = None
        self.font_small: Optional[pygame.font.Font] = None

        # Playback state
        self.sim_time = 0.0  # Current time in simulation
        self.paused = False
        self.speed = 1.0
        self.skip_requested = False

        # Track what's currently active
        self.current_event: Optional[SimulatedEvent] = None
        self.event_index = 0

        # Histogram data (built incrementally)
        self.histogram_bins = np.linspace(0, 800, 25)  # 0-800ms in 25 bins
        self.histogram_counts = np.zeros(len(self.histogram_bins) - 1)

        # Drift regions for visualization
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

    def _get_real_duration(self, event: SimulatedEvent) -> float:
        """Get compressed playback duration for an event."""
        raw_duration = event.end_time - event.start_time
        if event.compression_tier == CompressionTier.NONE:
            return raw_duration
        elif event.compression_tier == CompressionTier.MEDIUM:
            return raw_duration / 15.0
        else:  # HEAVY
            return raw_duration / 60.0

    def _format_time(self, seconds: float) -> str:
        """Format seconds as MM:SS."""
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes:02d}:{secs:02d}"

    def _draw_panel_background(self, x: int, y: int, width: int, height: int, title: str):
        """Draw a panel with background and title."""
        # Background
        pygame.draw.rect(self.screen, self.COLOR_PANEL_BG, (x, y, width, height))
        pygame.draw.rect(self.screen, self.COLOR_ACCENT, (x, y, width, height), 1)

        # Title
        title_surface = self.font.render(title, True, self.COLOR_ACCENT)
        self.screen.blit(title_surface, (x + 10, y + 5))

    def _draw_histogram(self, x: int, y: int, width: int, height: int, current_delay: float):
        """Draw the timing delay histogram."""
        # Update histogram with delays up to current time
        delays_to_show = [d for i, d in enumerate(self.sim.delay_samples)
                         if i < len([e for e in self.sim.events
                                    if e.event_type == EventType.ACTION and e.start_time <= self.sim_time])]

        if delays_to_show:
            counts, _ = np.histogram(delays_to_show, bins=self.histogram_bins)
        else:
            counts = np.zeros(len(self.histogram_bins) - 1)

        max_count = max(counts.max(), 1)

        bar_width = width // len(counts)
        for i, count in enumerate(counts):
            bar_height = int((count / max_count) * (height - 40))
            bar_x = x + i * bar_width
            bar_y = y + height - 10 - bar_height

            # Color based on delay range
            if self.histogram_bins[i] < 200:
                color = (100, 255, 150)  # Fast - green
            elif self.histogram_bins[i] < 400:
                color = (255, 255, 100)  # Medium - yellow
            else:
                color = (255, 150, 100)  # Slow - orange

            pygame.draw.rect(self.screen, color, (bar_x, bar_y, bar_width - 2, bar_height))

        # Draw current delay marker
        if current_delay > 0 and current_delay < 800:
            marker_x = x + int((current_delay / 800) * width)
            pygame.draw.line(self.screen, (255, 50, 50), (marker_x, y + 30), (marker_x, y + height - 10), 2)

        # Labels
        text = f"Current: {current_delay:.0f}ms"
        self.screen.blit(self.font_small.render(text, True, self.COLOR_TEXT), (x + 10, y + height - 25))

        # X-axis labels
        for ms in [0, 200, 400, 600, 800]:
            lx = x + int((ms / 800) * width)
            self.screen.blit(self.font_small.render(f"{ms}", True, self.COLOR_TEXT_DIM), (lx - 10, y + height - 10))

    def _draw_fatigue_graph(self, x: int, y: int, width: int, height: int):
        """Draw the fatigue level line graph."""
        # Get fatigue samples up to current time
        samples = [(t, f) for t, f in self.sim.fatigue_samples if t <= self.sim_time]

        if len(samples) < 2:
            return

        # Draw axes
        graph_x = x + 40
        graph_y = y + 25
        graph_w = width - 50
        graph_h = height - 50

        pygame.draw.line(self.screen, self.COLOR_TEXT_DIM, (graph_x, graph_y), (graph_x, graph_y + graph_h), 1)
        pygame.draw.line(self.screen, self.COLOR_TEXT_DIM, (graph_x, graph_y + graph_h), (graph_x + graph_w, graph_y + graph_h), 1)

        # Y-axis labels
        for level in [0, 0.5, 1.0]:
            ly = graph_y + graph_h - int(level * graph_h)
            self.screen.blit(self.font_small.render(f"{level:.1f}", True, self.COLOR_TEXT_DIM), (x + 5, ly - 6))

        # Draw line
        max_time = self.sim.session_duration
        points = []
        for t, f in samples:
            px = graph_x + int((t / max_time) * graph_w)
            py = graph_y + graph_h - int(f * graph_h)
            points.append((px, py))

        if len(points) >= 2:
            pygame.draw.lines(self.screen, self.COLOR_FATIGUE, False, points, 2)

        # Current value
        current_fatigue = samples[-1][1] if samples else 0
        slowdown = 1.0 + (current_fatigue * self.sim.fatigue_max_slowdown)
        text = f"Level: {current_fatigue:.2f} | Mult: {slowdown:.2f}x"
        self.screen.blit(self.font_small.render(text, True, self.COLOR_TEXT), (x + 10, y + height - 20))

    def _draw_break_timeline(self, x: int, y: int, width: int, height: int):
        """Draw the break scheduler timeline."""
        # Draw timeline bar
        bar_y = y + 50
        bar_h = 20
        pygame.draw.rect(self.screen, (50, 50, 60), (x + 10, bar_y, width - 20, bar_h))

        max_time = self.sim.session_duration

        # Draw break markers
        for event in self.sim.break_events:
            marker_x = x + 10 + int((event.start_time / max_time) * (width - 20))
            marker_w = max(2, int((event.end_time - event.start_time) / max_time * (width - 20)))

            if event.event_type == EventType.BREAK_MICRO:
                color = self.COLOR_MICRO_BREAK
            else:
                color = self.COLOR_LONG_BREAK

            # Dim if not yet reached
            if event.start_time > self.sim_time:
                color = tuple(c // 3 for c in color)

            pygame.draw.rect(self.screen, color, (marker_x, bar_y, marker_w, bar_h))

        # Current position marker
        current_x = x + 10 + int((self.sim_time / max_time) * (width - 20))
        pygame.draw.line(self.screen, (255, 255, 255), (current_x, bar_y - 5), (current_x, bar_y + bar_h + 5), 2)

        # Find next break
        next_break = None
        for event in self.sim.break_events:
            if event.start_time > self.sim_time:
                next_break = event
                break

        if next_break:
            time_until = next_break.start_time - self.sim_time
            break_type = "micro" if next_break.event_type == EventType.BREAK_MICRO else "long"
            text = f"Next: {break_type} in {self._format_time(time_until)}"
        else:
            text = "No more breaks scheduled"

        self.screen.blit(self.font_small.render(text, True, self.COLOR_TEXT), (x + 10, y + height - 25))

        # Legend
        pygame.draw.rect(self.screen, self.COLOR_MICRO_BREAK, (x + 10, y + 25, 15, 15))
        self.screen.blit(self.font_small.render("Micro", True, self.COLOR_TEXT_DIM), (x + 30, y + 25))
        pygame.draw.rect(self.screen, self.COLOR_LONG_BREAK, (x + 90, y + 25, 15, 15))
        self.screen.blit(self.font_small.render("Long", True, self.COLOR_TEXT_DIM), (x + 110, y + 25))

    def _draw_attention_drift_panel(self, x: int, y: int, width: int, height: int):
        """Draw the attention drift panel."""
        # Count drifts so far
        drifts_so_far = [e for e in self.sim.drift_events if e.start_time <= self.sim_time]
        drift_count = len(drifts_so_far)

        # Last drift target
        last_target = drifts_so_far[-1].data["target"] if drifts_so_far else "none"

        # Target distribution
        target_counts = {}
        for e in drifts_so_far:
            t = e.data["target"]
            target_counts[t] = target_counts.get(t, 0) + 1

        text1 = f"Drifts: {drift_count}"
        text2 = f"Last: {last_target}"
        self.screen.blit(self.font.render(text1, True, self.COLOR_TEXT), (x + 10, y + 30))
        self.screen.blit(self.font.render(text2, True, self.COLOR_DRIFT), (x + 10, y + 55))

        # Mini bar chart of targets
        bar_y = y + 85
        bar_total_w = width - 20
        if drift_count > 0:
            bar_x = x + 10
            for target, count in sorted(target_counts.items()):
                bar_w = int((count / drift_count) * bar_total_w)
                color = self.drift_regions.get(target, DriftRegion("", 0, 0, 0, 0, (150, 150, 150))).color
                pygame.draw.rect(self.screen, color, (bar_x, bar_y, bar_w, 15))
                bar_x += bar_w

        # Labels
        label_y = y + 105
        for i, (target, count) in enumerate(sorted(target_counts.items())):
            color = self.drift_regions.get(target, DriftRegion("", 0, 0, 0, 0, (150, 150, 150))).color
            pygame.draw.rect(self.screen, color, (x + 10 + i * 80, label_y, 10, 10))
            self.screen.blit(self.font_small.render(f"{target[:6]}", True, self.COLOR_TEXT_DIM), (x + 25 + i * 80, label_y))

    def _draw_skill_checker_panel(self, x: int, y: int, width: int, height: int):
        """Draw the skill checker panel."""
        # Count checks so far
        checks_so_far = [e for e in self.sim.skill_check_events if e.start_time <= self.sim_time]
        check_count = len(checks_so_far)

        # Find next check
        next_check = None
        for event in self.sim.skill_check_events:
            if event.start_time > self.sim_time:
                next_check = event
                break

        text1 = f"Checks: {check_count}"
        self.screen.blit(self.font.render(text1, True, self.COLOR_TEXT), (x + 10, y + 30))

        if next_check:
            time_until = next_check.start_time - self.sim_time
            text2 = f"Next: {self._format_time(time_until)}"
            self.screen.blit(self.font.render(text2, True, self.COLOR_SKILL_CHECK), (x + 10, y + 55))
        else:
            self.screen.blit(self.font.render("No more checks", True, self.COLOR_TEXT_DIM), (x + 10, y + 55))

        # Show active skill check animation
        current_event = self._get_current_event()
        if current_event and current_event.event_type == EventType.SKILL_CHECK:
            progress = (self.sim_time - current_event.start_time) / (current_event.end_time - current_event.start_time)
            bar_w = int(progress * (width - 20))
            pygame.draw.rect(self.screen, self.COLOR_SKILL_CHECK, (x + 10, y + 85, bar_w, 20))
            pygame.draw.rect(self.screen, self.COLOR_ACCENT, (x + 10, y + 85, width - 20, 20), 1)
            self.screen.blit(self.font_small.render("Checking skill...", True, self.COLOR_TEXT), (x + 10, y + 110))

    def _draw_main_canvas(self, x: int, y: int, width: int, height: int):
        """Draw the main visualization canvas."""
        # Background
        pygame.draw.rect(self.screen, self.COLOR_CANVAS_BG, (x, y, width, height))
        pygame.draw.rect(self.screen, self.COLOR_ACCENT, (x, y, width, height), 1)

        # Draw drift region boxes
        for name, region in self.drift_regions.items():
            rect = pygame.Rect(x + region.x, y + region.y, region.width, region.height)
            # Dim color normally
            color = tuple(c // 4 for c in region.color)

            # Highlight if current drift is this region
            current_event = self._get_current_event()
            if current_event and current_event.event_type == EventType.DRIFT:
                if current_event.data.get("target") == name:
                    color = region.color

            pygame.draw.rect(self.screen, color, rect, 2)
            self.screen.blit(self.font_small.render(name, True, color), (rect.x + 5, rect.y + 5))

        # Draw cursor (simulated position)
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
                # Move cursor toward skills tab area
                cursor_x = x + 900
                cursor_y = y + 250

        # Draw cursor
        pygame.draw.circle(self.screen, (255, 100, 100), (cursor_x, cursor_y), 10)
        pygame.draw.circle(self.screen, (255, 255, 255), (cursor_x - 3, cursor_y - 3), 3)

        # Draw current event info overlay
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

                # Background box
                bg_rect = text_rect.inflate(20, 10)
                pygame.draw.rect(self.screen, (0, 0, 0, 180), bg_rect)
                pygame.draw.rect(self.screen, overlay_color, bg_rect, 2)
                self.screen.blit(text_surface, text_rect)

    def _draw_status_bar(self, x: int, y: int, width: int, height: int):
        """Draw the status bar at the top."""
        pygame.draw.rect(self.screen, self.COLOR_PANEL_BG, (x, y, width, height))

        # Time display
        time_text = f"Sim Time: {self._format_time(self.sim_time)} / {self._format_time(self.sim.session_duration)}"
        self.screen.blit(self.font.render(time_text, True, self.COLOR_TEXT), (10, y + 15))

        # Speed display
        speed_text = f"Speed: {self.speed:.1f}x"
        self.screen.blit(self.font.render(speed_text, True, self.COLOR_ACCENT), (250, y + 15))

        # Compression indicator
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

        # Pause indicator
        if self.paused:
            pause_surface = self.font_large.render("PAUSED", True, (255, 255, 100))
            self.screen.blit(pause_surface, (600, y + 12))

        # Current action
        if current_event:
            action_text = f"Event: {current_event.event_type.value}"
            self.screen.blit(self.font.render(action_text, True, self.COLOR_TEXT_DIM), (750, y + 15))

    def _draw_timeline_scrubber(self, x: int, y: int, width: int, height: int):
        """Draw the timeline scrubber at the bottom."""
        pygame.draw.rect(self.screen, self.COLOR_PANEL_BG, (x, y, width, height))

        bar_x = x + 50
        bar_y = y + 15
        bar_w = width - 100
        bar_h = 20

        # Background track
        pygame.draw.rect(self.screen, (50, 50, 60), (bar_x, bar_y, bar_w, bar_h))

        # Color zones for different event types
        max_time = self.sim.session_duration
        for event in self.sim.events:
            event_x = bar_x + int((event.start_time / max_time) * bar_w)
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
                continue  # Don't show regular actions

            pygame.draw.rect(self.screen, color, (event_x, bar_y, event_w, bar_h))

        # Current position
        current_x = bar_x + int((self.sim_time / max_time) * bar_w)
        pygame.draw.line(self.screen, (255, 255, 255), (current_x, bar_y - 3), (current_x, bar_y + bar_h + 3), 3)

        # Time labels
        self.screen.blit(self.font_small.render("0:00", True, self.COLOR_TEXT_DIM), (bar_x - 30, bar_y + 3))
        end_label = self._format_time(max_time)
        self.screen.blit(self.font_small.render(end_label, True, self.COLOR_TEXT_DIM), (bar_x + bar_w + 5, bar_y + 3))

        # Controls hint
        hint = "SPACE: Pause | S: Skip | +/-: Speed | R: Restart | ENTER: New Sim | Q: Quit"
        self.screen.blit(self.font_small.render(hint, True, self.COLOR_TEXT_DIM), (x + 10, y + 38))

    def _get_current_event(self) -> Optional[SimulatedEvent]:
        """Get the event active at current simulation time."""
        for event in self.sim.events:
            if event.start_time <= self.sim_time < event.end_time:
                return event
        return None

    def _update_time(self, dt: float):
        """Update simulation time with compression."""
        if self.paused:
            return

        current_event = self._get_current_event()

        # Apply speed multiplier
        time_step = dt * self.speed

        # Apply compression based on current event
        if current_event:
            if current_event.compression_tier == CompressionTier.MEDIUM:
                time_step *= 15
            elif current_event.compression_tier == CompressionTier.HEAVY:
                time_step *= 60

            # Handle skip request
            if self.skip_requested and current_event.compression_tier != CompressionTier.NONE:
                self.sim_time = current_event.end_time
                self.skip_requested = False
                return

        self.sim_time += time_step

        # Loop when reaching end
        if self.sim_time >= self.sim.session_duration:
            self.sim_time = 0

    def run(self) -> bool:
        """Run the visualization loop.

        Returns:
            True if user wants a new simulation (ENTER), False to quit.
        """
        self.init_pygame()

        running = True
        run_again = False
        last_time = pygame.time.get_ticks() / 1000

        while running:
            current_time = pygame.time.get_ticks() / 1000
            dt = current_time - last_time
            last_time = current_time

            # Handle events
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
                    elif event.key in (pygame.K_PLUS, pygame.K_EQUALS):
                        self.speed = min(5.0, self.speed + 0.5)
                    elif event.key == pygame.K_MINUS:
                        self.speed = max(0.25, self.speed - 0.5)
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    # Click on timeline to scrub
                    mx, my = event.pos
                    timeline_y = self.WINDOW_HEIGHT - self.TIMELINE_HEIGHT
                    if timeline_y <= my <= self.WINDOW_HEIGHT:
                        bar_x = 50
                        bar_w = self.WINDOW_WIDTH - 100
                        if bar_x <= mx <= bar_x + bar_w:
                            ratio = (mx - bar_x) / bar_w
                            self.sim_time = ratio * self.sim.session_duration

            # Update simulation time
            self._update_time(dt)

            # Clear screen
            self.screen.fill(self.COLOR_BG)

            # Draw status bar
            self._draw_status_bar(0, 0, self.WINDOW_WIDTH, self.STATUS_HEIGHT)

            # Draw main canvas
            canvas_y = self.STATUS_HEIGHT
            self._draw_main_canvas(0, canvas_y, self.CANVAS_WIDTH, self.CANVAS_HEIGHT)

            # Draw side panels
            panel_x = self.CANVAS_WIDTH
            panel_y = self.STATUS_HEIGHT

            # Panel 1: Timing Randomizer (histogram)
            self._draw_panel_background(panel_x, panel_y, self.PANEL_WIDTH, self.PANEL_HEIGHT, "TIMING RANDOMIZER")
            current_event = self._get_current_event()
            current_delay = current_event.data.get("delay_ms", 0) if current_event and current_event.event_type == EventType.ACTION else 0
            self._draw_histogram(panel_x, panel_y, self.PANEL_WIDTH, self.PANEL_HEIGHT, current_delay)

            # Panel 2: Fatigue Simulator (line graph)
            panel_y += self.PANEL_HEIGHT
            self._draw_panel_background(panel_x, panel_y, self.PANEL_WIDTH, self.PANEL_HEIGHT, "FATIGUE SIMULATOR")
            self._draw_fatigue_graph(panel_x, panel_y, self.PANEL_WIDTH, self.PANEL_HEIGHT)

            # Panel 3: Break Scheduler (timeline)
            panel_y += self.PANEL_HEIGHT
            self._draw_panel_background(panel_x, panel_y, self.PANEL_WIDTH, self.PANEL_HEIGHT, "BREAK SCHEDULER")
            self._draw_break_timeline(panel_x, panel_y, self.PANEL_WIDTH, self.PANEL_HEIGHT)

            # Panel 4: Attention Drift
            panel_y += self.PANEL_HEIGHT
            self._draw_panel_background(panel_x, panel_y, self.PANEL_WIDTH, self.PANEL_HEIGHT, "ATTENTION DRIFT")
            self._draw_attention_drift_panel(panel_x, panel_y, self.PANEL_WIDTH, self.PANEL_HEIGHT)

            # Panel 5: Skill Checker
            panel_y += self.PANEL_HEIGHT
            self._draw_panel_background(panel_x, panel_y, self.PANEL_WIDTH, self.PANEL_HEIGHT, "SKILL CHECKER")
            self._draw_skill_checker_panel(panel_x, panel_y, self.PANEL_WIDTH, self.PANEL_HEIGHT)

            # Draw timeline scrubber
            timeline_y = self.WINDOW_HEIGHT - self.TIMELINE_HEIGHT
            self._draw_timeline_scrubber(0, timeline_y, self.WINDOW_WIDTH, self.TIMELINE_HEIGHT)

            pygame.display.flip()
            self.clock.tick(60)

        pygame.quit()
        return run_again


# =============================================================================
# Main Entry Point
# =============================================================================


def main():
    parser = argparse.ArgumentParser(description="Visualize anti-detection mechanics")
    parser.add_argument("-c", "--config", type=str, default=None, help="Path to config file")
    parser.add_argument("--duration", type=float, default=90, help="Session duration in minutes (default: 90)")
    args = parser.parse_args()

    print("Anti-Detection Mechanics Visualization")
    print("=" * 50)

    config = SimpleConfigManager(args.config)
    run_count = 0

    while True:
        run_count += 1
        print(f"\n=== Simulation #{run_count} ===")

        # Create and run simulation
        simulator = AntiDetectionSimulator(config, session_duration_minutes=args.duration)
        simulator.simulate()

        # Create and run visualizer
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
