import requests

url = "https://api.pokemontcg.io/v2/cards?q=set.id:me5"

session = requests.Session()

session.headers.update({
    "User-Agent": "Mozilla/5.0"
})

try:
    print("Connecting...")

    response = session.get(url, timeout=(10, 120))

    print("Status:", response.status_code)
    print("Downloaded:", len(response.content), "bytes")

except Exception as e:
    print(type(e).__name__)
    print(e)