# Project Structure

```
osrs_herblore/
│
├── 📁 src/                          # Source code
│   ├── 📁 anti_detection/           # Human-like behavior patterns
│   │   ├── attention_drift.py       # Attention drift simulation
│   │   ├── break_scheduler.py       # Break scheduling
│   │   ├── fatigue_simulator.py     # Fatigue simulation
│   │   └── timing_randomizer.py     # Randomized timing
│   │
│   ├── 📁 core/                     # Bot controller and state machine
│   │   ├── bot_controller.py        # Main bot controller
│   │   ├── config_manager.py        # Configuration management
│   │   └── state_machine.py         # State machine logic
│   │
│   ├── 📁 input/                    # Mouse and keyboard control
│   │   ├── bezier_movement.py       # Bezier curve mouse movements
│   │   ├── click_handler.py         # Click handling
│   │   ├── keyboard_controller.py   # Keyboard input
│   │   └── mouse_controller.py      # Mouse input
│   │
│   ├── 📁 safety/                   # Safety features
│   │   ├── emergency_stop.py        # Emergency stop handler
│   │   └── session_tracker.py       # Session time tracking
│   │
│   ├── 📁 vision/                   # Computer vision
│   │   ├── bank_detector.py         # Bank interface detection
│   │   ├── inventory_auto_detect.py # Auto inventory detection
│   │   ├── inventory_detector.py    # Inventory detection
│   │   ├── screen_capture.py        # Screen capture
│   │   └── template_matcher.py      # Template matching
│   │
│   └── main.py                      # Bot entry point
│
├── 📁 tests/                        # Test scripts
│   ├── test_inventory_detection.py  # Test inventory detection
│   ├── test_bot_actions.py          # Test all bot actions
│   ├── test_bank_stack_diagnostic.py # Bank stack detection tests
│   ├── test_bank_detection_improvements.py # Test improvements
│   └── README.md                    # Test documentation
│
├── 📁 debug/                        # Debug and diagnostic tools
│   ├── debug_inventory.py           # Visual inventory debugger
│   ├── debug_bank_matching.py       # Bank matching debugger
│   ├── investigate_herb_colors.py   # Herb color analysis
│   ├── inventory_detection_result.png # Debug output
│   └── README.md                    # Debug tools documentation
│
├── 📁 scripts/                      # Utility scripts
│   │
│   ├── 📁 setup/                    # Setup and download scripts
│   │   ├── setup_inventory.py       # Interactive inventory setup
│   │   └── download_herb_templates.py # Download herb templates
│   │
│   ├── 📁 windows/                  # Windows batch files
│   │   ├── setup_windows.bat        # Windows setup
│   │   ├── run_bot.bat              # Run the bot
│   │   ├── test_actions.bat         # Run tests
│   │   ├── test_detection.bat       # Test detection
│   │   ├── debug_inventory.bat      # Debug inventory
│   │   ├── debug_bank.bat           # Debug bank
│   │   ├── setup_inventory.bat      # Setup inventory
│   │   └── download_templates.bat   # Download templates
│   │
│   ├── 📁 linux/                    # Linux shell scripts
│   │   ├── setup_linux.sh           # Linux setup
│   │   ├── run_bot.sh               # Run the bot
│   │   └── test_actions.sh          # Run tests
│   │
│   └── README.md                    # Scripts documentation
│
├── 📁 docs/                         # Documentation
│   ├── README.md                    # Main documentation
│   ├── ANTI_DETECTION.md            # Anti-detection features
│   ├── IMPROVEMENTS.md              # Recent improvements
│   ├── INVENTORY_SETUP_GUIDE.md     # Inventory setup guide
│   ├── TEMPLATE_DOWNLOAD_GUIDE.md   # Template download guide
│   └── WINDOWS_SETUP.md             # Windows setup guide
│
├── 📁 config/                       # Configuration files
│   ├── default_config.yaml          # Main configuration
│   └── 📁 templates/                # Template images
│       ├── bank_booth.png
│       ├── bank_chest.png
│       ├── bank_close.png
│       ├── deposit_all.png
│       ├── grimy_ranarr.png
│       ├── grimy_toadflax.png
│       ├── grimy_irit.png
│       ├── grimy_avantoe.png
│       ├── grimy_kwuarm.png
│       ├── grimy_snapdragon.png
│       ├── grimy_cadantine.png
│       ├── grimy_lantadyme.png
│       ├── grimy_dwarf_weed.png
│       └── grimy_torstol.png
│
├── 📄 main.py                       # Entry point wrapper
├── 📄 requirements.txt              # Python dependencies
├── 📄 README.md                     # Quick start guide
├── 📄 PROJECT_STRUCTURE.md          # This file
└── 📄 .gitignore                    # Git ignore rules
```

## Directory Purposes

### `/src/` - Source Code
All production bot code. Well-organized into modules by functionality.

### `/tests/` - Test Scripts
Automated tests and validation scripts. Run these to verify functionality.

### `/debug/` - Debug Tools
Interactive debugging and diagnostic tools. Use when troubleshooting issues.

### `/scripts/` - Utility Scripts
Helper scripts for setup, running, and testing. Platform-specific wrappers.

### `/docs/` - Documentation
All documentation files. Complete guides and references.

### `/config/` - Configuration
YAML configuration and template images used for detection.

## Key Files

### Entry Points
- **`main.py`** - Main entry point (wrapper to `src/main.py`)
- **`src/main.py`** - Actual bot implementation

### Setup
- **`scripts/windows/setup_windows.bat`** - Windows setup
- **`scripts/linux/setup_linux.sh`** - Linux setup

### Configuration
- **`config/default_config.yaml`** - All bot settings

### Documentation
- **`README.md`** - Quick start
- **`docs/README.md`** - Full documentation
- **`docs/IMPROVEMENTS.md`** - Recent improvements

## Quick Reference

### Running the Bot

**Windows:**
```bash
scripts\windows\run_bot.bat
```

**Linux:**
```bash
python main.py
```

### Testing

**Windows:**
```bash
scripts\windows\test_actions.bat
```

**Linux:**
```bash
python tests/test_bot_actions.py
```

### Debugging

**Inventory:**
```bash
python debug/debug_inventory.py
```

**Bank:**
```bash
python debug/debug_bank_matching.py
```

**Herb Colors:**
```bash
python debug/investigate_herb_colors.py
```

### Setup

**Download Templates:**
```bash
python scripts/setup/download_herb_templates.py
```

**Configure Inventory:**
```bash
python scripts/setup/setup_inventory.py
```

## Design Principles

1. **Separation of Concerns** - Each module has a single, clear purpose
2. **Platform Independence** - Core code works on Windows and Linux
3. **Easy Testing** - Tests separated from production code
4. **Clear Documentation** - Every directory has a README
5. **User-Friendly** - Simple batch/shell wrappers for common tasks

## Development Workflow

1. **Source Code** (`/src/`) - Make changes here
2. **Test** (`/tests/`) - Verify changes work
3. **Debug** (`/debug/`) - Troubleshoot issues
4. **Document** (`/docs/`) - Update documentation
5. **Configure** (`/config/`) - Adjust settings

## Adding New Features

1. Add source code to appropriate `/src/` module
2. Create test in `/tests/`
3. Add debug tool in `/debug/` if needed
4. Update `/docs/` with documentation
5. Add templates to `/config/templates/` if needed
6. Update configuration in `/config/default_config.yaml`

## See Also

- [README.md](README.md) - Quick start guide
- [docs/README.md](docs/README.md) - Full documentation
- [tests/README.md](tests/README.md) - Testing guide
- [debug/README.md](debug/README.md) - Debugging guide
- [scripts/README.md](scripts/README.md) - Scripts guide
