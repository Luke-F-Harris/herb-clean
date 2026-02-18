#!/usr/bin/env python3
"""Test inventory detection with config support.

This script loads your config and tests inventory detection.
"""

import sys
import cv2
import numpy as np
import yaml
from pathlib import Path

# Add src to path (go up to project root, then into src)
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from vision.screen_capture import ScreenCapture
from vision.inventory_auto_detect import InventoryAutoDetector, InventoryRegion


def load_config():
    """Load configuration from YAML file."""
    config_path = project_root / "config" / "default_config.yaml"

    if not config_path.exists():
        print(f"⚠ Config not found: {config_path}")
        return {}

    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def main():
    """Test inventory detection."""
    print("=" * 60)
    print("RuneLite Inventory Detection Test")
    print("=" * 60)

    # Load config
    print("\n1. Loading configuration...")
    config = load_config()
    window_config = config.get('window', {})

    auto_detect = window_config.get('auto_detect_inventory', True)
    template_name = window_config.get('inventory_template')
    manual_config = window_config.get('inventory', {})

    print(f"  Auto-detection: {auto_detect}")
    print(f"  Template: {template_name or 'None'}")
    print(f"  Manual config: {'Present' if manual_config else 'None'}")

    # Initialize screen capture
    screen = ScreenCapture("RuneLite")

    # Find window
    print("\n2. Looking for RuneLite window...")
    bounds = screen.find_window()
    if not bounds:
        print("ERROR: Could not find RuneLite window!")
        print("Make sure RuneLite is running and visible.")
        return 1

    print(f"✓ Found window at ({bounds.x}, {bounds.y}), size: {bounds.width}x{bounds.height}")

    # Capture window
    print("\n3. Capturing window screenshot...")
    window_img = screen.capture_window()
    if window_img is None:
        print("ERROR: Could not capture window!")
        return 1

    print(f"✓ Captured {window_img.shape[1]}x{window_img.shape[0]} image")

    # Determine detection method
    region = None

    if auto_detect:
        print("\n4. Using AUTO-DETECTION mode")

        # Check for template
        template_path = None
        if template_name:
            template_path = Path(__file__).parent / "config" / "templates" / template_name
            if template_path.exists():
                print(f"  ✓ Found template: {template_path}")
            else:
                print(f"  ⚠ Template not found: {template_path}")
                template_path = None

        # Create detector
        detector = InventoryAutoDetector(template_path)

        # Detect with fallback to manual config
        region = detector.detect_with_fallback(window_img, manual_config)

    else:
        print("\n4. Using MANUAL CONFIGURATION mode")

        if not manual_config:
            print("  ERROR: Manual mode enabled but no manual config found!")
            print("  Run setup_inventory.bat to configure.")
            return 1

        # Use manual config directly
        region = InventoryRegion(
            x=manual_config.get('x', 0),
            y=manual_config.get('y', 0),
            slot_width=manual_config.get('slot_width', 42),
            slot_height=manual_config.get('slot_height', 36),
            cols=manual_config.get('cols', 4),
            rows=manual_config.get('rows', 7),
            confidence=1.0,  # Manual config is 100% trusted
        )
        print(f"  ✓ Using manual position: ({region.x}, {region.y})")
        print(f"  ✓ Slot size: {region.slot_width}x{region.slot_height}")

    # Display results
    print("\n5. Detection Results:")
    print(f"  Position: ({region.x}, {region.y})")
    print(f"  Slot size: {region.slot_width}x{region.slot_height}")
    print(f"  Grid: {region.cols}x{region.rows}")
    print(f"  Confidence: {region.confidence:.2%}")

    if region.confidence < 0.5:
        print("\n  ⚠ WARNING: Low confidence!")
        print("  This position might be wrong.")
        print("  Try running setup_inventory.bat")

    # Draw detection result
    print("\n6. Creating visualization...")
    result_img = window_img.copy()

    # Draw inventory border
    x, y = region.x, region.y
    w = region.slot_width * region.cols
    h = region.slot_height * region.rows

    color = (0, 255, 0) if region.confidence > 0.7 else (0, 165, 255)  # Green or Orange
    cv2.rectangle(result_img, (x, y), (x + w, y + h), color, 2)

    # Draw grid lines
    for row in range(1, region.rows):
        y_line = y + row * region.slot_height
        cv2.line(result_img, (x, y_line), (x + w, y_line), color, 1)

    for col in range(1, region.cols):
        x_line = x + col * region.slot_width
        cv2.line(result_img, (x_line, y), (x_line, y + h), color, 1)

    # Add label
    mode = "MANUAL" if not auto_detect else "AUTO"
    label = f"{mode} - Inventory ({region.confidence:.0%})"
    cv2.putText(result_img, label, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

    # Save result
    output_path = Path(__file__).parent / "inventory_detection_result.png"
    cv2.imwrite(str(output_path), result_img)

    print(f"✓ Saved visualization to: {output_path}")

    # Show result
    print("\n7. Displaying result...")
    print("   Close the window to exit.")

    cv2.imshow("Inventory Detection", result_img)
    cv2.waitKey(0)
    cv2.destroyAllWindows()

    print("\n" + "=" * 60)
    if region.confidence > 0.8:
        print("SUCCESS: Inventory detection looks good!")
    elif region.confidence > 0.5:
        print("PARTIAL: Detection might work, but verify the green box is correct.")
    else:
        print("FAILED: Detection is likely wrong.")
        print("\nTroubleshooting:")
        print("1. Run setup_inventory.bat to configure manually")
        print("2. Select your inventory carefully")
        print("3. Choose option 2 (Manual) if template doesn't work")

    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
