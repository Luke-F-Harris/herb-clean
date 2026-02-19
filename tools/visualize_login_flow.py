#!/usr/bin/env python3
"""Login Flow Visualization.

Demonstrates the re-login sequence after inactivity logout:
1. inactivity_logout -> click OK button
2. play_now_state -> click Play Now button
3. logged_in_state -> click Play button
4. Back in game

Uses actual screenshots and templates to show template matching
and simulated mouse movements through the login sequence.

Usage:
    python tools/visualize_login_flow.py [--speed SPEED]

Controls:
    SPACE - Pause/Resume
    R     - Restart
    ESC   - Quit
"""

import argparse
import sys
import time
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
import pygame

# Add src to path for imports
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))


class LoginStage(Enum):
    """Stages of the login flow."""
    INACTIVITY_LOGOUT = auto()
    CLICKING_OK = auto()
    WAITING_AFTER_OK = auto()
    PLAY_NOW_SCREEN = auto()
    CLICKING_PLAY_NOW = auto()
    WAITING_AFTER_PLAY_NOW = auto()
    LOGGED_IN_SCREEN = auto()
    CLICKING_PLAY = auto()
    WAITING_AFTER_PLAY = auto()
    LOGGED_IN = auto()
    COMPLETE = auto()


@dataclass
class TemplateMatch:
    """Result of template matching."""
    found: bool
    center_x: int = 0
    center_y: int = 0
    width: int = 0
    height: int = 0
    confidence: float = 0.0


class LoginFlowVisualizer:
    """Visualizes the login flow sequence."""

    SCREENSHOT_DIR = SCRIPT_DIR / "viz_screenshots"
    TEMPLATE_DIR = PROJECT_ROOT / "config" / "templates"

    # Screenshot filenames for each stage
    SCREENSHOTS = {
        LoginStage.INACTIVITY_LOGOUT: "inactivity_logout.png",
        LoginStage.PLAY_NOW_SCREEN: "play_now_state.png",
        LoginStage.LOGGED_IN_SCREEN: "logged_in_state.png",
        LoginStage.LOGGED_IN: "world_view.png",  # Back in game
    }

    # Template filenames for buttons
    TEMPLATES = {
        "ok_button": "inactivity_logout_ok_button.png",
        "play_now": "play_now_button.png",
        "play_button": "logged_in_play_button.png",
    }

    # Colors
    COLOR_BG = (30, 30, 35)
    COLOR_TEXT = (220, 220, 220)
    COLOR_HIGHLIGHT = (100, 200, 100)
    COLOR_MATCH_BOX = (0, 255, 0)
    COLOR_MOUSE = (255, 100, 100)
    COLOR_STAGE = (255, 200, 100)

    def __init__(self, speed: float = 1.0):
        """Initialize visualizer.

        Args:
            speed: Playback speed multiplier
        """
        self.speed = speed
        self._rng = np.random.default_rng()

        # Window dimensions
        self.window_width = 1200
        self.window_height = 800

        # Load resources
        self._screenshots: dict[LoginStage, np.ndarray] = {}
        self._templates: dict[str, np.ndarray] = {}
        self._load_resources()

        # State
        self._current_stage = LoginStage.INACTIVITY_LOGOUT
        self._stage_start_time = 0.0
        self._mouse_pos = (0, 0)
        self._target_pos = (0, 0)
        self._mouse_moving = False
        self._paused = False

        # Pygame
        pygame.init()
        pygame.display.set_caption("Login Flow Visualization")
        self._screen = pygame.display.set_mode((self.window_width, self.window_height))
        self._clock = pygame.time.Clock()
        self._font = pygame.font.SysFont("monospace", 16)
        self._font_large = pygame.font.SysFont("monospace", 24, bold=True)

    def _load_resources(self) -> None:
        """Load screenshots and templates."""
        # Load screenshots
        for stage, filename in self.SCREENSHOTS.items():
            path = self.SCREENSHOT_DIR / filename
            if path.exists():
                img = cv2.imread(str(path))
                if img is not None:
                    self._screenshots[stage] = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                    print(f"Loaded screenshot: {filename}")
            else:
                print(f"Warning: Screenshot not found: {path}")

        # Load templates
        for name, filename in self.TEMPLATES.items():
            path = self.TEMPLATE_DIR / filename
            if path.exists():
                img = cv2.imread(str(path))
                if img is not None:
                    self._templates[name] = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                    print(f"Loaded template: {filename}")
            else:
                print(f"Warning: Template not found: {path}")

    def _match_template(
        self, screenshot: np.ndarray, template_name: str
    ) -> TemplateMatch:
        """Match a template on a screenshot.

        Args:
            screenshot: Screenshot image
            template_name: Name of template to match

        Returns:
            TemplateMatch result
        """
        if template_name not in self._templates:
            return TemplateMatch(found=False)

        template = self._templates[template_name]

        # Convert to grayscale for matching
        gray_screen = cv2.cvtColor(screenshot, cv2.COLOR_RGB2GRAY)
        gray_template = cv2.cvtColor(template, cv2.COLOR_RGB2GRAY)

        # Multi-scale template matching
        best_match = TemplateMatch(found=False)
        scales = [0.8, 0.9, 1.0, 1.1, 1.2]

        for scale in scales:
            if scale != 1.0:
                width = int(gray_template.shape[1] * scale)
                height = int(gray_template.shape[0] * scale)
                scaled = cv2.resize(gray_template, (width, height))
            else:
                scaled = gray_template

            if scaled.shape[0] > gray_screen.shape[0] or scaled.shape[1] > gray_screen.shape[1]:
                continue

            result = cv2.matchTemplate(gray_screen, scaled, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)

            if max_val > best_match.confidence and max_val > 0.7:
                h, w = scaled.shape
                best_match = TemplateMatch(
                    found=True,
                    center_x=max_loc[0] + w // 2,
                    center_y=max_loc[1] + h // 2,
                    width=w,
                    height=h,
                    confidence=max_val,
                )

        return best_match

    def _get_stage_screenshot(self) -> Optional[np.ndarray]:
        """Get screenshot for current display stage."""
        display_stage = self._current_stage

        # Map intermediate stages to their screenshots
        if display_stage in (LoginStage.CLICKING_OK, LoginStage.WAITING_AFTER_OK):
            display_stage = LoginStage.INACTIVITY_LOGOUT
        elif display_stage in (LoginStage.CLICKING_PLAY_NOW, LoginStage.WAITING_AFTER_PLAY_NOW):
            display_stage = LoginStage.PLAY_NOW_SCREEN
        elif display_stage in (LoginStage.CLICKING_PLAY, LoginStage.WAITING_AFTER_PLAY):
            display_stage = LoginStage.LOGGED_IN_SCREEN
        elif display_stage == LoginStage.COMPLETE:
            display_stage = LoginStage.LOGGED_IN

        return self._screenshots.get(display_stage)

    def _get_current_button_template(self) -> Optional[str]:
        """Get template name for current stage's button."""
        if self._current_stage in (LoginStage.INACTIVITY_LOGOUT, LoginStage.CLICKING_OK):
            return "ok_button"
        elif self._current_stage in (LoginStage.PLAY_NOW_SCREEN, LoginStage.CLICKING_PLAY_NOW):
            return "play_now"
        elif self._current_stage in (LoginStage.LOGGED_IN_SCREEN, LoginStage.CLICKING_PLAY):
            return "play_button"
        return None

    def _advance_stage(self) -> None:
        """Advance to next stage."""
        stage_order = list(LoginStage)
        current_idx = stage_order.index(self._current_stage)

        if current_idx < len(stage_order) - 1:
            self._current_stage = stage_order[current_idx + 1]
            self._stage_start_time = time.time()
            print(f"Stage: {self._current_stage.name}")

    def _get_stage_duration(self) -> float:
        """Get duration for current stage in seconds."""
        base_durations = {
            LoginStage.INACTIVITY_LOGOUT: 2.0,
            LoginStage.CLICKING_OK: 1.0,
            LoginStage.WAITING_AFTER_OK: 3.0,
            LoginStage.PLAY_NOW_SCREEN: 1.5,
            LoginStage.CLICKING_PLAY_NOW: 1.0,
            LoginStage.WAITING_AFTER_PLAY_NOW: 4.0,
            LoginStage.LOGGED_IN_SCREEN: 1.5,
            LoginStage.CLICKING_PLAY: 1.0,
            LoginStage.WAITING_AFTER_PLAY: 5.0,
            LoginStage.LOGGED_IN: 3.0,
        }
        return base_durations.get(self._current_stage, 1.0) / self.speed

    def _update(self, dt: float) -> None:
        """Update simulation state.

        Args:
            dt: Delta time in seconds
        """
        if self._paused or self._current_stage == LoginStage.COMPLETE:
            return

        elapsed = time.time() - self._stage_start_time
        duration = self._get_stage_duration()

        # Check if stage should advance
        if elapsed >= duration:
            self._advance_stage()
            return

        # Update mouse position for clicking stages
        if self._current_stage in (
            LoginStage.CLICKING_OK,
            LoginStage.CLICKING_PLAY_NOW,
            LoginStage.CLICKING_PLAY,
        ):
            # Interpolate mouse toward target
            progress = min(1.0, elapsed / (duration * 0.7))  # Reach target at 70%
            eased = self._ease_out_quad(progress)

            start_x, start_y = self._mouse_pos
            target_x, target_y = self._target_pos
            self._mouse_pos = (
                int(start_x + (target_x - start_x) * eased),
                int(start_y + (target_y - start_y) * eased),
            )

    def _ease_out_quad(self, t: float) -> float:
        """Quadratic ease-out function."""
        return 1 - (1 - t) ** 2

    def _render(self) -> None:
        """Render current state."""
        self._screen.fill(self.COLOR_BG)

        # Get and render screenshot
        screenshot = self._get_stage_screenshot()
        if screenshot is not None:
            self._render_screenshot(screenshot)

        # Render UI overlay
        self._render_ui()

        pygame.display.flip()

    def _render_screenshot(self, screenshot: np.ndarray) -> None:
        """Render screenshot with template match overlay.

        Args:
            screenshot: Screenshot to render
        """
        # Scale screenshot to fit display area
        display_width = self.window_width - 40
        display_height = self.window_height - 150

        h, w = screenshot.shape[:2]
        scale = min(display_width / w, display_height / h)
        new_w, new_h = int(w * scale), int(h * scale)

        scaled = cv2.resize(screenshot, (new_w, new_h))

        # Convert to pygame surface
        surface = pygame.surfarray.make_surface(scaled.swapaxes(0, 1))

        # Position centered
        x = (self.window_width - new_w) // 2
        y = 60

        self._screen.blit(surface, (x, y))

        # Draw template match box
        template_name = self._get_current_button_template()
        if template_name and template_name in self._templates:
            match = self._match_template(screenshot, template_name)
            if match.found:
                # Scale match coordinates
                box_x = x + int(match.center_x * scale) - int(match.width * scale) // 2
                box_y = y + int(match.center_y * scale) - int(match.height * scale) // 2
                box_w = int(match.width * scale)
                box_h = int(match.height * scale)

                pygame.draw.rect(
                    self._screen,
                    self.COLOR_MATCH_BOX,
                    (box_x, box_y, box_w, box_h),
                    2,
                )

                # Set target for mouse
                self._target_pos = (
                    x + int(match.center_x * scale),
                    y + int(match.center_y * scale),
                )

                # Initialize mouse position if starting a click stage
                if self._mouse_moving is False and self._current_stage in (
                    LoginStage.CLICKING_OK,
                    LoginStage.CLICKING_PLAY_NOW,
                    LoginStage.CLICKING_PLAY,
                ):
                    # Start from random edge
                    edge = self._rng.choice(["top", "bottom", "left", "right"])
                    if edge == "top":
                        self._mouse_pos = (self._rng.integers(x, x + new_w), y - 20)
                    elif edge == "bottom":
                        self._mouse_pos = (self._rng.integers(x, x + new_w), y + new_h + 20)
                    elif edge == "left":
                        self._mouse_pos = (x - 20, self._rng.integers(y, y + new_h))
                    else:
                        self._mouse_pos = (x + new_w + 20, self._rng.integers(y, y + new_h))
                    self._mouse_moving = True

        # Draw mouse cursor
        if self._current_stage in (
            LoginStage.CLICKING_OK,
            LoginStage.CLICKING_PLAY_NOW,
            LoginStage.CLICKING_PLAY,
        ):
            pygame.draw.circle(
                self._screen,
                self.COLOR_MOUSE,
                self._mouse_pos,
                8,
            )
            pygame.draw.circle(
                self._screen,
                (255, 255, 255),
                self._mouse_pos,
                8,
                2,
            )

    def _render_ui(self) -> None:
        """Render UI elements."""
        # Title
        title = self._font_large.render("Login Flow Visualization", True, self.COLOR_TEXT)
        self._screen.blit(title, (20, 15))

        # Current stage
        stage_text = f"Stage: {self._current_stage.name}"
        stage_surface = self._font.render(stage_text, True, self.COLOR_STAGE)
        self._screen.blit(stage_surface, (self.window_width - 300, 20))

        # Instructions
        instructions = [
            "Controls:",
            "SPACE - Pause/Resume",
            "R - Restart",
            "ESC - Quit",
        ]

        y_offset = self.window_height - 80
        for line in instructions:
            text = self._font.render(line, True, self.COLOR_TEXT)
            self._screen.blit(text, (20, y_offset))
            y_offset += 18

        # Stage description
        descriptions = {
            LoginStage.INACTIVITY_LOGOUT: "Detected: Inactivity logout dialog",
            LoginStage.CLICKING_OK: "Clicking OK button...",
            LoginStage.WAITING_AFTER_OK: "Waiting for screen transition (2-4s)...",
            LoginStage.PLAY_NOW_SCREEN: "Detected: Play Now screen",
            LoginStage.CLICKING_PLAY_NOW: "Clicking Play Now button...",
            LoginStage.WAITING_AFTER_PLAY_NOW: "Waiting for screen transition (2-5s)...",
            LoginStage.LOGGED_IN_SCREEN: "Detected: Account selection screen",
            LoginStage.CLICKING_PLAY: "Clicking 'Click Here To Play' button...",
            LoginStage.WAITING_AFTER_PLAY: "Waiting for game to load (3-6s)...",
            LoginStage.LOGGED_IN: "Successfully logged back in!",
            LoginStage.COMPLETE: "Login sequence complete - returning to bot operation",
        }

        desc = descriptions.get(self._current_stage, "")
        desc_surface = self._font.render(desc, True, self.COLOR_HIGHLIGHT)
        self._screen.blit(desc_surface, (20, self.window_height - 25))

        # Paused indicator
        if self._paused:
            paused_text = self._font_large.render("PAUSED", True, (255, 100, 100))
            self._screen.blit(
                paused_text,
                (self.window_width // 2 - 50, self.window_height // 2),
            )

    def _restart(self) -> None:
        """Restart the visualization."""
        self._current_stage = LoginStage.INACTIVITY_LOGOUT
        self._stage_start_time = time.time()
        self._mouse_pos = (0, 0)
        self._mouse_moving = False
        print("Restarted visualization")

    def run(self) -> None:
        """Run the visualization loop."""
        print("Starting login flow visualization...")
        print("Press SPACE to pause, R to restart, ESC to quit")

        self._stage_start_time = time.time()
        running = True

        while running:
            dt = self._clock.tick(60) / 1000.0

            # Handle events
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    elif event.key == pygame.K_SPACE:
                        self._paused = not self._paused
                        if not self._paused:
                            self._stage_start_time = time.time()
                    elif event.key == pygame.K_r:
                        self._restart()

            self._update(dt)
            self._render()

        pygame.quit()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Visualize the login flow sequence",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--speed",
        type=float,
        default=1.0,
        help="Playback speed multiplier (default: 1.0)",
    )

    args = parser.parse_args()

    visualizer = LoginFlowVisualizer(speed=args.speed)
    visualizer.run()


if __name__ == "__main__":
    main()
