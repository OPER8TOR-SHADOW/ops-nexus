import customtkinter as ctk

from gui.theme import *
from gui.build_worker import BuildWorker

from gui.components.set_selector import SetSelector
from gui.components.progress_card import ProgressCard
from gui.components.console import Console


class BuildPage(ctk.CTkFrame):

    def __init__(self, master):

        super().__init__(master, fg_color="transparent")

        # ======================================================
        # Layout
        # ======================================================

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(5, weight=1)

        # ======================================================
        # Title
        # ======================================================

        title = ctk.CTkLabel(
            self,
            text="Build Listing",
            font=(FONT, 30, "bold"),
            text_color=TEXT
        )

        title.grid(
            row=0,
            column=0,
            sticky="w",
            pady=(0, 20)
        )

        subtitle = ctk.CTkLabel(
            self,
            text="Draft workspace for validation, pricing, and listing preparation before upload to eBay.",
            font=(FONT, 14),
            text_color=MUTED,
        )

        subtitle.grid(
            row=1,
            column=0,
            sticky="w",
            pady=(0, 18)
        )

        # ======================================================
        # Set Selector
        # ======================================================

        self.set_selector = SetSelector(self)

        self.set_selector.grid(
            row=2,
            column=0,
            sticky="ew",
            pady=(0, 20)
        )

        # ======================================================
        # Progress Card
        # ======================================================

        self.progress = ProgressCard(self)

        self.progress.grid(
            row=3,
            column=0,
            sticky="ew",
            pady=(0, 20)
        )

        # ======================================================
        # Build Button
        # ======================================================

        self.build_button = ctk.CTkButton(
            self,
            text="🚀 BUILD LISTING",
            height=50,
            corner_radius=12,
            font=(FONT, 18, "bold"),
            fg_color=ACCENT,
            hover_color="#B00000",
            command=self.build
        )

        self.build_button.grid(
            row=4,
            column=0,
            sticky="ew",
            pady=(0, 20)
        )

        # ======================================================
        # Console
        # ======================================================

        self.console = Console(self)

        self.console.grid(
            row=5,
            column=0,
            sticky="nsew"
        )

    # ======================================================
    # Build
    # ======================================================

    def build(self):

        self.console.clear()
        self.build_button.configure(state="disabled")

        self.set_progress(0, "Starting Build...")

        try:
            selected_set = self.set_selector.get_id()
        except KeyError:
            self.log("No valid set selected.")
            self.set_progress(1, "Build Cancelled")
            self.build_button.configure(state="normal")
            return

        self.log("=" * 60)
        self.log("OPS Nexus")
        self.log("=" * 60)
        self.log(f"Selected Set: {selected_set}")
        self.log("")

        self.worker = BuildWorker(
            self,
            selected_set
        )

        self.worker.start()

    # ======================================================
    # Worker Callbacks
    # ======================================================

    def log(self, message):

        self.console.write(message)

    def set_progress(self, value, task):

        self.progress.set_progress(
            value,
            task
        )

        if value >= 1:

            self.build_button.configure(
                state="normal"
            )

    # ======================================================
    # Build Finished
    # ======================================================

    def build_finished(self):

        self.set_progress(
            1,
            "Build Complete"
        )

        self.build_button.configure(
            state="normal"
        )

        self.log("")
        self.log("=" * 60)
        self.log("✅ Build Complete")
        self.log("=" * 60)