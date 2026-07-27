# ==========================================
# OPS COLLECTABLES - Configuration
# ==========================================

# Default quantity for every listing
DEFAULT_QUANTITY = 1

# Default fallback price
DEFAULT_PRICE = 1.99


# ==========================================
# eBay Title Format
# ==========================================

# Available placeholders:
# {name}
# {number}
# {set_size}
# {rarity}

TITLE_FORMAT = "{name} {number}/{rarity}"


# ==========================================
# Finish Prices
# ==========================================

# Common / Uncommon / Rare
NORMAL_PRICE = 1.00
REVERSE_HOLO_PRICE = 1.50

# Higher rarities
HOLO_PRICE = 1.5


# ==========================================
# Rarity Prices
# (Used for holo-only cards)
# ==========================================

RARITY_PRICES = {
    "Double Rare": 5.99,
    "Ultra Rare": 19.99,
    "Illustration Rare": 14.99,
    "Special Illustration Rare": 39.99,
    "Hyper Rare": 49.99,
    "ACE SPEC Rare": 6.99,
}

# ==========================================
# GitHub
# ==========================================

GITHUB_OWNER = "OPER8TOR-SHADOW"
GITHUB_REPO = "ops-ebay-images"
GITHUB_BRANCH = "main"

# ==========================================
# Current Set
# ==========================================

SET_ID = "ME5"
SET_NAME = "Pitch Black"

# ==========================================
# Images
# ==========================================

LOCAL_IMAGE_FOLDER = f"images/{SET_ID}"
REMOTE_IMAGE_FOLDER = f"cards/{SET_ID}"

IMAGE_BASE_URL = (
    f"https://raw.githubusercontent.com/"
    f"{GITHUB_OWNER}/{GITHUB_REPO}/{GITHUB_BRANCH}/"
    f"{REMOTE_IMAGE_FOLDER}"
)
