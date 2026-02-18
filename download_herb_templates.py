#!/usr/bin/env python3
"""Download grimy herb template images from OSRS Wiki API.

This script automatically fetches herb icons from the Old School RuneScape Wiki
instead of requiring manual screenshots.

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


def download_herb_templates(output_dir: Path):
    """Download all grimy herb template images.

    Args:
        output_dir: Directory to save template images
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("Downloading Grimy Herb Templates from OSRS Wiki")
    print("=" * 70)
    print(f"\nSource: https://oldschool.runescape.wiki")
    print(f"Output directory: {output_dir}")
    print(f"Downloading {len(GRIMY_HERBS)} herb templates...\n")

    success_count = 0
    failed = []

    for filename, item_name in GRIMY_HERBS.items():
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

    # Summary
    print("\n" + "=" * 70)
    print("Download Summary")
    print("=" * 70)
    print(f"✓ Successfully downloaded: {success_count}/{len(GRIMY_HERBS)}")

    if failed:
        print(f"✗ Failed downloads: {len(failed)}")
        for filename, item_name, error in failed:
            print(f"  - {filename} ({item_name}): {error}")
    else:
        print("\n✓ All herb templates downloaded successfully!")
        print(f"\nTemplates saved to: {output_dir}")
        print("\nYou can now run test_bot_actions.py to verify detection works.")

    print("=" * 70)

    return success_count, failed


def main():
    """Main entry point."""
    # Determine templates directory
    script_dir = Path(__file__).parent
    templates_dir = script_dir / "config" / "templates"

    print("\nThis script will download grimy herb icon images from the OSRS Wiki.")
    print("Source: https://oldschool.runescape.wiki")
    print()
    print("The following herb templates will be downloaded:")
    for filename in GRIMY_HERBS.keys():
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
