# Inventory Detection Setup Guide

Quick guide to ensure the bot can find your inventory, especially for **Resizable - Classic layout**.

## Why Detection Might Fail

The **Resizable - Classic layout** in RuneLite has tabs that **overlap the top portion of the inventory**. This confuses color-based detection because:
- The tabs have similar brown/tan colors
- The inventory is partially obscured
- The exact position varies with window size

## Solution: Use Template-Based Detection (Recommended)

Template matching is **99% reliable** and works with any layout.

### Step 1: Capture Your Inventory

1. **Open RuneLite** with your desired layout ("Resizable - Classic layout")
2. **Empty your inventory** (or have items, doesn't matter)
3. **Take a screenshot** of your FULL inventory:
   - Use Windows Snipping Tool (`Win + Shift + S`)
   - Capture the **entire inventory grid** (all 28 slots)
   - Include the borders/edges
   - Don't include the tabs above

**Example of what to capture:**
```
┌─────────────────┐
│ □ □ □ □         │  ← All 4 columns
│ □ □ □ □         │
│ □ □ □ □         │
│ □ □ □ □         │
│ □ □ □ □         │
│ □ □ □ □         │
│ □ □ □ □         │  ← All 7 rows
└─────────────────┘
```

4. **Save as PNG**: `config/templates/inventory_template.png`

### Step 2: Enable Template Detection

Edit `config/default_config.yaml`:

```yaml
window:
  auto_detect_inventory: true
  inventory_template: "inventory_template.png"  # ← Make sure this is set
```

### Step 3: Test It

```powershell
# Run the test script
test_detection.bat
```

You should see:
```
✓ Template-detected inventory at (XXX, YYY), confidence: 0.95
```

**Confidence > 0.90 = Perfect detection!**

## Alternative: Smart Default (No Template)

If you don't want to capture a template, the bot now has a **smart default** that places the inventory in the bottom-right based on your window size.

### Configuration

```yaml
window:
  auto_detect_inventory: true
  inventory_template: null  # ← Set to null or remove line
```

The bot will:
1. Try color-based detection (looks for inventory background)
2. If that fails, calculate position based on window size:
   - **Right side**: 73% across the window
   - **Bottom half**: 42% down the window
   - Ensures it fits within window bounds

This works for most RuneLite layouts!

## Manual Configuration (Last Resort)

If auto-detection and smart default both fail, you can manually set the position.

### Step 1: Find Your Inventory Position

1. Run `test_detection.bat` and take note of where it draws the green box
2. Use Windows Snipping Tool to measure the coordinates
3. Find the top-left corner of your inventory

### Step 2: Set Manual Position

Edit `config/default_config.yaml`:

```yaml
window:
  auto_detect_inventory: false  # ← Disable auto-detection
  inventory_template: null
  inventory:
    x: 650      # ← Your measured X position
    y: 250      # ← Your measured Y position
    slot_width: 42
    slot_height: 36
    cols: 4
    rows: 7
```

### Step 3: Test It

```powershell
test_detection.bat
```

The green box should now align perfectly with your inventory!

## Troubleshooting

### "No inventory-colored regions found"

**Solution**: Use template-based detection (Step 1-2 above)

The color-based detection is confused by tabs or different themes.

### "Template match confidence too low"

**Possible causes:**
- Template captured at different resolution
- RuneLite theme changed
- Window scaled differently

**Solution**: Recapture the template at your current resolution/theme

### Detection finds the wrong area

**Solution**:
1. Try template-based detection first
2. If still wrong, use manual configuration

### Green box is slightly off

**If close but not perfect:**
- This is usually fine! The bot adds randomization anyway
- If it's off by more than 10 pixels, try recapturing the template

## Recommended Approach

**For Resizable - Classic layout:**

1. ✅ **Use template-based detection** (most reliable)
2. ⚠️ Fallback: Smart default
3. ❌ Last resort: Manual configuration

**For Fixed mode:**

1. ✅ Color-based detection usually works
2. ✅ Smart default as fallback

## Window Size Recommendations

The bot works with any window size, but these are tested:

- **800x600** - Works well with smart default
- **1024x768** - Works with all methods
- **1920x1080** - Works best with template

**Tip**: Keep your RuneLite window size consistent between template capture and running the bot!

## Need Help?

If detection still fails:

1. Share your `inventory_detection_result.png` (created by `test_detection.bat`)
2. Mention your RuneLite layout name
3. Note your window resolution

The bot will still work with manual configuration!
