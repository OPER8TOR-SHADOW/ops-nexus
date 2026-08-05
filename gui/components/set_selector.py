import customtkinter as ctk

from gui.theme import *
from database.service import DatabaseService


class SetSelector(ctk.CTkFrame):

    def __init__(self, master):

        super().__init__(
            master,
            fg_color=CARD,
            border_width=1,
            border_color=BORDER,
            corner_radius=15
        )

        title = ctk.CTkLabel(
            self,
            text="Pokémon Set",
            font=(FONT, 18, "bold"),
            text_color=TEXT
        )

        title.pack(
            anchor="w",
            padx=20,
            pady=(18, 12)
        )

        self._entries_by_label = {}
        self.names = []
        self.selected_name = ctk.StringVar(value="No imported sets available")

        self.combo = ctk.CTkOptionMenu(
            self,
            values=["No imported sets available"],
            variable=self.selected_name,
            height=40
        )

        self.combo.pack(
            fill="x",
            padx=20,
            pady=(0,20)
        )

        self.refresh()

    def refresh(self):

        selected_before = str(self.selected_name.get() or "").strip()

        self._entries_by_label = {}
        self.names = []

        db = DatabaseService()
        try:
            imported_sets = db.get_sets_with_counts()
        finally:
            db.close()

        for row in imported_sets:
            set_id = str(row["id"] or "").strip().lower()
            api_set = str(row["api_set"] or set_id).strip().lower()
            name = str(row["name"] or "").strip()
            series = str(row["series"] or "").strip() or "Unknown Series"
            release_date = str(row["release_date"] or "").strip() or "Unknown"
            card_count = int(row["card_count"] or 0)

            label = f"{set_id.upper()} - {name} | {series} | {release_date} | {card_count} cards"
            self.names.append(label)
            self._entries_by_label[label] = {
                "id": set_id,
                "api_set": api_set,
                "name": name,
                "series": series,
                "release_date": release_date,
                "card_count": card_count,
            }

        if not self.names:
            self.names = ["No imported sets available"]

        self.combo.configure(values=self.names)

        if selected_before in self._entries_by_label:
            self.selected_name.set(selected_before)
            return

        if self.names and self.names[0] != "No imported sets available":
            self.selected_name.set(self.names[0])
        else:
            self.selected_name.set("No imported sets available")

    def get_name(self):

        return str(self.selected_name.get() or "")

    def get_id(self):
        selected = str(self.selected_name.get() or "")
        if selected == "No imported sets available":
            raise KeyError("No imported sets available")

        return self._entries_by_label[selected]["id"]

    def get_api_set(self):
        selected = str(self.selected_name.get() or "")
        if selected == "No imported sets available":
            raise KeyError("No imported sets available")

        return self._entries_by_label[selected]["api_set"]