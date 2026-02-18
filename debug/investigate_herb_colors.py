#!/usr/bin/env python3
"""Analyze color profiles of all herb templates.

This script helps understand why herb detection might be failing by:
1. Computing color histograms for each herb template
2. Creating a similarity matrix showing which herbs look most similar
3. Visualizing color distributions
"""

import cv2
import numpy as np
from pathlib import Path
import yaml


def compute_color_histogram(image: np.ndarray) -> np.ndarray:
    """Compute color histogram for an image."""
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    hist = cv2.calcHist(
        [hsv],
        [0, 1],  # Hue and Saturation
        None,
        [32, 32],
        [0, 180, 0, 256]
    )
    cv2.normalize(hist, hist, 0, 1, cv2.NORM_MINMAX)
    return hist


def compare_histograms(hist1: np.ndarray, hist2: np.ndarray) -> float:
    """Compare two histograms using correlation."""
    return cv2.compareHist(hist1, hist2, cv2.HISTCMP_CORREL)


def main():
    """Analyze herb template colors."""
    # Load config
    config_path = Path(__file__).parent / "config" / "default_config.yaml"
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    # Get herb templates
    templates_dir = Path(__file__).parent / "config" / "templates"
    herb_configs = config['herbs']['grimy']

    # Load all herb templates and compute histograms
    herb_data = []
    for herb_config in herb_configs:
        template_path = templates_dir / herb_config['template']
        if not template_path.exists():
            print(f"⚠️  Template not found: {template_path}")
            continue

        template = cv2.imread(str(template_path))
        if template is None:
            print(f"⚠️  Failed to load: {template_path}")
            continue

        hist = compute_color_histogram(template)
        herb_data.append({
            'name': herb_config['name'],
            'template': herb_config['template'],
            'histogram': hist,
            'image': template
        })

    print(f"\n📊 Loaded {len(herb_data)} herb templates\n")

    # Create similarity matrix
    print("🎨 Color Similarity Matrix (higher = more similar)")
    print("=" * 80)

    # Print header
    print(f"{'':20}", end="")
    for herb in herb_data:
        print(f"{herb['name'][:12]:>12}", end="")
    print()

    # Print rows
    for i, herb1 in enumerate(herb_data):
        print(f"{herb1['name'][:20]:20}", end="")
        for j, herb2 in enumerate(herb_data):
            similarity = compare_histograms(herb1['histogram'], herb2['histogram'])
            if i == j:
                print(f"{'1.000':>12}", end="")
            else:
                color = ""
                if similarity > 0.9:
                    color = "\033[91m"  # Red - very similar (potential confusion)
                elif similarity > 0.8:
                    color = "\033[93m"  # Yellow - similar
                else:
                    color = "\033[92m"  # Green - distinct
                print(f"{color}{similarity:>12.3f}\033[0m", end="")
        print()

    print()

    # Find most confusable pairs
    print("\n⚠️  Most Confusable Herb Pairs (by color):")
    print("=" * 80)

    pairs = []
    for i, herb1 in enumerate(herb_data):
        for j, herb2 in enumerate(herb_data):
            if i < j:  # Only upper triangle
                similarity = compare_histograms(herb1['histogram'], herb2['histogram'])
                pairs.append((herb1['name'], herb2['name'], similarity))

    pairs.sort(key=lambda x: x[2], reverse=True)
    for i, (name1, name2, sim) in enumerate(pairs[:5]):
        print(f"{i+1}. {name1:20} ↔ {name2:20}  Similarity: {sim:.3f}")

    # Find most distinct herbs
    print("\n✅ Most Distinct Herbs (by color):")
    print("=" * 80)

    # Calculate average similarity to all other herbs
    avg_similarities = []
    for i, herb1 in enumerate(herb_data):
        similarities = []
        for j, herb2 in enumerate(herb_data):
            if i != j:
                sim = compare_histograms(herb1['histogram'], herb2['histogram'])
                similarities.append(sim)
        avg_sim = np.mean(similarities)
        avg_similarities.append((herb1['name'], avg_sim))

    avg_similarities.sort(key=lambda x: x[1])
    for i, (name, avg_sim) in enumerate(avg_similarities[:5]):
        print(f"{i+1}. {name:20}  Avg Similarity: {avg_sim:.3f}")

    # Analyze specific herb colors
    print("\n🎨 Color Profile Analysis:")
    print("=" * 80)

    for herb in herb_data:
        img = herb['image']
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

        # Calculate dominant color
        mean_hue = np.mean(hsv[:, :, 0])
        mean_sat = np.mean(hsv[:, :, 1])
        mean_val = np.mean(hsv[:, :, 2])

        # Classify color
        color_name = "Unknown"
        if mean_sat < 50:
            color_name = "Gray/Brown"
        elif mean_hue < 30:
            color_name = "Red/Orange"
        elif mean_hue < 60:
            color_name = "Yellow/Green-Yellow"
        elif mean_hue < 90:
            color_name = "Green"
        elif mean_hue < 120:
            color_name = "Blue-Green/Cyan"
        elif mean_hue < 150:
            color_name = "Blue"
        else:
            color_name = "Purple/Magenta"

        print(f"{herb['name']:20} - {color_name:20} (H:{mean_hue:5.1f} S:{mean_sat:5.1f} V:{mean_val:5.1f})")

    print("\n✅ Analysis complete!")
    print("\nRecommendations:")
    print("- Herbs with similarity > 0.90 will be hard to distinguish by color alone")
    print("- The hybrid approach (color + template) should help with most cases")
    print("- Consider using higher confidence thresholds for similar herbs")


if __name__ == "__main__":
    main()
