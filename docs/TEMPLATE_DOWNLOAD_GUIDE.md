# Template Download Guide

## Automatic Template Download (Recommended)

Instead of manually taking screenshots, you can automatically download herb template images from the **OSRS Wiki**.

### Quick Start

**Windows:**
```
download_templates.bat
```

**Linux/Mac:**
```
python3 download_herb_templates.py
```

### What Gets Downloaded

The script automatically downloads all 10 grimy herb templates:

1. grimy_ranarr.png
2. grimy_irit.png
3. grimy_avantoe.png
4. grimy_kwuarm.png
5. grimy_dwarf_weed.png
6. grimy_torstol.png
7. grimy_lantadyme.png
8. grimy_toadflax.png
9. grimy_snapdragon.png
10. grimy_cadantine.png

### How It Works

The script uses the **OSRS Wiki MediaWiki API** to fetch official item images:

1. Queries the API for each herb's image URL
2. Downloads the PNG image (29x25 pixels)
3. Saves to `config/templates/` directory

### After Downloading

Once templates are downloaded:

1. Run `test_actions.bat` to verify detection works
2. The test should now properly detect grimy herbs in your inventory
3. If detection doesn't work, you may need to adjust your game zoom level

### Sources

- **OSRS Wiki**: https://oldschool.runescape.wiki
- **MediaWiki API**: https://oldschool.runescape.wiki/api.php
- **License**: OSRS Wiki content is available under non-commercial license

### Troubleshooting

**Script fails to download:**
- Check your internet connection
- Ensure you have Python 3 installed
- The OSRS Wiki may be temporarily unavailable

**Herbs still not detected after download:**
- Your game zoom level may be different from the template zoom
- Try adjusting zoom in RuneLite
- Manually capture templates at your current zoom level (see INVENTORY_SETUP_GUIDE.md)

### Manual Template Capture (Alternative)

If automatic download doesn't work for your setup, see `INVENTORY_SETUP_GUIDE.md` for instructions on manually capturing template images at your specific zoom level.
