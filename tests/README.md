# Tests Directory

This directory contains all test scripts for the OSRS Herblore Bot.

## Test Scripts

### `test_inventory_detection.py`
Tests inventory slot detection and template matching.

**Usage:**
```bash
# Windows
..\scripts\windows\test_detection.bat

# Linux
python tests/test_inventory_detection.py
```

### `test_bot_actions.py`
Comprehensive test of all bot actions including mouse movement, clicking, and detection.

**Usage:**
```bash
# Windows
..\scripts\windows\test_actions.bat

# Linux
python tests/test_bot_actions.py
```

### `test_bank_stack_diagnostic.py`
Diagnoses bank item stack detection issues.

**Usage:**
```bash
python tests/test_bank_stack_diagnostic.py
```

### `test_bank_detection_improvements.py`
Validates the improved scale-aware bank region detection and hybrid herb matching.

**Usage:**
```bash
python tests/test_bank_detection_improvements.py
```

**Features:**
- Tests scale-aware bank region detection
- Validates color pre-filtering for herbs
- Visualizes detection results
- Saves debug images

## Running Tests

### All Tests

**Windows:**
```bash
cd ..
scripts\windows\test_actions.bat
```

**Linux:**
```bash
cd ..
python tests/test_bot_actions.py
```

### Individual Tests

```bash
cd ..
python tests/test_inventory_detection.py
python tests/test_bank_stack_diagnostic.py
python tests/test_bank_detection_improvements.py
```

## Test Requirements

- RuneLite must be running
- For bank tests: Bank must be open
- For inventory tests: Have items in inventory
- Virtual environment must be activated

## Expected Results

All tests should:
- ✅ Detect RuneLite window
- ✅ Find inventory/bank regions
- ✅ Detect items with >75% confidence
- ✅ Display visualization windows
- ✅ Save debug images

## Troubleshooting

### Test fails to find window
- Ensure RuneLite is running
- Check window title matches "RuneLite"
- Try maximizing the window

### Low confidence scores
- Check template images exist in `config/templates/`
- Run template download: `scripts/setup/download_herb_templates.py`
- Verify game zoom level (recommended: 100%)

### Import errors
- Ensure virtual environment is activated
- Run setup: `scripts/windows/setup_windows.bat` or `scripts/linux/setup_linux.sh`
