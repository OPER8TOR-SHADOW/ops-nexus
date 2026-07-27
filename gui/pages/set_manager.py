import customtkinter as ctk

from database.service import DatabaseService
from gui.theme import *


class SetManagerPage(ctk.CTkFrame):

    def __init__(self, master, page_manager=None):

        super().__init__(
            master,
            fg_color=BACKGROUND
        )

        self.page_manager = page_manager
        self.db = DatabaseService()

        sets = self.db.get_sets_with_counts()

        title = ctk.CTkLabel(
            self,
            text="Imported Sets",
            font=(FONT, 30, "bold"),
            text_color=TEXT
        )

        title.pack(
            anchor="w",
            padx=30,
            pady=(25, 15)
        )

        for s in sets:

            card = ctk.CTkFrame(
               self,
               fg_color=CARD,
               corner_radius=12
            )

            card.pack(
                fill="x",
                padx=30,
                pady=8
            )

            header = ctk.CTkFrame(card, fg_color="transparent")
            header.pack(fill="x", padx=20, pady=(15, 10))

            ctk.CTkLabel(
                header,
                text=f"{s['name']} ({s['id'].upper()})",
                font=(FONT, 20, "bold"),
                text_color=TEXT
            ).pack(anchor="w")

            ctk.CTkLabel(
                header,
                text=f"{s['series'] or 'Unknown Series'} • {s['release_date'] or 'Unknown'}",
                font=(FONT, 13),
                text_color=SUBTEXT
            ).pack(anchor="w", pady=(2, 0))

            footer = ctk.CTkFrame(card, fg_color="transparent")
            footer.pack(fill="x", padx=20, pady=(0, 15))

            ctk.CTkLabel(
                footer,
                text=f"{s['card_count']} cards • Imported",
                font=(FONT, 14),
                text_color=SUBTEXT
            ).pack(anchor="w")

            open_button = ctk.CTkButton(
                footer,
                text="Open",
                width=80,
                command=lambda selected_id=s['id']: self.open_set(selected_id),
            )
            open_button.pack(anchor="e")

        self.db.close()

    def open_set(self, set_id):
        if self.page_manager is not None:
            self.page_manager.show_card_manager(selected_set=set_id)
