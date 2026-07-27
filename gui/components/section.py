import customtkinter as ctk

from gui.theme import *


class Section(ctk.CTkFrame):

    def __init__(
        self,
        master,
        title="",
        height=None
    ):

        super().__init__(
            master,
            fg_color=CARD,
            border_width=1,
            border_color=BORDER,
            corner_radius=15
        )

        if height:
            self.configure(height=height)
            self.grid_propagate(False)

        self.grid_columnconfigure(0, weight=1)

        # -----------------------
        # Title
        # -----------------------

        self.title = ctk.CTkLabel(
            self,
            text=title,
            font=(FONT, 18, "bold"),
            text_color=TEXT
        )

        self.title.pack(
            anchor="w",
            padx=20,
            pady=(18, 15)
        )

        # -----------------------
        # Content Frame
        # -----------------------

        self.content = ctk.CTkFrame(
            self,
            fg_color="transparent"
        )

        self.content.pack(
            fill="both",
            expand=True,
            padx=20,
            pady=(0, 20)
        )