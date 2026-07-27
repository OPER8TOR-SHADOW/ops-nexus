from pathlib import Path
import sys

import requests

from pokemon_api import get_cards

HOLO_ONLY = {
    "Double Rare",
    "Ultra Rare",
    "Illustration Rare",
    "Special Illustration Rare",
    "Hyper Rare",
    "ACE SPEC Rare",
}


def download_images(cards, set_id):
    folder = Path("images") / set_id.upper()
    folder.mkdir(parents=True, exist_ok=True)

    downloaded = 0
    skipped = 0
    failed = 0

    headers = {
        "User-Agent": "OPS Collectables Image Downloader/1.0"
    }

    total = len(cards)

    print(f"\nDownloading {total} cards...\n")

    for index, card in enumerate(cards, start=1):

        number = str(card["number"]).zfill(3)
        rarity = card.get("rarity", "")
        image_url = card["images"]["large"]

        if rarity in HOLO_ONLY:
            filenames = [
                f"{set_id.upper()}-{number}-H.png"
            ]
        else:
            filenames = [
                f"{set_id.upper()}-{number}-N.png",
                f"{set_id.upper()}-{number}-RH.png",
            ]

        for filename in filenames:

            path = folder / filename

            if path.exists():
                skipped += 1
                continue

            try:
                response = requests.get(
                    image_url,
                    headers=headers,
                    timeout=(10, 60),
                )

                response.raise_for_status()

                path.write_bytes(response.content)

                downloaded += 1

                print(f"[{index}/{total}] ✓ {filename}")

            except Exception as e:
                failed += 1
                print(f"[{index}/{total}] ✗ {filename}")
                print(e)

    print("\n" + "=" * 50)
    print("Download Complete")
    print("=" * 50)
    print(f"Downloaded : {downloaded}")
    print(f"Skipped    : {skipped}")
    print(f"Failed     : {failed}")


def main():

    if len(sys.argv) < 2:
        print("Usage:")
        print("python image_downloader.py ME5")
        sys.exit(1)

    set_id = sys.argv[1].lower()

    print(f"Fetching cards for {set_id.upper()}...")

    cards = get_cards(set_id)

    print(f"Found {len(cards)} cards.")

    download_images(cards, set_id)


if __name__ == "__main__":
    main()