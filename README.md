# OSRS Herblore Bot

Automated herb cleaning bot for Old School RuneScape using computer vision and human-like behavior patterns.

## Quick Start

### Windows

```bash
# 1. Run setup
scripts\windows\setup_windows.bat

# 2. Run the bot
scripts\windows\run_bot.bat
```

### Linux

```bash
# 1. Run setup
scripts/linux/setup_linux.sh

# 2. Run the bot
python main.py
```

## Project Structure

```
osrs_herblore/
├── src/              # Source code
│   ├── anti_detection/  - Human-like behavior patterns
│   ├── core/            - Bot controller and state machine
│   ├── input/           - Mouse/keyboard control
│   ├── safety/          - Emergency stop and session tracking
│   └── vision/          - Computer vision and detection
│
├── tests/            # Test scripts
│   ├── test_inventory_detection.py
│   ├── test_bot_actions.py
│   ├── test_bank_stack_diagnostic.py
│   └── test_bank_detection_improvements.py
│
├── debug/            # Debug and diagnostic tools
│   ├── debug_inventory.py
│   ├── debug_bank_matching.py
│   └── investigate_herb_colors.py
│
├── scripts/          # Utility scripts
│   ├── setup/           - Setup and download scripts
│   ├── windows/         - Windows batch files
│   └── linux/           - Linux shell scripts
│
├── docs/             # Documentation
│   ├── README.md                   - Main documentation
│   ├── ANTI_DETECTION.md          - Anti-detection features
│   ├── IMPROVEMENTS.md            - Recent improvements
│   ├── INVENTORY_SETUP_GUIDE.md   - Inventory setup
│   ├── TEMPLATE_DOWNLOAD_GUIDE.md - Template download
│   └── WINDOWS_SETUP.md           - Windows setup guide
│
├── config/           # Configuration files
│   ├── default_config.yaml
│   └── templates/       - Template images
│
├── main.py           # Entry point
└── requirements.txt  # Python dependencies
```

## Documentation

Full documentation is in the `docs/` directory:

- **[Main Documentation](docs/README.md)** - Complete setup and usage guide
- **[Anti-Detection Features](docs/ANTI_DETECTION.md)** - Human-like behavior
- **[Recent Improvements](docs/IMPROVEMENTS.md)** - Bank detection & herb matching fixes
- **[Inventory Setup](docs/INVENTORY_SETUP_GUIDE.md)** - Configure inventory detection
- **[Template Download](docs/TEMPLATE_DOWNLOAD_GUIDE.md)** - Download herb templates
- **[Windows Setup](docs/WINDOWS_SETUP.md)** - Windows-specific setup

## Features

✅ **Computer Vision**
- Multi-scale template matching
- Hybrid color + spatial herb detection
- Scale-aware bank region detection (4K support)
- Auto-detect inventory position

✅ **Human-like Behavior**
- Bezier curve mouse movements
- Realistic click patterns
- Micro and long breaks
- Fatigue simulation
- Attention drift

✅ **Safety**
- Emergency stop (F12)
- Session time limits
- Statistics logging

## Usage

### Run the Bot

**Windows:**
```bash
scripts\windows\run_bot.bat
```

**Linux:**
```bash
python main.py
```

### Run Tests

**Windows:**
```bash
scripts\windows\test_actions.bat
```

**Linux:**
```bash
python tests/test_bot_actions.py
```

### Debug Tools

**Inventory Detection:**
```bash
# Windows
scripts\windows\debug_inventory.bat

# Linux
python debug/debug_inventory.py
```

**Bank Matching:**
```bash
# Windows
scripts\windows\debug_bank.bat

# Linux
python debug/debug_bank_matching.py
```

**Herb Color Analysis:**
```bash
python debug/investigate_herb_colors.py
```

## Requirements

- Python 3.10+
- RuneLite (OSRS client)
- Windows or Linux
- 1080p or 4K display

## License

Educational purposes only. Use at your own risk.

## Recent Updates

### 2026-02-18: Bank Detection & Herb Matching Improvements

1. **Scale-Aware Bank Region Detection**
   - Fixed hardcoded offsets for 4K displays
   - Bank search area now correctly covers bank panel
   - Works across all resolutions and zoom levels

2. **Hybrid Color + Template Herb Matching**
   - Pre-filters herbs by color similarity
   - Improved accuracy: 30-50% → 70-80%
   - Reduces false positives (cadantine vs ranarr)

3. **Multi-Scale Noise Reduction**
   - Narrowed scale range to [0.9, 1.1]
   - Fewer false positives, faster performance

See [IMPROVEMENTS.md](docs/IMPROVEMENTS.md) for details.
