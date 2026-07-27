from pricing_manager import get_price

# Cards that only exist as holo
HOLO_ONLY = {
    "Double Rare",
    "Ultra Rare",
    "Illustration Rare",
    "Special Illustration Rare",
    "Hyper Rare",
    "ACE SPEC Rare",
}


def create_variant(set_id, number, finish, rarity):
    """Create a single listing variant."""

    suffix = {
        "Normal": "N",
        "Reverse Holo": "RH",
        "Holo": "H",
    }[finish]

    price = float(get_price(finish, rarity))

    return {
        "sku": f"{set_id.upper()}-{number}-{suffix}",
        "finish": finish,
        "price": price,
        "image": f"{set_id.upper()}-{number}-{suffix}.png",
    }


def get_listing_variants(card, set_id):
    """
    Build all listing variants for a Pokémon card.
    """

    number = str(card["number"]).zfill(3)
    name = card["name"]
    rarity = card.get("rarity", "Common")
    set_name = card["set"]["name"]

    variants = []

    if rarity in HOLO_ONLY:
        variants.append(
            create_variant(set_id, number, "Holo", rarity)
        )
    else:
        variants.append(
            create_variant(set_id, number, "Normal", rarity)
        )

        variants.append(
            create_variant(set_id, number, "Reverse Holo", rarity)
        )

    return {
        "name": name,
        "number": number,
        "rarity": rarity,
        "set_name": set_name,
        "variants": variants,
    }


if __name__ == "__main__":

    test_card = {
        "number": "1",
        "name": "Bulbasaur",
        "rarity": "Common",
        "set": {
            "name": "Test Set"
        }
    }

    print(get_listing_variants(test_card, "me5"))