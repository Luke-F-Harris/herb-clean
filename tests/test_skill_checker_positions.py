#!/usr/bin/env python3
"""Debug test for skill checker position detection.

Visualizes hardcoded UI positions on actual screenshots to verify accuracy.
Shows overlays for:
- Skills tab icon (cyan)
- Inventory tab icon (green)
- Herblore skill in skills panel (purple)
"""

import sys
from pathlib import Path
import cv2
import numpy as np


def draw_position_marker(image, x, y, width, height, label, color):
    """Draw a rectangle with crosshair and label."""
    # Rectangle
    cv2.rectangle(image, (x, y), (x + width, y + height), color, 2)
    # Center crosshair
    cx, cy = x + width // 2, y + height // 2
    cv2.line(image, (cx - 10, cy), (cx + 10, cy), color, 1)
    cv2.line(image, (cx, cy - 10), (cx, cy + 10), color, 1)
    # Label above
    cv2.putText(image, label, (x, y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
    # Position text below
    pos_text = f"({x}, {y})"
    cv2.putText(image, pos_text, (x, y + height + 15), cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)


def get_positions_for_screenshot(filename):
    """Return the positions to highlight based on screenshot context."""
    # Position definitions (from skill_checker.py)
    skills_tab = (509, 205, 30, 30, "Skills Tab", (255, 255, 0))      # Cyan
    inventory_tab = (571, 205, 30, 30, "Inventory Tab", (0, 255, 0))  # Green

    # Herblore position (calculated)
    panel_x, panel_y = 550, 210
    skill_w, skill_h = 58, 32
    herblore_row, herblore_col = 2, 1
    herblore_x = panel_x + (herblore_col * skill_w)
    herblore_y = panel_y + (herblore_row * skill_h)
    herblore_skill = (herblore_x, herblore_y, skill_w, skill_h, "Herblore", (255, 0, 255))  # Purple

    # Context-specific positions
    if filename == "skills_tab_view.png":
        # Skills panel is open - need inventory tab and herblore skill
        return [inventory_tab, herblore_skill]
    elif filename == "herblore_skill_hover.png":
        # Skills panel is open with hover - need inventory tab and herblore skill
        return [inventory_tab, herblore_skill]
    elif filename == "world_view.png":
        # Main game view - need skills tab to open skills panel
        return [skills_tab]
    else:
        return []


def test_on_screenshot(screenshot_path, output_path):
    """Test positions on a single screenshot."""
    image = cv2.imread(str(screenshot_path))
    if image is None:
        print(f"  ERROR: Could not load {screenshot_path}")
        return False

    print(f"  Image size: {image.shape[1]}x{image.shape[0]}")

    # Get context-specific positions for this screenshot
    positions = get_positions_for_screenshot(screenshot_path.name)
    if not positions:
        print(f"  SKIP: No positions defined for {screenshot_path.name}")
        return False

    # Draw all positions
    for x, y, w, h, label, color in positions:
        draw_position_marker(image, x, y, w, h, label, color)

    # Add legend
    cv2.putText(image, "Position Debug Test", (10, 25),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    cv2.putText(image, f"Source: {screenshot_path.name}", (10, 50),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)

    # Save result
    cv2.imwrite(str(output_path), image)
    print(f"  Saved: {output_path}")

    # Show interactive window
    cv2.imshow(f"Position Test - {screenshot_path.name}", image)
    return True


def main():
    print("=" * 70)
    print("Skill Checker Position Detection Debug Test")
    print("=" * 70)

    project_root = Path(__file__).parent.parent
    screenshots_dir = project_root / "tools" / "viz_screenshots"
    output_dir = Path(__file__).parent / "debug_output"
    output_dir.mkdir(exist_ok=True)

    # Test on skill-related screenshots
    test_screenshots = [
        "skills_tab_view.png",
        "herblore_skill_hover.png",
        "world_view.png",
    ]

    loaded = 0
    for filename in test_screenshots:
        filepath = screenshots_dir / filename
        print(f"\nTesting: {filename}")
        if filepath.exists():
            output_path = output_dir / f"debug_{filename}"
            if test_on_screenshot(filepath, output_path):
                loaded += 1
        else:
            print(f"  SKIP: File not found")

    if loaded > 0:
        print("\n" + "=" * 70)
        print("Review the overlays. Press any key to close windows.")
        print("If positions are incorrect, measure correct values from images.")
        print("=" * 70)
        cv2.waitKey(0)
        cv2.destroyAllWindows()

    return 0


if __name__ == "__main__":
    sys.exit(main())
