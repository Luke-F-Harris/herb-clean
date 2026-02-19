#!/usr/bin/env python3
"""Download herb template images from OSRS Wiki API.

This script automatically fetches herb icons (both grimy and clean) from the
Old School RuneScape Wiki instead of requiring manual screenshots.

Source: https://oldschool.runescape.wiki
API: https://oldschool.runescape.wiki/api.php (MediaWiki API)
"""

import json
import urllib.request
import urllib.parse
from pathlib import Path


# Grimy herb names (as they appear on the OSRS Wiki)
GRIMY_HERBS = {
    "grimy_ranarr.png": "Grimy ranarr weed",
    "grimy_irit.png": "Grimy irit leaf",
    "grimy_avantoe.png": "Grimy avantoe",
    "grimy_kwuarm.png": "Grimy kwuarm",
    "grimy_dwarf_weed.png": "Grimy dwarf weed",
    "grimy_torstol.png": "Grimy torstol",
    "grimy_lantadyme.png": "Grimy lantadyme",
    "grimy_toadflax.png": "Grimy toadflax",
    "grimy_snapdragon.png": "Grimy snapdragon",
    "grimy_cadantine.png": "Grimy cadantine",
}

# Clean herb names (as they appear on the OSRS Wiki)
CLEAN_HERBS = {
    "clean_ranarr.png": "Ranarr weed",
    "clean_irit.png": "Irit leaf",
    "clean_avantoe.png": "Avantoe",
    "clean_kwuarm.png": "Kwuarm",
    "clean_dwarf_weed.png": "Dwarf weed",
    "clean_torstol.png": "Torstol",
    "clean_lantadyme.png": "Lantadyme",
    "clean_toadflax.png": "Toadflax",
    "clean_snapdragon.png": "Snapdragon",
    "clean_cadantine.png": "Cadantine",
}

# Bank interface elements (these vary by bank type - booth, chest, etc.)
# Note: Bank booth/chest appearance varies, user may need to capture manually
BANK_TEMPLATES = {
    # Deposit button is universal across all banks
    "deposit_all.png": "Bank deposit Inventory button",
}

# OSRS Wiki MediaWiki API
WIKI_API_URL = "https://oldschool.runescape.wiki/api.php"


def get_image_url(item_name: str) -> str:
    """Get image URL from OSRS Wiki API.

    Args:
        item_name: Name of the item (e.g., "Grimy ranarr weed")

    Returns:
        Direct URL to the image file

    Raises:
        Exception: If image cannot be found
    """
    # Construct filename with proper case and spaces
    filename = f"File:{item_name}.png"

    # Query the MediaWiki API
    params = {
        'action': 'query',
        'titles': filename,
        'prop': 'imageinfo',
        'iiprop': 'url',
        'format': 'json'
    }

    url = f"{WIKI_API_URL}?{urllib.parse.urlencode(params)}"

    req = urllib.request.Request(
        url,
        headers={'User-Agent': 'OSRS-Herb-Bot/1.0 (Educational Project)'}
    )

    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read().decode('utf-8'))

    # Extract image URL from response
    pages = data.get('query', {}).get('pages', {})
    for page_id, page_data in pages.items():
        if 'imageinfo' in page_data:
            image_url = page_data['imageinfo'][0]['url']
            return image_url

    raise Exception(f"Image not found on wiki: {filename}")


def download_templates(templates: dict, category: str, output_dir: Path) -> tuple[int, list]:
    """Download template images from OSRS Wiki.

    Args:
        templates: Dict mapping filename to wiki item name
        category: Category name for logging (e.g., "Grimy Herbs")
        output_dir: Directory to save template images

    Returns:
        Tuple of (success_count, failed_list)
    """
    print(f"\n--- {category} ---")
    print(f"Downloading {len(templates)} templates...\n")

    success_count = 0
    failed = []

    for filename, item_name in templates.items():
        output_path = output_dir / filename

        try:
            print(f"Downloading {filename}...", end=" ")

            # Get image URL from wiki API
            image_url = get_image_url(item_name)

            # Download the image
            req = urllib.request.Request(
                image_url,
                headers={'User-Agent': 'OSRS-Herb-Bot/1.0 (Educational Project)'}
            )

            with urllib.request.urlopen(req) as response:
                image_data = response.read()

            with open(output_path, 'wb') as f:
                f.write(image_data)

            print("✓")
            success_count += 1

        except Exception as e:
            print(f"✗ Failed: {e}")
            failed.append((filename, item_name, str(e)))

    return success_count, failed


def download_herb_templates(output_dir: Path):
    """Download all herb template images (grimy and clean).

    Args:
        output_dir: Directory to save template images
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    total_templates = len(GRIMY_HERBS) + len(CLEAN_HERBS)

    print("=" * 70)
    print("Downloading Herb Templates from OSRS Wiki")
    print("=" * 70)
    print(f"\nSource: https://oldschool.runescape.wiki")
    print(f"Output directory: {output_dir}")
    print(f"Total templates to download: {total_templates}")

    total_success = 0
    all_failed = []

    # Download grimy herbs
    success, failed = download_templates(GRIMY_HERBS, "Grimy Herbs", output_dir)
    total_success += success
    all_failed.extend(failed)

    # Download clean herbs
    success, failed = download_templates(CLEAN_HERBS, "Clean Herbs", output_dir)
    total_success += success
    all_failed.extend(failed)

    # Summary
    print("\n" + "=" * 70)
    print("Download Summary")
    print("=" * 70)
    print(f"✓ Successfully downloaded: {total_success}/{total_templates}")

    if all_failed:
        print(f"✗ Failed downloads: {len(all_failed)}")
        for filename, item_name, error in all_failed:
            print(f"  - {filename} ({item_name}): {error}")
    else:
        print("\n✓ All herb templates downloaded successfully!")
        print(f"\nTemplates saved to: {output_dir}")
        print("\nYou can now run test_bot_actions.py to verify detection works.")

    print("=" * 70)

    return total_success, all_failed


def main():
    """Main entry point."""
    # Determine templates directory
    script_dir = Path(__file__).parent
    templates_dir = script_dir / "config" / "templates"

    print("\nThis script will download herb icon images from the OSRS Wiki.")
    print("Source: https://oldschool.runescape.wiki")
    print()
    print("The following GRIMY herb templates will be downloaded:")
    for filename in GRIMY_HERBS.keys():
        print(f"  - {filename}")
    print()
    print("The following CLEAN herb templates will be downloaded:")
    for filename in CLEAN_HERBS.keys():
        print(f"  - {filename}")
    print()

    response = input("Continue with download? (y/n): ")
    if response.lower() != 'y':
        print("Download cancelled.")
        return 1

    print()
    success, failed = download_herb_templates(templates_dir)

    return 0 if not failed else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
