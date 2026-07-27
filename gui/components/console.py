import customtkinter as ctk

from gui.theme import *


class Console(ctk.CTkFrame):

    def __init__(self, master):

        super().__init__(
            master,
            fg_color=CARD,
            border_width=1,
            border_color=BORDER,
            corner_radius=15
        )

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # -------------------------
        # Header
        # -------------------------

        self.title = ctk.CTkLabel(
            self,
            text="Live Console",
            font=(FONT, 18, "bold"),
            text_color=TEXT
        )

        self.title.grid(
            row=0,
            column=0,
            sticky="w",
            padx=20,
            pady=(18, 10)
        )

        # -------------------------
        # Console
        # -------------------------

        self.console = ctk.CTkTextbox(
            self,
            fg_color="#111111",
            border_width=0,
            corner_radius=8,
            font=("Consolas", 11),
            wrap="none"
        )

        self.console.grid(
            row=1,
            column=0,
            sticky="nsew",
            padx=20,
            pady=(0, 20)
        )

        self.console.configure(state="disabled")

    # -----------------------------------

    def clear(self):

        self.console.configure(state="normal")

        self.console.delete("1.0", "end")

        self.console.configure(state="disabled")

    # -----------------------------------

    def write(self, text):

        self.console.configure(state="normal")

        self.console.insert("end", text + "\n")

        self.console.see("end")

        self.console.configure(state="disabled")