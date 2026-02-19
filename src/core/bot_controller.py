"""Main bot controller - orchestrates all components."""

import logging
import time
from typing import Optional

import numpy as np

from utils import create_rng
from pynput.mouse import Button

from .config_manager import ConfigManager
from .state_machine import HerbCleaningStateMachine, BotState
from .events import EventEmitter
from .status_aggregator import StatusAggregator
from ..vision.screen_capture import ScreenCapture
from ..vision.template_matcher import TemplateMatcher
from ..vision.inventory_detector import InventoryDetector
from ..vision.bank_detector import BankDetector
from ..input.mouse_controller import MouseController
from ..input.bezier_movement import MovementConfig
from ..input.organic_easing import OrganicEasingConfig
from ..input.click_handler import ClickConfig, ClickTarget
from ..input.keyboard_controller import KeyboardController
from ..anti_detection.timing_randomizer import TimingRandomizer, ActionType, TimingConfig
from ..anti_detection.fatigue_simulator import FatigueSimulator, FatigueConfig
from ..anti_detection.break_scheduler import BreakScheduler, BreakConfig, BreakType
from ..anti_detection.attention_drift import AttentionDrift, DriftConfig
from ..anti_detection.skill_checker import SkillChecker, SkillCheckConfig
from ..safety.emergency_stop import EmergencyStop
from ..safety.session_tracker import SessionTracker, SessionConfig
from ..safety.login_handler import LoginHandler, LoginConfig


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
        # Get inventory template path if configured
        inventory_template = self.config.window.get("inventory_template")
        inventory_template_path = None
        if inventory_template:
            inventory_template_path = self.config.templates_dir / inventory_template

        self.inventory = InventoryDetector(
            screen_capture=self.screen,
            template_matcher=self.template_matcher,
            inventory_config=self.config.window.get("inventory", {}),
            grimy_templates=self.config.get("herbs.grimy", []),
            auto_detect=self.config.window.get("auto_detect_inventory", True),
            inventory_template_path=str(inventory_template_path) if inventory_template_path else None,
            traversal_config=self.config.get_section("traversal"),
        )
        self.bank = BankDetector(
            screen_capture=self.screen,
            template_matcher=self.template_matcher,
            bank_config=self.config.get_section("bank"),
            grimy_templates=self.config.get("herbs.grimy", []),
        )

        # Initialize input components
        mouse_cfg = self.config.mouse
        cleaning_cfg = self.config.get_section("cleaning")
        hesitation_cfg = cleaning_cfg.get("hesitation", {})
        missed_click_cfg = cleaning_cfg.get("missed_click", {})
        path_cfg = self.config.get_section("path")
        speed_var_cfg = mouse_cfg.get("speed_variation", {})
        jitter_cfg = path_cfg.get("jitter", mouse_cfg.get("jitter", {}))
        imperfection_cfg = path_cfg.get("imperfection", mouse_cfg.get("imperfection", {}))
        micro_corr_cfg = imperfection_cfg.get("micro_correction", {})
        micro_pause_cfg = speed_var_cfg.get("micro_pause", {})
        multi_segment_cfg = path_cfg.get("multi_segment", {})
        organic_easing_cfg = mouse_cfg.get("organic_easing", {})

        # Post-click drift config
        post_click_drift_cfg = cleaning_cfg.get("post_click_drift", {})

        self.mouse = MouseController(
            movement_config=MovementConfig(
                speed_range=tuple(mouse_cfg.get("speed_range", [800, 1400])),
                overshoot_chance=path_cfg.get("overshoot_chance", mouse_cfg.get("overshoot_chance", 0.30)),
                overshoot_distance=tuple(path_cfg.get("overshoot_distance", mouse_cfg.get("overshoot_distance", [5, 15]))),
                curve_variance=path_cfg.get("curve_variance", mouse_cfg.get("curve_variance", 0.3)),
                # Jitter settings
                jitter_enabled=jitter_cfg.get("enabled", True),
                jitter_radius=tuple(jitter_cfg.get("radius", [1.0, 3.0])),
                jitter_points=jitter_cfg.get("points", 3),
                # Imperfection settings
                imperfection_enabled=imperfection_cfg.get("enabled", True),
                simple_curve_chance=imperfection_cfg.get("simple_curve_chance", 0.15),
                control_point_variance=imperfection_cfg.get("control_point_variance", 0.2),
                micro_correction_chance=micro_corr_cfg.get("chance", 0.3),
                micro_correction_magnitude=tuple(micro_corr_cfg.get("magnitude", [2.0, 8.0])),
                # Multi-segment curves (3-4 control points)
                multi_segment_chance=multi_segment_cfg.get("chance", 0.25),
                max_control_points=multi_segment_cfg.get("max_control_points", 4),
                # Speed variation settings
                speed_variation_enabled=speed_var_cfg.get("enabled", True),
                micro_pause_chance=micro_pause_cfg.get("chance", 0.25),
                micro_pause_duration=tuple(micro_pause_cfg.get("duration", [0.03, 0.12])),
                min_speed_factor=speed_var_cfg.get("min_speed_factor", 0.2),
                max_speed_factor=speed_var_cfg.get("max_speed_factor", 1.5),
                burst_chance=speed_var_cfg.get("burst_chance", 0.15),
                burst_speed_multiplier=speed_var_cfg.get("burst_speed_multiplier", 1.8),
                burst_duration_ratio=speed_var_cfg.get("burst_duration_ratio", 0.15),
                # Organic easing (procedural curves replacing mathematical functions)
                organic_easing_config=OrganicEasingConfig(
                    enabled=organic_easing_cfg.get("enabled", True),
                    inflection_range=tuple(organic_easing_cfg.get("inflection_range", [0.35, 0.65])),
                    power_range=tuple(organic_easing_cfg.get("power_range", [1.5, 2.5])),
                    amplitude_range=tuple(organic_easing_cfg.get("amplitude_range", [0.85, 1.0])),
                    perturbation_strength_range=tuple(organic_easing_cfg.get("perturbation_strength", [0.03, 0.08])),
                    noise_octaves=organic_easing_cfg.get("noise_octaves", 3),
                    drift_rate_range=tuple(organic_easing_cfg.get("drift_rate_range", [-0.05, 0.05])),
                    drift_curve_range=tuple(organic_easing_cfg.get("drift_curve_range", [0.5, 2.0])),
                ),
            ),
            click_config=ClickConfig(
                position_sigma_ratio=self.config.click.get("position_sigma_ratio", 6),
                duration_mean=self.config.click.get("duration_mean", 100),
                duration_min=self.config.click.get("duration_min", 50),
                duration_max=self.config.click.get("duration_max", 200),
            ),
            hesitation_chance=hesitation_cfg.get("chance", 0.15) if hesitation_cfg.get("enabled", True) else 0.0,
            hesitation_movements=tuple(hesitation_cfg.get("movements", [1, 3])),
            correction_delay=tuple(missed_click_cfg.get("correction_delay", [0.15, 0.35])),
            post_click_drift_enabled=post_click_drift_cfg.get("enabled", True),
            post_click_drift_chance=post_click_drift_cfg.get("chance", 0.6),
            post_click_drift_distance=tuple(post_click_drift_cfg.get("distance", [1, 4])),
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

        skill_check_cfg = self.config.get_section("skill_check")
        self.skill_checker = SkillChecker(
            config=SkillCheckConfig(
                enabled=skill_check_cfg.get("enabled", True),
                cooldown_interval=tuple(skill_check_cfg.get("cooldown_interval", [600, 900])),
                hover_duration=tuple(skill_check_cfg.get("hover_duration", [3.0, 8.0])),
            ),
            keyboard=self.keyboard,
            mouse=self.mouse,
            screen=self.screen,
            template_matcher=self.template_matcher,
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

        # Initialize login handler for re-login after inactivity logout
        self.login_handler = LoginHandler(
            screen=self.screen,
            template_matcher=self.template_matcher,
            mouse=self.mouse,
            config=LoginConfig(),
        )

        self._is_running = False
        self._rng = create_rng()

        # Initialize event emitter and status aggregator
        self.events = EventEmitter()
        self.status_aggregator = StatusAggregator(
            fatigue=self.fatigue,
            breaks=self.breaks,
            timing=self.timing,
            attention=self.attention,
            skill_checker=self.skill_checker,
            session=self.session,
            state_machine=self.state_machine,
        )

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
            # Check for logout and re-login if needed
            if self.login_handler.is_logged_out():
                self._handle_logout_recovery()
                continue

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
                self.events.emit_attention_lapse(lapse_duration)
                time.sleep(lapse_duration)
                continue

            # Check for skill check (only during cleaning)
            state = self.state_machine.get_current_state()
            if state == BotState.CLEANING and self.skill_checker.should_check():
                self._handle_skill_check()
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
        booth_match = self.bank.find_bank_booth()
        if not booth_match or not booth_match.found:
            self._logger.warning("Could not find bank booth")
            time.sleep(1)
            return

        # Click bank booth with actual template dimensions
        target = ClickTarget(
            center_x=booth_match.center_x,
            center_y=booth_match.center_y,
            width=booth_match.width,
            height=booth_match.height,
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
        """Handle depositing cleaned herbs.

        Randomly chooses between clicking the deposit button or clicking
        one of the cleaned herbs in the inventory for human-like variation.
        """
        self._logger.debug("Depositing herbs...")

        # Randomize deposit method: deposit button vs click clean herb
        click_herb_chance = self.config.get("bank.deposit_click_herb_chance", 0.30)
        use_herb_click = self._rng.random() < click_herb_chance

        if use_herb_click:
            # Try to click a random clean herb in inventory
            clean_slots = [s for s in self.inventory.slots if s.state.value == "clean_herb"]
            if clean_slots:
                # Pick a random clean herb slot
                chosen_slot = clean_slots[self._rng.integers(0, len(clean_slots))]
                screen_x, screen_y = self.inventory.get_slot_screen_coords(chosen_slot.index)

                inv_config = self.config.window.get("inventory", {})
                target = ClickTarget(
                    center_x=screen_x,
                    center_y=screen_y,
                    width=inv_config.get("slot_width", 42),
                    height=inv_config.get("slot_height", 36),
                )

                self._logger.debug(f"Depositing by clicking clean herb at slot {chosen_slot.index}")
                completed, _ = self.mouse.click_at_target(
                    target,
                    misclick_rate=self.fatigue.get_misclick_rate(),
                )

                if completed:
                    time.sleep(self.timing.get_post_action_delay(ActionType.DEPOSIT))
                    self.state_machine.withdraw_herbs()
                return

        # Default: click deposit button
        deposit_match = self.bank.find_deposit_button()
        if not deposit_match or not deposit_match.found:
            self._logger.warning("Could not find deposit button")
            return

        # Click deposit with actual template dimensions
        target = ClickTarget(
            center_x=deposit_match.center_x,
            center_y=deposit_match.center_y,
            width=deposit_match.width,
            height=deposit_match.height,
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
        herb_match = self.bank.find_grimy_herb_in_bank()
        if not herb_match or not herb_match.found:
            self._logger.warning("Could not find grimy herbs in bank")
            # End session if no herbs
            self._is_running = False
            return

        # Click grimy herbs with actual template dimensions
        target = ClickTarget(
            center_x=herb_match.center_x,
            center_y=herb_match.center_y,
            width=herb_match.width,
            height=herb_match.height,
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
            close_match = self.bank.find_close_button()

            if close_match and close_match.found:
                target = ClickTarget(
                    center_x=close_match.center_x,
                    center_y=close_match.center_y,
                    width=close_match.width,
                    height=close_match.height,
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

        # Reset traversal for new inventory
        self.inventory.reset_traversal()

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

        # Get current mouse position for weighted_nearest pattern
        mouse_pos = self.mouse.get_position()

        # Get next grimy herb slot using randomized traversal pattern
        slot = self.inventory.get_next_grimy_slot(mouse_pos=mouse_pos)
        if not slot:
            self.state_machine.start_banking()
            return

        # Occasionally skip this herb and get the next one (5% chance)
        skip_chance = self.config.get("cleaning.skip_herb_chance", 0.05)
        if self._rng.random() < skip_chance:
            skipped_slot = slot
            slot = self.inventory.get_next_grimy_slot(mouse_pos=mouse_pos)
            if slot:
                self._logger.debug(f"Skipped slot {skipped_slot.index}, now cleaning slot {slot.index}")
            else:
                slot = skipped_slot  # No more slots, use the one we were going to skip

        # Get screen coordinates
        screen_x, screen_y = self.inventory.get_slot_screen_coords(slot.index)

        # Create click target
        inv_config = self.config.window.get("inventory", {})
        slot_width = inv_config.get("slot_width", 42)
        slot_height = inv_config.get("slot_height", 36)
        target = ClickTarget(
            center_x=screen_x,
            center_y=screen_y,
            width=slot_width,
            height=slot_height,
        )

        # Click the herb
        start_time = time.time()

        # Check for accidental drag (5% chance, only on middle rows)
        accidental_drag_chance = self.config.get("cleaning.accidental_drag_chance", 0.05)
        allow_drag = 0 < slot.row < 6  # Only middle rows

        if allow_drag and self._rng.random() < accidental_drag_chance:
            # Accidental drag - hold mouse too long and drag toward adjacent cell
            self._logger.debug(f"Accidental drag on slot {slot.index}")
            completed = self.mouse.accidental_drag_to_adjacent(
                target=target,
                slot_row=slot.row,
                slot_col=slot.col,
                slot_width=slot_width,
                slot_height=slot_height,
            )
            was_misclick = False  # Not a misclick, but a drag
        else:
            # Normal click
            completed, was_misclick = self.mouse.click_at_target(
                target,
                misclick_rate=self.fatigue.get_misclick_rate(),
                slot_row=slot.row,
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

            # Record delay for status display
            self.status_aggregator.record_delay(delay * 1000)

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

        # Emit break start event
        self.events.emit_break_start(break_type.value, scheduled_break.duration)

        # Execute break
        duration = self.breaks.execute_break(scheduled_break)

        # Emit break end event
        self.events.emit_break_end(break_type.value, duration)

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

        # Emit drift event
        self.events.emit_drift(target_type.value, duration)

        self.session.record_attention_drift()

    def _handle_skill_check(self) -> None:
        """Handle periodic skill check."""
        self._logger.info("Checking herblore skill...")
        self.skill_checker.perform_skill_check()

        # Emit skill check event
        self.events.emit_skill_check(0.0)  # Duration tracked internally

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

    def _handle_logout_recovery(self) -> None:
        """Handle logout detection and re-login.

        After successful re-login, resets state to IDLE to start fresh
        since inventory state and bank may have changed.
        """
        self._logger.warning("Logout detected! Attempting re-login...")

        if self.login_handler.perform_relogin():
            self._logger.info("Re-login successful, resetting to IDLE state")

            # Reset state machine to idle
            # First recover from any error state, then start fresh
            if self.state_machine.current_state == self.state_machine.error:
                self.state_machine.recover()

            # Force back to idle by using internal state reset
            # The state machine should handle this gracefully
            self.state_machine._current_state = self.state_machine.idle

            # Reset inventory detection since we may have been gone a while
            self.inventory.reset_traversal()

            # Small delay to let the game fully load
            time.sleep(self._rng.uniform(1.0, 2.0))

        else:
            self._logger.error("Re-login failed! Stopping bot.")
            self._is_running = False
