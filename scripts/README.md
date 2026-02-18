# Scripts Directory

Utility scripts for setup, testing, and running the bot.

## Directory Structure

```
scripts/
├── setup/         # Setup and download utilities
├── windows/       # Windows batch files (.bat)
├── linux/         # Linux shell scripts (.sh)
└── README.md      # This file
```

## Setup Scripts (`setup/`)

### `setup_inventory.py`
Interactive tool to configure inventory detection.

**Usage:**
```bash
# Windows
scripts\windows\setup_inventory.bat

# Linux
python scripts/setup/setup_inventory.py
```

**Features:**
- Captures inventory template
- Auto-detects inventory position
- Saves configuration

### `download_herb_templates.py`
Downloads herb template images from OSRSBox API.

**Usage:**
```bash
# Windows
scripts\windows\download_templates.bat

# Linux
python scripts/setup/download_herb_templates.py
```

**Downloads:** All 10 grimy herb templates to `config/templates/`

## Windows Scripts (`windows/`)

All Windows batch files automatically:
- Change to project root directory
- Activate virtual environment
- Run the appropriate Python script
- Handle errors gracefully

### Setup & Installation

**`setup_windows.bat`** - Initial setup
```bash
scripts\windows\setup_windows.bat
```
- Creates virtual environment
- Installs dependencies
- Prepares project for first run

### Running the Bot

**`run_bot.bat`** - Start the bot
```bash
scripts\windows\run_bot.bat
```

### Testing

**`test_actions.bat`** - Run all tests
```bash
scripts\windows\test_actions.bat
```

**`test_detection.bat`** - Test inventory detection
```bash
scripts\windows\test_detection.bat
```

### Debug Tools

**`debug_inventory.bat`** - Debug inventory detection
```bash
scripts\windows\debug_inventory.bat
```

**`debug_bank.bat`** - Debug bank matching
```bash
scripts\windows\debug_bank.bat
```

### Setup Tools

**`setup_inventory.bat`** - Interactive inventory setup
```bash
scripts\windows\setup_inventory.bat
```

**`download_templates.bat`** - Download herb templates
```bash
scripts\windows\download_templates.bat
```

## Linux Scripts (`linux/`)

All Linux shell scripts automatically:
- Change to project root directory
- Activate virtual environment
- Run the appropriate Python script
- Handle errors gracefully

### Setup & Installation

**`setup_linux.sh`** - Initial setup
```bash
scripts/linux/setup_linux.sh
```
- Creates virtual environment
- Installs dependencies
- Prepares project for first run

### Running the Bot

**`run_bot.sh`** - Start the bot
```bash
scripts/linux/run_bot.sh
```

### Testing

**`test_actions.sh`** - Run all tests
```bash
scripts/linux/test_actions.sh
```

## Usage Patterns

### First Time Setup

**Windows:**
```bash
# 1. Run setup
scripts\windows\setup_windows.bat

# 2. Download templates
scripts\windows\download_templates.bat

# 3. Configure inventory
scripts\windows\setup_inventory.bat

# 4. Run bot
scripts\windows\run_bot.bat
```

**Linux:**
```bash
# 1. Run setup
scripts/linux/setup_linux.sh

# 2. Download templates
python scripts/setup/download_herb_templates.py

# 3. Configure inventory (if needed)
python scripts/setup/setup_inventory.py

# 4. Run bot
python main.py
```

### Daily Usage

**Windows:**
```bash
scripts\windows\run_bot.bat
```

**Linux:**
```bash
python main.py
# or
scripts/linux/run_bot.sh
```

### Troubleshooting

**Windows:**
```bash
# Test inventory detection
scripts\windows\test_detection.bat

# Debug inventory issues
scripts\windows\debug_inventory.bat

# Debug bank matching
scripts\windows\debug_bank.bat

# Run full test suite
scripts\windows\test_actions.bat
```

**Linux:**
```bash
# Test detection
python tests/test_inventory_detection.py

# Debug tools
python debug/debug_inventory.py
python debug/debug_bank_matching.py

# Full test suite
python tests/test_bot_actions.py
```

## Script Conventions

### Windows (.bat)
- Use `cd /d "%~dp0\..\.."` to change to project root
- Check for venv before activating
- Use `pause` to keep window open
- Provide helpful error messages

### Linux (.sh)
- Use `cd "$(dirname "$0")/../.."` to change to project root
- Check for venv before activating
- Make executable with `chmod +x`
- Use `$?` to check exit codes

## Adding New Scripts

### Windows Batch File Template

```batch
@echo off
REM Description of what this script does
REM Run from project root: scripts\windows\script_name.bat

cd /d "%~dp0\..\.."

REM Activate virtual environment
call .\venv\Scripts\activate.bat
if errorlevel 1 (
    echo ERROR: Virtual environment not found
    echo Please run scripts\windows\setup_windows.bat first
    pause
    exit /b 1
)

REM Run your Python script
python path\to\script.py
pause
```

### Linux Shell Script Template

```bash
#!/bin/bash
# Description of what this script does
# Run from project root: scripts/linux/script_name.sh

# Change to project root
cd "$(dirname "$0")/../.."

# Activate virtual environment
if [ ! -d "venv" ]; then
    echo "ERROR: Virtual environment not found"
    echo "Please run scripts/linux/setup_linux.sh first"
    exit 1
fi

source venv/bin/activate

# Run your Python script
python path/to/script.py
```

## See Also

- [Main README](../README.md) - Project overview
- [Tests](../tests/README.md) - Test scripts documentation
- [Debug](../debug/README.md) - Debug tools documentation
- [Docs](../docs/) - Full documentation
