import customtkinter as ctk

from gui.theme import *
from sets import SETS


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

        self.names = list(SETS.keys())

        if not self.names:
            self.names = ["No sets available"]

        self.combo = ctk.CTkComboBox(
            self,
            values=self.names,
            height=40
        )

        self.combo.pack(
            fill="x",
            padx=20,
            pady=(0,20)
        )

        if self.names and self.names[0] != "No sets available":
            self.combo.set(self.names[0])

    def get_name(self):

        return self.combo.get()

    def get_id(self):

        return SETS[self.combo.get()]["id"]

    def get_api_set(self):

        return SETS[self.combo.get()]["api_set"]