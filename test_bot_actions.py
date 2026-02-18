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
    """Draw an enhanced detection marker with semi-transparent overlay."""
    if position:
        x, y = position

        # Add semi-transparent filled circle for better visibility
        overlay = image.copy()
        cv2.circle(overlay, (x, y), size // 2, color, -1)
        cv2.addWeighted(overlay, 0.3, image, 0.7, 0, image)

        # Draw crosshair
        cv2.line(image, (x - size, y), (x + size, y), color, 2)
        cv2.line(image, (x, y - size), (x, y + size), color, 2)
        cv2.circle(image, (x, y), size // 2, color, 2)

        # Add background box for label text (better readability)
        text_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0]
        cv2.rectangle(image,
                      (x + size - 5, y - size - text_size[1] - 10),
                      (x + size + text_size[0] + 5, y - size),
                      (0, 0, 0), -1)

        # Draw label (white text on black background)
        cv2.putText(image, label, (x + size, y - size - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)


def draw_inventory_grid(image, inventory_detector, color=(0, 255, 0)):
    """Draw inventory grid with slot numbers."""
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


def draw_inventory_border(image, inventory_detector, color=(0, 255, 0)):
    """Draw a colored border around the inventory area."""
    x = inventory_detector.config.get('x')
    y = inventory_detector.config.get('y')
    slot_width = inventory_detector.config.get('slot_width', 42)
    slot_height = inventory_detector.config.get('slot_height', 36)

    # Calculate inventory bounds (4 columns x 7 rows)
    width = slot_width * 4
    height = slot_height * 7

    # Convert to screen coordinates if needed
    bounds = inventory_detector.screen.window_bounds
    if bounds:
        screen_x = bounds.x + x
        screen_y = bounds.y + y
    else:
        screen_x = x
        screen_y = y

    # Draw thick border
    cv2.rectangle(image, (screen_x - 2, screen_y - 2),
                  (screen_x + width + 2, screen_y + height + 2), color, 3)


def main():
    """Test all bot actions with sequential visual feedback."""
    print("=" * 70)
    print("OSRS Herb Bot - Comprehensive Action Test")
    print("=" * 70)
    print("\nThis test will show visual results immediately after each test.")
    print("Press any key to advance between tests.\n")

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

    # Storage for test results
    test_results = {}

    # ========================================================================
    # TEST 1: Window + Inventory Detection
    # ========================================================================
    print("=" * 70)
    print("TEST 1: Window + Inventory Detection")
    print("=" * 70)

    bounds = screen.find_window()
    if not bounds:
        print("❌ FAILED: Could not find RuneLite window!")
        print("   Make sure RuneLite is running.")
        return 1

    print(f"✓ Found window at ({bounds.x}, {bounds.y})")
    print(f"  Size: {bounds.width}x{bounds.height}")

    # Capture window
    window_img = screen.capture_window()
    if window_img is None:
        print("❌ FAILED: Could not capture window!")
        return 1

    # Detect inventory
    inventory.detect_inventory_state()

    grimy_count = inventory.count_grimy_herbs()
    clean_count = inventory.count_clean_herbs()
    empty_count = inventory.count_empty_slots()

    print(f"✓ Inventory detected at ({inventory.config.get('x')}, {inventory.config.get('y')})")
    print(f"  Grimy herbs: {grimy_count}")
    print(f"  Clean herbs: {clean_count}")
    print(f"  Empty slots: {empty_count}")

    # Draw inventory visualization
    test1_img = window_img.copy()
    draw_inventory_grid(test1_img, inventory, (0, 255, 0))
    draw_inventory_border(test1_img, inventory, (0, 255, 0))

    # Show Test 1 result
    print("\nShowing inventory detection... (Press any key to continue)")
    cv2.imshow("Test 1: Inventory Detection", test1_img)
    cv2.waitKey(0)
    cv2.destroyAllWindows()

    test_results["Window Detection"] = "✓ PASS"
    test_results["Inventory Detection"] = "✓ PASS"

    # ========================================================================
    # TEST 2: Bank Booth Detection
    # ========================================================================
    print("\n" + "=" * 70)
    print("TEST 2: Bank Booth/Chest Detection")
    print("=" * 70)
    print("Make sure you're standing near a bank booth or chest.\n")

    # Capture fresh screenshot
    window_img = screen.capture_window()
    booth_pos = bank.find_bank_booth()

    if booth_pos:
        print(f"✓ Bank booth detected at ({booth_pos[0]}, {booth_pos[1]})")
        test_results["Bank Booth"] = "✓ PASS"
    else:
        print("❌ Could not find bank booth/chest")
        print("  Options:")
        print("  1. Stand closer to a bank")
        print("  2. Capture bank_booth.png template (see template setup)")
        print("  3. Try with bank_chest.png if using a chest")
        test_results["Bank Booth"] = "❌ FAIL"

    # Draw visualization
    test2_img = window_img.copy()
    draw_inventory_grid(test2_img, inventory, (0, 255, 0))
    draw_inventory_border(test2_img, inventory, (0, 255, 0))
    if booth_pos:
        draw_detection(test2_img, booth_pos, "BANK", (255, 255, 0), 30)

    # Show Test 2 result
    print("\nShowing bank booth detection... (Press any key to continue)")
    cv2.imshow("Test 2: Bank Booth Detection", test2_img)
    cv2.waitKey(0)
    cv2.destroyAllWindows()

    # ========================================================================
    # TEST 3: Bank Interface Detection
    # ========================================================================
    print("\n" + "=" * 70)
    print("ACTION REQUIRED: Open Bank Interface")
    print("=" * 70)
    print("Please click on a bank booth/chest to open the bank.")
    print("Once the bank interface is open, press ENTER to continue...")
    input()

    # Capture fresh screenshot with bank open
    window_img = screen.capture_window()
    bank_state = bank.detect_bank_state()

    if bank_state.is_open:
        print("✓ Bank interface detected as OPEN")

        # Test deposit button
        if bank_state.deposit_button:
            print(f"  ✓ Deposit button: ({bank_state.deposit_button[0]}, {bank_state.deposit_button[1]})")
            test_results["Deposit Button"] = "✓ PASS"
        else:
            print("  ⚠ Deposit button not found")
            print("    Capture deposit_all.png template if needed")
            test_results["Deposit Button"] = "⚠ WARN"

        # Test close button
        if bank_state.close_button:
            print(f"  ✓ Close button: ({bank_state.close_button[0]}, {bank_state.close_button[1]})")
        else:
            print("  ⚠ Close button not found (will use ESC key)")

        # Test grimy herb in bank
        if bank_state.grimy_herb_location:
            print(f"  ✓ Grimy herbs in bank: ({bank_state.grimy_herb_location[0]}, {bank_state.grimy_herb_location[1]})")
            test_results["Grimy Herbs in Bank"] = "✓ PASS"
        else:
            print("  ⚠ Grimy herbs not found in bank")
            print("    Make sure you have grimy herbs in your bank")
            print("    Capture template for your herb type (e.g., grimy_ranarr.png)")
            test_results["Grimy Herbs in Bank"] = "⚠ WARN"

        # Draw all bank interface elements
        test3_img = window_img.copy()
        draw_inventory_grid(test3_img, inventory, (0, 255, 0))
        draw_inventory_border(test3_img, inventory, (0, 255, 0))

        if bank_state.deposit_button:
            draw_detection(test3_img, bank_state.deposit_button, "DEPOSIT", (0, 255, 255), 20)
        if bank_state.close_button:
            draw_detection(test3_img, bank_state.close_button, "CLOSE", (0, 165, 255), 20)
        if bank_state.grimy_herb_location:
            draw_detection(test3_img, bank_state.grimy_herb_location, "HERBS", (255, 0, 255), 25)

        test_results["Bank Interface"] = "✓ PASS"
    else:
        print("⚠ Bank interface not detected as open")
        print("  If you opened the bank, check bank templates")
        test3_img = window_img.copy()
        draw_inventory_grid(test3_img, inventory, (0, 255, 0))
        draw_inventory_border(test3_img, inventory, (0, 255, 0))
        test_results["Bank Interface"] = "⚠ SKIP"

    # Show Test 3 result
    print("\nShowing bank interface detection... (Press any key to continue)")
    cv2.imshow("Test 3: Bank Interface Detection", test3_img)
    cv2.waitKey(0)
    cv2.destroyAllWindows()

    # ========================================================================
    # TEST 4: Grimy Herb Click Targets
    # ========================================================================
    print("\n" + "=" * 70)
    print("ACTION REQUIRED: Add Grimy Herbs to Inventory")
    print("=" * 70)
    print("Please put grimy herbs in your inventory for this test.")
    print("Once you have herbs in inventory, press ENTER to continue...")
    input()

    # Refresh inventory state
    window_img = screen.capture_window()
    inventory.detect_inventory_state()
    grimy_slots = inventory.get_grimy_slots()

    if grimy_slots:
        print(f"✓ Found {len(grimy_slots)} grimy herb(s) in inventory")

        for i, slot in enumerate(grimy_slots[:5]):  # Show first 5
            screen_x, screen_y = inventory.get_slot_screen_coords(slot.index)
            print(f"  Slot {slot.index}: ({screen_x}, {screen_y}) - {slot.item_name}")

        if len(grimy_slots) > 5:
            print(f"  ... and {len(grimy_slots) - 5} more")

        test_results["Grimy Herbs in Inventory"] = "✓ PASS"
    else:
        print("⚠ No grimy herbs found in inventory")
        print("  Put some grimy herbs in inventory for full test")
        test_results["Grimy Herbs in Inventory"] = "⚠ WARN"

    # Draw visualization
    test4_img = window_img.copy()
    draw_inventory_grid(test4_img, inventory, (0, 255, 0))
    draw_inventory_border(test4_img, inventory, (0, 255, 0))

    # Draw click targets for each grimy herb
    for slot in grimy_slots:
        screen_x, screen_y = inventory.get_slot_screen_coords(slot.index)
        draw_detection(test4_img, (screen_x, screen_y), f"HERB{slot.index}", (0, 255, 0), 15)

    # Show Test 4 result
    print("\nShowing grimy herb click targets... (Press any key to continue)")
    cv2.imshow("Test 4: Grimy Herb Click Targets", test4_img)
    cv2.waitKey(0)
    cv2.destroyAllWindows()

    # ========================================================================
    # TEST 5: Final Composite (All Detections)
    # ========================================================================
    print("\n" + "=" * 70)
    print("TEST 5: Final Composite - All Detections")
    print("=" * 70)
    print("Re-capturing final screenshot with all elements...\n")

    # Capture final screenshot (with bank still open if possible)
    window_img = screen.capture_window()
    final_img = window_img.copy()

    # Re-detect everything for final composite
    inventory.detect_inventory_state()
    bank_state = bank.detect_bank_state()
    booth_pos = bank.find_bank_booth()
    grimy_slots = inventory.get_grimy_slots()

    # Draw ALL detections on one image
    draw_inventory_grid(final_img, inventory, (0, 255, 0))
    draw_inventory_border(final_img, inventory, (0, 255, 0))

    if booth_pos:
        draw_detection(final_img, booth_pos, "BANK", (255, 255, 0), 30)

    if bank_state.is_open:
        if bank_state.deposit_button:
            draw_detection(final_img, bank_state.deposit_button, "DEPOSIT", (0, 255, 255), 20)
        if bank_state.close_button:
            draw_detection(final_img, bank_state.close_button, "CLOSE", (0, 165, 255), 20)
        if bank_state.grimy_herb_location:
            draw_detection(final_img, bank_state.grimy_herb_location, "HERBS", (255, 0, 255), 25)

    for slot in grimy_slots:
        screen_x, screen_y = inventory.get_slot_screen_coords(slot.index)
        draw_detection(final_img, (screen_x, screen_y), f"H{slot.index}", (0, 255, 0), 15)

    # Save composite image
    output_path = Path(__file__).parent / "bot_actions_test_result.png"
    cv2.imwrite(str(output_path), final_img)
    print(f"✓ Saved composite image to: {output_path}")

    # ========================================================================
    # SUMMARY REPORT
    # ========================================================================
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)

    for test, result in test_results.items():
        print(f"  {test:.<30} {result}")

    print()

    # Check for critical failures
    critical_failures = []
    if test_results.get("Bank Booth") == "❌ FAIL":
        critical_failures.append("Bank booth detection")
    if bank_state.is_open and test_results.get("Grimy Herbs in Bank") == "⚠ WARN":
        critical_failures.append("Grimy herbs in bank")

    if critical_failures:
        print("❌ CRITICAL FAILURES:")
        for failure in critical_failures:
            print(f"   - {failure}")
        print("\nBot may not work correctly. Fix these issues first!")
    else:
        print("✓ ALL CRITICAL TESTS PASSED!")
        print("\nOptional improvements:")
        if test_results.get("Deposit Button") == "⚠ WARN":
            print("  - Capture deposit_all.png template")
        if not bank_state.close_button:
            print("  - Capture bank_close.png template (ESC works as fallback)")
        if test_results.get("Grimy Herbs in Inventory") == "⚠ WARN":
            print("  - Put grimy herbs in inventory to test herb detection")

    # Show final composite
    print("\n" + "=" * 70)
    print("Showing final composite with ALL detections... (Press any key to exit)")
    cv2.imshow("Test 5: Final Composite - All Detections", final_img)
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
