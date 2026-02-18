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
    print("This script shows the confidence score for each herb template.")
    print("Open your bank with grimy herbs visible, then press ENTER...")
    input()

    # Load config
    config_path = Path(__file__).parent / "config" / "default_config.yaml"
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    # Initialize
    templates_dir = Path(__file__).parent / "config" / "templates"
    screen = ScreenCapture("RuneLite")
    matcher = TemplateMatcher(
        templates_dir,
        confidence_threshold=0.70,
        multi_scale=True,
        scale_range=(0.7, 1.3),
        scale_steps=7
    )

    if not screen.find_window():
        print("ERROR: Could not find RuneLite window!")
        return 1

    # Capture screen
    window_img = screen.capture_window()
    if window_img is None:
        print("ERROR: Could not capture screen!")
        return 1

    print("Testing all herb templates...")
    print()

    grimy_templates = config.get('herbs', {}).get('grimy', [])
    results = []

    for herb_config in grimy_templates:
        herb_name = herb_config['name']
        template_name = herb_config['template']

        # Test both methods
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
    print(f"Region-based confidence: {best['region_conf']:.3f} ({'PASS' if best['region_found'] else 'FAIL'})")

    if best['region_pos']:
        print(f"Position: {best['region_pos']}")

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

        cv2.imshow("Best Match", vis_img)
        print()
        print("Press ENTER to exit...")
        input()
        cv2.destroyAllWindows()

    return 0


if __name__ == "__main__":
    sys.exit(main())
