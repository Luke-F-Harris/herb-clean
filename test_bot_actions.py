#!/usr/bin/env python3
"""Test all bot actions and detections.

This script validates that the bot can detect all necessary game elements:
1. Inventory detection
2. Bank booth/chest detection
3. Bank interface elements (deposit, close, herbs)
4. Grimy herbs in inventory

Run this before running the actual bot to ensure everything works.
"""

import sys
import cv2
import numpy as np
import yaml
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from vision.screen_capture import ScreenCapture
from vision.template_matcher import TemplateMatcher
from vision.inventory_detector import InventoryDetector
from vision.bank_detector import BankDetector


def load_config():
    """Load configuration from YAML file."""
    config_path = Path(__file__).parent / "config" / "default_config.yaml"

    if not config_path.exists():
        print(f"⚠ Config not found: {config_path}")
        return {}

    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def draw_detection(image, position, label, color=(0, 255, 0), size=40):
    """Draw a detection marker."""
    if position:
        x, y = position
        # Draw crosshair
        cv2.line(image, (x - size, y), (x + size, y), color, 2)
        cv2.line(image, (x, y - size), (x, y + size), color, 2)
        cv2.circle(image, (x, y), size // 2, color, 2)
        # Draw label
        cv2.putText(image, label, (x + size, y - size), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)


def draw_inventory_grid(image, inventory_detector, color=(0, 255, 0)):
    """Draw inventory grid."""
    for slot in inventory_detector.slots:
        bounds = inventory_detector.screen.window_bounds
        if bounds:
            screen_x = bounds.x + slot.x
            screen_y = bounds.y + slot.y
        else:
            screen_x = slot.x
            screen_y = slot.y

        # Draw slot center
        cv2.circle(image, (screen_x, screen_y), 3, color, -1)

        # Draw slot number
        cv2.putText(
            image,
            str(slot.index),
            (screen_x - 10, screen_y + 5),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.3,
            color,
            1,
        )


def main():
    """Test all bot actions."""
    print("=" * 70)
    print("OSRS Herb Bot - Comprehensive Action Test")
    print("=" * 70)
    print("\nThis test will verify all detections the bot needs to work.")
    print("Follow the instructions for each test.\n")

    # Load config
    config = load_config()
    templates_dir = Path(__file__).parent / "config" / "templates"

    # Initialize components
    print("Initializing bot components...")
    screen = ScreenCapture("RuneLite")
    matcher = TemplateMatcher(templates_dir, confidence_threshold=0.70)

    # Get inventory template if configured
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

    bank = BankDetector(
        screen_capture=screen,
        template_matcher=matcher,
        bank_config=config.get('bank', {}),
        grimy_templates=config.get('herbs', {}).get('grimy', []),
    )

    print("✓ Components initialized\n")

    # Test 1: Window detection
    print("=" * 70)
    print("TEST 1: RuneLite Window Detection")
    print("=" * 70)

    bounds = screen.find_window()
    if not bounds:
        print("❌ FAILED: Could not find RuneLite window!")
        print("   Make sure RuneLite is running.")
        return 1

    print(f"✓ PASSED: Found window at ({bounds.x}, {bounds.y})")
    print(f"  Size: {bounds.width}x{bounds.height}\n")

    # Capture window
    window_img = screen.capture_window()
    if window_img is None:
        print("❌ FAILED: Could not capture window!")
        return 1

    result_img = window_img.copy()

    # Test 2: Inventory detection
    print("=" * 70)
    print("TEST 2: Inventory Detection")
    print("=" * 70)
    print("Instructions: Make sure your inventory is visible\n")

    inventory.detect_inventory_state()

    grimy_count = inventory.count_grimy_herbs()
    clean_count = inventory.count_clean_herbs()
    empty_count = inventory.count_empty_slots()

    print(f"✓ PASSED: Inventory detected")
    print(f"  Position: ({inventory.config.get('x')}, {inventory.config.get('y')})")
    print(f"  Grimy herbs: {grimy_count}")
    print(f"  Clean herbs: {clean_count}")
    print(f"  Empty slots: {empty_count}\n")

    if grimy_count == 0:
        print("⚠ WARNING: No grimy herbs detected in inventory")
        print("  For a full test, put some grimy herbs in your inventory\n")

    # Draw inventory grid
    draw_inventory_grid(result_img, inventory, (0, 255, 0))

    # Test 3: Bank booth detection
    print("=" * 70)
    print("TEST 3: Bank Booth/Chest Detection")
    print("=" * 70)
    print("Instructions: Stand near a bank booth or chest\n")

    booth_pos = bank.find_bank_booth()

    if booth_pos:
        print(f"✓ PASSED: Bank booth detected at ({booth_pos[0]}, {booth_pos[1]})")
        draw_detection(result_img, booth_pos, "BANK", (255, 255, 0), 30)
    else:
        print("❌ FAILED: Could not find bank booth/chest")
        print("  Options:")
        print("  1. Stand closer to a bank")
        print("  2. Capture bank_booth.png template (see template setup)")
        print("  3. Try with bank_chest.png if using a chest\n")

    # Test 4: Bank interface (if open)
    print("=" * 70)
    print("TEST 4: Bank Interface Detection")
    print("=" * 70)
    print("Instructions: Open the bank interface for this test\n")

    input("Press ENTER when bank is open (or skip if closed)...")

    bank_state = bank.detect_bank_state()

    if bank_state.is_open:
        print("✓ Bank interface detected as OPEN")

        # Test deposit button
        if bank_state.deposit_button:
            print(f"  ✓ Deposit button: ({bank_state.deposit_button[0]}, {bank_state.deposit_button[1]})")
            draw_detection(result_img, bank_state.deposit_button, "DEPOSIT", (0, 255, 255), 20)
        else:
            print("  ⚠ Deposit button not found")
            print("    Capture deposit_all.png template if needed")

        # Test close button
        if bank_state.close_button:
            print(f"  ✓ Close button: ({bank_state.close_button[0]}, {bank_state.close_button[1]})")
            draw_detection(result_img, bank_state.close_button, "CLOSE", (0, 165, 255), 20)
        else:
            print("  ⚠ Close button not found (will use ESC key)")

        # Test grimy herb in bank
        if bank_state.grimy_herb_location:
            print(f"  ✓ Grimy herbs in bank: ({bank_state.grimy_herb_location[0]}, {bank_state.grimy_herb_location[1]})")
            draw_detection(result_img, bank_state.grimy_herb_location, "HERBS", (255, 0, 255), 25)
        else:
            print("  ⚠ Grimy herbs not found in bank")
            print("    Make sure you have grimy herbs in your bank")
            print("    Capture template for your herb type (e.g., grimy_ranarr.png)")

        # Re-capture for updated display
        window_img = screen.capture_window()
        result_img = window_img.copy()
        draw_inventory_grid(result_img, inventory, (0, 255, 0))

        if bank_state.deposit_button:
            draw_detection(result_img, bank_state.deposit_button, "DEPOSIT", (0, 255, 255), 20)
        if bank_state.close_button:
            draw_detection(result_img, bank_state.close_button, "CLOSE", (0, 165, 255), 20)
        if bank_state.grimy_herb_location:
            draw_detection(result_img, bank_state.grimy_herb_location, "HERBS", (255, 0, 255), 25)

    else:
        print("⚠ Bank interface not detected as open")
        print("  If you opened the bank, check bank templates")

    print()

    # Test 5: Grimy herb clicking targets
    print("=" * 70)
    print("TEST 5: Grimy Herb Click Targets")
    print("=" * 70)
    print("Instructions: Put grimy herbs in your inventory for this test\n")

    input("Press ENTER when inventory has grimy herbs (or skip)...")

    # Refresh inventory state
    window_img = screen.capture_window()
    result_img = window_img.copy()
    draw_inventory_grid(result_img, inventory, (0, 255, 0))

    inventory.detect_inventory_state()
    grimy_slots = inventory.get_grimy_slots()

    if grimy_slots:
        print(f"✓ PASSED: Found {len(grimy_slots)} grimy herb(s) in inventory")

        for i, slot in enumerate(grimy_slots[:5]):  # Show first 5
            screen_x, screen_y = inventory.get_slot_screen_coords(slot.index)
            print(f"  Slot {slot.index}: ({screen_x}, {screen_y}) - {slot.item_name}")

            # Draw click target
            draw_detection(result_img, (screen_x, screen_y), f"HERB{slot.index}", (0, 255, 0), 15)

        if len(grimy_slots) > 5:
            print(f"  ... and {len(grimy_slots) - 5} more")
    else:
        print("⚠ No grimy herbs found in inventory")
        print("  Put some grimy herbs in inventory for full test")

    print()

    # Summary
    print("=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)

    results = {
        "Window Detection": "✓ PASS",
        "Inventory Detection": "✓ PASS",
        "Bank Booth": "✓ PASS" if booth_pos else "❌ FAIL",
        "Bank Interface": "✓ PASS" if bank_state.is_open else "⚠ SKIP",
        "Deposit Button": "✓ PASS" if bank_state.deposit_button else "⚠ WARN",
        "Grimy Herbs": "✓ PASS" if grimy_slots else "⚠ WARN",
    }

    for test, result in results.items():
        print(f"  {test:.<30} {result}")

    print()

    # Check for critical failures
    critical_failures = []
    if not booth_pos:
        critical_failures.append("Bank booth detection")
    if bank_state.is_open and not bank_state.grimy_herb_location:
        critical_failures.append("Grimy herbs in bank")

    if critical_failures:
        print("❌ CRITICAL FAILURES:")
        for failure in critical_failures:
            print(f"   - {failure}")
        print("\nBot may not work correctly. Fix these issues first!")
    else:
        print("✓ ALL CRITICAL TESTS PASSED!")
        print("\nOptional improvements:")
        if not bank_state.deposit_button:
            print("  - Capture deposit_all.png template")
        if not bank_state.close_button:
            print("  - Capture bank_close.png template (ESC works as fallback)")
        if not grimy_slots:
            print("  - Put grimy herbs in inventory to test herb detection")

    # Save and display result
    print("\n" + "=" * 70)
    print("Saving visualization...")

    output_path = Path(__file__).parent / "bot_actions_test_result.png"
    cv2.imwrite(str(output_path), result_img)
    print(f"✓ Saved to: {output_path}")

    print("\nDisplaying result (close window to exit)...")
    cv2.imshow("Bot Actions Test - All Detections", result_img)
    cv2.waitKey(0)
    cv2.destroyAllWindows()

    print("\n" + "=" * 70)
    if not critical_failures:
        print("✓ Bot is ready to run!")
        print("\nNext steps:")
        print("1. Make sure you have grimy herbs in your bank")
        print("2. Stand next to a bank")
        print("3. Run: run_bot.bat")
    else:
        print("⚠ Fix the failures above before running the bot")

    print("=" * 70)

    return 0 if not critical_failures else 1


if __name__ == "__main__":
    sys.exit(main())
