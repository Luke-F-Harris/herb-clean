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
from vision.template_matcher import TemplateMatcher, MatchResult
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


def draw_clickable_box(image, match_result, label, color=(0, 255, 0)):
    """Draw a rectangular box showing clickable area from template match."""
    if match_result and match_result.found:
        # Get bounds
        x = match_result.x
        y = match_result.y
        width = match_result.width
        height = match_result.height

        # Draw thick border box (like inventory)
        cv2.rectangle(image, (x, y), (x + width, y + height), color, 3)

        # Add label with background
        text_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0]
        label_x = x
        label_y = y - 10

        # Draw label background
        cv2.rectangle(image,
                      (label_x, label_y - text_size[1] - 5),
                      (label_x + text_size[0] + 10, label_y + 5),
                      (0, 0, 0), -1)

        # Draw label text
        cv2.putText(image, label, (label_x + 5, label_y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)


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

    # Validate templates
    print("Checking for template files...")
    missing_templates = []

    # Check grimy herb templates
    for herb_config in config.get('herbs', {}).get('grimy', []):
        template_name = herb_config["template"]
        template_path = templates_dir / template_name
        if not template_path.exists():
            missing_templates.append(template_name)

    # Check bank templates
    bank_templates = ["bank_booth.png", "bank_chest.png", "deposit_all.png"]
    for template in bank_templates:
        template_path = templates_dir / template
        if not template_path.exists():
            missing_templates.append(template)

    if missing_templates:
        print("⚠ WARNING: Missing template files!")
        print("  The following templates were not found:")
        for template in missing_templates:
            print(f"    - {template}")
        print()
        print("  Without templates, herb detection will not work.")
        print("  See INVENTORY_SETUP_GUIDE.md for instructions on capturing templates.")
        print()
        response = input("Continue anyway? (y/n): ")
        if response.lower() != 'y':
            print("Exiting...")
            return 1
        print()
    else:
        print("✓ All template files found\n")

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

    # Warning if no herbs detected
    if grimy_count == 0:
        print()
        print("⚠ WARNING: No grimy herbs detected in inventory")
        if missing_templates:
            print("  REASON: Template files are missing (see warning above)")
            print("  ACTION: Capture grimy herb template files to enable detection")
        else:
            print("  Possible reasons:")
            print("  - No grimy herbs in inventory")
            print("  - Template images don't match your herb type/zoom level")
            print("  - Try recapturing templates at your current zoom level")

    # Draw inventory visualization
    test1_img = window_img.copy()
    draw_inventory_grid(test1_img, inventory, (0, 255, 0))
    draw_inventory_border(test1_img, inventory, (0, 255, 0))

    # Show Test 1 result
    cv2.imshow("Test 1: Inventory Detection", test1_img)
    for _ in range(5):
        cv2.waitKey(100)  # Total 500ms for rendering on 4K displays
    print("\nShowing inventory detection...")
    print("Press ENTER in this terminal to continue...")
    input()
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

    # Check if bank templates exist
    booth_template_path = templates_dir / config.get('bank', {}).get('booth_template', 'bank_booth.png')
    chest_template_path = templates_dir / config.get('bank', {}).get('chest_template', 'bank_chest.png')

    has_booth_template = booth_template_path.exists()
    has_chest_template = chest_template_path.exists()

    booth_match = None
    test2_img = None

    if has_booth_template or has_chest_template:
        # Create a faster matcher specifically for bank booth (fewer scale steps)
        bank_matcher = TemplateMatcher(
            templates_dir,
            confidence_threshold=0.75,
            multi_scale=True,
            scale_range=(0.8, 1.2),  # Narrower range
            scale_steps=3  # Fewer steps = faster
        )

        # Retry loop for bank booth detection
        while True:
            # Capture fresh screenshot
            window_img = screen.capture_window()

            print("Searching for bank booth/chest...")
            print("  (This may take 5-15 seconds on 4K displays, please wait...)")

            # Get full match result (not just position)
            if has_booth_template:
                print("  Trying bank_booth.png...", flush=True)
                booth_match = bank_matcher.match(
                    window_img,
                    config.get('bank', {}).get('booth_template', 'bank_booth.png')
                )
                print("  Done.", flush=True)

            if has_chest_template and (booth_match is None or not booth_match.found):
                # Try chest as fallback
                print("  Trying bank_chest.png...", flush=True)
                booth_match = bank_matcher.match(
                    window_img,
                    config.get('bank', {}).get('chest_template', 'bank_chest.png')
                )
                print("  Done.", flush=True)

            if booth_match and booth_match.found:
                # Success! Convert to screen coordinates
                bounds = screen.window_bounds
                if bounds:
                    booth_match.x += bounds.x
                    booth_match.y += bounds.y
                    booth_match.center_x += bounds.x
                    booth_match.center_y += bounds.y

                print(f"✓ Bank booth detected at ({booth_match.center_x}, {booth_match.center_y})")
                print(f"  Clickable area: {booth_match.width}x{booth_match.height} pixels")
                test_results["Bank Booth"] = "✓ PASS"

                # Draw visualization
                test2_img = window_img.copy()
                draw_inventory_grid(test2_img, inventory, (0, 255, 0))
                draw_inventory_border(test2_img, inventory, (0, 255, 0))
                draw_clickable_box(test2_img, booth_match, "BANK", (255, 255, 0))
                break
            else:
                # Detection failed - ask to retry
                print()
                print("❌ Could not find bank booth/chest")
                print("  Options:")
                print("  1. Move closer to a bank booth/chest")
                print("  2. Try a different bank location")
                print("  3. Ensure the bank is clearly visible on screen")
                print()
                retry = input("Retry detection? (y/n): ")
                if retry.lower() != 'y':
                    print("Skipping bank booth detection...")
                    test_results["Bank Booth"] = "⚠ SKIP"
                    # Create a simple screenshot without booth marker
                    test2_img = window_img.copy()
                    draw_inventory_grid(test2_img, inventory, (0, 255, 0))
                    draw_inventory_border(test2_img, inventory, (0, 255, 0))
                    break
    else:
        print("⚠ Skipping: No bank booth/chest templates found")
        print("  Bank booth templates must be captured manually (they vary by location)")
        test_results["Bank Booth"] = "⚠ SKIP"
        # Capture screenshot for inventory only
        window_img = screen.capture_window()
        test2_img = window_img.copy()
        draw_inventory_grid(test2_img, inventory, (0, 255, 0))
        draw_inventory_border(test2_img, inventory, (0, 255, 0))

    # Show Test 2 result (only if we have an image to show)
    if test2_img is not None:
        cv2.imshow("Test 2: Bank Booth Detection", test2_img)
        # Give Windows extra time to render large 4K images with drawings
        for _ in range(5):
            cv2.waitKey(100)  # Total 500ms for rendering
        print("\nShowing bank booth detection...")
        print("Press ENTER in this terminal to continue...")
        input()
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

    # Detect bank interface elements directly to get full MatchResult with dimensions
    deposit_match = matcher.match(
        window_img,
        config.get('bank', {}).get('deposit_all_template', 'deposit_all.png')
    )
    close_match = matcher.match(
        window_img,
        config.get('bank', {}).get('close_button_template', 'bank_close.png')
    )

    # Look for grimy herbs in bank
    herb_match = None
    for herb_config in config.get('herbs', {}).get('grimy', []):
        herb_match = matcher.match(window_img, herb_config['template'])
        if herb_match.found:
            break

    # Convert to screen coordinates
    bounds = screen.window_bounds
    if deposit_match.found and bounds:
        deposit_match.x += bounds.x
        deposit_match.y += bounds.y
        deposit_match.center_x += bounds.x
        deposit_match.center_y += bounds.y

    if close_match.found and bounds:
        close_match.x += bounds.x
        close_match.y += bounds.y
        close_match.center_x += bounds.x
        close_match.center_y += bounds.y

    if herb_match and herb_match.found and bounds:
        herb_match.x += bounds.x
        herb_match.y += bounds.y
        herb_match.center_x += bounds.x
        herb_match.center_y += bounds.y

    # Check if bank is open
    is_bank_open = deposit_match.found or close_match.found

    if is_bank_open:
        print("✓ Bank interface detected as OPEN")

        # Test deposit button
        if deposit_match.found:
            print(f"  ✓ Deposit button: ({deposit_match.center_x}, {deposit_match.center_y})")
            print(f"    Clickable area: {deposit_match.width}x{deposit_match.height} pixels")
            test_results["Deposit Button"] = "✓ PASS"
        else:
            print("  ⚠ Deposit button not found")
            print("    Capture deposit_all.png template if needed")
            test_results["Deposit Button"] = "⚠ WARN"

        # Test close button
        if close_match.found:
            print(f"  ✓ Close button: ({close_match.center_x}, {close_match.center_y})")
            print(f"    Clickable area: {close_match.width}x{close_match.height} pixels")
        else:
            print("  ⚠ Close button not found (will use ESC key)")

        # Test grimy herb in bank
        if herb_match and herb_match.found:
            print(f"  ✓ Grimy herbs in bank: ({herb_match.center_x}, {herb_match.center_y})")
            print(f"    Clickable area: {herb_match.width}x{herb_match.height} pixels")
            test_results["Grimy Herbs in Bank"] = "✓ PASS"
        else:
            print("  ⚠ Grimy herbs not found in bank")
            print("    Make sure you have grimy herbs in your bank")
            print("    Capture template for your herb type (e.g., grimy_ranarr.png)")
            test_results["Grimy Herbs in Bank"] = "⚠ WARN"

        # Draw all bank interface elements with boxes
        test3_img = window_img.copy()
        draw_inventory_grid(test3_img, inventory, (0, 255, 0))
        draw_inventory_border(test3_img, inventory, (0, 255, 0))

        # Draw clickable boxes for each element
        if deposit_match.found:
            draw_clickable_box(test3_img, deposit_match, "DEPOSIT BUTTON", (0, 255, 255))
        if close_match.found:
            draw_clickable_box(test3_img, close_match, "CLOSE BUTTON", (0, 165, 255))
        if herb_match and herb_match.found:
            draw_clickable_box(test3_img, herb_match, "GRIMY HERBS", (255, 0, 255))

        test_results["Bank Interface"] = "✓ PASS"
    else:
        print("⚠ Bank interface not detected as open")
        print("  If you opened the bank, check bank templates")
        test3_img = window_img.copy()
        draw_inventory_grid(test3_img, inventory, (0, 255, 0))
        draw_inventory_border(test3_img, inventory, (0, 255, 0))
        test_results["Bank Interface"] = "⚠ SKIP"

    # Show Test 3 result
    cv2.imshow("Test 3: Bank Interface Detection", test3_img)
    for _ in range(5):
        cv2.waitKey(100)  # Total 500ms for rendering on 4K displays
    print("\nShowing bank interface detection...")
    print("Press ENTER in this terminal to continue...")
    input()
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
    cv2.imshow("Test 4: Grimy Herb Click Targets", test4_img)
    for _ in range(5):
        cv2.waitKey(100)  # Total 500ms for rendering on 4K displays
    print("\nShowing grimy herb click targets...")
    print("Press ENTER in this terminal to continue...")
    input()
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
    grimy_slots = inventory.get_grimy_slots()

    # Get bank booth match result for box visualization
    booth_match = bank_matcher.match(
        window_img,
        config.get('bank', {}).get('booth_template', 'bank_booth.png')
    )
    if not booth_match.found:
        booth_match = bank_matcher.match(
            window_img,
            config.get('bank', {}).get('chest_template', 'bank_chest.png')
        )

    # Get bank interface elements
    deposit_match_final = matcher.match(
        window_img,
        config.get('bank', {}).get('deposit_all_template', 'deposit_all.png')
    )
    close_match_final = matcher.match(
        window_img,
        config.get('bank', {}).get('close_button_template', 'bank_close.png')
    )
    herb_match_final = None
    for herb_config in config.get('herbs', {}).get('grimy', []):
        herb_match_final = matcher.match(window_img, herb_config['template'])
        if herb_match_final.found:
            break

    # Convert to screen coordinates
    bounds = screen.window_bounds
    if booth_match.found and bounds:
        booth_match.x += bounds.x
        booth_match.y += bounds.y

    if deposit_match_final.found and bounds:
        deposit_match_final.x += bounds.x
        deposit_match_final.y += bounds.y

    if close_match_final.found and bounds:
        close_match_final.x += bounds.x
        close_match_final.y += bounds.y

    if herb_match_final and herb_match_final.found and bounds:
        herb_match_final.x += bounds.x
        herb_match_final.y += bounds.y

    # Draw ALL detections on one image
    draw_inventory_grid(final_img, inventory, (0, 255, 0))
    draw_inventory_border(final_img, inventory, (0, 255, 0))

    # Draw bank booth
    draw_clickable_box(final_img, booth_match, "BANK BOOTH", (255, 255, 0))

    # Draw bank interface elements with boxes
    if deposit_match_final.found:
        draw_clickable_box(final_img, deposit_match_final, "DEPOSIT BUTTON", (0, 255, 255))
    if close_match_final.found:
        draw_clickable_box(final_img, close_match_final, "CLOSE BUTTON", (0, 165, 255))
    if herb_match_final and herb_match_final.found:
        draw_clickable_box(final_img, herb_match_final, "GRIMY HERBS (BANK)", (255, 0, 255))

    # Draw inventory herb slots
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
    cv2.imshow("Test 5: Final Composite - All Detections", final_img)
    for _ in range(5):
        cv2.waitKey(100)  # Total 500ms for rendering on 4K displays
    print("Showing final composite with ALL detections...")
    print("Press ENTER in this terminal to exit...")
    input()
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
