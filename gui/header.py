import customtkinter as ctk

from gui.theme import *


class Header(ctk.CTkFrame):

    def __init__(self, master):

        super().__init__(
            master,
            fg_color="transparent",
            height=70
        )

        self.grid_columnconfigure(0, weight=1)

        # --------------------------
        # Page Title
        # --------------------------

        self.title = ctk.CTkLabel(

            self,

            text="Dashboard",

            font=(FONT, 30, "bold"),

            text_color=TEXT

        )

        self.title.grid(
            row=0,
            column=0,
            sticky="w"
        )

        # --------------------------
        # Version
        # --------------------------

        self.version = ctk.CTkLabel(

            self,

            text="OPS Nexus v1.0",

            font=(FONT, 13),

            text_color=SUBTEXT

        )

        self.version.grid(
            row=1,
            column=0,
            sticky="w",
            pady=(4,0)
        )