"""Main bot controller - orchestrates all components."""

import logging
import time
from typing import Optional

import numpy as np
from pynput.mouse import Button

from .config_manager import ConfigManager
from .state_machine import HerbCleaningStateMachine, BotState
from ..vision.screen_capture import ScreenCapture
from ..vision.template_matcher import TemplateMatcher
from ..vision.inventory_detector import InventoryDetector
from ..vision.bank_detector import BankDetector
from ..input.mouse_controller import MouseController
from ..input.bezier_movement import MovementConfig
from ..input.click_handler import ClickConfig, ClickTarget
from ..input.keyboard_controller import KeyboardController
from ..anti_detection.timing_randomizer import TimingRandomizer, ActionType, TimingConfig
from ..anti_detection.fatigue_simulator import FatigueSimulator, FatigueConfig
from ..anti_detection.break_scheduler import BreakScheduler, BreakConfig, BreakType
from ..anti_detection.attention_drift import AttentionDrift, DriftConfig
from ..safety.emergency_stop import EmergencyStop
from ..safety.session_tracker import SessionTracker, SessionConfig


class BotController:
    """Main controller for herb cleaning bot."""

    def __init__(self, config_path: Optional[str] = None):
        """Initialize bot controller.

        Args:
            config_path: Path to config file
        """
        self._logger = logging.getLogger(__name__)

        # Load configuration
        self.config = ConfigManager(config_path)

        # Initialize state machine
        self.state_machine = HerbCleaningStateMachine()

        # Initialize vision components
        self.screen = ScreenCapture(self.config.window.get("title", "RuneLite"))
        self.template_matcher = TemplateMatcher(
            templates_dir=self.config.templates_dir,
            confidence_threshold=self.config.vision.get("confidence_threshold", 0.80),
            multi_scale=self.config.vision.get("multi_scale", True),
            scale_range=tuple(self.config.vision.get("scale_range", [0.8, 1.2])),
            scale_steps=self.config.vision.get("scale_steps", 5),
        )
        self.inventory = InventoryDetector(
            screen_capture=self.screen,
            template_matcher=self.template_matcher,
            inventory_config=self.config.window.get("inventory", {}),
            grimy_templates=self.config.get("herbs.grimy", []),
            auto_detect=self.config.window.get("auto_detect_inventory", True),
        )
        self.bank = BankDetector(
            screen_capture=self.screen,
            template_matcher=self.template_matcher,
            bank_config=self.config.get_section("bank"),
            grimy_templates=self.config.get("herbs.grimy", []),
        )

        # Initialize input components
        mouse_cfg = self.config.mouse
        self.mouse = MouseController(
            movement_config=MovementConfig(
                speed_range=tuple(mouse_cfg.get("speed_range", [200, 400])),
                overshoot_chance=mouse_cfg.get("overshoot_chance", 0.30),
                overshoot_distance=tuple(mouse_cfg.get("overshoot_distance", [5, 15])),
                curve_variance=mouse_cfg.get("curve_variance", 0.3),
            ),
            click_config=ClickConfig(
                position_sigma_ratio=self.config.click.get("position_sigma_ratio", 6),
                duration_mean=self.config.click.get("duration_mean", 100),
                duration_min=self.config.click.get("duration_min", 50),
                duration_max=self.config.click.get("duration_max", 200),
            ),
        )
        self.keyboard = KeyboardController()

        # Initialize anti-detection components
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

        fatigue_cfg = self.config.fatigue
        self.fatigue = FatigueSimulator(
            config=FatigueConfig(
                onset_minutes=fatigue_cfg.get("onset_minutes", 30),
                max_slowdown_percent=fatigue_cfg.get("max_slowdown_percent", 50),
                misclick_rate_start=fatigue_cfg.get("misclick_rate_start", 0.01),
                misclick_rate_max=fatigue_cfg.get("misclick_rate_max", 0.05),
            )
        )

        break_cfg = self.config.breaks
        self.breaks = BreakScheduler(
            config=BreakConfig(
                micro_interval=tuple(break_cfg.get("micro", {}).get("interval", [480, 900])),
                micro_duration=tuple(break_cfg.get("micro", {}).get("duration", [2, 10])),
                long_interval=tuple(break_cfg.get("long", {}).get("interval", [2700, 5400])),
                long_duration=tuple(break_cfg.get("long", {}).get("duration", [60, 300])),
            )
        )

        attention_cfg = self.config.attention
        self.attention = AttentionDrift(
            config=DriftConfig(
                drift_chance=attention_cfg.get("drift_chance", 0.03),
                drift_targets=attention_cfg.get("drift_targets", None),
            )
        )

        # Initialize safety components
        safety_cfg = self.config.safety
        self.emergency_stop = EmergencyStop(
            stop_key=safety_cfg.get("emergency_stop_key", "f12"),
            on_stop_callback=self._handle_emergency_stop,
        )
        self.session = SessionTracker(
            config=SessionConfig(
                max_session_hours=safety_cfg.get("max_session_hours", 4),
                stats_log_interval=safety_cfg.get("stats_log_interval", 60),
            )
        )

        self._is_running = False
        self._rng = np.random.default_rng()

    def _handle_emergency_stop(self) -> None:
        """Handle emergency stop trigger."""
        self._logger.warning("EMERGENCY STOP TRIGGERED")
        self._is_running = False
        self.mouse.set_stop_flag(True)
        self.keyboard.set_stop_flag(True)

        if not self.state_machine.is_stopped():
            self.state_machine.emergency()

    def start(self) -> None:
        """Start the bot."""
        self._logger.info("Starting herb cleaning bot...")

        # Find RuneLite window
        if not self.screen.find_window():
            raise RuntimeError("Could not find RuneLite window")

        self._logger.info("Found RuneLite window at %s", self.screen.window_bounds)

        # Start components
        self.emergency_stop.start_listening()
        self.session.start_session()
        self.fatigue.start_session()
        self.breaks.start_session()

        self._is_running = True

        try:
            self._main_loop()
        except Exception as e:
            self._logger.exception("Bot error: %s", e)
            self.state_machine.set_error(str(e))
            if not self.state_machine.is_stopped():
                self.state_machine.handle_error()
        finally:
            self.stop()

    def stop(self) -> None:
        """Stop the bot."""
        self._logger.info("Stopping bot...")
        self._is_running = False

        self.emergency_stop.stop_listening()
        stats = self.session.end_session()

        self._logger.info("Final stats: %s", self.session.get_status_string())

        if not self.state_machine.is_stopped():
            if self.state_machine.current_state == self.state_machine.emergency_stop:
                self.state_machine.stop()
            elif self.state_machine.can_transition_to("stopped"):
                self.state_machine.stop()

    def _main_loop(self) -> None:
        """Main bot loop."""
        while self._is_running and not self.emergency_stop.is_stopped():
            # Check for session end
            if self.session.should_end_session():
                self._logger.info("Max session time reached")
                break

            # Update fatigue multiplier
            self.timing.set_fatigue_multiplier(self.fatigue.get_slowdown_multiplier())

            # Check for breaks
            scheduled_break = self.breaks.check_break_needed()
            if scheduled_break:
                self._handle_break(scheduled_break)
                continue

            # Check for attention drift
            if self.attention.should_drift(self.fatigue.get_fatigue_level()):
                self._handle_attention_drift()

            # Check for attention lapse from fatigue
            if self.fatigue.should_have_attention_lapse():
                lapse_duration = self.fatigue.get_attention_lapse_duration()
                self._logger.debug("Attention lapse: %.1fs", lapse_duration)
                time.sleep(lapse_duration)
                continue

            # Log stats periodically
            if self.session.should_log_stats():
                self.session.log_stats()

            # Execute current state
            state = self.state_machine.get_current_state()
            self._execute_state(state)

    def _execute_state(self, state: BotState) -> None:
        """Execute actions for current state.

        Args:
            state: Current bot state
        """
        if state == BotState.IDLE:
            self._handle_idle()
        elif state == BotState.BANKING_OPEN:
            self._handle_banking_open()
        elif state == BotState.BANKING_DEPOSIT:
            self._handle_banking_deposit()
        elif state == BotState.BANKING_WITHDRAW:
            self._handle_banking_withdraw()
        elif state == BotState.BANKING_CLOSE:
            self._handle_banking_close()
        elif state == BotState.CLEANING:
            self._handle_cleaning()
        elif state == BotState.ERROR:
            self._handle_error()

    def _handle_idle(self) -> None:
        """Handle idle state - start banking."""
        self._logger.debug("Idle -> Starting bank sequence")
        self.state_machine.start_banking()

    def _handle_banking_open(self) -> None:
        """Handle opening the bank."""
        self._logger.debug("Opening bank...")

        # Find bank booth
        booth_pos = self.bank.find_bank_booth()
        if not booth_pos:
            self._logger.warning("Could not find bank booth")
            time.sleep(1)
            return

        # Click bank booth
        target = ClickTarget(
            center_x=booth_pos[0],
            center_y=booth_pos[1],
            width=40,
            height=40,
        )

        completed, _ = self.mouse.click_at_target(
            target,
            misclick_rate=self.fatigue.get_misclick_rate(),
        )

        if not completed:
            return

        # Wait for bank to open
        time.sleep(self.timing.get_delay(ActionType.OPEN_BANK))

        # Verify bank opened
        if self.bank.is_bank_open():
            time.sleep(self.timing.get_post_action_delay(ActionType.OPEN_BANK))

            # Check if we have herbs to deposit
            self.inventory.detect_inventory_state()
            if self.inventory.count_clean_herbs() > 0:
                self.state_machine.deposit_herbs()
            else:
                self.state_machine.skip_deposit()
        else:
            self._logger.warning("Bank did not open")
            time.sleep(0.5)

    def _handle_banking_deposit(self) -> None:
        """Handle depositing cleaned herbs."""
        self._logger.debug("Depositing herbs...")

        # Find deposit button
        deposit_pos = self.bank.find_deposit_button()
        if not deposit_pos:
            self._logger.warning("Could not find deposit button")
            # Try clicking deposit all anyway at expected position
            return

        # Click deposit
        target = ClickTarget(
            center_x=deposit_pos[0],
            center_y=deposit_pos[1],
            width=30,
            height=30,
        )

        completed, _ = self.mouse.click_at_target(
            target,
            misclick_rate=self.fatigue.get_misclick_rate(),
        )

        if completed:
            time.sleep(self.timing.get_post_action_delay(ActionType.DEPOSIT))
            self.state_machine.withdraw_herbs()

    def _handle_banking_withdraw(self) -> None:
        """Handle withdrawing grimy herbs."""
        self._logger.debug("Withdrawing grimy herbs...")

        # Find grimy herbs in bank
        herb_pos = self.bank.find_grimy_herb_in_bank()
        if not herb_pos:
            self._logger.warning("Could not find grimy herbs in bank")
            # End session if no herbs
            self._is_running = False
            return

        # Click grimy herbs (withdraw all)
        target = ClickTarget(
            center_x=herb_pos[0],
            center_y=herb_pos[1],
            width=36,
            height=32,
        )

        completed, _ = self.mouse.click_at_target(
            target,
            misclick_rate=self.fatigue.get_misclick_rate(),
        )

        if completed:
            time.sleep(self.timing.get_post_action_delay(ActionType.WITHDRAW))
            self.session.record_bank_trip()
            self.state_machine.close_bank()

    def _handle_banking_close(self) -> None:
        """Handle closing the bank.

        Randomly chooses between ESC key and clicking close button
        for human-like variation.
        """
        self._logger.debug("Closing bank...")

        # Random choice: ESC key or click close button
        esc_chance = self.config.get("bank.esc_chance", 0.70)
        use_esc = self._rng.random() < esc_chance

        if use_esc:
            # Press ESC key (70% default)
            self._logger.debug("Closing bank with ESC")
            self.keyboard.press_escape()
        else:
            # Click close button (30% default)
            self._logger.debug("Closing bank by clicking X")
            close_pos = self.bank.find_close_button()

            if close_pos:
                target = ClickTarget(
                    center_x=close_pos[0],
                    center_y=close_pos[1],
                    width=20,
                    height=20,
                )
                self.mouse.click_at_target(
                    target,
                    misclick_rate=self.fatigue.get_misclick_rate(),
                )
            else:
                # Fallback to ESC if close button not found
                self._logger.warning("Close button not found, using ESC")
                self.keyboard.press_escape()

        time.sleep(self.timing.get_post_action_delay(ActionType.CLOSE_BANK))

        self.state_machine.start_cleaning()

    def _handle_cleaning(self) -> None:
        """Handle cleaning herbs."""
        # Detect inventory state
        self.inventory.detect_inventory_state()

        # Check if we need to bank
        if not self.inventory.has_grimy_herbs():
            self._logger.debug("No grimy herbs, going to bank")
            self.state_machine.start_banking()
            return

        # Get next grimy herb slot
        slot = self.inventory.get_next_grimy_slot()
        if not slot:
            self.state_machine.start_banking()
            return

        # Get screen coordinates
        screen_x, screen_y = self.inventory.get_slot_screen_coords(slot.index)

        # Create click target
        inv_config = self.config.window.get("inventory", {})
        target = ClickTarget(
            center_x=screen_x,
            center_y=screen_y,
            width=inv_config.get("slot_width", 42),
            height=inv_config.get("slot_height", 36),
        )

        # Click the herb
        start_time = time.time()

        completed, was_misclick = self.mouse.click_at_target(
            target,
            misclick_rate=self.fatigue.get_misclick_rate(),
        )

        if was_misclick:
            self.session.record_misclick()

        if completed:
            clean_time_ms = (time.time() - start_time) * 1000
            self.session.record_herb_cleaned(clean_time_ms)

            # Wait before next action
            delay = self.timing.get_delay(ActionType.CLICK_HERB)

            # Occasional think pause
            delay += self.timing.get_think_pause()

            # Micro pause
            if self.timing.should_have_micro_pause():
                delay += self.timing.get_micro_pause_duration()

            time.sleep(delay)

    def _handle_break(self, scheduled_break) -> None:
        """Handle taking a break.

        Args:
            scheduled_break: The scheduled break to take
        """
        break_type = scheduled_break.break_type
        self._logger.info("Taking %s break...", break_type.value)

        # Transition state machine
        if break_type == BreakType.MICRO:
            if self.state_machine.can_transition_to("break_micro"):
                self.state_machine.take_micro_break()
        else:
            if self.state_machine.can_transition_to("break_long"):
                self.state_machine.take_long_break()

        # Execute break
        duration = self.breaks.execute_break(scheduled_break)

        # Record break
        if break_type == BreakType.MICRO:
            self.session.record_micro_break(duration)
        else:
            self.session.record_long_break(duration)

        # Reduce fatigue
        self.fatigue.record_break(duration)

        # Resume
        if break_type == BreakType.MICRO:
            self.state_machine.resume_from_micro()
        else:
            self.state_machine.resume_from_long()

        self._logger.info("Break complete, resuming...")

    def _handle_attention_drift(self) -> None:
        """Handle attention drift."""
        target_type, position = self.attention.get_drift_target()
        self._logger.debug("Attention drift to %s", target_type.value)

        # Add window offset
        bounds = self.screen.window_bounds
        if bounds:
            position = (bounds.x + position[0], bounds.y + position[1])

        # Move to drift position
        self.mouse.move_to(position[0], position[1])

        # Stay there briefly
        duration = self.attention.get_drift_duration()
        time.sleep(duration)

        self.session.record_attention_drift()

    def _handle_error(self) -> None:
        """Handle error state."""
        self._logger.error("In error state: %s", self.state_machine.get_error())
        self.session.record_error()

        # Try to recover after delay
        time.sleep(2)

        if self.state_machine.get_error_count() < 5:
            self.state_machine.recover()
        else:
            self._logger.error("Too many errors, stopping")
            self._is_running = False
