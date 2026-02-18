#!/usr/bin/env python3
"""Debug script to show matching confidence for all herb templates."""

import sys
from pathlib import Path
import cv2
import yaml

sys.path.insert(0, str(Path(__file__).parent / "src"))

from vision.screen_capture import ScreenCapture
from vision.template_matcher import TemplateMatcher


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

    grimy_templates = config.get('herbs', {}).get('grimy', [])
    print(f"Testing {len(grimy_templates)} herb templates...")
    print()
    results = []

    for i, herb_config in enumerate(grimy_templates):
        herb_name = herb_config['name']
        template_name = herb_config['template']

        print(f"  [{i+1}/{len(grimy_templates)}] Testing {herb_name}...", end=' ', flush=True)

        # Test both methods
        try:
            standard_match = matcher.match(window_img, template_name)
            region_match = matcher.match_bottom_region(window_img, template_name, 0.65)

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

        # Get match again for visualization
        match = matcher.match_bottom_region(window_img, best['template'], 0.65)

        # Convert to screen coords
        bounds = screen.window_bounds
        if bounds:
            match.x += bounds.x
            match.y += bounds.y

        # Draw box
        cv2.rectangle(
            vis_img,
            (match.x, match.y),
            (match.x + match.width, match.y + match.height),
            (0, 255, 0),
            3
        )

        # Add label
        label = f"{best['name']}: {best['region_conf']:.3f}"
        cv2.putText(
            vis_img,
            label,
            (match.x, match.y - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 255, 0),
            2
        )

        # Save image
        output_path = Path(__file__).parent / "debug_bank_match.png"
        cv2.imwrite(str(output_path), vis_img)
        print(f"✓ Saved visualization to: {output_path}")

        cv2.imshow("Best Match", vis_img)
        print()
        print("Showing visualization window...")
        print("Press ENTER in this terminal to exit...")
        input()
        cv2.destroyAllWindows()
    else:
        print("⚠ No match found - skipping visualization")

    print()
    print("=" * 70)
    print("DEBUG COMPLETE")
    print("=" * 70)

    return 0


if __name__ == "__main__":
    sys.exit(main())
