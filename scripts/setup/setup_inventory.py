#!/usr/bin/env python3
"""Interactive inventory setup tool.

Helps you:
1. Capture inventory template (recommended)
2. Manually select inventory position
3. Test the configuration
"""

import sys
from pathlib import Path

import cv2
import numpy as np
import yaml

# Add src to path (go up to project root, then into src)
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

from vision.screen_capture import ScreenCapture

# Global state for mouse callback
selecting = False
start_point = None
end_point = None
current_image = None


def mouse_callback(event, x, y, flags, param):
    """Handle mouse events for region selection."""
    global selecting, start_point, end_point, current_image

    if event == cv2.EVENT_LBUTTONDOWN:
        selecting = True
        start_point = (x, y)
        end_point = (x, y)

    elif event == cv2.EVENT_MOUSEMOVE:
        if selecting:
            end_point = (x, y)

    elif event == cv2.EVENT_LBUTTONUP:
        selecting = False
        end_point = (x, y)


def draw_selection(image, start, end):
    """Draw selection rectangle."""
    if start and end:
        img_copy = image.copy()
        cv2.rectangle(img_copy, start, end, (0, 255, 0), 2)

        # Draw instructions
        cv2.putText(
            img_copy,
            "Release to confirm selection",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 0),
            2,
        )

        return img_copy
    return image


def capture_inventory_template():
    """Interactive tool to capture inventory template."""
    global current_image, start_point, end_point

    print("=" * 60)
    print("Inventory Template Capture Tool")
    print("=" * 60)

    # Find RuneLite window
    print("\n1. Finding RuneLite window...")
    screen = ScreenCapture("RuneLite")
    bounds = screen.find_window()

    if not bounds:
        print("ERROR: Could not find RuneLite window!")
        print("Make sure RuneLite is running and visible.")
        return False

    print(f"✓ Found window at ({bounds.x}, {bounds.y}), size: {bounds.width}x{bounds.height}")

    # Capture window
    print("\n2. Capturing window screenshot...")
    current_image = screen.capture_window()

    if current_image is None:
        print("ERROR: Could not capture window!")
        return False

    print(f"✓ Captured {current_image.shape[1]}x{current_image.shape[0]} image")

    # Interactive selection
    print("\n3. Select your inventory:")
    print("   - Click and drag to select the FULL inventory area")
    print("   - Include all 28 slots (4 columns x 7 rows)")
    print("   - Don't include the tabs above")
    print("   - Press SPACE to confirm")
    print("   - Press ESC to cancel")

    cv2.namedWindow("Select Inventory", cv2.WINDOW_NORMAL)
    cv2.setMouseCallback("Select Inventory", mouse_callback)

    while True:
        if start_point and end_point:
            display = draw_selection(current_image, start_point, end_point)
        else:
            display = current_image.copy()
            cv2.putText(
                display,
                "Click and drag to select inventory",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 255),
                2,
            )

        cv2.imshow("Select Inventory", display)
        key = cv2.waitKey(1) & 0xFF

        if key == 27:  # ESC
            print("\nCancelled.")
            cv2.destroyAllWindows()
            return False

        elif key == 32:  # SPACE
            if start_point and end_point:
                break

    cv2.destroyAllWindows()

    # Extract selection
    x1, y1 = start_point
    x2, y2 = end_point

    # Ensure correct order
    x1, x2 = min(x1, x2), max(x1, x2)
    y1, y2 = min(y1, y2), max(y1, y2)

    width = x2 - x1
    height = y2 - y1

    print(f"\n4. Selection: ({x1}, {y1}) to ({x2}, {y2})")
    print(f"   Size: {width}x{height}")

    # Validate dimensions (should be roughly 4:7 ratio)
    aspect_ratio = width / height if height > 0 else 0
    expected_ratio = 4 * 42 / (7 * 36)  # Typical inventory ratio

    if abs(aspect_ratio - expected_ratio) > 0.3:
        print(f"\n⚠ WARNING: Aspect ratio {aspect_ratio:.2f} seems wrong")
        print(f"   Expected: {expected_ratio:.2f} (4 cols x 7 rows)")
        print("   Make sure you selected the full inventory grid")

        response = input("\nContinue anyway? (y/n): ")
        if response.lower() != 'y':
            return False

    # Extract template
    template = current_image[y1:y2, x1:x2]

    # Save template
    template_dir = project_root / "config" / "templates"
    template_dir.mkdir(parents=True, exist_ok=True)
    template_path = template_dir / "inventory_template.png"

    cv2.imwrite(str(template_path), template)
    print(f"\n✓ Saved template to: {template_path}")

    # Calculate slot dimensions
    slot_width = width // 4
    slot_height = height // 7

    print(f"\nInventory settings:")
    print(f"  Position: ({x1}, {y1})")
    print(f"  Slot size: {slot_width}x{slot_height}")

    # Automatically update config file
    print("\n4. Updating config file...")
    config_path = project_root / "config" / "default_config.yaml"

    try:
        # Read current config
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)

        # Update inventory template setting
        if 'window' not in config:
            config['window'] = {}

        config['window']['inventory_template'] = "inventory_template.png"
        config['window']['auto_detect_inventory'] = True

        # Also save the position as fallback
        if 'inventory' not in config['window']:
            config['window']['inventory'] = {}

        config['window']['inventory']['x'] = x1
        config['window']['inventory']['y'] = y1
        config['window']['inventory']['slot_width'] = slot_width
        config['window']['inventory']['slot_height'] = slot_height

        # Write back
        with open(config_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)

        print(f"✓ Updated {config_path}")

    except Exception as e:
        print(f"⚠ Could not auto-update config: {e}")
        print("\nPlease manually update your config/default_config.yaml:")
        print("""
window:
  auto_detect_inventory: true
  inventory_template: "inventory_template.png"
""")

    # Update config suggestion
    print("\n" + "=" * 60)
    print("SUCCESS! Template saved and config updated.")
    print("=" * 60)

    # Verify template works
    print("\n5. Verifying template...")
    from vision.inventory_auto_detect import InventoryAutoDetector

    test_detector = InventoryAutoDetector(template_path)
    test_region = test_detector.detect_inventory_region(current_image)

    if test_region and test_region.confidence > 0.70:
        print(f"✓ Template detection works! Confidence: {test_region.confidence:.2%}")
        print(f"  Detected at: ({test_region.x}, {test_region.y})")
    else:
        conf = test_region.confidence if test_region else 0.0
        print(f"⚠ Template detection weak. Confidence: {conf:.2%}")
        print("  This might still work, but try recapturing if issues occur.")

    print("\nRun 'test_detection.bat' to see full visual verification!")

    return True


def manual_position_setup():
    """Help user manually configure inventory position."""
    global current_image, start_point, end_point

    print("=" * 60)
    print("Manual Position Setup Tool")
    print("=" * 60)

    # Find RuneLite window
    print("\n1. Finding RuneLite window...")
    screen = ScreenCapture("RuneLite")
    bounds = screen.find_window()

    if not bounds:
        print("ERROR: Could not find RuneLite window!")
        return False

    print(f"✓ Found window")

    # Capture window
    print("\n2. Capturing window screenshot...")
    current_image = screen.capture_window()

    if current_image is None:
        print("ERROR: Could not capture window!")
        return False

    print("✓ Captured screenshot")

    # Interactive selection
    print("\n3. Select your inventory:")
    print("   - Click and drag to select the inventory area")
    print("   - Press SPACE to confirm")
    print("   - Press ESC to cancel")

    cv2.namedWindow("Select Inventory", cv2.WINDOW_NORMAL)
    cv2.setMouseCallback("Select Inventory", mouse_callback)

    while True:
        if start_point and end_point:
            display = draw_selection(current_image, start_point, end_point)
        else:
            display = current_image.copy()
            cv2.putText(
                display,
                "Click and drag to select inventory",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 255),
                2,
            )

        cv2.imshow("Select Inventory", display)
        key = cv2.waitKey(1) & 0xFF

        if key == 27:  # ESC
            print("\nCancelled.")
            cv2.destroyAllWindows()
            return False

        elif key == 32:  # SPACE
            if start_point and end_point:
                break

    cv2.destroyAllWindows()

    # Extract selection
    x1, y1 = start_point
    x2, y2 = end_point

    # Ensure correct order
    x1, x2 = min(x1, x2), max(x1, x2)
    y1, y2 = min(y1, y2), max(y1, y2)

    width = x2 - x1
    height = y2 - y1

    # Calculate slot dimensions
    slot_width = width // 4
    slot_height = height // 7

    # Automatically update config file
    print("\n4. Updating config file...")
    config_path = project_root / "config" / "default_config.yaml"

    try:
        # Read current config
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)

        # Disable auto-detect, set manual position
        if 'window' not in config:
            config['window'] = {}

        config['window']['auto_detect_inventory'] = False
        config['window']['inventory_template'] = None

        if 'inventory' not in config['window']:
            config['window']['inventory'] = {}

        config['window']['inventory']['x'] = x1
        config['window']['inventory']['y'] = y1
        config['window']['inventory']['slot_width'] = slot_width
        config['window']['inventory']['slot_height'] = slot_height
        config['window']['inventory']['cols'] = 4
        config['window']['inventory']['rows'] = 7

        # Write back
        with open(config_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)

        print(f"✓ Updated {config_path}")

    except Exception as e:
        print(f"⚠ Could not auto-update config: {e}")
        print("\nPlease manually add this to your config/default_config.yaml:")
        print(f"""
window:
  auto_detect_inventory: false
  inventory_template: null
  inventory:
    x: {x1}
    y: {y1}
    slot_width: {slot_width}
    slot_height: {slot_height}
    cols: 4
    rows: 7
""")

    print("\n" + "=" * 60)
    print("SUCCESS! Manual configuration saved.")
    print("=" * 60)
    print("\nRun 'test_detection.bat' to verify it works!")

    return True


def main():
    """Main entry point."""
    print("\n" + "=" * 60)
    print("OSRS Herb Bot - Inventory Setup Tool")
    print("=" * 60)

    print("\nWhat would you like to do?")
    print("1. Capture inventory template (RECOMMENDED)")
    print("2. Set manual position")
    print("3. Exit")

    choice = input("\nEnter choice (1-3): ").strip()

    if choice == "1":
        print("\n")
        if capture_inventory_template():
            print("\n✓ Template setup complete!")
            print("Run 'test_detection.bat' to verify it works.")
        return 0

    elif choice == "2":
        print("\n")
        if manual_position_setup():
            print("\n✓ Manual configuration ready!")
            print("Copy the config above to your default_config.yaml")
        return 0

    elif choice == "3":
        print("\nExiting...")
        return 0

    else:
        print("\nInvalid choice.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
