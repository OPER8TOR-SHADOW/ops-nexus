import customtkinter as ctk

from gui.theme import *


class StatCard(ctk.CTkFrame):

    def __init__(
        self,
        master,
        title,
        value="0",
        status=None
    ):

        super().__init__(
            master,
            fg_color=CARD,
            corner_radius=15,
            border_width=1,
            border_color=BORDER,
            height=130
        )

        self.grid_propagate(False)

        # -----------------------------------
        # Title
        # -----------------------------------

        self.title_label = ctk.CTkLabel(
            self,
            text=title,
            font=(FONT, 16, "bold"),
            text_color=MUTED
        )

        self.title_label.pack(
            anchor="w",
            padx=18,
            pady=(16, 8)
        )

        # -----------------------------------
        # Value
        # -----------------------------------

        self.value_label = ctk.CTkLabel(
            self,
            text=str(value),
            font=(FONT, 34, "bold"),
            text_color=TEXT
        )

        self.value_label.pack(
            anchor="w",
            padx=18
        )

        # -----------------------------------
        # Status
        # -----------------------------------

        self.status_label = ctk.CTkLabel(
            self,
            text="",
            font=(FONT, 13),
            text_color=SUCCESS
        )

        self.status_label.pack(
            anchor="w",
            padx=18,
            pady=(4, 16)
        )

        if status is not None:
            self.set_status(status)
        else:
            self.status_label.pack_forget()

    # =====================================================
    # Public Methods
    # =====================================================

    def set_value(self, value):
        """Update the card's main value."""
        self.value_label.configure(text=str(value))

    def set_title(self, title):
        """Update the card title."""
        self.title_label.configure(text=title)

    def set_status(self, status):

        if not self.status_label.winfo_ismapped():
            self.status_label.pack(
                anchor="w",
                padx=18,
                pady=(4, 16)
            )

        if isinstance(status, bool):

            if status:
                self.status_label.configure(
                    text="● Online",
                    text_color=SUCCESS
                )
            else:
                self.status_label.configure(
                    text="● Offline",
                    text_color=ERROR
                )

            return

        text = str(status)

        colour = SUCCESS

        lower = text.lower()

        if any(word in lower for word in ("error", "failed", "offline", "missing")):
            colour = ERROR

        elif any(word in lower for word in ("warning", "attention")):
            colour = WARNING

        self.status_label.configure(
            text=text,
            text_color=colour
        )

    def clear_status(self):
        """Hide the status label."""
        self.status_label.pack_forget()