import json
from pathlib import Path

import requests


# Paste an OAuth user access token here before running this script.
ACCESS_TOKEN = ""

# OPS Nexus stores tokens here, but that file is DPAPI-encrypted.
# With the import constraints for this standalone script, it cannot be decrypted.
TOKEN_STORE_PATH = Path(__file__).resolve().parent / ".secrets" / "ebay_oauth.bin"


REQUESTS_TO_TEST = [
    {
        "label": "Identity API getUser",
        "method": "GET",
        "url": "https://api.sandbox.ebay.com/commerce/identity/v1/user",
        "params": None,
    },
    {
        "label": "Inventory API getOffers",
        "method": "GET",
        "url": "https://api.sandbox.ebay.com/sell/inventory/v1/offer",
        "params": {"limit": 200, "offset": 0},
    },
]


def redact_headers(headers):
    safe = dict(headers)
    if "Authorization" in safe:
        safe["Authorization"] = "Bearer [redacted]"
    return safe


def build_headers(token):
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }


def print_separator():
    print("=" * 36)


def print_curl(method, url, headers):
    print("CURL EQUIVALENT:")
    print(
        "curl -i -X {method} \"{url}\" -H \"Authorization: Bearer <PASTE_TOKEN_HERE>\" -H \"Accept: application/json\"".format(
            method=method,
            url=url,
        )
    )


def run_request(session, request_spec, token):
    method = request_spec["method"]
    url = request_spec["url"]
    params = request_spec["params"]
    headers = build_headers(token)

    response = session.request(method=method, url=url, headers=headers, params=params, timeout=45)
    prepared = response.request

    print_separator()
    print(request_spec["label"])
    print("METHOD")
    print(prepared.method)
    print("FULL URL")
    print(prepared.url)
    print("REQUEST HEADERS")
    print(json.dumps(redact_headers(prepared.headers), indent=2, sort_keys=True))
    print("STATUS CODE")
    print(response.status_code)
    print("REASON")
    print(response.reason)
    print("RESPONSE HEADERS")
    print(json.dumps(dict(response.headers), indent=2, sort_keys=True))
    print("RAW RESPONSE BODY")
    print(response.text)
    if response.status_code >= 400:
        print_curl(prepared.method, prepared.url, prepared.headers)
    print_separator()


def main():
    print("Standalone eBay Sandbox API probe")
    print(f"Encrypted OPS Nexus token store: {TOKEN_STORE_PATH}")

    if not ACCESS_TOKEN.strip():
        print("Paste an OAuth access token into ACCESS_TOKEN at the top of this script before running it.")
        return

    with requests.Session() as session:
        for request_spec in REQUESTS_TO_TEST:
            run_request(session, request_spec, ACCESS_TOKEN.strip())


if __name__ == "__main__":
    main()