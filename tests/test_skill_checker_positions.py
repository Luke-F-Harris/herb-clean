#!/usr/bin/env python3
"""Debug test for skill checker position detection.

Visualizes hardcoded UI positions on actual screenshots to verify accuracy.
Shows overlays for each element one at a time with Enter to continue.

This test helps identify if the hardcoded positions in skill_checker.py
are correct for the current window size/resolution.
"""

import sys
from pathlib import Path
import cv2
import numpy as np


# =============================================================================
# CORRECTED POSITIONS (measured from actual screenshots)
# These are window-relative coordinates for 1208x802 RuneLite window
# The right panel starts around x=730, tab icons row is at y=198
# =============================================================================

SKILLS_TAB = {
    "x": 765,
    "y": 198,
    "width": 33,
    "height": 30,
    "label": "Skills Tab",
    "color": (255, 255, 0),  # Cyan
}

INVENTORY_TAB = {
    "x": 865,
    "y": 198,
    "width": 33,
    "height": 30,
    "label": "Inventory Tab",
    "color": (0, 255, 0),  # Green
}

# Herblore skill in the skills panel
# Skills panel content area starts at approximately x=755, y=208
# Grid: 3 columns x 8 rows, each cell ~56x32 pixels
# Herblore is at row 2, column 1 (middle column)
# x = 755 + (1 * 56) = 811
# y = 208 + (2 * 32) = 272
HERBLORE_SKILL = {
    "x": 811,
    "y": 276,
    "width": 56,
    "height": 32,
    "label": "Herblore",
    "color": (255, 0, 255),  # Purple
}


def draw_position_marker(image, pos_config):
    """Draw a rectangle with crosshair and label."""
    x = pos_config["x"]
    y = pos_config["y"]
    width = pos_config["width"]
    height = pos_config["height"]
    label = pos_config["label"]
    color = pos_config["color"]

    # Rectangle
    cv2.rectangle(image, (x, y), (x + width, y + height), color, 2)

    # Center crosshair
    cx, cy = x + width // 2, y + height // 2
    cv2.line(image, (cx - 15, cy), (cx + 15, cy), color, 2)
    cv2.line(image, (cx, cy - 15), (cx, cy + 15), color, 2)

    # Label with background
    text_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0]
    cv2.rectangle(image, (x, y - 25), (x + text_size[0] + 10, y - 5), (0, 0, 0), -1)
    cv2.putText(image, label, (x + 5, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

    # Position text below
    pos_text = f"({x}, {y}) {width}x{height}"
    cv2.putText(image, pos_text, (x, y + height + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)


def draw_reference_grid(image):
    """Draw a light reference grid to help measure positions."""
    h, w = image.shape[:2]
    grid_color = (50, 50, 50)

    # Draw vertical lines every 100 pixels
    for x in range(0, w, 100):
        cv2.line(image, (x, 0), (x, h), grid_color, 1)
        cv2.putText(image, str(x), (x + 2, 15), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (100, 100, 100), 1)

    # Draw horizontal lines every 100 pixels
    for y in range(0, h, 100):
        cv2.line(image, (0, y), (w, y), grid_color, 1)
        cv2.putText(image, str(y), (2, y + 15), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (100, 100, 100), 1)


def test_screenshot(screenshot_path, positions, output_dir):
    """Test positions on a single screenshot.

    Args:
        screenshot_path: Path to the screenshot
        positions: List of position configs to draw
        output_dir: Directory to save output images

    Returns:
        True if successful
    """
    image = cv2.imread(str(screenshot_path))
    if image is None:
        print(f"  ERROR: Could not load {screenshot_path}")
        return False

    print(f"  Image size: {image.shape[1]}x{image.shape[0]}")

    # Draw reference grid
    draw_reference_grid(image)

    # Draw all position markers
    for pos in positions:
        draw_position_marker(image, pos)
        print(f"  Drawing {pos['label']} at ({pos['x']}, {pos['y']})")

    # Add header
    cv2.putText(image, f"Position Debug: {screenshot_path.name}", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    cv2.putText(image, "Check if rectangles align with actual UI elements", (10, 55),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)

    # Save result
    output_path = output_dir / f"debug_{screenshot_path.name}"
    cv2.imwrite(str(output_path), image)
    print(f"  Saved: {output_path}")

    # Show image
    cv2.imshow(f"Position Test - {screenshot_path.name}", image)

    # Give OpenCV time to render
    for _ in range(5):
        cv2.waitKey(100)

    return True


def main():
    print("=" * 70)
    print("Skill Checker Position Detection Debug Test")
    print("=" * 70)
    print("\nThis test shows the hardcoded positions from skill_checker.py")
    print("overlaid on actual screenshots. If the rectangles don't align")
    print("with the actual UI elements, the positions need to be corrected.")
    print("\nPress ENTER in this terminal to advance between tests.\n")

    project_root = Path(__file__).parent.parent
    screenshots_dir = project_root / "tools" / "viz_screenshots"
    output_dir = Path(__file__).parent / "debug_output"
    output_dir.mkdir(exist_ok=True)

    # Define test cases: (screenshot, positions to test, description)
    test_cases = [
        (
            "world_view.png",
            [SKILLS_TAB],
            "Skills Tab - click target when inventory is visible"
        ),
        (
            "skills_tab_view.png",
            [INVENTORY_TAB, HERBLORE_SKILL],
            "Inventory Tab + Herblore Skill - targets when skills panel is open"
        ),
        (
            "herblore_skill_hover.png",
            [INVENTORY_TAB, HERBLORE_SKILL],
            "Inventory Tab + Herblore Skill - verification with hover state"
        ),
    ]

    # Run each test case
    for i, (filename, positions, description) in enumerate(test_cases, 1):
        print("=" * 70)
        print(f"TEST {i}/{len(test_cases)}: {description}")
        print("=" * 70)

        filepath = screenshots_dir / filename
        print(f"\nScreenshot: {filename}")

        if not filepath.exists():
            print(f"  SKIP: File not found at {filepath}")
            continue

        if test_screenshot(filepath, positions, output_dir):
            print("\nReview the overlay. Do the rectangles align with the UI elements?")
            print("Press ENTER to continue...")
            input()
            cv2.destroyAllWindows()
        else:
            print("  Test failed to load image")

    # Final summary
    print("\n" + "=" * 70)
    print("TEST COMPLETE")
    print("=" * 70)
    print("\nIf positions are incorrect, measure the correct values from the images.")
    print(f"Debug images saved to: {output_dir}")
    print("\nCurrent hardcoded positions (skill_checker.py):")
    print(f"  Skills Tab:    ({SKILLS_TAB['x']}, {SKILLS_TAB['y']}) {SKILLS_TAB['width']}x{SKILLS_TAB['height']}")
    print(f"  Inventory Tab: ({INVENTORY_TAB['x']}, {INVENTORY_TAB['y']}) {INVENTORY_TAB['width']}x{INVENTORY_TAB['height']}")
    print(f"  Herblore:      ({HERBLORE_SKILL['x']}, {HERBLORE_SKILL['y']}) {HERBLORE_SKILL['width']}x{HERBLORE_SKILL['height']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
