#!/usr/bin/env python3
"""Debug inventory detection to see what's being detected."""

import sys
import cv2
import yaml
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from vision.screen_capture import ScreenCapture
from vision.template_matcher import TemplateMatcher
from vision.inventory_detector import InventoryDetector


def main():
    """Debug inventory detection."""
    print("=" * 70)
    print("Inventory Detection Debugger")
    print("=" * 70)

    # Load config
    config_path = Path(__file__).parent / "config" / "default_config.yaml"
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    templates_dir = Path(__file__).parent / "config" / "templates"

    # Initialize
    screen = ScreenCapture("RuneLite")
    matcher = TemplateMatcher(templates_dir, confidence_threshold=0.70)

    inventory_template = config.get('window', {}).get('inventory_template')
    inventory_template_path = None
    if inventory_template:
        inventory_template_path = str(templates_dir / inventory_template)

    inventory = InventoryDetector(
        screen_capture=screen,
        template_matcher=matcher,
        inventory_config=config.get('window', {}).get('inventory', {}),
        grimy_templates=config.get('herbs', {}).get('grimy', []),
        auto_detect=config.get('window', {}).get('auto_detect_inventory', True),
        inventory_template_path=inventory_template_path,
    )

    # Find window
    bounds = screen.find_window()
    if not bounds:
        print("ERROR: Could not find RuneLite window")
        return 1

    print(f"\n✓ Window found at: ({bounds.x}, {bounds.y})")
    print(f"  Window size: {bounds.width}x{bounds.height}")

    # Capture screenshot
    window_img = screen.capture_window()
    if window_img is None:
        print("ERROR: Could not capture window")
        return 1

    print(f"  Screenshot size: {window_img.shape[1]}x{window_img.shape[0]}")

    # Try to detect inventory
    print("\n" + "=" * 70)
    print("Attempting inventory detection...")
    print("=" * 70)

    inventory.detect_inventory_state()

    print(f"\nInventory configuration:")
    print(f"  Position: ({inventory.config.get('x')}, {inventory.config.get('y')})")
    print(f"  Slot size: {inventory.config.get('slot_width')}x{inventory.config.get('slot_height')}")
    print(f"  Grid: {inventory.config.get('cols')}x{inventory.config.get('rows')}")

    # Calculate inventory bounds
    inv_x = inventory.config.get('x')
    inv_y = inventory.config.get('y')
    inv_width = inventory.config.get('slot_width', 42) * 4
    inv_height = inventory.config.get('slot_height', 36) * 7

    # Draw on image
    debug_img = window_img.copy()

    # Draw inventory border (GREEN)
    if bounds:
        screen_x = bounds.x + inv_x
        screen_y = bounds.y + inv_y
    else:
        screen_x = inv_x
        screen_y = inv_y

    cv2.rectangle(debug_img,
                  (screen_x, screen_y),
                  (screen_x + inv_width, screen_y + inv_height),
                  (0, 255, 0), 3)

    # Draw each slot
    for slot in inventory.slots:
        if bounds:
            sx = bounds.x + slot.x
            sy = bounds.y + slot.y
        else:
            sx = slot.x
            sy = slot.y

        # Draw center dot
        cv2.circle(debug_img, (sx, sy), 3, (0, 255, 0), -1)

        # Draw slot number
        cv2.putText(debug_img, str(slot.index), (sx - 10, sy + 5),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.3, (0, 255, 0), 1)

    # Also draw the RAW inventory position (RED) to compare
    raw_x = config.get('window', {}).get('inventory', {}).get('x', 563)
    raw_y = config.get('window', {}).get('inventory', {}).get('y', 208)

    if bounds:
        raw_screen_x = bounds.x + raw_x
        raw_screen_y = bounds.y + raw_y
    else:
        raw_screen_x = raw_x
        raw_screen_y = raw_y

    cv2.rectangle(debug_img,
                  (raw_screen_x, raw_screen_y),
                  (raw_screen_x + inv_width, raw_screen_y + inv_height),
                  (0, 0, 255), 2)

    # Add labels
    cv2.putText(debug_img, "GREEN = Detected", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    cv2.putText(debug_img, "RED = Config Default", (10, 60),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

    print("\n" + "=" * 70)
    print("Opening visualization window...")
    print("=" * 70)
    print("VISUALIZATION:")
    print("  - GREEN box = Where inventory was detected")
    print("  - RED box = Default config position")
    print("  - Dots = Slot centers (numbered)")
    print("=" * 70)

    window_name = "Inventory Detection - Press any key to close"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.imshow(window_name, debug_img)

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

    return 0


if __name__ == "__main__":
    sys.exit(main())
