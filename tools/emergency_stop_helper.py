#!/usr/bin/env python3
"""Emergency stop helper for ydotool mode.

Since ydotool uses uinput and can't listen for key presses,
this helper script runs separately to catch F12 and write
a signal file that the bot polls.

Usage:
    python emergency_stop_helper.py &

The bot will poll /tmp/osrs_herblore_stop_signal every 100ms.
"""

import os
import sys
import signal
import logging

try:
    from pynput import keyboard
except ImportError:
    print("ERROR: pynput is required. Install with: pip install pynput")
    sys.exit(1)


SIGNAL_FILE = "/tmp/osrs_herblore_stop_signal"
PID_FILE = "/tmp/osrs_herblore_stop_helper.pid"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def cleanup():
    """Clean up signal and PID files."""
    for f in [SIGNAL_FILE, PID_FILE]:
        try:
            if os.path.exists(f):
                os.remove(f)
        except OSError:
            pass


def signal_handler(signum, frame):
    """Handle termination signals."""
    logger.info("Received signal %d, shutting down...", signum)
    cleanup()
    sys.exit(0)


def on_press(key):
    """Handle key press events."""
    try:
        if key == keyboard.Key.f12:
            logger.warning("F12 pressed - triggering emergency stop!")
            with open(SIGNAL_FILE, "w") as f:
                f.write("1")
            # Keep running to allow multiple triggers if needed
    except Exception as e:
        logger.error("Error handling key press: %s", e)


def main():
    """Main entry point."""
    # Check if another instance is running
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE, "r") as f:
                old_pid = int(f.read().strip())
            # Check if process is still running
            os.kill(old_pid, 0)
            logger.error("Another instance is running (PID %d)", old_pid)
            sys.exit(1)
        except (ProcessLookupError, ValueError):
            # Process not running or invalid PID, clean up
            os.remove(PID_FILE)

    # Write our PID
    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))

    # Clean up any existing signal file
    if os.path.exists(SIGNAL_FILE):
        os.remove(SIGNAL_FILE)

    # Set up signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    logger.info("Emergency stop helper started (PID %d)", os.getpid())
    logger.info("Press F12 to trigger emergency stop")
    logger.info("Signal file: %s", SIGNAL_FILE)

    # Start keyboard listener
    try:
        with keyboard.Listener(on_press=on_press) as listener:
            listener.join()
    except KeyboardInterrupt:
        logger.info("Interrupted, shutting down...")
    finally:
        cleanup()


if __name__ == "__main__":
    main()
