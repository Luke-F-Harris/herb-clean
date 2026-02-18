# Testing Guide: Bank Detection Fix

## ✅ WHAT WAS FIXED

### The Problem
- Yellow "Bank Search Area" was covering the **game world (LEFT side)**
- Should have been covering the **bank interface (RIGHT side)**
- Root cause: offset was **900 pixels** (way too large!)
- Actual OSRS bank panel is only **~520 pixels wide**

### The Fix
- Changed offset from `900 * scale` to `510 * scale`
- Bank panel width: 520px - close button offset: 10px = **510px offset**
- Updated bank item grid dimensions to **480x460 pixels**
- Added visual debugging (blue box for close button, orange arrow for offset)

## 📋 BEFORE YOU TEST

### CRITICAL: You Need Bank Templates

The detection **requires** these template images:

1. **`bank_close.png`** - The X button at top-right of bank panel
2. **`bank_booth.png`** - Bank booth in game world (for finding bank)
3. **`deposit_all.png`** - Deposit inventory button (optional fallback)

**Check if you have them:**
```bash
ls config/templates/bank*.png
ls config/templates/deposit*.png
```

If missing, you need to capture them (see instructions below).

## 🎮 HOW TO CAPTURE BANK TEMPLATES

### Required: RuneLite with Bank Open

1. **Open RuneLite**
2. **Open your bank interface** (click bank booth/chest)
3. **Use Windows Snipping Tool** (Win + Shift + S)

### Capture Close Button (`bank_close.png`)

1. Zoom/crop TIGHTLY around the **X button** at top-right of bank
2. Should be a small image (~30x30 pixels)
3. Save as `config/templates/bank_close.png`

**Example:**
```
[X]  ← Capture just this, tightly cropped
```

### Capture Bank Booth (`bank_booth.png`)

1. Close bank interface
2. Zoom/crop around the **bank booth icon** in game world
3. Should show the booth clearly
4. Save as `config/templates/bank_booth.png`

### Capture Deposit Button (Optional)

1. Open bank again
2. Zoom/crop around **"Deposit inventory"** button at bottom
3. Save as `config/templates/deposit_all.png`

### Template Quality Tips

- ✅ PNG format (not JPG!)
- ✅ Crop tightly around the element
- ✅ Clear, unobstructed view
- ✅ Same resolution/zoom you'll use when running bot
- ❌ Don't include surrounding elements
- ❌ No transparent backgrounds (unless natural)

## 🧪 TESTING THE FIX

### Step 1: Run Debug Script

```bash
scripts\windows\debug_bank.bat
```

### Step 2: What You Should See in Terminal

```
HYBRID COLOR + TEMPLATE DETECTION (What the bot uses)
======================================================================

Step 1: Color Pre-Filtering
----------------------------------------------------------------------
Top 3 matches by color similarity:
  1. ranarr          - Color similarity: 0.921
  ...

Bank region detected: (1340, 95) 480x460
  Close button at: (1850, 85)
  Detected scale: 1.00x
  Scaled offset: 510px (was 900px hardcoded)
```

**Key numbers to verify:**
- Scale should be close to 1.0 at 1080p (2.0 at 4K)
- Offset should be ~510px at 1080p (~1020px at 4K)
- Bank region X coordinate should be > 1200 at 1080p (RIGHT side)

### Step 3: What You Should See in Visualization Window

The window will show:

**BLUE BOX + CIRCLE:**
- Shows where close button was detected
- Should be at **top-right corner of bank panel**
- If this is wrong, template doesn't match

**ORANGE ARROW:**
- Points from close button to bank region
- Shows the offset direction
- Should point **LEFT** from close button

**YELLOW BOX:**
- The detected bank search area
- Should cover the **bank interface on RIGHT side**
- Should NOT cover game world on left

**GREEN/RED BOX:**
- Shows detected herb
- Green = passed threshold
- Red = failed threshold

**TEXT OVERLAY (top-left):**
- Shows exact coordinates
- Screen size, close button position, bank region, offset, scale
- Use this to verify numbers

## ✅ SUCCESS CRITERIA

### Visual Check
- [ ] Blue box is on the close button (X) at top-right of bank panel
- [ ] Orange arrow points from close button leftward to yellow box
- [ ] Yellow box covers the bank interface panel (RIGHT side of screen)
- [ ] Yellow box does NOT cover game world (LEFT side)
- [ ] Herb detection (if any) is INSIDE the yellow box

### Coordinate Check
At 1080p resolution:
- [ ] Close button X coordinate: ~1800-1900
- [ ] Bank region X coordinate: ~1300-1400
- [ ] Offset: ~510 pixels
- [ ] Scale: ~1.0x

At 4K resolution (2160p):
- [ ] Close button X coordinate: ~3600-3800
- [ ] Bank region X coordinate: ~2600-2800
- [ ] Offset: ~1020 pixels
- [ ] Scale: ~2.0x

## ❌ FAILURE SCENARIOS

### Scenario 1: No Blue Box (Close Button Not Detected)

**Symptom:** No blue box/circle appears

**Cause:** Missing or incorrect `bank_close.png` template

**Solution:**
1. Verify `config/templates/bank_close.png` exists
2. Recapture template at your current zoom level
3. Make sure it's a tight crop of just the X button

### Scenario 2: Blue Box in Wrong Place

**Symptom:** Blue box is not on the close button

**Cause:** Template doesn't match current bank interface

**Solution:**
1. Check your bank interface style (some banks may vary)
2. Recapture `bank_close.png` from YOUR bank
3. Ensure clean capture without obstructions

### Scenario 3: Yellow Box Still on Left Side

**Symptom:** Yellow box still covers game world

**Possible Causes:**
- Close button template matched something on left side
- Scale detection is very wrong
- Coordinate system issue

**Debug Steps:**
1. Check text overlay for actual coordinates
2. Verify close button X is > 1500 at 1080p
3. Check detected scale is reasonable (~1.0 at 1080p)
4. Share screenshot and coordinates with developer

### Scenario 4: Yellow Box Too Small/Large

**Symptom:** Yellow box doesn't cover full bank interface

**Cause:** Bank dimensions may vary slightly

**Solution:**
- Minor size issues are OK (margins around item grid)
- If way off, may need manual dimension adjustment
- Report measurements from your screenshot

## 📊 DIFFERENT RESOLUTIONS

### 1920x1080 (1080p)
- Expected scale: ~1.0x
- Expected offset: ~510px
- Bank region: ~480x460px
- Close button X: ~1850px

### 2560x1440 (1440p)
- Expected scale: ~1.33x
- Expected offset: ~680px
- Bank region: ~640x613px
- Close button X: ~2467px

### 3840x2160 (4K)
- Expected scale: ~2.0x
- Expected offset: ~1020px
- Bank region: ~960x920px
- Close button X: ~3700px

## 🔧 TROUBLESHOOTING

### Q: Templates exist but close button not detected

**A:** Lower confidence threshold temporarily:
```yaml
# config/default_config.yaml
vision:
  confidence_threshold: 0.60  # Try lower (was 0.75)
```

### Q: Detection works but herb matching still fails

**A:** This is a separate issue. The bank region fix should help, but herb templates may also need work. Check:
1. Do you have all herb templates?
2. Are they captured at same zoom as current game?
3. Run `python debug/investigate_herb_colors.py` to analyze

### Q: Can I adjust the offset manually?

**A:** Yes, edit `src/vision/bank_detector.py` line 193:
```python
offset_x = int(510 * scale)  # Try adjusting 510 to other values
```

### Q: Different bank types (booth vs chest)?

**A:** Should work for all banks. The interface is the same. If issues:
1. Try both bank booth and bank chest
2. Capture templates from the specific bank type you use

## 📷 SHARE RESULTS

If still not working, please share:

1. **Screenshot** of visualization window
2. **Terminal output** (full text)
3. **Text overlay values** from screenshot:
   - Screen size
   - Close button position
   - Bank region position
   - Offset used
   - Scale detected

This will help diagnose any remaining issues!

## 🎯 NEXT STEPS AFTER BANK REGION WORKS

Once yellow box correctly covers bank interface:

1. **Test herb detection** - Does it find the right herb?
2. **Check confidence scores** - Are they above threshold?
3. **Try color analysis** - Run `python debug/investigate_herb_colors.py`
4. **Adjust threshold if needed** - Lower if too strict

The bank region fix was the CRITICAL first step. Herb matching should improve significantly once the search area is correct!
