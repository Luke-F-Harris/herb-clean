"""Base bot controller for all OSRS bots."""
import logging
import time
from abc import ABC, abstractmethod
from typing import Optional, TypeVar, Generic

from osrs_botlib.utils import create_rng
from osrs_botlib.core.config_manager import ConfigManager
from osrs_botlib.core.base_state_machine import BaseBotStateMachine
from osrs_botlib.core.events import EventEmitter
from osrs_botlib.vision.screen_capture import ScreenCapture
from osrs_botlib.vision.template_matcher import TemplateMatcher
from osrs_botlib.input.mouse_controller import MouseController
from osrs_botlib.input.keyboard_controller import KeyboardController
from osrs_botlib.input.drivers.validation import require_interception
from osrs_botlib.anti_detection.break_scheduler import BreakScheduler, BreakType
from osrs_botlib.anti_detection.fatigue_simulator import FatigueSimulator
from osrs_botlib.anti_detection.attention_drift import AttentionDrift
from osrs_botlib.safety.emergency_stop import EmergencyStop
from osrs_botlib.safety.login_handler import LoginHandler

StateT = TypeVar('StateT', bound=BaseBotStateMachine)


class BaseBotController(ABC, Generic[StateT]):
    """Abstract base controller for all OSRS bots.

    Subclasses implement skill-specific logic by:
    - Defining concrete state machine type
    - Implementing _init_skill_components()
    - Implementing _execute_state()
    """

    def __init__(self, config_path: Optional[str] = None, overlay_enabled: bool = False):
        """Initialize bot controller.

        Args:
            config_path: Path to config file
            overlay_enabled: Enable transparent overlay for vision debugging
        """
        self._logger = logging.getLogger(__name__)
        self._overlay_enabled = overlay_enabled
        self._running = False
        self._rng = create_rng()

        # Validate Interception driver is installed (required for undetectable input)
        require_interception()

        # Load configuration
        self.config = ConfigManager(config_path)

        # Initialize event system
        self.events = EventEmitter()

        # Initialize shared components
        self._init_shared_components()

        # Initialize skill-specific components (subclass responsibility)
        self._init_skill_components()

    def _init_shared_components(self) -> None:
        """Initialize components shared by all bots."""
        # Vision components
        self.screen = ScreenCapture(self.config.window.get("title", "RuneLite"))
        self.template_matcher = TemplateMatcher(
            templates_dir=self.config.templates_dir,
            confidence_threshold=self.config.vision.get("confidence_threshold", 0.80),
            multi_scale=self.config.vision.get("multi_scale", True),
            scale_range=tuple(self.config.vision.get("scale_range", [0.8, 1.2])),
            scale_steps=self.config.vision.get("scale_steps", 5),
        )

        # Input components (mouse, keyboard) - to be initialized by subclass
        # using skill-specific configs

        # Safety components
        self.emergency_stop = EmergencyStop()

        # Anti-detection components (break scheduler, fatigue, etc.)
        # to be initialized by subclass using skill-specific configs

    @abstractmethod
    def _init_skill_components(self) -> None:
        """Initialize skill-specific components.

        Subclasses should:
        - Create state machine
        - Create inventory detector
        - Create bank detector
        - Create session tracker
        - Initialize mouse/keyboard with skill-specific configs
        - Initialize timing randomizer
        - Initialize anti-detection components
        """
        pass

    @abstractmethod
    def _execute_state(self, state) -> None:
        """Execute skill-specific state logic.

        Args:
            state: Current state from state machine
        """
        pass

    def start(self) -> None:
        """Start the bot."""
        self._logger.info("Starting bot...")
        self._running = True

        try:
            self._main_loop()
        except KeyboardInterrupt:
            self._logger.info("Bot interrupted by user")
        except Exception as e:
            self._logger.error("Fatal error: %s", e, exc_info=True)
        finally:
            self.stop()

    def stop(self) -> None:
        """Stop the bot."""
        if not self._running:
            return

        self._logger.info("Stopping bot...")
        self._running = False

        # Cleanup (subclass can override)
        self._cleanup()

    def _cleanup(self) -> None:
        """Cleanup resources. Subclasses can override."""
        pass

    def _main_loop(self) -> None:
        """Main bot loop with shared logic.

        Handles:
        - Emergency stop checks
        - Break scheduling
        - Fatigue simulation
        - Login handling
        - State execution delegation
        """
        while self._running:
            try:
                # Check emergency stop
                if self.emergency_stop.should_stop():
                    self._logger.warning("Emergency stop triggered!")
                    break

                # Get current state (from subclass state machine)
                current_state = self._get_current_state()

                # Execute state-specific logic
                self._execute_state(current_state)

                # Small delay between iterations
                time.sleep(0.1)

            except Exception as e:
                self._logger.error("Error in main loop: %s", e, exc_info=True)
                time.sleep(1.0)  # Avoid rapid error loops

    @abstractmethod
    def _get_current_state(self):
        """Get current state from skill-specific state machine.

        Returns:
            Current state
        """
        pass
