"""Real-time animated visualization of bot mouse movements and keypresses.

Captures a screenshot, simulates bot movements, and replays them with:
- A ball following the path in real-time
- Alpha-blended trail lines showing movement history
- Keypress events appearing in bottom-left as they occur
"""

import argparse
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np
import pygame

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from input.bezier_movement import BezierMovement, MovementConfig
from input.click_handler import ClickHandler, ClickTarget
from vision.screen_capture import ScreenCapture


@dataclass
class PathSegment:
    """A segment of mouse movement path."""
    points: list[tuple[int, int]]
    delays: list[float]
    total_time: float
    color: tuple[int, int, int] = (0, 255, 0)  # RGB
    is_overshoot: bool = False


@dataclass
class KeypressEvent:
    """A keypress event to display."""
    key_name: str
    duration_ms: float
    timestamp: float  # When to show this event
    index: int


@dataclass
class ClickEvent:
    """A click event to display."""
    x: int
    y: int
    timestamp: float


@dataclass
class SimulatedAction:
    """An action in the simulation timeline."""
    action_type: str  # "move", "keypress", "click"
    start_time: float
    end_time: float
    data: dict = field(default_factory=dict)


class MovementVisualizer:
    """Real-time animated visualization of bot movements."""

    # Colors (RGB for pygame)
    COLOR_BANK_PATH = (0, 255, 100)      # Green - movement to bank
    COLOR_INVENTORY_PATH = (100, 255, 255)  # Cyan - movement to inventory
    COLOR_OVERSHOOT = (255, 100, 255)    # Magenta - overshoot correction
    COLOR_CLICK = (255, 255, 100)        # Yellow - click markers
    COLOR_CURSOR = (255, 50, 50)         # Red - cursor ball
    COLOR_TEXT = (255, 255, 255)         # White - text
    COLOR_TEXT_BG = (0, 0, 0)            # Black - text background

    def __init__(self, screenshot: np.ndarray, window_offset: tuple[int, int] = (0, 0)):
        """Initialize visualizer.

        Args:
            screenshot: BGR numpy array of the game screenshot
            window_offset: (x, y) offset of game window on screen
        """
        self.screenshot = screenshot
        self.window_offset = window_offset
        self.height, self.width = screenshot.shape[:2]

        # Initialize movement generators
        self.bezier = BezierMovement(MovementConfig(
            overshoot_chance=0.35,
            overshoot_distance=(8, 18),
        ))
        self.click_handler = ClickHandler()
        self._rng = np.random.default_rng()

        # Simulation state
        self.path_segments: list[PathSegment] = []
        self.keypress_events: list[KeypressEvent] = []
        self.click_events: list[ClickEvent] = []
        self.actions: list[SimulatedAction] = []

        # Playback state
        self.current_time = 0.0
        self.cursor_pos = (self.width // 2, self.height // 2)
        self.drawn_path_points: list[tuple[tuple[int, int], tuple[int, int], int, tuple[int, int, int]]] = []
        self.visible_keypresses: list[KeypressEvent] = []
        self.visible_clicks: list[ClickEvent] = []

        # Pygame setup
        pygame.init()
        pygame.display.set_caption("Bot Movement Visualization")
        self.screen = pygame.display.set_mode((self.width, self.height))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("monospace", 16)
        self.font_large = pygame.font.SysFont("monospace", 20, bold=True)

        # Convert screenshot to pygame surface (BGR to RGB)
        screenshot_rgb = screenshot[:, :, ::-1].copy()
        self.background = pygame.surfarray.make_surface(screenshot_rgb.swapaxes(0, 1))

    def simulate_click_movement(
        self,
        start: tuple[int, int],
        target: ClickTarget,
        color: tuple[int, int, int],
        start_time: float,
    ) -> tuple[PathSegment, float]:
        """Simulate mouse movement to a click target.

        Args:
            start: Starting position
            target: Click target
            color: Path color
            start_time: When this movement starts

        Returns:
            (PathSegment, end_time)
        """
        # Calculate randomized click position
        click_result = self.click_handler.calculate_click(target)
        end = (click_result.x - self.window_offset[0], click_result.y - self.window_offset[1])

        # Generate path
        path = self.bezier.generate_path(start, end, num_points=60)

        # Calculate timing
        total_time = self.bezier.calculate_movement_time(start, end)
        delays = self.bezier.get_point_delays(path, total_time)

        # Check if this path has overshoot (path goes past end point then returns)
        is_overshoot = len(path) > 30 and self._detect_overshoot(path, end)

        segment = PathSegment(
            points=path,
            delays=delays,
            total_time=total_time,
            color=color,
            is_overshoot=is_overshoot,
        )

        # Store action
        self.actions.append(SimulatedAction(
            action_type="move",
            start_time=start_time,
            end_time=start_time + total_time,
            data={"segment": segment, "path_index": len(self.path_segments)},
        ))

        self.path_segments.append(segment)

        # Add click event at end
        click_time = start_time + total_time
        self.click_events.append(ClickEvent(x=end[0], y=end[1], timestamp=click_time))
        self.actions.append(SimulatedAction(
            action_type="click",
            start_time=click_time,
            end_time=click_time + click_result.duration,
            data={"x": end[0], "y": end[1]},
        ))

        return segment, click_time + click_result.duration

    def simulate_keypress(self, key_name: str, start_time: float) -> float:
        """Simulate a keypress event.

        Args:
            key_name: Name of key (e.g., "Escape", "1")
            start_time: When keypress starts

        Returns:
            End time after keypress
        """
        # Random duration similar to KeyboardController._get_key_duration()
        duration_ms = self._rng.gamma(2.0, 30) * 2
        duration_ms = max(30, min(200, duration_ms))

        # Add pre-key delay (hand movement to keyboard)
        pre_delay = self._rng.gamma(2.0, 0.08) + 0.15
        pre_delay = min(0.40, pre_delay)

        event = KeypressEvent(
            key_name=key_name,
            duration_ms=duration_ms,
            timestamp=start_time + pre_delay,
            index=len(self.keypress_events) + 1,
        )

        self.keypress_events.append(event)
        self.actions.append(SimulatedAction(
            action_type="keypress",
            start_time=start_time,
            end_time=start_time + pre_delay + (duration_ms / 1000),
            data={"event": event},
        ))

        return start_time + pre_delay + (duration_ms / 1000)

    def _detect_overshoot(self, path: list[tuple[int, int]], end: tuple[int, int]) -> bool:
        """Detect if path overshoots the target."""
        if len(path) < 10:
            return False

        # Check if any point in last third is further from end than the end point itself
        check_start = len(path) * 2 // 3
        for i in range(check_start, len(path) - 1):
            px, py = path[i]
            dist_to_end = ((px - end[0])**2 + (py - end[1])**2)**0.5
            if dist_to_end > 10:  # More than 10 pixels from target
                return True
        return False

    def generate_herb_cleaning_cycle(self, herb_bank_pos: tuple[int, int], inventory_slots: list[tuple[int, int]]):
        """Generate a full herb cleaning cycle simulation.

        Args:
            herb_bank_pos: Position of herb in bank (window-relative)
            inventory_slots: List of inventory slot centers (window-relative)
        """
        current_time = 0.5  # Start after brief pause

        # Start position (center of screen roughly)
        current_pos = (self.width // 2, self.height // 2)

        # 1. Click herb in bank (withdraw)
        herb_target = ClickTarget(
            center_x=herb_bank_pos[0] + self.window_offset[0],
            center_y=herb_bank_pos[1] + self.window_offset[1],
            width=32,
            height=32,
        )
        segment, current_time = self.simulate_click_movement(
            current_pos, herb_target, self.COLOR_BANK_PATH, current_time
        )
        current_pos = segment.points[-1]

        # Small delay after click
        current_time += self._rng.uniform(0.1, 0.2)

        # 2. Press Escape (close bank)
        current_time = self.simulate_keypress("Escape", current_time)
        current_time += self._rng.uniform(0.2, 0.4)  # Wait for bank to close

        # 3. Click inventory slots to clean herbs
        for i, slot_pos in enumerate(inventory_slots[:4]):  # First 4 slots
            slot_target = ClickTarget(
                center_x=slot_pos[0] + self.window_offset[0],
                center_y=slot_pos[1] + self.window_offset[1],
                width=36,
                height=32,
            )
            segment, current_time = self.simulate_click_movement(
                current_pos, slot_target, self.COLOR_INVENTORY_PATH, current_time
            )
            current_pos = segment.points[-1]

            # Small delay between clicks
            current_time += self._rng.uniform(0.05, 0.15)

    def get_thickness_from_delay(self, delay: float) -> int:
        """Calculate line thickness from delay (slower = thicker)."""
        min_delay, max_delay = 0.003, 0.06
        normalized = (delay - min_delay) / (max_delay - min_delay)
        normalized = max(0, min(1, normalized))
        return int(1 + normalized * 6)  # Range: 1-7 pixels

    def draw_path_with_alpha(self, surface: pygame.Surface, p1: tuple[int, int], p2: tuple[int, int],
                             thickness: int, color: tuple[int, int, int], alpha: int = 100):
        """Draw a line segment with alpha transparency."""
        # Create a temporary surface for alpha blending
        temp_surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        pygame.draw.line(temp_surface, (*color, alpha), p1, p2, thickness)
        surface.blit(temp_surface, (0, 0))

    def draw_cursor(self, surface: pygame.Surface, pos: tuple[int, int], clicking: bool = False):
        """Draw the cursor ball."""
        radius = 12 if clicking else 8
        color = self.COLOR_CLICK if clicking else self.COLOR_CURSOR

        # Outer glow
        pygame.draw.circle(surface, (*color, 100), pos, radius + 4)
        # Main circle
        pygame.draw.circle(surface, color, pos, radius)
        # Inner highlight
        pygame.draw.circle(surface, (255, 255, 255), (pos[0] - 2, pos[1] - 2), radius // 3)

    def draw_click_marker(self, surface: pygame.Surface, pos: tuple[int, int], age: float):
        """Draw a click marker that fades with age."""
        alpha = max(0, min(255, int(255 * (1 - age / 2.0))))  # Fade over 2 seconds
        if alpha <= 0:
            return

        # Expanding ring effect
        radius = int(8 + age * 20)
        temp_surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        pygame.draw.circle(temp_surface, (*self.COLOR_CLICK, alpha), pos, radius, 2)
        surface.blit(temp_surface, (0, 0))

    def draw_keypress_list(self, surface: pygame.Surface):
        """Draw keypress events in bottom-left corner."""
        if not self.visible_keypresses:
            return

        padding = 10
        line_height = 24
        box_width = 200
        box_height = len(self.visible_keypresses) * line_height + padding * 2

        # Semi-transparent background
        bg_rect = pygame.Rect(padding, self.height - box_height - padding, box_width, box_height)
        bg_surface = pygame.Surface((box_width, box_height), pygame.SRCALPHA)
        bg_surface.fill((0, 0, 0, 180))
        surface.blit(bg_surface, bg_rect.topleft)

        # Draw each keypress
        for i, event in enumerate(self.visible_keypresses[-8:]):  # Show last 8
            y = self.height - box_height - padding + padding + i * line_height
            text = f"{event.index}. {event.key_name} ({int(event.duration_ms)}ms)"
            text_surface = self.font.render(text, True, self.COLOR_TEXT)
            surface.blit(text_surface, (padding + 10, y))

    def draw_status(self, surface: pygame.Surface, paused: bool, speed: float):
        """Draw status info in top-right."""
        status_text = f"{'PAUSED' if paused else 'PLAYING'} | Speed: {speed:.1f}x | Time: {self.current_time:.2f}s"
        text_surface = self.font.render(status_text, True, self.COLOR_TEXT)
        text_rect = text_surface.get_rect(topright=(self.width - 10, 10))

        # Background
        bg_rect = text_rect.inflate(10, 6)
        bg_surface = pygame.Surface(bg_rect.size, pygame.SRCALPHA)
        bg_surface.fill((0, 0, 0, 180))
        surface.blit(bg_surface, bg_rect.topleft)
        surface.blit(text_surface, text_rect)

    def draw_instructions(self, surface: pygame.Surface):
        """Draw control instructions."""
        instructions = "SPACE: Pause | R: Restart | +/-: Speed | Q: Quit"
        text_surface = self.font.render(instructions, True, (200, 200, 200))
        text_rect = text_surface.get_rect(midbottom=(self.width // 2, self.height - 10))
        surface.blit(text_surface, text_rect)

    def get_cursor_position_at_time(self, t: float) -> tuple[tuple[int, int], bool, Optional[PathSegment]]:
        """Get cursor position at given time.

        Returns:
            (position, is_clicking, current_segment)
        """
        is_clicking = False
        current_segment = None

        # Check if we're clicking
        for click in self.click_events:
            if click.timestamp <= t < click.timestamp + 0.1:
                is_clicking = True
                break

        # Find active movement action
        for action in self.actions:
            if action.action_type == "move" and action.start_time <= t < action.end_time:
                segment = action.data["segment"]
                current_segment = segment

                # Calculate position along path
                progress = (t - action.start_time) / (action.end_time - action.start_time)
                point_index = int(progress * (len(segment.points) - 1))
                point_index = min(point_index, len(segment.points) - 1)

                return segment.points[point_index], is_clicking, segment

        # Find last completed movement
        last_pos = (self.width // 2, self.height // 2)
        for action in reversed(self.actions):
            if action.action_type == "move" and action.end_time <= t:
                last_pos = action.data["segment"].points[-1]
                break

        return last_pos, is_clicking, None

    def get_drawn_segments_at_time(self, t: float) -> list[tuple[PathSegment, int]]:
        """Get path segments that should be drawn at given time.

        Returns:
            List of (segment, points_to_draw) tuples
        """
        result = []

        for action in self.actions:
            if action.action_type != "move":
                continue

            segment = action.data["segment"]

            if action.end_time <= t:
                # Fully completed - draw all points
                result.append((segment, len(segment.points)))
            elif action.start_time <= t < action.end_time:
                # In progress - draw up to current point
                progress = (t - action.start_time) / (action.end_time - action.start_time)
                points_drawn = int(progress * len(segment.points))
                result.append((segment, points_drawn))

        return result

    def run(self):
        """Run the visualization loop."""
        running = True
        paused = False
        speed = 1.0
        last_update = time.time()

        # Calculate total duration
        if self.actions:
            total_duration = max(a.end_time for a in self.actions) + 1.0
        else:
            total_duration = 5.0

        while running:
            dt = time.time() - last_update
            last_update = time.time()

            # Handle events
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_q or event.key == pygame.K_ESCAPE:
                        running = False
                    elif event.key == pygame.K_SPACE:
                        paused = not paused
                    elif event.key == pygame.K_r:
                        self.current_time = 0
                        self.visible_keypresses = []
                    elif event.key == pygame.K_PLUS or event.key == pygame.K_EQUALS:
                        speed = min(5.0, speed + 0.5)
                    elif event.key == pygame.K_MINUS:
                        speed = max(0.25, speed - 0.5)

            # Update time
            if not paused:
                self.current_time += dt * speed
                if self.current_time > total_duration:
                    self.current_time = 0
                    self.visible_keypresses = []

            # Update visible keypresses
            for event in self.keypress_events:
                if event.timestamp <= self.current_time and event not in self.visible_keypresses:
                    self.visible_keypresses.append(event)

            # Clear with background
            self.screen.blit(self.background, (0, 0))

            # Draw completed and in-progress path segments
            segments_to_draw = self.get_drawn_segments_at_time(self.current_time)
            for segment, points_count in segments_to_draw:
                for i in range(min(points_count - 1, len(segment.points) - 1)):
                    p1 = segment.points[i]
                    p2 = segment.points[i + 1]

                    # Get delay for thickness
                    delay = segment.delays[i] if i < len(segment.delays) else 0.01
                    thickness = self.get_thickness_from_delay(delay)

                    # Use overshoot color for overshoot segments
                    color = self.COLOR_OVERSHOOT if segment.is_overshoot else segment.color

                    self.draw_path_with_alpha(self.screen, p1, p2, thickness, color, alpha=100)

            # Draw click markers
            for click in self.click_events:
                if click.timestamp <= self.current_time:
                    age = self.current_time - click.timestamp
                    self.draw_click_marker(self.screen, (click.x, click.y), age)

            # Draw cursor
            cursor_pos, is_clicking, _ = self.get_cursor_position_at_time(self.current_time)
            self.draw_cursor(self.screen, cursor_pos, is_clicking)

            # Draw UI
            self.draw_keypress_list(self.screen)
            self.draw_status(self.screen, paused, speed)
            self.draw_instructions(self.screen)

            pygame.display.flip()
            self.clock.tick(60)

        pygame.quit()


def main():
    parser = argparse.ArgumentParser(description="Visualize bot mouse movements in real-time")
    parser.add_argument("--demo", action="store_true", help="Run with demo positions (no game detection)")
    args = parser.parse_args()

    print("Bot Movement Visualizer")
    print("=" * 40)

    # Capture screenshot
    print("Capturing RuneLite window...")
    screen_capture = ScreenCapture()
    bounds = screen_capture.find_window()

    if bounds is None:
        print("ERROR: Could not find RuneLite window!")
        print("Make sure RuneLite is running and visible.")
        if not args.demo:
            sys.exit(1)
        # Create demo screenshot
        print("Running in demo mode with synthetic background...")
        screenshot = np.zeros((600, 800, 3), dtype=np.uint8)
        screenshot[:] = (40, 40, 50)  # Dark gray background
        window_offset = (0, 0)
    else:
        screenshot = screen_capture.capture_window()
        if screenshot is None:
            print("ERROR: Could not capture screenshot!")
            sys.exit(1)
        window_offset = (bounds.x, bounds.y)
        print(f"Captured {screenshot.shape[1]}x{screenshot.shape[0]} screenshot")

    # Create visualizer
    visualizer = MovementVisualizer(screenshot, window_offset)

    # Generate demo herb cleaning cycle
    # These positions are approximate - in real use would come from detectors
    herb_bank_pos = (300, 250)  # Approximate bank herb position

    # Calculate inventory slot positions (typical RuneLite layout)
    inv_start_x = 580
    inv_start_y = 230
    slot_width = 42
    slot_height = 36

    inventory_slots = []
    for row in range(7):
        for col in range(4):
            x = inv_start_x + col * slot_width + slot_width // 2
            y = inv_start_y + row * slot_height + slot_height // 2
            inventory_slots.append((x, y))

    print("Generating simulated herb cleaning cycle...")
    visualizer.generate_herb_cleaning_cycle(herb_bank_pos, inventory_slots)

    print(f"Generated {len(visualizer.path_segments)} movement paths")
    print(f"Generated {len(visualizer.keypress_events)} keypress events")
    print()
    print("Controls:")
    print("  SPACE - Pause/Resume")
    print("  R     - Restart")
    print("  +/-   - Adjust speed")
    print("  Q/ESC - Quit")
    print()
    print("Starting visualization...")

    visualizer.run()

    screen_capture.close()
    print("Done!")


if __name__ == "__main__":
    main()
