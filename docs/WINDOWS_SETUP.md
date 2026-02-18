# Windows Setup Guide

Quick guide to get the OSRS Herb Cleaning Bot running on Windows.

## Prerequisites

- Windows 10 or Windows 11
- Python 3.10 or newer ([Download](https://www.python.org/downloads/))
- RuneLite client ([Download](https://runelite.net/))
- Git (optional, for cloning)

## Quick Setup

### Option 1: Using Setup Script (Recommended)

1. **Download or clone the repository:**
   ```powershell
   git clone https://github.com/Luke-F-Harris/osrs-herb-clean.git
   cd osrs-herb-clean
   ```

2. **Run the setup script:**
   ```powershell
   setup_windows.bat
   ```

   This will automatically:
   - Create a virtual environment
   - Install all dependencies
   - Set up pywin32

3. **Done!** Skip to [Capturing Templates](#capturing-templates)

### Option 2: Manual Setup

1. **Clone repository:**
   ```powershell
   git clone https://github.com/Luke-F-Harris/osrs-herb-clean.git
   cd osrs-herb-clean
   ```

2. **Create virtual environment:**
   ```powershell
   python -m venv venv
   ```

3. **Activate virtual environment:**
   ```powershell
   .\venv\Scripts\activate
   ```

4. **Install dependencies:**
   ```powershell
   pip install -r requirements.txt
   ```

## Capturing Templates

You need to capture template images from RuneLite:

1. **Open RuneLite** with GPU plugin enabled

2. **Take screenshots** of these elements (use Windows Snipping Tool or `Win + Shift + S`):
   - Bank booth or bank chest
   - Grimy herb (the specific herb you want to clean)
   - "Deposit inventory" button in bank
   - Bank close button (X)

3. **Crop tightly** around each element

4. **Save as PNG** to `config/templates/`:
   - `bank_booth.png`
   - `grimy_ranarr.png` (or your herb type)
   - `deposit_all.png`
   - `bank_close.png`

**Tips:**
- Use PNG format (not JPG)
- Crop closely around the item/button
- Capture at the resolution you'll be playing at

## Testing

### Test Inventory Detection

```powershell
# Make sure RuneLite is running
test_detection.bat
```

This will show you if the bot can detect your inventory position.

### Test Configuration

```powershell
run_bot.bat --dry-run
```

Validates your config without actually running the bot.

## Running the Bot

### Using Launcher (Easy)

```powershell
run_bot.bat
```

### Manual Run

```powershell
# Activate venv (if not already active)
.\venv\Scripts\activate

# Run bot
python .\src\main.py
```

### With Options

```powershell
# Verbose logging
run_bot.bat -v

# Save log file
run_bot.bat -l session.log

# Custom config
run_bot.bat -c custom_config.yaml
```

## In-Game Setup

1. Open RuneLite with GPU plugin enabled
2. Stand next to a bank booth or chest
3. Have grimy herbs in your bank (preferably first visible slot)
4. Make sure inventory is fully visible on screen

## Controls

- **F12** - Emergency stop (stops bot immediately)

## Common Issues

### "pywin32 is required for Windows"

```powershell
pip install pywin32
python .\venv\Scripts\pywin32_postinstall.py -install
```

### "Could not find RuneLite window"

- Make sure RuneLite is running
- Check that the window title contains "RuneLite"
- Try restarting RuneLite

### Template matching fails

- Recapture templates at your current resolution
- Make sure GPU plugin is enabled when capturing
- Try lowering `vision.confidence_threshold` in config.yaml (default: 0.80)

### Inventory auto-detection fails

- Make sure inventory is fully visible
- Not covered by other windows
- Using default RuneLite theme
- Try manual configuration in `config/default_config.yaml`

## Configuration

Edit `config/default_config.yaml` to adjust:

```yaml
# Speed vs safety
timing:
  click_herb_mean: 600  # Lower = faster, higher = safer

# Breaks
breaks:
  micro:
    interval: [480, 900]  # 8-15 minutes

# Auto-detection (enabled by default)
window:
  auto_detect_inventory: true
```

## Next Steps

- Read the main [README.md](README.md) for detailed information
- Adjust timing in `config/default_config.yaml` for your risk tolerance
- Start with conservative (slow) settings and monitor for a few hours

## Disclaimer

Botting violates OSRS Terms of Service and can result in permanent bans. Use at your own risk. This is for educational purposes only.
