from pokemon_api import get_set, get_cards
from database.service import DatabaseService


class Importer:
    def __init__(self):
        self.db = DatabaseService()

    def import_set(self, set_id):
        try:
            print(f"\nImporting {set_id}...")

            # -------------------------
            # Import set information
            # -------------------------
            set_data = get_set(set_id)
            self.db.add_set(set_data)

            print("✓ Set imported")

            # -------------------------
            # Download all cards
            # -------------------------
            cards = get_cards(set_id)

            print(f"Found {len(cards)} cards")

            # -------------------------
            # Save cards
            # -------------------------
            for card in cards:
                self.db.add_card(card)
                self.db.create_finishes(card)

            print(f"✓ Imported {len(cards)} cards")

            print(
                f"Database now contains "
                f"{self.db.get_card_count(set_id.lower())} cards "
                f"for {set_id.upper()}."
            )

            print("\nFinished!")

        except Exception as e:
            print(f"\n❌ Import failed:\n{e}")

        finally:
            self.db.close()