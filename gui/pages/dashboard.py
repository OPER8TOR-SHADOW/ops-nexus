import customtkinter as ctk

from gui.theme import *

from gui.dashboard_service import DashboardService

from gui.components.stat_card import StatCard
from gui.components.section import Section
from gui.components.status_badge import StatusBadge


class DashboardPage(ctk.CTkFrame):

    def __init__(self, master):

        super().__init__(master, fg_color="transparent")

        self.service = DashboardService()

        self.grid_columnconfigure((0, 1, 2, 3), weight=1)
        self.grid_rowconfigure(2, weight=1)

        # =====================================================
        # Title
        # =====================================================

        title = ctk.CTkLabel(
            self,
            text="Dashboard",
            font=(FONT, 30, "bold"),
            text_color=TEXT
        )

        title.grid(
            row=0,
            column=0,
            columnspan=4,
            sticky="w",
            pady=(0, 25)
        )

        # =====================================================
        # Statistics
        # =====================================================

        self.inventory_card = StatCard(
            self,
            "📦 Inventory",
            "0"
        )

        self.images_card = StatCard(
            self,
            "🖼 Images",
            "0"
        )

        self.csv_card = StatCard(
            self,
            "📄 CSV Files",
            "0"
        )

        self.status_card = StatCard(
            self,
            "⚡ Status",
            "Ready"
        )

        self.inventory_card.grid(row=1, column=0, padx=8, sticky="ew")
        self.images_card.grid(row=1, column=1, padx=8, sticky="ew")
        self.csv_card.grid(row=1, column=2, padx=8, sticky="ew")
        self.status_card.grid(row=1, column=3, padx=8, sticky="ew")

        # =====================================================
        # Bottom Layout
        # =====================================================

        self.grid_columnconfigure(0, weight=2)
        self.grid_columnconfigure(1, weight=1)

        self.left = ctk.CTkFrame(
            self,
            fg_color="transparent"
        )

        self.right = ctk.CTkFrame(
            self,
            fg_color="transparent"
        )

        self.left.grid(
            row=2,
            column=0,
            columnspan=3,
            sticky="nsew",
            pady=25,
            padx=(0, 10)
        )

        self.right.grid(
            row=2,
            column=3,
            sticky="nsew",
            pady=25
        )

        # =====================================================
        # Recent Activity
        # =====================================================

        recent = Section(
            self.left,
            "Recent Activity"
        )

        recent.pack(fill="x", pady=(0, 20))

        self.activity = ctk.CTkTextbox(
            recent,
            height=180
        )

        self.activity.pack(
            fill="both",
            expand=True,
            padx=15,
            pady=(0, 15)
        )

        # =====================================================
        # System Status
        # =====================================================

        status = Section(
            self.right,
            "System Status"
        )

        status.pack(fill="both", expand=True)

        self.python = StatusBadge(status, "Python")
        self.github = StatusBadge(status, "GitHub")
        self.templates = StatusBadge(status, "Templates")
        self.inventory = StatusBadge(status, "Inventory")
        self.images = StatusBadge(status, "Images")
        self.output = StatusBadge(status, "Output")

        self.python.pack(fill="x", padx=15, pady=6)
        self.github.pack(fill="x", padx=15, pady=6)
        self.templates.pack(fill="x", padx=15, pady=6)
        self.inventory.pack(fill="x", padx=15, pady=6)
        self.images.pack(fill="x", padx=15, pady=6)
        self.output.pack(fill="x", padx=15, pady=6)

        self.refresh()

    # =====================================================
    # Refresh Dashboard
    # =====================================================

    def refresh(self):

        data = self.service.get_dashboard_data()

        self.inventory_card.set_value(data["inventory"])
        self.images_card.set_value(data["images"])
        self.csv_card.set_value(data["csv"])

        if data["github"]:
            self.status_card.set_value("Ready")
        else:
            self.status_card.set_value("Attention")

        self.python.set_status(data["python"])
        self.github.set_status(data["github"])
        self.templates.set_status(data["templates"])
        self.inventory.set_status(data["inventory_folder"])
        self.images.set_status(data["images_folder"])
        self.output.set_status(data["output"])

        self.activity.delete("1.0", "end")

        self.activity.insert(
            "end",
            "OPS Nexus Started\n\n"
        )

        self.activity.insert(
            "end",
            f"Inventory Files : {data['inventory']}\n"
        )

        self.activity.insert(
            "end",
            f"Images          : {data['images']}\n"
        )

        self.activity.insert(
            "end",
            f"CSV Files       : {data['csv']}\n"
        )

        self.activity.insert(
            "end",
            "\nSystem Ready."
        )