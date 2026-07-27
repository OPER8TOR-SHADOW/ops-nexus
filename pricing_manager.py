import json
from pathlib import Path

PRICE_FILE = Path("pricing.json")

DEFAULT_PRICES = {
    "Normal": 1.00,
    "Reverse Holo": 1.50,
    "Common": 1.00,
    "Uncommon": 1.00,
    "Rare": 4.00,
    "Double Rare": 5.99,
    "Ultra Rare": 8.99,
    "Illustration Rare": 14.99,
    "Special Illustration Rare": 34.99,
    "Hyper Rare": 24.99,
    "ACE SPEC Rare": 7.99,
}


def load_prices():
    """Load pricing.json or create it with defaults."""

    if not PRICE_FILE.exists():
        save_prices(DEFAULT_PRICES)
        return DEFAULT_PRICES.copy()

    try:
        with open(PRICE_FILE, "r", encoding="utf-8") as f:
            prices = json.load(f)
    except (json.JSONDecodeError, OSError):
        prices = DEFAULT_PRICES.copy()
        save_prices(prices)

    # Ensure every default key exists
    for key, value in DEFAULT_PRICES.items():
        prices.setdefault(key, value)

    return prices


def save_prices(prices):
    """Save prices to pricing.json."""

    with open(PRICE_FILE, "w", encoding="utf-8") as f:
        json.dump(prices, f, indent=4)


def get_price(finish, rarity):
    """Return the correct price as a float."""

    prices = load_prices()

    if finish == "Normal":
        return float(prices["Normal"])

    if finish == "Reverse Holo":
        return float(prices["Reverse Holo"])

    return float(prices.get(rarity, 5.99))


def pricing_menu():

    while True:

        prices = load_prices()

        print("\n" + "=" * 45)
        print("           PRICING MANAGER")
        print("=" * 45)

        keys = list(prices.keys())

        for i, key in enumerate(keys, start=1):
            print(f"{i}. {key:<30} ${prices[key]:.2f}")

        print(f"{len(keys)+1}. Reset to Defaults")
        print(f"{len(keys)+2}. Back")

        choice = input("\nSelect option: ").strip()

        if not choice.isdigit():
            continue

        choice = int(choice)

        if choice == len(keys) + 2:
            return

        if choice == len(keys) + 1:
            save_prices(DEFAULT_PRICES.copy())
            print("\n✅ Prices reset to defaults.")
            continue

        if 1 <= choice <= len(keys):

            key = keys[choice - 1]

            try:
                new_price = float(input(f"Enter new price for {key}: $"))
            except ValueError:
                print("\n❌ Invalid price.")
                continue

            prices[key] = round(new_price, 2)
            save_prices(prices)

            print("\n✅ Price updated.")


if __name__ == "__main__":

    print("Testing Pricing Manager\n")

    print("Normal Common:", get_price("Normal", "Common"))
    print("Reverse Common:", get_price("Reverse Holo", "Common"))
    print("Double Rare:", get_price("Holo", "Double Rare"))