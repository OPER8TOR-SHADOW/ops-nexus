import time
import requests

BASE_URL = "https://api.pokemontcg.io/v2"

HEADERS = {
    "User-Agent": "OPS Nexus/1.0",
    "Accept": "application/json",
}

PAGE_SIZE = 250
MAX_RETRIES = 5


def request_json(url):
    """Perform a GET request with retries."""

    for attempt in range(1, MAX_RETRIES + 1):

        try:
            response = requests.get(
                url,
                headers=HEADERS,
                timeout=(10, 120),
            )

            print(f"Status Code: {response.status_code}")

            if response.status_code == 200:
                return response.json()

            if response.status_code >= 500:
                if attempt < MAX_RETRIES:
                    wait = attempt * 3
                    print(f"Server error. Retrying in {wait}s...")
                    time.sleep(wait)
                    continue

            response.raise_for_status()

        except (requests.ConnectionError, requests.Timeout):

            if attempt < MAX_RETRIES:
                wait = attempt * 3
                print(f"Connection failed. Retrying in {wait}s...")
                time.sleep(wait)
                continue

            raise

    raise RuntimeError("Maximum retries exceeded.")


def get_cards(set_id):
    """Download every card in a set."""

    page = 1
    cards = []

    while True:

        url = (
            f"{BASE_URL}/cards"
            f"?q=set.id:{set_id.lower()}"
            f"&page={page}"
            f"&pageSize={PAGE_SIZE}"
        )

        print(f"\nDownloading page {page}...")

        data = request_json(url)

        batch = data.get("data", [])

        if not batch:
            break

        cards.extend(batch)

        total = data.get("totalCount", len(cards))

        print(f"Downloaded {len(cards)} / {total}")

        if len(cards) >= total:
            break

        page += 1

    print(f"\nFinished. {len(cards)} cards loaded.")

    return cards


def get_set(set_id):
    """Return metadata for a set."""

    url = f"{BASE_URL}/sets/{set_id.lower()}"

    data = request_json(url)

    return data["data"]


def get_all_sets():
    """Return every Pokémon set."""

    url = f"{BASE_URL}/sets?pageSize=250"

    data = request_json(url)

    return data["data"]