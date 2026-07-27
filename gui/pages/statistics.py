import customtkinter as ctk

from gui.theme import *


class StatisticsPage(ctk.CTkFrame):

    def __init__(self, master):

        super().__init__(master, fg_color="transparent")

        title = ctk.CTkLabel(
            self,
            text="Statistics",
            font=(FONT, 30, "bold"),
            text_color=TEXT
        )

        title.pack(anchor="w", padx=20, pady=(20, 10))

        description = ctk.CTkLabel(
            self,
            text="View inventory statistics.",
            font=(FONT, 16),
            text_color=MUTED
        )

        description.pack(anchor="w", padx=20)