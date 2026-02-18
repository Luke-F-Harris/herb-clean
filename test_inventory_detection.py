#!/usr/bin/env python3
"""Test inventory auto-detection.

This script captures a RuneLite window and shows where it detected the inventory.
"""

import sys
import cv2
import numpy as np
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from vision.screen_capture import ScreenCapture
from vision.inventory_auto_detect import InventoryAutoDetector


def main():
    """Test inventory detection."""
    print("=" * 60)
    print("RuneLite Inventory Auto-Detection Test")
    print("=" * 60)

    # Initialize screen capture
    screen = ScreenCapture("RuneLite")

    # Find window
    print("\n1. Looking for RuneLite window...")
    bounds = screen.find_window()
    if not bounds:
        print("ERROR: Could not find RuneLite window!")
        print("Make sure RuneLite is running and visible.")
        return 1

    print(f"✓ Found window at ({bounds.x}, {bounds.y}), size: {bounds.width}x{bounds.height}")

    # Capture window
    print("\n2. Capturing window screenshot...")
    window_img = screen.capture_window()
    if window_img is None:
        print("ERROR: Could not capture window!")
        return 1

    print(f"✓ Captured {window_img.shape[1]}x{window_img.shape[0]} image")

    # Auto-detect inventory
    print("\n3. Auto-detecting inventory...")
    detector = InventoryAutoDetector()
    region = detector.detect_with_fallback(window_img, None)

    if region.confidence > 0:
        print(f"✓ Detected inventory!")
        print(f"  Position: ({region.x}, {region.y})")
        print(f"  Slot size: {region.slot_width}x{region.slot_height}")
        print(f"  Grid: {region.cols}x{region.rows}")
        print(f"  Confidence: {region.confidence:.2%}")
    else:
        print("⚠ Using fallback/default position")
        print(f"  Position: ({region.x}, {region.y})")
        print(f"  Slot size: {region.slot_width}x{region.slot_height}")

    # Draw detection result
    print("\n4. Creating visualization...")
    result_img = window_img.copy()

    # Draw inventory border
    x, y = region.x, region.y
    w = region.slot_width * region.cols
    h = region.slot_height * region.rows

    color = (0, 255, 0) if region.confidence > 0.5 else (0, 165, 255)  # Green or Orange
    cv2.rectangle(result_img, (x, y), (x + w, y + h), color, 2)

    # Draw grid lines
    for row in range(1, region.rows):
        y_line = y + row * region.slot_height
        cv2.line(result_img, (x, y_line), (x + w, y_line), color, 1)

    for col in range(1, region.cols):
        x_line = x + col * region.slot_width
        cv2.line(result_img, (x_line, y), (x_line, y + h), color, 1)

    # Add label
    label = f"Inventory ({region.confidence:.0%})" if region.confidence > 0 else "Inventory (default)"
    cv2.putText(result_img, label, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

    # Save result
    output_path = Path(__file__).parent / "inventory_detection_result.png"
    cv2.imwrite(str(output_path), result_img)

    print(f"✓ Saved visualization to: {output_path}")

    # Show result
    print("\n5. Displaying result...")
    print("   Close the window to exit.")

    cv2.imshow("Inventory Detection", result_img)
    cv2.waitKey(0)
    cv2.destroyAllWindows()

    print("\n" + "=" * 60)
    if region.confidence > 0.5:
        print("SUCCESS: Inventory auto-detection working!")
    else:
        print("WARNING: Auto-detection failed, using default position.")
        print("This may not work correctly. Check that:")
        print("  - RuneLite inventory is fully visible")
        print("  - You're using the default RuneLite theme")
        print("  - GPU plugin is enabled")

    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
