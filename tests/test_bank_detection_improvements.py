#!/usr/bin/env python3
"""Test the improved bank detection and herb matching.

This script validates:
1. Scale-aware bank region detection
2. Hybrid color + template herb matching
3. Overall detection accuracy
"""

import cv2
import numpy as np
import yaml
from pathlib import Path

from src.vision.screen_capture import ScreenCapture
from src.vision.template_matcher import TemplateMatcher
from src.vision.bank_detector import BankDetector


def draw_region(image, region, color, label):
    """Draw a labeled rectangle on the image."""
    if region is None:
        return

    x, y, width, height = region

    # Draw rectangle
    cv2.rectangle(image, (x, y), (x + width, y + height), color, 2)

    # Draw label background
    label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0]
    cv2.rectangle(
        image,
        (x, y - label_size[1] - 10),
        (x + label_size[0] + 10, y),
        color,
        -1
    )

    # Draw label text
    cv2.putText(
        image,
        label,
        (x + 5, y - 5),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (255, 255, 255),
        2
    )


def main():
    """Test bank detection improvements."""
    print("🔍 Testing Bank Detection Improvements")
    print("=" * 80)

    # Load config
    config_path = Path("config/default_config.yaml")
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    # Initialize components
    templates_dir = Path("config/templates")

    screen = ScreenCapture(config['window']['title'])

    matcher = TemplateMatcher(
        templates_dir=templates_dir,
        confidence_threshold=config['vision']['confidence_threshold'],
        multi_scale=config['vision']['multi_scale'],
        scale_range=tuple(config['vision']['scale_range']),
        scale_steps=config['vision']['scale_steps'],
    )

    detector = BankDetector(
        screen_capture=screen,
        template_matcher=matcher,
        bank_config=config['bank'],
        grimy_templates=config['herbs']['grimy'],
    )

    # Capture current screen
    print("\n📸 Capturing screen...")
    screen_image = screen.capture_window()

    if screen_image is None:
        print("❌ Failed to capture screen. Is RuneLite running?")
        return

    print(f"✅ Captured {screen_image.shape[1]}x{screen_image.shape[0]} image")

    # Test 1: Bank region detection
    print("\n" + "=" * 80)
    print("Test 1: Bank Region Detection (Scale-Aware)")
    print("=" * 80)

    # Find close button
    close_match = matcher.match(screen_image, config['bank']['close_button_template'])

    if close_match.found:
        print(f"✅ Found close button at ({close_match.x}, {close_match.y})")
        print(f"   Scale detected: {close_match.scale:.2f}x")
        print(f"   Confidence: {close_match.confidence:.3f}")
    else:
        print("❌ Close button not found. Is bank open?")

    # Get bank region using new scale-aware method
    bank_region = detector._get_bank_item_region(screen_image)

    if bank_region:
        x, y, width, height = bank_region
        print(f"\n✅ Bank region detected:")
        print(f"   Position: ({x}, {y})")
        print(f"   Size: {width}x{height}")
        print(f"   Scale factor applied: {close_match.scale:.2f}x")

        # Check if region seems reasonable
        if width < 100 or height < 100:
            print(f"   ⚠️  Region seems too small")
        elif width > screen_image.shape[1] * 0.8:
            print(f"   ⚠️  Region seems too wide")
        else:
            print(f"   ✅ Region size looks reasonable")
    else:
        print("❌ Failed to detect bank region")

    # Test 2: Herb detection
    print("\n" + "=" * 80)
    print("Test 2: Hybrid Color + Template Herb Detection")
    print("=" * 80)

    if bank_region:
        # Extract bank region for analysis
        x, y, width, height = bank_region
        bank_image = screen_image[y:y+height, x:x+width]

        # Get all herb template names
        template_names = [herb['template'] for herb in config['herbs']['grimy']]

        print(f"\n🎨 Running color pre-filter on {len(template_names)} herb templates...")

        # Test color filtering
        color_candidates = matcher.filter_templates_by_color(
            bank_image,
            template_names,
            top_k=3
        )

        print(f"\n✅ Top 3 color matches:")
        for i, (template_name, similarity) in enumerate(color_candidates):
            herb_name = template_name.replace('grimy_', '').replace('.png', '')
            print(f"   {i+1}. {herb_name:15} - Color similarity: {similarity:.3f}")

    # Find herb in bank using hybrid approach
    print(f"\n🔍 Running hybrid detection...")
    herb_match = detector.find_grimy_herb_in_bank()

    if herb_match:
        print(f"\n✅ Herb detected:")
        print(f"   Position: ({herb_match.x}, {herb_match.y})")
        print(f"   Size: {herb_match.width}x{herb_match.height}")
        print(f"   Confidence: {herb_match.confidence:.3f}")

        # Determine which herb was matched
        # We need to re-run to see which template matched
        # This is a limitation - we should store the template name in MatchResult
        print(f"   ⚠️  Note: Template name not stored in result (enhancement needed)")
    else:
        print("❌ No herb detected in bank")

    # Visualize results
    print("\n" + "=" * 80)
    print("Visualization")
    print("=" * 80)

    # Create visualization image
    vis_image = screen_image.copy()

    # Draw bank region (green)
    if bank_region:
        draw_region(vis_image, bank_region, (0, 255, 0), "Bank Region (Scale-Aware)")

    # Draw close button (blue)
    if close_match.found:
        close_region = (
            close_match.x,
            close_match.y,
            close_match.width,
            close_match.height
        )
        draw_region(vis_image, close_region, (255, 0, 0), f"Close (scale={close_match.scale:.2f})")

    # Draw herb match (red)
    if herb_match:
        herb_region = (
            herb_match.x,
            herb_match.y,
            herb_match.width,
            herb_match.height
        )
        draw_region(vis_image, herb_region, (0, 0, 255), f"Herb (conf={herb_match.confidence:.2f})")

    # Save visualization
    output_path = Path("debug_improved_bank_detection.png")
    cv2.imwrite(str(output_path), vis_image)
    print(f"\n💾 Saved visualization to: {output_path}")

    # Display if possible
    try:
        # Resize for display if too large
        display_image = vis_image
        max_display_width = 1920
        if vis_image.shape[1] > max_display_width:
            scale = max_display_width / vis_image.shape[1]
            new_width = max_display_width
            new_height = int(vis_image.shape[0] * scale)
            display_image = cv2.resize(vis_image, (new_width, new_height))

        cv2.imshow("Bank Detection Test", display_image)
        print("\n👁️  Displaying visualization window...")
        print("   Press any key to close")
        cv2.waitKey(0)
        cv2.destroyAllWindows()
    except:
        print("   (Display not available, check saved file)")

    # Summary
    print("\n" + "=" * 80)
    print("Summary")
    print("=" * 80)

    print(f"\n✅ Improvements implemented:")
    print(f"   1. Scale-aware bank region detection")
    print(f"   2. Narrowed multi-scale range (0.9-1.1 instead of 0.7-1.3)")
    print(f"   3. Reduced scale steps (3 instead of 7)")
    print(f"   4. Hybrid color + template herb matching")

    print(f"\n📊 Results:")
    print(f"   Close button: {'✅ Found' if close_match.found else '❌ Not found'}")
    print(f"   Bank region: {'✅ Detected' if bank_region else '❌ Not detected'}")
    print(f"   Herb match: {'✅ Found' if herb_match else '❌ Not found'}")

    if close_match.found:
        print(f"\n   Detected scale: {close_match.scale:.2f}x")
        print(f"   This scale factor is now used for bank region offsets")

    print("\n✅ Testing complete!")


if __name__ == "__main__":
    main()
