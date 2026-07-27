import json
from pathlib import Path

SETTINGS_FILE = Path("settings.json")


def load_settings():

    if not SETTINGS_FILE.exists():

        defaults = {
            "store_name": "OPS COLLECTABLES",
            "default_quantity": 5,
            "default_condition": "Near Mint",
            "currency": "AUD",
            "title_format": "{name} {number}/{set_size} {rarity}",
        }

        save_settings(defaults)
        return defaults

    with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_settings(settings):

    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=4)


def settings_menu():

    while True:

        settings = load_settings()

        keys = list(settings.keys())

        print("\n" + "=" * 50)
        print("             SETTINGS")
        print("=" * 50)

        for i, key in enumerate(keys, start=1):
            print(f"{i}. {key:<20} {settings[key]}")

        print(f"{len(keys)+1}. Back")

        choice = input("\nSelect option: ")

        if not choice.isdigit():
            continue

        choice = int(choice)

        if choice == len(keys) + 1:
            break

        if 1 <= choice <= len(keys):

            key = keys[choice - 1]

            value = input(f"New value for {key}: ")

            if key == "default_quantity":

                try:
                    value = int(value)
                except ValueError:
                    print("Quantity must be a number.")
                    continue

            settings[key] = value

            save_settings(settings)

            print("✅ Saved!")