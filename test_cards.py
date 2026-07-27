from database.service import DatabaseService

db = DatabaseService()

cards = db.get_cards("ME5")

print(f"Cards: {len(cards)}")

for card in cards[:5]:
    print(card["number"], "-", card["name"])

db.close()