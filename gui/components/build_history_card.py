from datetime import datetime

import customtkinter as ctk

from gui.theme import *


class BuildHistoryCard(ctk.CTkFrame):

    def __init__(self, master):

        super().__init__(
            master,
            fg_color=CARD,
            border_width=1,
            border_color=BORDER,
            corner_radius=15,
        )

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.title = ctk.CTkLabel(
            self,
            text="Build History",
            font=(FONT, 18, "bold"),
            text_color=TEXT,
        )

        self.title.grid(row=0, column=0, sticky="w", padx=18, pady=(14, 10))

        self.history_list = ctk.CTkScrollableFrame(
            self,
            fg_color="#111111",
            corner_radius=10,
            border_width=1,
            border_color=BORDER,
        )

        self.history_list.grid(row=1, column=0, sticky="nsew", padx=18, pady=(0, 18))

        self.empty_label = ctk.CTkLabel(
            self.history_list,
            text="No builds yet.",
            text_color=SUBTEXT,
            font=(FONT, 12),
        )
        self.empty_label.pack(anchor="w", padx=8, pady=8)

    # --------------------------------

    def set_history(self, entries):

        for child in self.history_list.winfo_children():
            child.destroy()

        if not entries:
            self.empty_label = ctk.CTkLabel(
                self.history_list,
                text="No builds yet.",
                text_color=SUBTEXT,
                font=(FONT, 12),
            )
            self.empty_label.pack(anchor="w", padx=8, pady=8)
            return

        for entry in entries:
            self._render_entry(entry)

    # --------------------------------

    def _render_entry(self, entry):

        row = ctk.CTkFrame(
            self.history_list,
            fg_color="#1A1A1A",
            border_width=1,
            border_color=BORDER,
            corner_radius=8,
        )
        row.pack(fill="x", padx=4, pady=(0, 8))

        result = str(entry.get("result", "Failed")).lower()
        icon = "✔" if result == "success" else "✖"
        colour = SUCCESS if result == "success" else ERROR

        set_id = str(entry.get("set", "--"))
        cards = int(entry.get("cards", 0) or 0)
        duration = str(entry.get("duration_text", "--"))
        date_label = self._format_datetime(entry.get("timestamp"))

        title = ctk.CTkLabel(
            row,
            text=f"{icon} {set_id}",
            text_color=colour,
            font=(FONT, 14, "bold"),
        )
        title.pack(anchor="w", padx=10, pady=(8, 2))

        details = ctk.CTkLabel(
            row,
            text=f"{cards} Cards\n{duration}\n{date_label}",
            text_color=SUBTEXT,
            justify="left",
            font=(FONT, 12),
        )
        details.pack(anchor="w", padx=10, pady=(0, 8))

    # --------------------------------

    def _format_datetime(self, timestamp_value):

        if not timestamp_value:
            return "--"

        try:
            dt = datetime.fromisoformat(str(timestamp_value))
        except ValueError:
            return str(timestamp_value)

        now = datetime.now()
        day_label = dt.strftime("%b %d")

        if dt.date() == now.date():
            day_label = "Today"
        elif (now.date() - dt.date()).days == 1:
            day_label = "Yesterday"

        return f"{day_label} {dt.strftime('%I:%M %p').lstrip('0')}"
