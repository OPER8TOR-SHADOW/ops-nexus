from pathlib import Path
import sys

import requests

from pokemon_api import get_cards
from sets import get_set_config_by_id

HOLO_ONLY = {
    "Double Rare",
    "Ultra Rare",
    "Illustration Rare",
    "Special Illustration Rare",
    "Hyper Rare",
    "ACE SPEC Rare",
}

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def download_images(cards, set_id, progress_callback=None):
    folder = PROJECT_ROOT / "images" / set_id.upper()
    folder.mkdir(parents=True, exist_ok=True)

    downloaded = 0
    skipped = 0
    failed = 0

    headers = {
        "User-Agent": "OPS Collectables Image Downloader/1.0"
    }

    total = len(cards)

    print(f"\nDownloading {total} cards...\n", flush=True)

    for index, card in enumerate(cards, start=1):
        card_failed = False

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

                print(f"[{index}/{total}] ✓ {filename}", flush=True)

            except Exception as e:
                failed += 1
                card_failed = True
                print(f"[{index}/{total}] ✗ {filename}", flush=True)
                print(e, flush=True)

        if progress_callback is not None:
            progress_callback(index, total, card, "failed" if card_failed else "processed")

    print("\n" + "=" * 50)
    print("Download Complete")
    print("=" * 50)
    print(f"Downloaded : {downloaded}")
    print(f"Skipped    : {skipped}")
    print(f"Failed     : {failed}")

    return {
        "downloaded": downloaded,
        "skipped": skipped,
        "failed": failed,
        "total_cards": total,
    }


def download_set_images(set_id, progress_callback=None):
    normalized_set_id = str(set_id or "").strip().lower()
    set_config = get_set_config_by_id(normalized_set_id)
    api_set_id = set_config["api_set"]

    print(f"Fetching cards for {normalized_set_id.upper()}...", flush=True)

    cards = get_cards(api_set_id)

    print(f"Found {len(cards)} cards.", flush=True)

    return download_images(cards, normalized_set_id, progress_callback=progress_callback)


def main():

    if len(sys.argv) < 2:
        print("Usage:")
        print("python image_downloader.py <SET_ID>")
        sys.exit(1)

    set_id = sys.argv[1].lower()
    download_set_images(set_id)


if __name__ == "__main__":
    main()