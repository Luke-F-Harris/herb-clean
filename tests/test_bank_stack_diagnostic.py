"""Diagnostic test for bank item detection with stack numbers.

This test helps visualize and debug the stack number interference problem
when detecting grimy herbs in the bank interface.

Run this test with the bank open and grimy herbs visible with stack numbers.
"""

import sys
from pathlib import Path
import cv2
import numpy as np

# Add src to path (go up to project root, then into src)
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from vision.screen_capture import ScreenCapture
from vision.template_matcher import TemplateMatcher
from core.config_manager import ConfigManager


def draw_match_box(image, match, label, color, confidence):
    """Draw match result with confidence score."""
    if not match.found:
        return

    x, y = match.x, match.y
    w, h = match.width, match.height

    # Draw rectangle
    cv2.rectangle(image, (x, y), (x + w, y + h), color, 3)

    # Create label with confidence
    label_text = f"{label}: {confidence:.2f}"
    text_size = cv2.getTextSize(label_text, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)[0]

    # Draw label background
    cv2.rectangle(
        image,
        (x, y - text_size[1] - 10),
        (x + text_size[0] + 10, y),
        (0, 0, 0),
        -1,
    )

    # Draw label text
    cv2.putText(
        image,
        label_text,
        (x + 5, y - 5),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        color,
        2,
    )


def draw_crop_indicator(image, match, crop_percentage, color):
    """Draw line showing where the crop occurs."""
    if not match.found:
        return

    x, y = match.x, match.y
    w, h = match.width, match.height

    # Calculate crop line position
    crop_y = y + int(h * (1.0 - crop_percentage))

    # Draw dashed line
    dash_length = 10
    for i in range(x, x + w, dash_length * 2):
        cv2.line(
            image,
            (i, crop_y),
            (min(i + dash_length, x + w), crop_y),
            color,
            2,
        )

    # Add label
    cv2.putText(
        image,
        f"Crop line (bottom {int(crop_percentage*100)}%)",
        (x + w + 10, crop_y),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        color,
        1,
    )


def show_template_comparison(template_path, crop_percentage=0.65):
    """Show original vs cropped template side-by-side."""
    template = cv2.imread(str(template_path))
    if template is None:
        return None

    h, w = template.shape[:2]
    crop_y = int(h * (1.0 - crop_percentage))
    cropped = template[crop_y:, :]

    # Create comparison image
    # Scale up for visibility (4x)
    scale = 4
    template_large = cv2.resize(template, (w * scale, h * scale),
                                interpolation=cv2.INTER_NEAREST)
    cropped_large = cv2.resize(cropped, (w * scale, cropped.shape[0] * scale),
                               interpolation=cv2.INTER_NEAREST)

    # Create canvas
    canvas_h = max(template_large.shape[0], cropped_large.shape[0]) + 60
    canvas_w = template_large.shape[1] + cropped_large.shape[1] + 30
    canvas = np.zeros((canvas_h, canvas_w, 3), dtype=np.uint8)

    # Place templates
    canvas[30:30+template_large.shape[0], 10:10+template_large.shape[1]] = template_large
    x_offset = template_large.shape[1] + 20
    canvas[30:30+cropped_large.shape[0], x_offset:x_offset+cropped_large.shape[1]] = cropped_large

    # Add labels
    cv2.putText(canvas, "Original Template", (10, 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    cv2.putText(canvas, f"Bottom {int(crop_percentage*100)}%", (x_offset, 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

    # Draw crop line on original
    crop_line_y = 30 + int((h * scale) * (1.0 - crop_percentage))
    cv2.line(canvas, (10, crop_line_y),
             (10 + template_large.shape[1], crop_line_y),
             (0, 255, 255), 2)

    return canvas


def main():
    """Run bank stack number diagnostic test."""
    print("=" * 70)
    print("BANK ITEM STACK NUMBER DIAGNOSTIC TEST")
    print("=" * 70)
    print()
    print("This test diagnoses template matching issues with stack numbers.")
    print()
    print("SETUP INSTRUCTIONS:")
    print("1. Open RuneLite OSRS")
    print("2. Open your bank")
    print("3. Ensure grimy herbs are visible WITH stack numbers")
    print("4. Leave bank open and return to this terminal")
    print()
    print("Press ENTER when ready...")
    input()

    # Initialize components
    config = ConfigManager()
    screen = ScreenCapture(config.window.get("title", "RuneLite"))

    if not screen.find_window():
        print("ERROR: Could not find RuneLite window!")
        return

    print(f"✓ Found window at {screen.window_bounds}")

    matcher = TemplateMatcher(
        templates_dir=config.templates_dir,
        confidence_threshold=config.vision.get("confidence_threshold", 0.75),
        multi_scale=config.vision.get("multi_scale", True),
        scale_range=tuple(config.vision.get("scale_range", [0.7, 1.3])),
        scale_steps=config.vision.get("scale_steps", 7),
    )

    # Get grimy herb templates
    grimy_templates = config.get("herbs.grimy", [])
    if not grimy_templates:
        print("ERROR: No grimy herb templates configured!")
        return

    print(f"✓ Loaded {len(grimy_templates)} herb templates")
    print()

    # Capture bank interface
    bank_image = screen.capture_window()
    if bank_image is None:
        print("ERROR: Could not capture screen!")
        return

    print("=" * 70)
    print("RUNNING DETECTION COMPARISON")
    print("=" * 70)
    print()

    # Test each herb template
    results = []

    for i, herb_config in enumerate(grimy_templates):
        herb_name = herb_config["name"]
        template_name = herb_config["template"]

        print(f"Testing: {herb_name}")
        print(f"  Template: {template_name}")

        # Standard matching
        standard_match = matcher.match(bank_image, template_name)
        print(f"  Standard match: confidence={standard_match.confidence:.3f}, found={standard_match.found}")

        # Region-based matching
        region_match = matcher.match_bottom_region(
            bank_image, template_name, region_percentage=0.65
        )
        print(f"  Region match:   confidence={region_match.confidence:.3f}, found={region_match.found}")

        # Store results
        results.append({
            "name": herb_name,
            "template": template_name,
            "standard": standard_match,
            "region": region_match,
        })

        print()

    # Find best match
    best_standard = max(results, key=lambda r: r["standard"].confidence)
    best_region = max(results, key=lambda r: r["region"].confidence)

    print("=" * 70)
    print("BEST MATCHES")
    print("=" * 70)
    print(f"Standard: {best_standard['name']} ({best_standard['standard'].confidence:.3f})")
    print(f"Region:   {best_region['name']} ({best_region['region'].confidence:.3f})")
    print()

    # Create visualization
    print("Creating diagnostic visualization...")
    vis_image = bank_image.copy()

    # Draw both matches if found
    if best_standard["standard"].found:
        draw_match_box(
            vis_image,
            best_standard["standard"],
            "Standard",
            (0, 0, 255),  # Red
            best_standard["standard"].confidence,
        )
        draw_crop_indicator(vis_image, best_standard["standard"], 0.65, (0, 165, 255))

    if best_region["region"].found:
        draw_match_box(
            vis_image,
            best_region["region"],
            "Region-Based",
            (0, 255, 0),  # Green
            best_region["region"].confidence,
        )

    # Show results
    cv2.imshow("Bank Detection Comparison", vis_image)

    # Show template comparison if best herb found
    if best_region["region"].found:
        template_path = config.templates_dir / best_region["template"]
        template_comp = show_template_comparison(template_path, 0.65)
        if template_comp is not None:
            cv2.imshow("Template Comparison", template_comp)

    # Wait for rendering
    for _ in range(5):
        cv2.waitKey(100)

    print()
    print("=" * 70)
    print("VISUALIZATION DISPLAYED")
    print("=" * 70)
    print()
    print("Red box = Standard matching")
    print("Green box = Region-based matching (bottom 65%)")
    print("Cyan dashed line = Crop boundary")
    print()
    print("Press ENTER in this terminal to save and exit...")
    input()

    # Save results
    output_path = Path("diagnostic_bank_stack.png")
    cv2.imwrite(str(output_path), vis_image)
    print(f"✓ Saved diagnostic image to: {output_path}")

    cv2.destroyAllWindows()

    print()
    print("=" * 70)
    print("DIAGNOSTIC COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
