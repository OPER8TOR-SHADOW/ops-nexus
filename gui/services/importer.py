from pokemon_api import get_set, get_cards
from database.service import DatabaseService


class Importer:

    def __init__(self):
        self.db = DatabaseService()

    def import_set(self, set_id):

        print(f"Importing {set_id}...")

        # Import set
        set_data = get_set(set_id)
        self.db.add_set(set_data)

        print("✓ Set imported")

        # Import cards
        cards = get_cards(set_id)

        for card in cards:
            self.db.add_card(card)

        print(f"✓ Imported {len(cards)} cards")

        self.db.close()

        print("Finished!")