# OSRS Herb Cleaning Bot

An automated herb cleaning bot for Old School RuneScape with extensive anti-detection measures.

**🪟 Windows-native support** with automatic setup and inventory detection!

## Disclaimer

**Botting violates OSRS Terms of Service and can result in permanent account bans.** Jagex employs sophisticated behavioral analysis. No bot is truly undetectable with sufficient usage data. This implementation is for **educational purposes only**.

## Features

- **Auto-Detection**: Automatically finds inventory position (no manual calibration needed!)
- **State Machine Architecture**: Clean FSM-based flow control
- **Human-like Mouse Movement**: Bezier curves with overshoot simulation
- **Click Randomization**: Gaussian position distribution, Gamma timing distribution
- **Keyboard Variation**: Unique timing for every keypress, randomized ESC vs click methods
- **Fatigue Simulation**: Gradual performance degradation over time
- **Break Scheduling**: Micro-breaks (2-10s) and long breaks (1-5min)
- **Attention Drift**: Random mouse movements to simulate distraction
- **Emergency Stop**: F12 hotkey for immediate halt
- **Session Tracking**: Statistics and runtime limits

📖 **See [ANTI_DETECTION.md](ANTI_DETECTION.md) for detailed anti-detection information**

## Requirements

- Python 3.10+
- RuneLite client with GPU plugin
- **Windows 10/11** (primary support) or Linux

### Dependencies

**Windows:**
```powershell
pip install -r requirements.txt
```

**Linux:**
```bash
pip install -r requirements.txt
sudo apt install xdotool  # Ubuntu/Debian
# OR
sudo pacman -S xdotool    # Arch
```

Required packages:
- numpy >= 1.24.0
- opencv-python >= 4.8.0
- PyYAML >= 6.0
- mss >= 9.0.0
- pynput >= 1.7.6
- python-statemachine >= 2.1.0
- Pillow >= 10.0.0
- pywin32 >= 306 (Windows only)

## Quick Start (Windows)

```powershell
# 1. Clone repository
git clone https://github.com/Luke-F-Harris/osrs-herb-clean.git
cd osrs-herb-clean

# 2. Run setup script
setup_windows.bat

# 3. Capture template images (see WINDOWS_SETUP.md)

# 4. Test inventory detection (with RuneLite running)
test_detection.bat

# 5. Run bot
run_bot.bat
```

📖 **See [WINDOWS_SETUP.md](WINDOWS_SETUP.md) for detailed Windows setup guide**

## Setup

### 1. Capture Template Images

You need to capture template images from your RuneLite client:

1. Take screenshots of your RuneLite with:
   - Bank booth/chest
   - Grimy herbs (the specific type you want to clean)
   - Deposit-all button
   - Bank close button

2. Crop these elements and save to `config/templates/`:
   - `bank_booth.png`
   - `grimy_ranarr.png` (or your herb type)
   - `deposit_all.png`
   - `bank_close.png`

**Tips for good templates:**
- Use PNG format (lossless)
- Crop tightly around the item
- Capture at your normal playing resolution
- GPU plugin should be enabled when capturing

### 2. Configure Settings

Edit `config/default_config.yaml`:

```yaml
# Auto-detection is enabled by default - no need to adjust inventory position!
window:
  auto_detect_inventory: true  # Automatically finds inventory

# Adjust timing for speed vs. safety
timing:
  click_herb_mean: 600    # Lower = faster, higher = safer
  click_herb_std: 150

# Configure breaks
breaks:
  micro:
    interval: [480, 900]  # 8-15 minutes between micro-breaks
```

**Note:** The bot now auto-detects inventory position by looking for the brown/tan OSRS inventory background. Manual configuration is only used as a fallback if auto-detection fails.

### 3. In-Game Setup

1. Open RuneLite with GPU plugin enabled
2. Stand directly next to a bank booth or bank chest
3. Have grimy herbs in your bank (first visible slot preferred)
4. Ensure inventory is visible (not covered by other interfaces)

## Usage

### Windows

```powershell
# Activate virtual environment (if not already active)
.\venv\Scripts\activate

# Basic run
python .\src\main.py

# Verbose logging
python .\src\main.py -v

# Custom config file
python .\src\main.py -c C:\path\to\config.yaml

# Log to file
python .\src\main.py -l session.log

# Dry run (validate config without running)
python .\src\main.py --dry-run
```

### Linux

```bash
# Activate virtual environment
source venv/bin/activate

# Basic run
python src/main.py

# Options same as Windows (use forward slashes for paths)
python src/main.py -v -l session.log
```

### Controls

- **F12**: Emergency stop (immediately halts all bot actions)

## Project Structure

```
osrs_herblore/
├── src/
│   ├── main.py                      # Entry point
│   ├── core/
│   │   ├── state_machine.py         # Bot state FSM
│   │   ├── bot_controller.py        # Main orchestration
│   │   └── config_manager.py        # YAML config loading
│   ├── vision/
│   │   ├── screen_capture.py        # mss screen grabbing
│   │   ├── template_matcher.py      # OpenCV template matching
│   │   ├── inventory_detector.py    # Inventory slot detection
│   │   └── bank_detector.py         # Bank interface detection
│   ├── input/
│   │   ├── mouse_controller.py      # Mouse movement orchestrator
│   │   ├── bezier_movement.py       # Human-like curved paths
│   │   ├── click_handler.py         # Click randomization
│   │   └── keyboard_controller.py   # Keyboard input
│   ├── anti_detection/
│   │   ├── timing_randomizer.py     # Gaussian/Gamma delays
│   │   ├── fatigue_simulator.py     # Performance degradation
│   │   ├── break_scheduler.py       # Micro/long breaks
│   │   └── attention_drift.py       # Random mouse movements
│   └── safety/
│       ├── emergency_stop.py        # F12 hotkey shutdown
│       └── session_tracker.py       # Runtime/stats tracking
├── config/
│   ├── default_config.yaml          # All tunable parameters
│   └── templates/                   # Template images
└── requirements.txt
```

## Anti-Detection Techniques

| Technique | Implementation |
|-----------|----------------|
| Mouse movement | Bezier curves, 2 control points, 200-400 px/s, 30% overshoot |
| Click position | Gaussian distribution within item bounds |
| Click duration | Gamma distribution, 50-200ms |
| Keyboard timing | Unique per keypress, 30-200ms hold, context-aware travel time |
| Bank closing | 70% ESC / 30% click X (randomized, configurable) |
| Action delays | Gamma distribution (~600ms mean), never uniform |
| Fatigue | After 30 min: 10-50% slower, 1-5% misclick rate |
| Breaks | Micro (2-10s / 8-15min), Long (1-5min / 45-90min) |
| Attention drift | 3% chance per action of moving to minimap/chat |

## Tuning

### Speed vs. Safety Trade-off

**Faster (more risky):**
```yaml
timing:
  click_herb_mean: 400
  click_herb_std: 100
breaks:
  micro:
    interval: [900, 1200]  # Less frequent breaks
```

**Safer (slower):**
```yaml
timing:
  click_herb_mean: 800
  click_herb_std: 200
breaks:
  micro:
    interval: [300, 600]  # More frequent breaks
attention:
  drift_chance: 0.05  # More random movements
```

## Troubleshooting

### "Could not find RuneLite window"
- Ensure RuneLite is running and visible
- Check window title matches config (default: "RuneLite")
- **Windows**: Make sure pywin32 is installed: `pip install pywin32`
- **Linux**: Install xdotool: `sudo apt install xdotool`

### "pywin32 is required for Windows"
```powershell
pip install pywin32
# If that fails, try:
pip install --upgrade pywin32
python .\venv\Scripts\pywin32_postinstall.py -install
```

### Template matching fails
- Recapture templates at current resolution
- Ensure GPU plugin settings match when capturing
- Try lowering `vision.confidence_threshold` (default: 0.80)

### Bot clicks wrong locations
- Auto-detection should handle this automatically
- Check logs for "Successfully auto-detected inventory" message
- If auto-detection fails, manually set `window.auto_detect_inventory: false` and configure coordinates
- Adjust `window.inventory` coordinates for your screen resolution/scaling

## License

Educational use only. Use at your own risk.
