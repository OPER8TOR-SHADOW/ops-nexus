import customtkinter as ctk

from gui.theme import *


class StatusBadge(ctk.CTkFrame):

    def __init__(self, master, title):

        super().__init__(
            master,
            fg_color="transparent"
        )

        self.grid_columnconfigure(0, weight=1)

        self.title = ctk.CTkLabel(
            self,
            text=title,
            font=(FONT, 14),
            text_color=TEXT
        )

        self.title.grid(
            row=0,
            column=0,
            sticky="w"
        )

        self.status = ctk.CTkLabel(
            self,
            text="● Unknown",
            font=(FONT, 13, "bold"),
            text_color=WARNING
        )

        self.status.grid(
            row=0,
            column=1,
            sticky="e",
            padx=(20, 0)
        )

    def set_status(self, status, colour_override=None):

        if isinstance(status, bool):

            if status:
                text = "● OK"
                colour = SUCCESS
            else:
                text = "● Missing"
                colour = ERROR

        else:

            text = f"● {status}"

            lower = str(status).lower()

            if any(word in lower for word in ("error", "failed", "missing", "offline")):
                colour = ERROR

            elif any(word in lower for word in ("warning", "attention")):
                colour = WARNING

            else:
                colour = SUCCESS

        if colour_override is not None:
            colour = colour_override

        self.status.configure(
            text=text,
            text_color=colour
        )