"""Real-time animated visualization of bot mouse movements and keypresses.

Uses the ACTUAL bot logic from BotController to simulate movements:
- Same Bezier curves and movement config
- Same click randomization
- Same timing patterns
- Same keypress behavior

Captures a screenshot and replays the simulated cycle with a cursor ball.
"""

import argparse
import importlib.util
import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pygame
import yaml


def _load_module_direct(module_name: str, file_path: Path):
    """Load a module directly from file, bypassing __init__.py."""
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


# Load modules directly to avoid __init__.py import chains
_src_dir = Path(__file__).parent.parent / "src"

_bezier_mod = _load_module_direct("bezier_movement", _src_dir / "input" / "bezier_movement.py")
BezierMovement = _bezier_mod.BezierMovement
MovementConfig = _bezier_mod.MovementConfig

_click_mod = _load_module_direct("click_handler", _src_dir / "input" / "click_handler.py")
ClickHandler = _click_mod.ClickHandler
ClickConfig = _click_mod.ClickConfig
ClickTarget = _click_mod.ClickTarget

_timing_mod = _load_module_direct("timing_randomizer", _src_dir / "anti_detection" / "timing_randomizer.py")
TimingRandomizer = _timing_mod.TimingRandomizer
ActionType = _timing_mod.ActionType
TimingConfig = _timing_mod.TimingConfig

# Try to load vision modules for position detection
try:
    _template_mod = _load_module_direct("template_matcher", _src_dir / "vision" / "template_matcher.py")
    TemplateMatcher = _template_mod.TemplateMatcher
    MatchResult = _template_mod.MatchResult
    HAS_VISION = True
except Exception:
    HAS_VISION = False
    TemplateMatcher = None
    MatchResult = None


class SimpleConfigManager:
    """Minimal config manager that loads YAML without complex dependencies."""

    DEFAULT_CONFIG_PATH = Path(__file__).parent.parent / "config" / "default_config.yaml"

    def __init__(self, config_path: str | Path | None = None):
        self.config_path = Path(config_path) if config_path else self.DEFAULT_CONFIG_PATH
        self._config: dict[str, Any] = {}
        if self.config_path.exists():
            with open(self.config_path, "r") as f:
                self._config = yaml.safe_load(f) or {}

    def get(self, key: str, default: Any = None) -> Any:
        keys = key.split(".")
        value = self._config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value

    @property
    def timing(self) -> dict[str, Any]:
        return self._config.get("timing", {})

    @property
    def mouse(self) -> dict[str, Any]:
        return self._config.get("mouse", {})

    @property
    def click(self) -> dict[str, Any]:
        return self._config.get("click", {})

    @property
    def window(self) -> dict[str, Any]:
        return self._config.get("window", {})


class GameState(Enum):
    """Game states corresponding to different background images."""
    WORLD_VIEW = "world_view"          # Standing near bank, bank closed
    BANK_OPEN = "bank_open"            # Bank interface open with grimy herbs
    BANK_OPEN_CLEAN = "bank_open_clean"  # Bank open with clean herbs in inventory
    INVENTORY_GRIMY = "inventory_grimy"  # Bank closed, grimy herbs in inventory


@dataclass
class PathSegment:
    """A segment of mouse movement path."""
    points: list[tuple[int, int]]
    delays: list[float]
    total_time: float
    color: tuple[int, int, int] = (0, 255, 0)
    is_overshoot: bool = False
    label: str = ""


@dataclass
class KeypressEvent:
    """A keypress event to display."""
    key_name: str
    duration_ms: float
    timestamp: float
    index: int


@dataclass
class ClickEvent:
    """A click event to display."""
    x: int
    y: int
    timestamp: float
    duration: float


@dataclass
class SimulatedAction:
    """An action in the simulation timeline."""
    action_type: str  # "move", "keypress", "click", "delay"
    start_time: float
    end_time: float
    data: dict = field(default_factory=dict)
    state_after: Optional[GameState] = None  # Background to show after this action


class BotMovementVisualizer:
    """Real-time visualization using actual bot logic."""

    # Colors (RGB for pygame)
    COLOR_BANK_BOOTH = (255, 165, 0)     # Orange - click bank booth
    COLOR_DEPOSIT = (255, 100, 100)      # Light red - deposit button
    COLOR_WITHDRAW = (0, 255, 100)       # Green - withdraw herbs
    COLOR_CLOSE_BANK = (255, 50, 50)     # Red - close bank
    COLOR_INVENTORY = (100, 255, 255)    # Cyan - inventory clicks
    COLOR_OVERSHOOT = (255, 100, 255)    # Magenta - overshoot correction
    COLOR_CLICK = (255, 255, 100)        # Yellow - click markers
    COLOR_CURSOR = (255, 50, 50)         # Red - cursor ball
    COLOR_TEXT = (255, 255, 255)         # White - text

    def __init__(self, config_path: Optional[str] = None):
        """Initialize visualizer using bot config.

        Args:
            config_path: Path to bot config file
        """
        # Load bot configuration
        self.config = SimpleConfigManager(config_path)

        # Movement config from bot settings
        mouse_cfg = self.config.mouse
        self.movement_config = MovementConfig(
            speed_range=tuple(mouse_cfg.get("speed_range", [200, 400])),
            overshoot_chance=mouse_cfg.get("overshoot_chance", 0.30),
            overshoot_distance=tuple(mouse_cfg.get("overshoot_distance", [5, 15])),
            curve_variance=mouse_cfg.get("curve_variance", 0.3),
        )
        self.bezier = BezierMovement(self.movement_config)

        # Click config from bot settings
        self.click_config = ClickConfig(
            position_sigma_ratio=self.config.click.get("position_sigma_ratio", 6),
            duration_mean=self.config.click.get("duration_mean", 100),
            duration_min=self.config.click.get("duration_min", 50),
            duration_max=self.config.click.get("duration_max", 200),
        )
        self.click_handler = ClickHandler(self.click_config)

        # Timing config from bot settings
        timing_cfg = self.config.timing
        self.timing = TimingRandomizer(
            config=TimingConfig(
                click_herb_mean=timing_cfg.get("click_herb_mean", 600),
                click_herb_std=timing_cfg.get("click_herb_std", 150),
                click_herb_min=timing_cfg.get("click_herb_min", 350),
                click_herb_max=timing_cfg.get("click_herb_max", 1200),
                bank_action_mean=timing_cfg.get("bank_action_mean", 800),
                bank_action_std=timing_cfg.get("bank_action_std", 200),
                bank_action_min=timing_cfg.get("bank_action_min", 500),
                bank_action_max=timing_cfg.get("bank_action_max", 1500),
                after_bank_open=timing_cfg.get("after_bank_open", 400),
                after_deposit=timing_cfg.get("after_deposit", 300),
                after_withdraw=timing_cfg.get("after_withdraw", 300),
                after_bank_close=timing_cfg.get("after_bank_close", 200),
            )
        )

        # Bank ESC chance from config
        self.esc_chance = self.config.get("bank.esc_chance", 0.70)

        self._rng = np.random.default_rng()

        # Simulation state
        self.path_segments: list[PathSegment] = []
        self.keypress_events: list[KeypressEvent] = []
        self.click_events: list[ClickEvent] = []
        self.actions: list[SimulatedAction] = []

        # Screenshot and window info
        self.screenshot: Optional[np.ndarray] = None
        self.window_offset = (0, 0)
        self.width = 800
        self.height = 600

        # Pygame state
        self.screen: Optional[pygame.Surface] = None
        self.background: Optional[pygame.Surface] = None
        self.backgrounds: dict[GameState, pygame.Surface] = {}
        self.current_state: GameState = GameState.WORLD_VIEW
        self.state_transitions: list[tuple[float, GameState]] = []
        self.clock: Optional[pygame.time.Clock] = None
        self.font: Optional[pygame.font.Font] = None
        self._alpha_surface: Optional[pygame.Surface] = None

        # Performance: cache for completed segments
        self._completed_segments_cache: list[tuple[PathSegment, int]] = []
        self._last_cache_time: float = -1.0

        # Debug: store click targets for visualization
        self.debug_targets: list[tuple[ClickTarget, str, tuple[int, int, int]]] = []
        self.debug_mode: bool = False

        # Detected UI positions (populated by detect_ui_positions)
        self.detected_positions: dict[str, tuple[int, int]] = {}

    def capture_screenshot(self) -> bool:
        """Capture screenshot from RuneLite.

        Note: Screen capture requires additional dependencies.
        Use --demo mode for standalone operation.

        Returns:
            True if successful
        """
        # Screen capture disabled in standalone mode
        # Use --demo flag instead
        return False

    def create_demo_screenshot(self):
        """Create a demo screenshot for testing without RuneLite.

        If real screenshots exist, uses their native resolution.
        Otherwise falls back to 800x600.
        """
        self.window_offset = (0, 0)

        # Try to get dimensions from real screenshots
        screenshots_dir = Path(__file__).parent / "viz_screenshots"
        sample_file = screenshots_dir / "world_view.png"

        if sample_file.exists():
            try:
                import cv2
                img = cv2.imread(str(sample_file))
                if img is not None:
                    self.height, self.width = img.shape[:2]
                    self.screenshot = np.zeros((self.height, self.width, 3), dtype=np.uint8)
                    self.screenshot[:] = (40, 40, 50)
                    print(f"Using native screenshot resolution: {self.width}x{self.height}")
                    return
            except ImportError:
                pass

        # Fallback to default size
        self.screenshot = np.zeros((600, 800, 3), dtype=np.uint8)
        self.screenshot[:] = (40, 40, 50)
        self.height, self.width = 600, 800

    def load_screenshots(self) -> dict[GameState, np.ndarray]:
        """Load state-specific screenshots from viz_screenshots directory.

        Returns:
            Dictionary mapping GameState to numpy arrays (BGR format)
        """
        screenshots_dir = Path(__file__).parent / "viz_screenshots"
        screenshots: dict[GameState, np.ndarray] = {}

        # Mapping of state to filename
        state_files = {
            GameState.WORLD_VIEW: "world_view.png",
            GameState.BANK_OPEN: "bank_open.png",
            GameState.BANK_OPEN_CLEAN: "bank_open_clean.png",
            GameState.INVENTORY_GRIMY: "inventory_grimy.png",
        }

        import cv2

        for state, filename in state_files.items():
            filepath = screenshots_dir / filename
            if filepath.exists():
                img = cv2.imread(str(filepath))
                if img is not None:
                    screenshots[state] = img
                    print(f"  Loaded {filename}")

        return screenshots

    def detect_ui_positions(self, screenshots: dict[GameState, np.ndarray]) -> dict[str, tuple[int, int]]:
        """Detect UI element positions from screenshots using template matching.

        Uses the same detection code as the real bot.

        Args:
            screenshots: Dictionary of game state screenshots

        Returns:
            Dictionary mapping element names to (x, y) center positions
        """
        if not HAS_VISION:
            print("  Vision module not available, using config positions")
            return {}

        positions = {}
        templates_dir = Path(__file__).parent.parent / "templates"

        if not templates_dir.exists():
            print(f"  Templates directory not found: {templates_dir}")
            return {}

        # Initialize template matcher with same settings as real bot
        vision_cfg = self.config.get("vision", {})
        matcher = TemplateMatcher(
            templates_dir=templates_dir,
            confidence_threshold=vision_cfg.get("confidence_threshold", 0.55),
            multi_scale=vision_cfg.get("multi_scale", True),
            scale_range=tuple(vision_cfg.get("scale_range", [0.9, 1.1])),
            scale_steps=vision_cfg.get("scale_steps", 3),
        )

        bank_cfg = self.config.get("bank", {}) or {}

        # Detect bank booth from world_view screenshot
        if GameState.WORLD_VIEW in screenshots:
            img = screenshots[GameState.WORLD_VIEW]
            booth_match = matcher.match(img, bank_cfg.get("booth_template", "bank_booth.png"))
            if booth_match.found:
                positions["bank_booth"] = (booth_match.center_x, booth_match.center_y)
                print(f"  Detected bank booth at ({booth_match.center_x}, {booth_match.center_y})")

        # Detect deposit, close, grimy herb from bank_open screenshot
        if GameState.BANK_OPEN in screenshots:
            img = screenshots[GameState.BANK_OPEN]

            deposit_match = matcher.match(img, bank_cfg.get("deposit_all_template", "deposit_all.png"))
            if deposit_match.found:
                positions["deposit_button"] = (deposit_match.center_x, deposit_match.center_y)
                print(f"  Detected deposit button at ({deposit_match.center_x}, {deposit_match.center_y})")

            close_match = matcher.match(img, bank_cfg.get("close_button_template", "bank_close.png"))
            if close_match.found:
                positions["close_button"] = (close_match.center_x, close_match.center_y)
                print(f"  Detected close button at ({close_match.center_x}, {close_match.center_y})")

            # Try to detect grimy herbs
            herbs_cfg = self.config.get("herbs", {}) or {}
            grimy_templates = herbs_cfg.get("grimy", [])
            for herb in grimy_templates:
                herb_match = matcher.match_bottom_region(img, herb["template"], region_percentage=0.70)
                if herb_match.found:
                    positions["grimy_herb"] = (herb_match.center_x, herb_match.center_y)
                    print(f"  Detected grimy herb at ({herb_match.center_x}, {herb_match.center_y})")
                    break

        return positions

    def create_demo_backgrounds(self) -> dict[GameState, np.ndarray]:
        """Create colored demo backgrounds for each game state.

        Returns:
            Dictionary mapping GameState to numpy arrays (BGR format)
        """
        backgrounds: dict[GameState, np.ndarray] = {}

        # Color scheme for each state (BGR format for OpenCV/numpy)
        state_colors = {
            GameState.WORLD_VIEW: (50, 80, 40),      # Dark green - outdoor
            GameState.BANK_OPEN: (40, 50, 70),       # Dark brown - bank interface
            GameState.BANK_OPEN_CLEAN: (50, 60, 80), # Slightly lighter brown
            GameState.INVENTORY_GRIMY: (70, 50, 40), # Dark blue - inventory focus
        }

        for state, color in state_colors.items():
            bg = np.zeros((self.height, self.width, 3), dtype=np.uint8)
            bg[:] = color
            backgrounds[state] = bg

        return backgrounds

    def _add_state_transition(self, timestamp: float, state: GameState):
        """Record a state transition at the given timestamp."""
        self.state_transitions.append((timestamp, state))

    def get_game_state_at_time(self, t: float) -> GameState:
        """Get the game state at a given simulation time.

        Args:
            t: Current simulation time in seconds

        Returns:
            The GameState that should be displayed at time t
        """
        current = GameState.WORLD_VIEW
        for timestamp, state in self.state_transitions:
            if t >= timestamp:
                current = state
            else:
                break
        return current

    def _simulate_move_to_target(
        self,
        start: tuple[int, int],
        target: ClickTarget,
        color: tuple[int, int, int],
        start_time: float,
        label: str = "",
    ) -> tuple[tuple[int, int], float]:
        """Simulate mouse movement to target using bot logic.

        This replicates MouseController.click_at_target() behavior.

        Returns:
            (final_position, end_time)
        """
        # Record target for debug visualization
        if self.debug_mode:
            self.debug_targets.append((target, label, color))

        # Calculate randomized click position (same as click_handler.calculate_click)
        click_result = self.click_handler.calculate_click(target)
        end = (click_result.x, click_result.y)

        # Generate Bezier path (same as bezier.generate_path)
        path = self.bezier.generate_path(start, end, num_points=60)

        # Calculate timing (same as bezier.calculate_movement_time + get_point_delays)
        total_time = self.bezier.calculate_movement_time(start, end)
        delays = self.bezier.get_point_delays(path, total_time)

        # Detect overshoot
        is_overshoot = self._detect_overshoot(path, end)

        segment = PathSegment(
            points=path,
            delays=delays,
            total_time=total_time,
            color=color,
            is_overshoot=is_overshoot,
            label=label,
        )
        self.path_segments.append(segment)

        # Record move action
        self.actions.append(SimulatedAction(
            action_type="move",
            start_time=start_time,
            end_time=start_time + total_time,
            data={"segment": segment},
        ))

        # Record click at end
        click_time = start_time + total_time
        self.click_events.append(ClickEvent(
            x=end[0], y=end[1],
            timestamp=click_time,
            duration=click_result.duration,
        ))
        self.actions.append(SimulatedAction(
            action_type="click",
            start_time=click_time,
            end_time=click_time + click_result.duration,
            data={"x": end[0], "y": end[1]},
        ))

        return end, click_time + click_result.duration

    def _simulate_keypress(self, key_name: str, start_time: float) -> float:
        """Simulate keypress using KeyboardController timing.

        Returns:
            End time after keypress
        """
        # Pre-key delay (hand movement from mouse to keyboard)
        # Replicates KeyboardController._get_pre_key_delay()
        pre_delay = self._rng.gamma(2.0, 0.08) + 0.15
        pre_delay = min(0.40, pre_delay)

        # Key hold duration
        # Replicates KeyboardController._get_key_duration()
        duration = self._rng.gamma(2.0, 0.03)
        duration = max(0.03, min(0.20, duration))
        duration_ms = duration * 1000

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
            end_time=start_time + pre_delay + duration,
            data={"event": event},
        ))

        return start_time + pre_delay + duration

    def _add_delay(self, start_time: float, delay: float) -> float:
        """Add a delay action."""
        self.actions.append(SimulatedAction(
            action_type="delay",
            start_time=start_time,
            end_time=start_time + delay,
            data={},
        ))
        return start_time + delay

    def _detect_overshoot(self, path: list[tuple[int, int]], end: tuple[int, int]) -> bool:
        """Detect if path has overshoot correction."""
        if len(path) < 10:
            return False
        check_start = len(path) * 2 // 3
        for i in range(check_start, len(path) - 1):
            px, py = path[i]
            dist = ((px - end[0])**2 + (py - end[1])**2)**0.5
            if dist > 10:
                return True
        return False

    def simulate_full_cycle(
        self,
        bank_booth_pos: Optional[tuple[int, int]] = None,
        deposit_button_pos: Optional[tuple[int, int]] = None,
        grimy_herb_pos: Optional[tuple[int, int]] = None,
        close_button_pos: Optional[tuple[int, int]] = None,
        inventory_slots: Optional[list[tuple[int, int]]] = None,
        has_clean_herbs: bool = False,
        num_grimy_herbs: int = 28,
    ):
        """Simulate a full herb cleaning cycle using bot logic.

        This replicates the BotController state machine:
        IDLE -> BANKING_OPEN -> BANKING_DEPOSIT -> BANKING_WITHDRAW ->
        BANKING_CLOSE -> CLEANING -> BANKING_OPEN ...

        Args:
            bank_booth_pos: Position of bank booth (window-relative)
            deposit_button_pos: Position of deposit button
            grimy_herb_pos: Position of grimy herbs in bank
            close_button_pos: Position of bank close button
            inventory_slots: List of inventory slot positions
            has_clean_herbs: Whether inventory has clean herbs to deposit
            num_grimy_herbs: Number of grimy herbs to clean
        """
        # Use detected positions if available, otherwise fall back to defaults
        if bank_booth_pos is None:
            bank_booth_pos = self.detected_positions.get("bank_booth", (400, 300))
        if deposit_button_pos is None:
            deposit_button_pos = self.detected_positions.get("deposit_button", (420, 470))
        if grimy_herb_pos is None:
            grimy_herb_pos = self.detected_positions.get("grimy_herb", (300, 250))
        if close_button_pos is None:
            close_button_pos = self.detected_positions.get("close_button", (510, 45))
        if inventory_slots is None:
            inv_cfg = self.config.window.get("inventory", {})
            inv_x = inv_cfg.get("x", 580)
            inv_y = inv_cfg.get("y", 230)
            slot_w = inv_cfg.get("slot_width", 42)
            slot_h = inv_cfg.get("slot_height", 36)
            inventory_slots = []
            for row in range(7):
                for col in range(4):
                    x = inv_x + col * slot_w + slot_w // 2
                    y = inv_y + row * slot_h + slot_h // 2
                    inventory_slots.append((x, y))

        current_time = 0.3  # Initial pause
        current_pos = (self.width // 2, self.height // 2)

        # === STATE: BANKING_OPEN ===
        # Click bank booth (replicates _handle_banking_open)
        booth_target = ClickTarget(
            center_x=bank_booth_pos[0],
            center_y=bank_booth_pos[1],
            width=40, height=40,
        )
        current_pos, current_time = self._simulate_move_to_target(
            current_pos, booth_target, self.COLOR_BANK_BOOTH, current_time,
            label="Click bank booth"
        )

        # Wait for bank to open (timing.get_delay(ActionType.OPEN_BANK))
        bank_open_delay = self.timing.get_delay(ActionType.OPEN_BANK)
        current_time = self._add_delay(current_time, bank_open_delay)

        # State transition: bank is now open
        if has_clean_herbs:
            self._add_state_transition(current_time, GameState.BANK_OPEN_CLEAN)
        else:
            self._add_state_transition(current_time, GameState.BANK_OPEN)

        # Post-open delay
        post_open_delay = self.timing.get_post_action_delay(ActionType.OPEN_BANK)
        current_time = self._add_delay(current_time, post_open_delay)

        # === STATE: BANKING_DEPOSIT (if has clean herbs) ===
        if has_clean_herbs:
            deposit_target = ClickTarget(
                center_x=deposit_button_pos[0],
                center_y=deposit_button_pos[1],
                width=35, height=25,
            )
            current_pos, current_time = self._simulate_move_to_target(
                current_pos, deposit_target, self.COLOR_DEPOSIT, current_time,
                label="Deposit herbs"
            )
            post_deposit_delay = self.timing.get_post_action_delay(ActionType.DEPOSIT)
            current_time = self._add_delay(current_time, post_deposit_delay)

            # State transition: inventory now empty, showing normal bank view
            self._add_state_transition(current_time, GameState.BANK_OPEN)

        # === STATE: BANKING_WITHDRAW ===
        herb_target = ClickTarget(
            center_x=grimy_herb_pos[0],
            center_y=grimy_herb_pos[1],
            width=32, height=32,
        )
        current_pos, current_time = self._simulate_move_to_target(
            current_pos, herb_target, self.COLOR_WITHDRAW, current_time,
            label="Withdraw grimy herbs"
        )
        post_withdraw_delay = self.timing.get_post_action_delay(ActionType.WITHDRAW)
        current_time = self._add_delay(current_time, post_withdraw_delay)

        # === STATE: BANKING_CLOSE ===
        # Random choice: ESC (70%) or click close button (30%)
        use_esc = self._rng.random() < self.esc_chance

        if use_esc:
            current_time = self._simulate_keypress("Escape", current_time)
        else:
            close_target = ClickTarget(
                center_x=close_button_pos[0],
                center_y=close_button_pos[1],
                width=21, height=21,
            )
            current_pos, current_time = self._simulate_move_to_target(
                current_pos, close_target, self.COLOR_CLOSE_BANK, current_time,
                label="Close bank"
            )

        post_close_delay = self.timing.get_post_action_delay(ActionType.CLOSE_BANK)
        current_time = self._add_delay(current_time, post_close_delay)

        # State transition: bank is closed, inventory has grimy herbs
        self._add_state_transition(current_time, GameState.INVENTORY_GRIMY)

        # === STATE: CLEANING ===
        # Click each grimy herb in inventory
        herbs_to_clean = min(num_grimy_herbs, len(inventory_slots))
        for i in range(herbs_to_clean):
            slot_pos = inventory_slots[i]
            inv_cfg = self.config.window.get("inventory", {})

            slot_target = ClickTarget(
                center_x=slot_pos[0],
                center_y=slot_pos[1],
                width=inv_cfg.get("slot_width", 42),
                height=inv_cfg.get("slot_height", 36),
            )
            current_pos, current_time = self._simulate_move_to_target(
                current_pos, slot_target, self.COLOR_INVENTORY, current_time,
                label=f"Clean herb {i+1}"
            )

            # Delay between herb clicks (timing.get_delay(ActionType.CLICK_HERB))
            herb_delay = self.timing.get_delay(ActionType.CLICK_HERB)
            current_time = self._add_delay(current_time, herb_delay)

    def init_pygame(self):
        """Initialize pygame display."""
        pygame.init()
        pygame.display.set_caption("Bot Movement Visualization (Using Actual Bot Logic)")
        self.screen = pygame.display.set_mode((self.width, self.height))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("monospace", 16)
        self.font_large = pygame.font.SysFont("monospace", 20, bold=True)
        self._alpha_surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)

        # Convert screenshot to pygame surface (BGR to RGB) for fallback
        screenshot_rgb = self.screenshot[:, :, ::-1].copy()
        self.background = pygame.surfarray.make_surface(screenshot_rgb.swapaxes(0, 1))

        # Load state-specific backgrounds
        self._load_state_backgrounds()

    def _load_state_backgrounds(self):
        """Load or create state-specific background images."""
        print("Loading state backgrounds...")

        # Try to load real screenshots
        screenshots = self.load_screenshots()

        # Create demo backgrounds for any missing states
        demo_backgrounds = self.create_demo_backgrounds()

        # Merge: use real screenshots where available, demo otherwise
        for state in GameState:
            if state in screenshots:
                # Convert loaded screenshot (BGR) to pygame surface
                img = screenshots[state]
                img_rgb = img[:, :, ::-1].copy()
                self.backgrounds[state] = pygame.surfarray.make_surface(img_rgb.swapaxes(0, 1))
            elif state in demo_backgrounds:
                # Use demo background
                img = demo_backgrounds[state]
                img_rgb = img[:, :, ::-1].copy()
                self.backgrounds[state] = pygame.surfarray.make_surface(img_rgb.swapaxes(0, 1))
                print(f"  Using demo background for {state.value}")
            else:
                # Fallback to main screenshot
                self.backgrounds[state] = self.background
                print(f"  Using fallback for {state.value}")

    def get_thickness_from_delay(self, delay: float) -> int:
        """Calculate line thickness from delay (slower = thicker)."""
        min_delay, max_delay = 0.003, 0.06
        normalized = (delay - min_delay) / (max_delay - min_delay)
        normalized = max(0, min(1, normalized))
        return int(1 + normalized * 6)

    def draw_path_with_alpha(self, p1: tuple[int, int], p2: tuple[int, int],
                             thickness: int, color: tuple[int, int, int], alpha: int = 100):
        """Draw a line segment with alpha transparency to shared alpha surface."""
        pygame.draw.line(self._alpha_surface, (*color, alpha), p1, p2, thickness)

    def draw_cursor(self, pos: tuple[int, int], clicking: bool = False):
        """Draw the cursor ball."""
        radius = 12 if clicking else 8
        color = self.COLOR_CLICK if clicking else self.COLOR_CURSOR

        # Outer glow
        glow_surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        pygame.draw.circle(glow_surface, (*color, 100), pos, radius + 4)
        self.screen.blit(glow_surface, (0, 0))

        # Main circle
        pygame.draw.circle(self.screen, color, pos, radius)
        # Inner highlight
        pygame.draw.circle(self.screen, (255, 255, 255), (pos[0] - 2, pos[1] - 2), radius // 3)

    def draw_click_marker(self, pos: tuple[int, int], age: float):
        """Draw a click marker that fades with age."""
        alpha = max(0, min(255, int(255 * (1 - age / 2.0))))
        if alpha <= 0:
            return
        radius = int(8 + age * 20)
        temp_surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        pygame.draw.circle(temp_surface, (*self.COLOR_CLICK, alpha), pos, radius, 2)
        self.screen.blit(temp_surface, (0, 0))

    def draw_debug_targets(self):
        """Draw rectangles around all click targets for debugging."""
        for target, label, color in self.debug_targets:
            # Draw target rectangle
            rect = pygame.Rect(
                target.center_x - target.width // 2,
                target.center_y - target.height // 2,
                target.width,
                target.height
            )
            pygame.draw.rect(self.screen, color, rect, 2)

            # Draw center crosshair
            cx, cy = target.center_x, target.center_y
            pygame.draw.line(self.screen, color, (cx - 5, cy), (cx + 5, cy), 1)
            pygame.draw.line(self.screen, color, (cx, cy - 5), (cx, cy + 5), 1)

            # Draw label
            if label:
                label_surface = self.font.render(label, True, color)
                self.screen.blit(label_surface, (rect.x, rect.y - 18))

    def draw_keypress_list(self, visible_keypresses: list[KeypressEvent]):
        """Draw keypress events in bottom-left corner."""
        if not visible_keypresses:
            return

        padding = 10
        line_height = 24
        box_width = 220
        box_height = min(len(visible_keypresses), 8) * line_height + padding * 2

        # Semi-transparent background
        bg_rect = pygame.Rect(padding, self.height - box_height - padding, box_width, box_height)
        bg_surface = pygame.Surface((box_width, box_height), pygame.SRCALPHA)
        bg_surface.fill((0, 0, 0, 180))
        self.screen.blit(bg_surface, bg_rect.topleft)

        # Header
        header = self.font.render("Keypresses:", True, (200, 200, 200))
        self.screen.blit(header, (padding + 5, self.height - box_height - padding + 5))

        # Draw each keypress (show last 7)
        for i, event in enumerate(visible_keypresses[-7:]):
            y = self.height - box_height - padding + padding + 20 + i * line_height
            text = f"{event.index}. {event.key_name} ({int(event.duration_ms)}ms)"
            text_surface = self.font.render(text, True, self.COLOR_TEXT)
            self.screen.blit(text_surface, (padding + 10, y))

    def draw_status(self, current_time: float, paused: bool, speed: float, total_duration: float,
                     game_state: Optional[GameState] = None):
        """Draw status info in top-right."""
        status_text = f"{'PAUSED' if paused else 'PLAYING'} | Speed: {speed:.1f}x | Time: {current_time:.2f}s / {total_duration:.2f}s"
        text_surface = self.font.render(status_text, True, self.COLOR_TEXT)
        text_rect = text_surface.get_rect(topright=(self.width - 10, 10))

        bg_rect = text_rect.inflate(10, 6)
        bg_surface = pygame.Surface(bg_rect.size, pygame.SRCALPHA)
        bg_surface.fill((0, 0, 0, 180))
        self.screen.blit(bg_surface, bg_rect.topleft)
        self.screen.blit(text_surface, text_rect)

        # Draw game state indicator
        if game_state:
            state_text = f"State: {game_state.value}"
            state_surface = self.font.render(state_text, True, (150, 200, 255))
            state_rect = state_surface.get_rect(topright=(self.width - 10, 32))
            state_bg_rect = state_rect.inflate(10, 6)
            state_bg_surface = pygame.Surface(state_bg_rect.size, pygame.SRCALPHA)
            state_bg_surface.fill((0, 0, 0, 180))
            self.screen.blit(state_bg_surface, state_bg_rect.topleft)
            self.screen.blit(state_surface, state_rect)

    def draw_instructions(self):
        """Draw control instructions."""
        instructions = "SPACE: Pause | R: Restart | +/-: Speed | Q: Quit"
        text_surface = self.font.render(instructions, True, (200, 200, 200))
        text_rect = text_surface.get_rect(midbottom=(self.width // 2, self.height - 10))
        self.screen.blit(text_surface, text_rect)

    def draw_action_label(self, current_time: float):
        """Draw current action label."""
        current_label = ""
        for action in self.actions:
            if action.action_type == "move" and action.start_time <= current_time < action.end_time:
                segment = action.data.get("segment")
                if segment and segment.label:
                    current_label = segment.label
                    break

        if current_label:
            text_surface = self.font_large.render(current_label, True, self.COLOR_TEXT)
            text_rect = text_surface.get_rect(midtop=(self.width // 2, 10))
            bg_rect = text_rect.inflate(20, 10)
            bg_surface = pygame.Surface(bg_rect.size, pygame.SRCALPHA)
            bg_surface.fill((0, 0, 0, 180))
            self.screen.blit(bg_surface, bg_rect.topleft)
            self.screen.blit(text_surface, text_rect)

    def get_cursor_position_at_time(self, t: float) -> tuple[tuple[int, int], bool]:
        """Get cursor position at given time.

        Optimized with reverse iteration and early termination since actions are chronological.
        """
        is_clicking = False
        cursor_pos = (self.width // 2, self.height // 2)

        # Iterate in reverse since actions are chronological - find relevant action faster
        for action in reversed(self.actions):
            # Skip actions that haven't started yet
            if action.start_time > t:
                continue

            if action.action_type == "move":
                if action.start_time <= t < action.end_time:
                    # Currently moving
                    segment = action.data["segment"]
                    progress = (t - action.start_time) / (action.end_time - action.start_time)
                    point_index = int(progress * (len(segment.points) - 1))
                    point_index = min(point_index, len(segment.points) - 1)
                    cursor_pos = segment.points[point_index]
                    break
                elif action.end_time <= t:
                    # Most recent completed movement
                    cursor_pos = action.data["segment"].points[-1]
                    break

            elif action.action_type == "click":
                if action.start_time <= t < action.end_time:
                    is_clicking = True
                    # Don't break - still need cursor position from move action

        return cursor_pos, is_clicking

    def get_drawn_segments_at_time(self, t: float) -> list[tuple[PathSegment, int]]:
        """Get path segments to draw at given time.

        Uses incremental caching to avoid O(n) scans each frame.
        """
        # Reset cache if time goes backwards (restart)
        if t < self._last_cache_time:
            self._completed_segments_cache = []
            self._last_cache_time = -1.0

        # Start with cached completed segments
        result = list(self._completed_segments_cache)
        cache_size = len(self._completed_segments_cache)

        # Scan only actions beyond current cache
        for i, action in enumerate(self.actions):
            if action.action_type != "move":
                continue
            segment = action.data["segment"]

            if action.end_time <= t:
                # Check if this segment is already cached
                if len(result) <= cache_size or (segment, len(segment.points)) not in self._completed_segments_cache:
                    completed = (segment, len(segment.points))
                    if completed not in result:
                        result.append(completed)
                        # Add to cache for future frames
                        if completed not in self._completed_segments_cache:
                            self._completed_segments_cache.append(completed)
            elif action.start_time <= t < action.end_time:
                # In-progress segment
                progress = (t - action.start_time) / (action.end_time - action.start_time)
                points_drawn = int(progress * len(segment.points))
                result.append((segment, points_drawn))

        self._last_cache_time = t
        return result

    def run(self):
        """Run the visualization loop."""
        self.init_pygame()

        running = True
        paused = False
        speed = 1.0
        current_time = 0.0
        last_update = time.time()
        visible_keypresses: list[KeypressEvent] = []

        # Calculate total duration
        if self.actions:
            total_duration = max(a.end_time for a in self.actions) + 0.5
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
                    if event.key in (pygame.K_q, pygame.K_ESCAPE):
                        running = False
                    elif event.key == pygame.K_SPACE:
                        paused = not paused
                    elif event.key == pygame.K_r:
                        current_time = 0
                        visible_keypresses = []
                        self.current_state = GameState.WORLD_VIEW
                        # Clear segment cache on restart
                        self._completed_segments_cache = []
                        self._last_cache_time = -1.0
                    elif event.key in (pygame.K_PLUS, pygame.K_EQUALS):
                        speed = min(5.0, speed + 0.5)
                    elif event.key == pygame.K_MINUS:
                        speed = max(0.25, speed - 0.5)

            # Update time
            if not paused:
                current_time += dt * speed
                if current_time > total_duration:
                    current_time = 0
                    visible_keypresses = []
                    # Clear segment cache on loop
                    self._completed_segments_cache = []
                    self._last_cache_time = -1.0

            # Update visible keypresses
            for event in self.keypress_events:
                if event.timestamp <= current_time and event not in visible_keypresses:
                    visible_keypresses.append(event)

            # Clear with background (use state-specific background)
            game_state = self.get_game_state_at_time(current_time)
            background = self.backgrounds.get(game_state, self.background)
            self.screen.blit(background, (0, 0))

            # Draw debug target rectangles if enabled
            if self.debug_mode:
                self.draw_debug_targets()

            # Clear alpha surface once, draw all segments, blit once
            self._alpha_surface.fill((0, 0, 0, 0))

            # Draw path segments
            segments_to_draw = self.get_drawn_segments_at_time(current_time)
            for segment, points_count in segments_to_draw:
                for i in range(min(points_count - 1, len(segment.points) - 1)):
                    p1 = segment.points[i]
                    p2 = segment.points[i + 1]
                    delay = segment.delays[i] if i < len(segment.delays) else 0.01
                    thickness = self.get_thickness_from_delay(delay)
                    color = self.COLOR_OVERSHOOT if segment.is_overshoot else segment.color
                    self.draw_path_with_alpha(p1, p2, thickness, color, alpha=100)

            # Blit all path segments at once
            self.screen.blit(self._alpha_surface, (0, 0))

            # Draw click markers (skip faded ones for performance)
            for click in self.click_events:
                if click.timestamp <= current_time:
                    age = current_time - click.timestamp
                    if age < 2.0:
                        self.draw_click_marker((click.x, click.y), age)

            # Draw cursor
            cursor_pos, is_clicking = self.get_cursor_position_at_time(current_time)
            self.draw_cursor(cursor_pos, is_clicking)

            # Draw UI
            self.draw_keypress_list(visible_keypresses)
            self.draw_status(current_time, paused, speed, total_duration, game_state)
            self.draw_action_label(current_time)
            self.draw_instructions()

            pygame.display.flip()
            self.clock.tick(60)

        pygame.quit()


def main():
    parser = argparse.ArgumentParser(description="Visualize bot movements using actual bot logic")
    parser.add_argument("-c", "--config", type=str, default=None, help="Path to bot config file")
    parser.add_argument("--demo", action="store_true", help="Run without RuneLite (demo mode)")
    parser.add_argument("--herbs", type=int, default=28, help="Number of herbs to clean (default: 28)")
    parser.add_argument("--with-deposit", action="store_true", help="Include deposit step (has clean herbs)")
    parser.add_argument("--debug", action="store_true", help="Show click target rectangles for debugging positions")
    args = parser.parse_args()

    print("Bot Movement Visualizer")
    print("=" * 50)
    print("Using ACTUAL bot logic from BotController")
    print("=" * 50)

    # Initialize visualizer with bot config
    visualizer = BotMovementVisualizer(args.config)
    visualizer.debug_mode = args.debug

    # Capture screenshot
    if not args.demo:
        print("Looking for RuneLite window...")
        if not visualizer.capture_screenshot():
            print("WARNING: Could not find RuneLite window!")
            print("Running in demo mode...")
            visualizer.create_demo_screenshot()
        else:
            print(f"Captured {visualizer.width}x{visualizer.height} screenshot")
    else:
        print("Running in demo mode (no RuneLite)")
        visualizer.create_demo_screenshot()

    # Detect UI positions from screenshots using template matching
    print("Detecting UI positions from screenshots...")
    screenshots = visualizer.load_screenshots()
    visualizer.detected_positions = visualizer.detect_ui_positions(screenshots)

    # Simulate full cycle
    print(f"Simulating herb cleaning cycle ({args.herbs} herbs)...")
    visualizer.simulate_full_cycle(
        has_clean_herbs=args.with_deposit,
        num_grimy_herbs=args.herbs,
    )

    print(f"Generated {len(visualizer.path_segments)} movement paths")
    print(f"Generated {len(visualizer.keypress_events)} keypress events")
    print(f"Generated {len(visualizer.click_events)} click events")
    print()
    print("Controls:")
    print("  SPACE  - Pause/Resume")
    print("  R      - Restart")
    print("  +/-    - Adjust speed")
    print("  Q/ESC  - Quit")
    print()
    print("Starting visualization...")

    visualizer.run()
    print("Done!")


if __name__ == "__main__":
    main()
