from pokemon_api import get_set, get_cards, get_all_sets
from database.service import DatabaseService


class Importer:
    def __init__(self):
        self.db = DatabaseService()

    def import_set(self, set_id):
        try:
            local_set_id = str(set_id or "").strip().lower()
            if not local_set_id:
                raise ValueError("Set ID is required")

            print(f"\nImporting {local_set_id}...")

            set_data = self._resolve_set_data(local_set_id)
            api_set_id = str(set_data["id"] or "").strip().lower()
            if not api_set_id:
                raise ValueError("Resolved set is missing API id")

            # -------------------------
            # Import set information
            # -------------------------
            set_record = dict(set_data)
            set_record["id"] = local_set_id
            set_record["api_set"] = api_set_id
            self.db.add_set(set_record)

            print("✓ Set imported")

            # -------------------------
            # Download all cards
            # -------------------------
            cards = get_cards(api_set_id)

            print(f"Found {len(cards)} cards")

            # -------------------------
            # Save cards
            # -------------------------
            for card in cards:
                self.db.add_card(card, set_id_override=local_set_id)
                self.db.create_finishes(card)

            print(f"✓ Imported {len(cards)} cards")

            print(
                f"Database now contains "
                f"{self.db.get_card_count(local_set_id)} cards "
                f"for {local_set_id.upper()} (api: {api_set_id.upper()})."
            )

            print("\nFinished!")

        except Exception as e:
            print(f"\n❌ Import failed:\n{e}")

        finally:
            self.db.close()

    def _resolve_set_data(self, set_query):
        normalized = str(set_query or "").strip().lower()

        try:
            return get_set(normalized)
        except Exception:
            pass

        all_sets = list(get_all_sets() or [])

        candidates = []
        normalized_compact = "".join(ch for ch in normalized if ch.isalnum())

        for set_data in all_sets:
            api_id = str(set_data.get("id") or "").strip().lower()
            ptcgo_code = str(set_data.get("ptcgoCode") or "").strip().lower()
            name = str(set_data.get("name") or "").strip().lower()
            series = str(set_data.get("series") or "").strip().lower()
            haystack = " ".join([api_id, ptcgo_code, name, series])
            api_compact = "".join(ch for ch in api_id if ch.isalnum())
            ptcgo_compact = "".join(ch for ch in ptcgo_code if ch.isalnum())

            if normalized in {api_id, ptcgo_code, name}:
                candidates.append(set_data)
                continue

            if normalized_compact and normalized_compact in {api_compact, ptcgo_compact}:
                candidates.append(set_data)
                continue

            if normalized and normalized in haystack:
                candidates.append(set_data)

        shorthand = self._resolve_scarlet_violet_shorthand(normalized, all_sets)
        if shorthand is not None:
            candidates.append(shorthand)

        if not candidates:
            raise ValueError(f"Set not found in API: {set_query}")

        candidates.sort(key=lambda row: str(row.get("releaseDate") or ""), reverse=True)
        return candidates[0]

    def _resolve_scarlet_violet_shorthand(self, normalized_query, all_sets):
        query = str(normalized_query or "")
        if not query.startswith("sv") or len(query) < 4:
            return None

        suffix = query[-1]
        if suffix not in {"b", "w"}:
            return None

        colour_word = "black" if suffix == "b" else "white"
        series_key = "scarlet"

        matched = []
        for set_data in all_sets:
            name = str(set_data.get("name") or "").strip().lower()
            series = str(set_data.get("series") or "").strip().lower()
            if colour_word in name and series_key in series:
                matched.append(set_data)

        if not matched:
            return None

        matched.sort(key=lambda row: str(row.get("releaseDate") or ""), reverse=True)
        return matched[0]