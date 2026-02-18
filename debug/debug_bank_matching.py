#!/usr/bin/env python3
"""Debug script to show matching confidence for all herb templates."""

import sys
from pathlib import Path

print("Starting debug script...")
print(f"Python version: {sys.version}")
print(f"Script location: {Path(__file__).parent}")
print()

# Check imports
print("Checking imports...")
try:
    import cv2
    print("✓ cv2 (OpenCV) imported")
except ImportError as e:
    print(f"✗ Failed to import cv2: {e}")
    print("  Install with: pip install opencv-python")
    input("Press ENTER to exit...")
    sys.exit(1)

try:
    import yaml
    print("✓ yaml imported")
except ImportError as e:
    print(f"✗ Failed to import yaml: {e}")
    print("  Install with: pip install pyyaml")
    input("Press ENTER to exit...")
    sys.exit(1)

try:
    import numpy as np
    print("✓ numpy imported")
except ImportError as e:
    print(f"✗ Failed to import numpy: {e}")
    print("  Install with: pip install numpy")
    input("Press ENTER to exit...")
    sys.exit(1)

print()

# Add src to path (go up to project root, then into src)
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

print(f"Project root: {project_root}")
print(f"Adding to path: {project_root / 'src'}")
print()

try:
    from vision.screen_capture import ScreenCapture
    print("✓ ScreenCapture imported")
except ImportError as e:
    print(f"✗ Failed to import ScreenCapture: {e}")
    print(f"  Looked in: {project_root / 'src' / 'vision'}")
    input("Press ENTER to exit...")
    sys.exit(1)

try:
    from vision.template_matcher import TemplateMatcher
    print("✓ TemplateMatcher imported")
except ImportError as e:
    print(f"✗ Failed to import TemplateMatcher: {e}")
    input("Press ENTER to exit...")
    sys.exit(1)

try:
    from vision.bank_detector import BankDetector
    print("✓ BankDetector imported")
except ImportError as e:
    print(f"✗ Failed to import BankDetector: {e}")
    input("Press ENTER to exit...")
    sys.exit(1)

print("✓ All imports successful")
print()


def main():
    print("=" * 70)
    print("BANK HERB MATCHING CONFIDENCE DEBUG")
    print("=" * 70)
    print()
    print("SETUP INSTRUCTIONS:")
    print("1. Open RuneLite OSRS")
    print("2. Open your bank interface")
    print("3. Make sure grimy herbs are visible WITH stack numbers")
    print("4. Keep the bank window open")
    print()
    print("Press ENTER when ready...")
    input()
    print()
    print("Starting detection...")

    # Load config (from project root)
    project_root = Path(__file__).parent.parent
    config_path = project_root / "config" / "default_config.yaml"
    print(f"Loading config from: {config_path}")

    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        print("✓ Config loaded")
    except Exception as e:
        print(f"ERROR: Could not load config: {e}")
        return 1

    # Initialize
    templates_dir = project_root / "config" / "templates"
    print(f"Templates directory: {templates_dir}")

    screen = ScreenCapture("RuneLite")
    print("✓ Screen capture initialized")

    matcher = TemplateMatcher(
        templates_dir,
        confidence_threshold=config['vision']['confidence_threshold'],
        multi_scale=config['vision']['multi_scale'],
        scale_range=tuple(config['vision']['scale_range']),
        scale_steps=config['vision']['scale_steps']
    )
    print("✓ Template matcher initialized")
    print(f"  Using scale range: {config['vision']['scale_range']}")
    print(f"  Using {config['vision']['scale_steps']} scale steps")
    print(f"  Confidence threshold: {config['vision']['confidence_threshold']}")

    # Check template transparency handling
    print()
    print("Checking template transparency handling...")
    test_template = config['herbs']['grimy'][0]['template']
    _ = matcher.load_template(test_template)
    mask = matcher.get_template_mask(test_template)
    if mask is not None:
        mask_pixels = np.count_nonzero(mask)
        total_pixels = mask.shape[0] * mask.shape[1]
        print(f"✓ Templates have alpha channel (transparency detected)")
        print(f"  {test_template}: {mask_pixels}/{total_pixels} opaque pixels ({100*mask_pixels/total_pixels:.1f}%)")
    else:
        print("⚠ Templates have no alpha channel (no transparency)")
        print("  Templates will be matched without transparency masking")

    # Initialize BankDetector (uses the improved scale-aware detection)
    bank_detector = BankDetector(
        screen_capture=screen,
        template_matcher=matcher,
        bank_config=config['bank'],
        grimy_templates=config['herbs']['grimy']
    )
    print("✓ Bank detector initialized")
    print()

    print("Searching for RuneLite window...")
    if not screen.find_window():
        print("ERROR: Could not find RuneLite window!")
        print("Make sure RuneLite is running and visible.")
        return 1

    print(f"✓ Found window at {screen.window_bounds}")
    print()

    # Capture screen
    print("Capturing screenshot...")
    window_img = screen.capture_window()
    if window_img is None:
        print("ERROR: Could not capture screen!")
        return 1

    print(f"✓ Captured {window_img.shape[1]}x{window_img.shape[0]} image")
    print()

    # Use the improved BankDetector to get bank region (scale-aware!)
    print("Detecting bank interface region (scale-aware)...")

    # Get scale-aware bank region using the improved method
    bank_region = bank_detector._get_bank_item_region(window_img)

    # Also get button positions for visualization
    close_match = matcher.match(
        window_img,
        config['bank']['close_button_template']
    )
    deposit_match = matcher.match(
        window_img,
        config['bank']['deposit_all_template']
    )

    if bank_region:
        x, y, width, height = bank_region
        print(f"✓ Bank region detected: ({x}, {y}) {width}x{height}")

        if close_match.found:
            print(f"  Close button at: ({close_match.x}, {close_match.y})")
            print(f"  Detected scale: {close_match.scale:.2f}x")
            print(f"  Scaled offset: {int(900 * close_match.scale)}px (was 900px hardcoded)")
        elif deposit_match.found:
            print(f"  Deposit button at: ({deposit_match.x}, {deposit_match.y})")
            print(f"  Detected scale: {deposit_match.scale:.2f}x")

        # Crop to bank region
        search_image = window_img[y:y+height, x:x+width]
        offset_x = x
        offset_y = y
        print(f"✓ Search area restricted to bank items only")
    else:
        print("⚠ Could not detect bank region - searching full image")
        print("  Make sure bank is open with close/deposit button visible")
        search_image = window_img
        offset_x = 0
        offset_y = 0

    print()

    # First, show the HYBRID color+template approach (what the bot actually uses)
    print("=" * 70)
    print("HYBRID COLOR + TEMPLATE DETECTION (What the bot uses)")
    print("=" * 70)
    print()

    grimy_templates = config.get('herbs', {}).get('grimy', [])
    template_names = [h['template'] for h in grimy_templates]

    # Show color pre-filtering
    print("Step 1: Color Pre-Filtering")
    print("-" * 70)
    color_candidates = matcher.filter_templates_by_color(
        search_image,
        template_names,
        top_k=3
    )

    print(f"Color analysis of {len(template_names)} templates:")
    print(f"Top 3 matches by color similarity:")
    for i, (template_name, similarity) in enumerate(color_candidates):
        herb_name = template_name.replace('grimy_', '').replace('.png', '')
        print(f"  {i+1}. {herb_name:15} - Color similarity: {similarity:.3f}")

    print()
    print("Step 2: Template Matching on Filtered Candidates")
    print("-" * 70)
    print(f"Confidence threshold: {matcher.confidence_threshold}")
    print()

    # Now run template matching on the filtered candidates
    best_hybrid_match = None
    best_hybrid_conf = 0.0
    best_hybrid_name = None
    best_hybrid_template = None

    for template_name, color_sim in color_candidates:
        herb_name = template_name.replace('grimy_', '').replace('.png', '')
        # Using 50% region to avoid 4-digit stack numbers
        match = matcher.match_bottom_region(search_image, template_name, 0.50)

        passed = "✓ PASS" if match.found else f"✗ FAIL (threshold: {matcher.confidence_threshold})"
        print(f"  {herb_name:15} - Confidence: {match.confidence:.3f} {passed}")

        # Keep track of best match even if it didn't pass threshold
        if match.confidence > best_hybrid_conf:
            best_hybrid_conf = match.confidence
            best_hybrid_match = match
            best_hybrid_name = herb_name
            best_hybrid_template = template_name

    print()
    if best_hybrid_match and best_hybrid_match.found:
        print(f"✓ HYBRID RESULT (PASSED): {best_hybrid_name} (confidence: {best_hybrid_conf:.3f})")
        # Adjust coords for offset
        best_hybrid_match.x += offset_x
        best_hybrid_match.y += offset_y
        best_hybrid_match.center_x += offset_x
        best_hybrid_match.center_y += offset_y
    elif best_hybrid_match:
        print(f"⚠ BEST MATCH (FAILED THRESHOLD): {best_hybrid_name} (confidence: {best_hybrid_conf:.3f})")
        print(f"  Threshold: {matcher.confidence_threshold}, needed {matcher.confidence_threshold - best_hybrid_conf:.3f} more")
        # Still adjust coords for visualization
        best_hybrid_match.x += offset_x
        best_hybrid_match.y += offset_y
        best_hybrid_match.center_x += offset_x
        best_hybrid_match.center_y += offset_y
    else:
        print("✗ No match found with hybrid approach")

    print()
    print()
    print("=" * 70)
    print("INDIVIDUAL TEMPLATE ANALYSIS (For diagnostic purposes)")
    print("=" * 70)
    print()
    print(f"Testing all {len(grimy_templates)} herb templates...")
    print()
    results = []

    for i, herb_config in enumerate(grimy_templates):
        herb_name = herb_config['name']
        template_name = herb_config['template']

        print(f"  [{i+1}/{len(grimy_templates)}] Testing {herb_name}...", end=' ', flush=True)

        # Test both methods on bank region (or full image if no region)
        try:
            standard_match = matcher.match(search_image, template_name)
            region_match = matcher.match_bottom_region(search_image, template_name, 0.50)

            # Adjust coordinates for offset
            if standard_match.found:
                standard_match.x += offset_x
                standard_match.y += offset_y
                standard_match.center_x += offset_x
                standard_match.center_y += offset_y

            if region_match.found:
                region_match.x += offset_x
                region_match.y += offset_y
                region_match.center_x += offset_x
                region_match.center_y += offset_y

            results.append({
                'name': herb_name,
                'template': template_name,
                'standard_conf': standard_match.confidence,
                'standard_found': standard_match.found,
                'region_conf': region_match.confidence,
                'region_found': region_match.found,
                'standard_pos': (standard_match.center_x, standard_match.center_y) if standard_match.found else None,
                'region_pos': (region_match.center_x, region_match.center_y) if region_match.found else None,
            })
            print(f"Standard: {standard_match.confidence:.3f}, Region: {region_match.confidence:.3f}")
        except Exception as e:
            print(f"ERROR: {e}")
            results.append({
                'name': herb_name,
                'template': template_name,
                'standard_conf': 0.0,
                'standard_found': False,
                'region_conf': 0.0,
                'region_found': False,
                'standard_pos': None,
                'region_pos': None,
            })

    # Sort by region confidence (what we're using now)
    results.sort(key=lambda x: x['region_conf'], reverse=True)

    print("=" * 70)
    print(f"{'Herb Type':<20} {'Standard':<20} {'Region-Based':<20}")
    print("=" * 70)

    for r in results:
        std_str = f"{r['standard_conf']:.3f} {'✓' if r['standard_found'] else '✗'}"
        reg_str = f"{r['region_conf']:.3f} {'✓' if r['region_found'] else '✗'}"
        print(f"{r['name']:<20} {std_str:<20} {reg_str:<20}")

    print()
    print("=" * 70)
    print("BEST MATCHES:")
    print("=" * 70)

    best = results[0]
    print(f"Herb: {best['name']}")
    print(f"Template: {best['template']}")
    print(f"Standard confidence: {best['standard_conf']:.3f} ({'PASS' if best['standard_found'] else 'FAIL'})")
    print(f"Region-based confidence: {best['region_conf']:.3f} ({'PASS' if best['region_found'] else 'FAIL'})")

    if best['region_pos']:
        print(f"Position: {best['region_pos']}")

    print()

    # Visualize HYBRID detection result - ALWAYS show window
    print("=" * 70)
    print("VISUALIZATION")
    print("=" * 70)

    vis_img = window_img.copy()

    # ALWAYS draw bank region rectangle if detected (YELLOW)
    if bank_region:
        x, y, width, height = bank_region
        cv2.rectangle(vis_img, (x, y), (x + width, y + height), (0, 255, 255), 3)

        # Add label with scale info
        if close_match.found:
            label = f"Bank Search Area (scale: {close_match.scale:.2f}x, {width}x{height})"
        else:
            label = f"Bank Search Area ({width}x{height})"

        cv2.putText(
            vis_img,
            label,
            (x + 10, y + 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 255),
            2
        )
    else:
        # Draw warning if bank region not detected
        cv2.putText(
            vis_img,
            "WARNING: Bank region not detected!",
            (50, 50),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.0,
            (0, 0, 255),
            2
        )

    # Draw close button location for debugging (BLUE)
    if close_match.found:
        # Draw close button bounding box
        cv2.rectangle(
            vis_img,
            (close_match.x, close_match.y),
            (close_match.x + close_match.width, close_match.y + close_match.height),
            (255, 0, 0),  # Blue rectangle
            3
        )

        # Draw circle at center
        cv2.circle(
            vis_img,
            (close_match.center_x, close_match.center_y),
            8,
            (255, 0, 0),  # Blue circle
            -1
        )

        # Add label
        close_label = f"Close Button (scale: {close_match.scale:.2f}x)"
        cv2.putText(
            vis_img,
            close_label,
            (close_match.x - 150, close_match.y - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 0, 0),
            2
        )

        # Draw arrow from close button to bank region to show offset
        if bank_region:
            bank_x, bank_y, _, _ = bank_region
            cv2.arrowedLine(
                vis_img,
                (close_match.center_x, close_match.center_y),
                (bank_x + 20, bank_y + 20),
                (255, 128, 0),  # Orange arrow
                3,
                tipLength=0.3
            )

    # Draw HYBRID detection result if we have any match (even if failed threshold)
    if best_hybrid_match:
        match_x = best_hybrid_match.center_x
        match_y = best_hybrid_match.center_y
        w = best_hybrid_match.width
        h = best_hybrid_match.height

        # Color: GREEN if passed, RED if failed threshold
        color = (0, 255, 0) if best_hybrid_match.found else (0, 0, 255)
        status = "PASS" if best_hybrid_match.found else "FAIL"

        cv2.rectangle(
            vis_img,
            (match_x - w // 2, match_y - h // 2),
            (match_x + w // 2, match_y + h // 2),
            color,
            3
        )

        # Add label
        label = f"HYBRID {status}: {best_hybrid_name}: {best_hybrid_conf:.3f}"
        cv2.putText(
            vis_img,
            label,
            (match_x - w // 2, match_y - h // 2 - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            color,
            2
        )

    # Add coordinate debug info overlay
    if bank_region and close_match.found:
        x, y, width, height = bank_region
        offset_x_actual = close_match.x - x
        offset_y_actual = close_match.y - y

        debug_text = [
            f"Screen: {vis_img.shape[1]}x{vis_img.shape[0]}",
            f"Close: ({close_match.x}, {close_match.y})",
            f"Bank: ({x}, {y}) {width}x{height}",
            f"Offset: ({offset_x_actual}, {offset_y_actual})",
            f"Scale: {close_match.scale:.2f}x",
        ]

        # Draw semi-transparent background for text
        overlay = vis_img.copy()
        cv2.rectangle(overlay, (5, 70), (400, 220), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.6, vis_img, 0.4, 0, vis_img)

        # Draw text
        text_y = 95
        for line in debug_text:
            cv2.putText(
                vis_img,
                line,
                (15, text_y),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 255, 255),
                1
            )
            text_y += 25

    # Draw bottom-left info box with detection summary
    img_h, img_w = vis_img.shape[:2]

    # Build info lines
    info_lines = [
        f"Threshold: {matcher.confidence_threshold:.2f}",
        f"Best Conf: {best_hybrid_conf:.3f}",
        f"Gap: {matcher.confidence_threshold - best_hybrid_conf:.3f}",
        f"Result: {'PASS' if (best_hybrid_match and best_hybrid_match.found) else 'FAIL'}",
        f"Herb: {best_hybrid_name or 'None'}",
        f"Crop: 50% (bottom region)",
    ]

    # Add transparency info
    if mask is not None:
        info_lines.append(f"Alpha: YES ({100*mask_pixels/total_pixels:.0f}% opaque)")
    else:
        info_lines.append("Alpha: NO (no mask)")

    # Calculate box dimensions
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.6
    thickness = 2
    line_height = 28
    padding = 15

    # Get max text width
    max_width = 0
    for line in info_lines:
        (text_w, _), _ = cv2.getTextSize(line, font, font_scale, thickness)
        max_width = max(max_width, text_w)

    box_width = max_width + padding * 2
    box_height = len(info_lines) * line_height + padding * 2

    # Position at bottom-left
    box_x = 10
    box_y = img_h - box_height - 10

    # Draw semi-transparent background
    overlay = vis_img.copy()
    cv2.rectangle(
        overlay,
        (box_x, box_y),
        (box_x + box_width, box_y + box_height),
        (40, 40, 40),  # Dark gray
        -1
    )
    cv2.addWeighted(overlay, 0.85, vis_img, 0.15, 0, vis_img)

    # Draw border
    border_color = (0, 255, 0) if (best_hybrid_match and best_hybrid_match.found) else (0, 0, 255)
    cv2.rectangle(
        vis_img,
        (box_x, box_y),
        (box_x + box_width, box_y + box_height),
        border_color,
        2
    )

    # Draw text lines
    text_y = box_y + padding + 20
    for line in info_lines:
        # Highlight result line
        if line.startswith("Result:"):
            color = (0, 255, 0) if "PASS" in line else (0, 0, 255)
        elif line.startswith("Gap:"):
            gap_val = matcher.confidence_threshold - best_hybrid_conf
            color = (0, 255, 0) if gap_val <= 0 else (0, 165, 255)  # Green if passing, orange if gap
        else:
            color = (255, 255, 255)

        cv2.putText(
            vis_img,
            line,
            (box_x + padding, text_y),
            font,
            font_scale,
            color,
            thickness
        )
        text_y += line_height

    # ALWAYS show visualization window
    print()
    print("Opening visualization window...")
    print()
    print("LEGEND:")
    print("  - BLUE box/circle = Close button position")
    print("  - ORANGE arrow = Offset from close button to bank region")
    print("  - YELLOW box = Bank search area (scale-aware!)")
    if best_hybrid_match:
        if best_hybrid_match.found:
            print("  - GREEN box = Hybrid detection (PASSED threshold)")
        else:
            print("  - RED box = Best match (FAILED threshold)")
    print("  - Text overlay (top-left) = Debug coordinates")
    print("  - Text overlay (bottom-left) = Detection summary")
    print()

    window_name = "Bank Herb Detection - Press any key to close"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.imshow(window_name, vis_img)

    # Try to bring window to front
    try:
        cv2.setWindowProperty(window_name, cv2.WND_PROP_TOPMOST, 1)
    except:
        pass  # Not all platforms support this

    print("✓ Window opened! Look for the image window.")
    print("  (It may appear behind other windows)")
    print()
    print("Press any key in the IMAGE WINDOW to close...")
    cv2.waitKey(0)
    cv2.destroyAllWindows()

    # Print diagnostic info if detection failed
    if not best_hybrid_match or not best_hybrid_match.found:
        print()
        print("=" * 70)
        print("DIAGNOSTIC INFO")
        print("=" * 70)
        print()
        print("Possible issues:")
        print("  1. Confidence threshold too high")
        print(f"     Current: {matcher.confidence_threshold}")
        print(f"     Best score: {best_hybrid_conf:.3f}")
        print(f"     Gap: {matcher.confidence_threshold - best_hybrid_conf:.3f}")
        print()
        print("  2. Wrong herb type in bank")
        print("     Make sure the herb in your bank matches one of the templates")
        print()
        print("  3. Template quality issues")
        print("     Templates may be from different zoom level or quality")
        print()
        print("Solutions:")
        print("  - Lower confidence_threshold in config/default_config.yaml")
        print("  - Recapture templates at your current zoom level")
        print("  - Ensure correct herb type is in bank")
        print()

    print()
    print("=" * 70)
    print("DEBUG COMPLETE")
    print("=" * 70)

    return 0


if __name__ == "__main__":
    try:
        exit_code = main()
        print()
        print("Press ENTER to close this window...")
        input()
        sys.exit(exit_code)
    except Exception as e:
        print()
        print("=" * 70)
        print("FATAL ERROR")
        print("=" * 70)
        print(f"Error: {e}")
        print()
        print("Full traceback:")
        import traceback
        traceback.print_exc()
        print()
        print("Press ENTER to close this window...")
        input()
        sys.exit(1)
