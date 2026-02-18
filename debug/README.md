# Debug Directory

This directory contains debug and diagnostic tools for troubleshooting the OSRS Herblore Bot.

## Debug Scripts

### `debug_inventory.py`
Visual debugger for inventory detection.

**Usage:**
```bash
# Windows
..\scripts\windows\debug_inventory.bat

# Linux
python debug/debug_inventory.py
```

**Features:**
- Shows detected inventory grid
- Displays slot positions
- Highlights detected items
- Saves debug visualization

**Output:** `inventory_detection_result.png`

### `debug_bank_matching.py`
Debugs bank interface detection and herb template matching.

**Usage:**
```bash
# Windows
..\scripts\windows\debug_bank.bat

# Linux
python debug/debug_bank_matching.py
```

**Features:**
- Shows bank region detection
- Tests all herb templates
- Displays confidence scores for each herb
- Compares template matching results
- Visualizes search area

**Requirements:** Bank must be open in RuneLite

### `investigate_herb_colors.py`
Analyzes color profiles of all herb templates to understand detection issues.

**Usage:**
```bash
python debug/investigate_herb_colors.py
```

**Features:**
- Computes color histograms for each herb
- Creates similarity matrix
- Identifies most confusable herb pairs
- Shows color profiles (HSV values)
- Recommends which herbs are easiest to distinguish

**Output:**
```
🎨 Color Similarity Matrix (higher = more similar)
⚠️  Most Confusable Herb Pairs
✅ Most Distinct Herbs
🎨 Color Profile Analysis
```

## When to Use Debug Tools

### Use `debug_inventory.py` when:
- Inventory items not detected
- Wrong items detected
- Slots not aligned correctly
- Need to verify inventory position

### Use `debug_bank_matching.py` when:
- Wrong herbs detected in bank
- Bank region not found
- Low confidence scores
- Herbs confused (e.g., cadantine vs ranarr)

### Use `investigate_herb_colors.py` when:
- Understanding why specific herbs are confused
- Determining if color-based filtering will help
- Analyzing template quality
- Optimizing detection parameters

## Debug Workflow

1. **Start with inventory detection:**
   ```bash
   python debug/debug_inventory.py
   ```
   - Verify inventory grid is correct
   - Check if items are detected

2. **Test bank detection:**
   ```bash
   python debug/debug_bank_matching.py
   ```
   - Open bank in RuneLite first
   - Check confidence scores
   - Verify correct herb is highest scoring

3. **Analyze color profiles:**
   ```bash
   python debug/investigate_herb_colors.py
   ```
   - Identify confusable herbs
   - Understand color-based pre-filtering
   - Determine if templates need improvement

## Reading Debug Output

### Confidence Scores
- **>0.85** - Excellent match
- **0.75-0.85** - Good match
- **0.65-0.75** - Acceptable (may need verification)
- **<0.65** - Poor match (likely incorrect)

### Color Similarity
- **>0.90** - Very similar (will be hard to distinguish by color)
- **0.80-0.90** - Similar (color helps somewhat)
- **<0.80** - Distinct (color is very helpful)

## Common Issues

### Debug script shows no detections
- ✅ Verify RuneLite is running
- ✅ Check window title is "RuneLite"
- ✅ Ensure bank/inventory is visible
- ✅ Verify templates exist in `config/templates/`

### Low confidence scores across all herbs
- ✅ Check RuneLite zoom level (100% recommended)
- ✅ Verify template images are correct resolution
- ✅ Try adjusting `confidence_threshold` in config
- ✅ Re-download templates: `scripts/setup/download_herb_templates.py`

### Wrong herb detected consistently
- ✅ Run `investigate_herb_colors.py` to see similarity
- ✅ If similarity >0.90, herbs are very similar
- ✅ Try increasing confidence threshold
- ✅ Consider using better quality templates

### Bank region not detected (yellow box in wrong place)
- ✅ Verify close button template exists
- ✅ Check if scale detection is working (`test_bank_detection_improvements.py`)
- ✅ See [IMPROVEMENTS.md](../docs/IMPROVEMENTS.md) for scale-aware detection details

## Tips

- **Always run debug scripts with bank/inventory visible**
- **Check saved debug images for visual confirmation**
- **Compare confidence scores between similar herbs**
- **Use color analysis to understand detection limitations**
- **Adjust thresholds in `config/default_config.yaml` if needed**

## See Also

- [IMPROVEMENTS.md](../docs/IMPROVEMENTS.md) - Recent detection improvements
- [tests/](../tests/) - Automated test scripts
- [config/default_config.yaml](../config/default_config.yaml) - Detection parameters
