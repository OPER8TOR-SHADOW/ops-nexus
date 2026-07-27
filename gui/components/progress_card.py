import customtkinter as ctk

from gui.theme import *
from gui.components.status_badge import StatusBadge


class ProgressCard(ctk.CTkFrame):

    def __init__(self, master):

        super().__init__(
            master,
            fg_color=CARD,
            border_width=1,
            border_color=BORDER,
            corner_radius=15
        )

        self.grid_columnconfigure(0, weight=1)

        # ----------------------------
        # Title
        # ----------------------------

        self.title = ctk.CTkLabel(
            self,
            text="Build Progress",
            font=(FONT, 18, "bold"),
            text_color=TEXT
        )

        self.title.pack(
            anchor="w",
            padx=20,
            pady=(18, 5)
        )

        # ----------------------------
        # Status Badge
        # ----------------------------

        self.status = StatusBadge(
            self,
            "Waiting"
        )

        self.status.pack(
            anchor="w",
            padx=20,
            pady=(0, 15)
        )

        # ----------------------------
        # Current Task
        # ----------------------------

        self.task = ctk.CTkLabel(
            self,
            text="Waiting for build...",
            font=(FONT, 15),
            text_color=SUBTEXT
        )

        self.task.pack(
            anchor="w",
            padx=20
        )

        # ----------------------------
        # Progress Bar
        # ----------------------------

        self.progress = ctk.CTkProgressBar(self)

        self.progress.pack(
            fill="x",
            padx=20,
            pady=(15, 20)
        )

        self.progress.set(0)

        # ----------------------------
        # Footer
        # ----------------------------

        self.footer = ctk.CTkFrame(
            self,
            fg_color="transparent"
        )

        self.footer.pack(
            fill="x",
            padx=20,
            pady=(0, 20)
        )

        self.percent = ctk.CTkLabel(
            self.footer,
            text="0%",
            text_color=TEXT,
            font=(FONT, 14, "bold")
        )

        self.percent.pack(
            side="left"
        )

        self.elapsed = ctk.CTkLabel(
            self.footer,
            text="Elapsed: 00:00",
            text_color=SUBTEXT,
            font=(FONT, 13)
        )

        self.elapsed.pack(
            side="right"
        )

    # --------------------------------

    def set_progress(self, value, task):

        value = max(0, min(1, value))

        self.progress.set(value)

        self.task.configure(
            text=task
        )

        self.percent.configure(
            text=f"{int(value * 100)}%"
        )

        if value == 1:

            self.status.set_status(
                "Complete",
                SUCCESS
            )

        elif value > 0:

            self.status.set_status(
                "Running",
                WARNING
            )

        else:

            self.status.set_status(
                "Waiting",
                SUCCESS
            )

    # --------------------------------

    def set_elapsed(self, text):

        self.elapsed.configure(
            text=f"Elapsed: {text}"
        )