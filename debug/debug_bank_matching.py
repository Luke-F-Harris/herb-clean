#!/usr/bin/env python3
"""Debug script to show matching confidence for all herb templates."""

import sys
from pathlib import Path

print("Starting debug script...")
print(f"Python version: {sys.version}")
print(f"Script location: {Path(__file__).parent}")
print()

# Check imports
print("Checking imports...")
try:
    import cv2
    print("✓ cv2 (OpenCV) imported")
except ImportError as e:
    print(f"✗ Failed to import cv2: {e}")
    print("  Install with: pip install opencv-python")
    input("Press ENTER to exit...")
    sys.exit(1)

try:
    import yaml
    print("✓ yaml imported")
except ImportError as e:
    print(f"✗ Failed to import yaml: {e}")
    print("  Install with: pip install pyyaml")
    input("Press ENTER to exit...")
    sys.exit(1)

try:
    import numpy as np
    print("✓ numpy imported")
except ImportError as e:
    print(f"✗ Failed to import numpy: {e}")
    print("  Install with: pip install numpy")
    input("Press ENTER to exit...")
    sys.exit(1)

print()

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

try:
    from vision.screen_capture import ScreenCapture
    print("✓ ScreenCapture imported")
except ImportError as e:
    print(f"✗ Failed to import ScreenCapture: {e}")
    input("Press ENTER to exit...")
    sys.exit(1)

try:
    from vision.template_matcher import TemplateMatcher
    print("✓ TemplateMatcher imported")
except ImportError as e:
    print(f"✗ Failed to import TemplateMatcher: {e}")
    input("Press ENTER to exit...")
    sys.exit(1)

print("✓ All imports successful")
print()


def main():
    print("=" * 70)
    print("BANK HERB MATCHING CONFIDENCE DEBUG")
    print("=" * 70)
    print()
    print("SETUP INSTRUCTIONS:")
    print("1. Open RuneLite OSRS")
    print("2. Open your bank interface")
    print("3. Make sure grimy herbs are visible WITH stack numbers")
    print("4. Keep the bank window open")
    print()
    print("Press ENTER when ready...")
    input()
    print()
    print("Starting detection...")

    # Load config
    config_path = Path(__file__).parent / "config" / "default_config.yaml"
    print(f"Loading config from: {config_path}")

    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        print("✓ Config loaded")
    except Exception as e:
        print(f"ERROR: Could not load config: {e}")
        return 1

    # Initialize
    templates_dir = Path(__file__).parent / "config" / "templates"
    print(f"Templates directory: {templates_dir}")

    screen = ScreenCapture("RuneLite")
    print("✓ Screen capture initialized")

    matcher = TemplateMatcher(
        templates_dir,
        confidence_threshold=0.70,
        multi_scale=True,
        scale_range=(0.7, 1.3),
        scale_steps=7
    )
    print("✓ Template matcher initialized")
    print()

    print("Searching for RuneLite window...")
    if not screen.find_window():
        print("ERROR: Could not find RuneLite window!")
        print("Make sure RuneLite is running and visible.")
        return 1

    print(f"✓ Found window at {screen.window_bounds}")
    print()

    # Capture screen
    print("Capturing screenshot...")
    window_img = screen.capture_window()
    if window_img is None:
        print("ERROR: Could not capture screen!")
        return 1

    print(f"✓ Captured {window_img.shape[1]}x{window_img.shape[0]} image")
    print()

    # Detect bank region to restrict search area
    print("Detecting bank interface region...")

    # Find close button to locate bank
    close_match = matcher.match(
        window_img,
        config.get('bank', {}).get('close_button_template', 'bank_close.png')
    )
    deposit_match = matcher.match(
        window_img,
        config.get('bank', {}).get('deposit_all_template', 'deposit_all.png')
    )

    bank_region = None
    if close_match.found:
        # Use close button to calculate bank region
        close_x = close_match.x
        close_y = close_match.y
        x = max(0, close_x - 900)
        y = max(0, close_y - 20)
        width = min(950, window_img.shape[1] - x)
        height = min(600, window_img.shape[0] - y)
        bank_region = (x, y, width, height)
        print(f"✓ Bank region detected via close button: ({x}, {y}) {width}x{height}")
    elif deposit_match.found:
        # Fallback to deposit button
        deposit_x = deposit_match.x
        deposit_y = deposit_match.y
        x = max(0, deposit_x - 400)
        y = max(0, deposit_y - 600)
        width = min(900, window_img.shape[1] - x)
        height = min(550, deposit_y - y)
        bank_region = (x, y, width, height)
        print(f"✓ Bank region detected via deposit button: ({x}, {y}) {width}x{height}")
    else:
        print("⚠ Could not detect bank region - searching full image")
        print("  Make sure bank is open with close/deposit button visible")

    # Crop to bank region if detected
    if bank_region:
        x, y, width, height = bank_region
        search_image = window_img[y:y+height, x:x+width]
        offset_x = x
        offset_y = y
        print(f"✓ Cropped search area to {width}x{height} (bank items only)")
    else:
        search_image = window_img
        offset_x = 0
        offset_y = 0

    print()

    grimy_templates = config.get('herbs', {}).get('grimy', [])
    print(f"Testing {len(grimy_templates)} herb templates...")
    print()
    results = []

    for i, herb_config in enumerate(grimy_templates):
        herb_name = herb_config['name']
        template_name = herb_config['template']

        print(f"  [{i+1}/{len(grimy_templates)}] Testing {herb_name}...", end=' ', flush=True)

        # Test both methods on bank region (or full image if no region)
        try:
            standard_match = matcher.match(search_image, template_name)
            region_match = matcher.match_bottom_region(search_image, template_name, 0.65)

            # Adjust coordinates for offset
            if standard_match.found:
                standard_match.x += offset_x
                standard_match.y += offset_y
                standard_match.center_x += offset_x
                standard_match.center_y += offset_y

            if region_match.found:
                region_match.x += offset_x
                region_match.y += offset_y
                region_match.center_x += offset_x
                region_match.center_y += offset_y

            results.append({
                'name': herb_name,
                'template': template_name,
                'standard_conf': standard_match.confidence,
                'standard_found': standard_match.found,
                'region_conf': region_match.confidence,
                'region_found': region_match.found,
                'standard_pos': (standard_match.center_x, standard_match.center_y) if standard_match.found else None,
                'region_pos': (region_match.center_x, region_match.center_y) if region_match.found else None,
            })
            print(f"Standard: {standard_match.confidence:.3f}, Region: {region_match.confidence:.3f}")
        except Exception as e:
            print(f"ERROR: {e}")
            results.append({
                'name': herb_name,
                'template': template_name,
                'standard_conf': 0.0,
                'standard_found': False,
                'region_conf': 0.0,
                'region_found': False,
                'standard_pos': None,
                'region_pos': None,
            })

    # Sort by region confidence (what we're using now)
    results.sort(key=lambda x: x['region_conf'], reverse=True)

    print("=" * 70)
    print(f"{'Herb Type':<20} {'Standard':<20} {'Region-Based':<20}")
    print("=" * 70)

    for r in results:
        std_str = f"{r['standard_conf']:.3f} {'✓' if r['standard_found'] else '✗'}"
        reg_str = f"{r['region_conf']:.3f} {'✓' if r['region_found'] else '✗'}"
        print(f"{r['name']:<20} {std_str:<20} {reg_str:<20}")

    print()
    print("=" * 70)
    print("BEST MATCHES:")
    print("=" * 70)

    best = results[0]
    print(f"Herb: {best['name']}")
    print(f"Template: {best['template']}")
    print(f"Standard confidence: {best['standard_conf']:.3f} ({'PASS' if best['standard_found'] else 'FAIL'})")
    print(f"Region-based confidence: {best['region_conf']:.3f} ({'PASS' if best['region_found'] else 'FAIL'})")

    if best['region_pos']:
        print(f"Position: {best['region_pos']}")

    print()

    if not best['region_found']:
        print("⚠ WARNING: Best match did not pass threshold (0.70)")
        print("  This means the bot will NOT detect this herb in the bank.")
        print()
        print("Possible issues:")
        print("  - Wrong herb type in bank (not matching templates)")
        print("  - Templates captured at different zoom level")
        print("  - Stack numbers interfering too much")
        print()
        print("Solutions:")
        print("  1. Ensure you have the right herb type (check config)")
        print("  2. Recapture templates at your current zoom level")
        print("  3. Try lowering confidence threshold in config")
        print()
    else:
        print("✓ Detection working! The bot should find this herb.")
        print()

    # Visualize best match
    if best['region_found']:
        vis_img = window_img.copy()

        # Draw bank region rectangle if detected
        if bank_region:
            x, y, width, height = bank_region
            cv2.rectangle(vis_img, (x, y), (x + width, y + height), (0, 255, 255), 2)
            cv2.putText(
                vis_img,
                "Bank Search Area",
                (x + 10, y + 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 255),
                2
            )

        # Use the position from our results (already adjusted for offset)
        match_x, match_y = best['region_pos']

        # We need width/height, so re-match just to get dimensions
        temp_match = matcher.match_bottom_region(search_image, best['template'], 0.65)

        # Draw herb match box (green)
        cv2.rectangle(
            vis_img,
            (match_x - temp_match.width // 2, match_y - temp_match.height // 2),
            (match_x + temp_match.width // 2, match_y + temp_match.height // 2),
            (0, 255, 0),
            3
        )

        # Add label
        label = f"{best['name']}: {best['region_conf']:.3f}"
        cv2.putText(
            vis_img,
            label,
            (match_x - temp_match.width // 2, match_y - temp_match.height // 2 - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 255, 0),
            2
        )

        # Show visualization window
        print()
        print("Opening visualization window...")
        print("=" * 70)
        print("VISUALIZATION:")
        print("  - YELLOW box = Bank search area")
        print("  - GREEN box = Detected herb")
        print("  - Label shows herb name and confidence")
        print("=" * 70)

        window_name = "Bank Herb Detection - Press any key to close"
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        cv2.imshow(window_name, vis_img)

        # Try to bring window to front
        try:
            cv2.setWindowProperty(window_name, cv2.WND_PROP_TOPMOST, 1)
        except:
            pass  # Not all platforms support this

        print()
        print("✓ Window opened! Look for the image window.")
        print("  (It may appear behind other windows)")
        print()
        print("Press any key in the IMAGE WINDOW to close...")
        cv2.waitKey(0)
        cv2.destroyAllWindows()
    else:
        print("⚠ No match found - skipping visualization")

    print()
    print("=" * 70)
    print("DEBUG COMPLETE")
    print("=" * 70)

    return 0


if __name__ == "__main__":
    try:
        exit_code = main()
        print()
        print("Press ENTER to close this window...")
        input()
        sys.exit(exit_code)
    except Exception as e:
        print()
        print("=" * 70)
        print("FATAL ERROR")
        print("=" * 70)
        print(f"Error: {e}")
        print()
        print("Full traceback:")
        import traceback
        traceback.print_exc()
        print()
        print("Press ENTER to close this window...")
        input()
        sys.exit(1)
