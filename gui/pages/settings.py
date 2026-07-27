import os
from pathlib import Path

import customtkinter as ctk

from gui.theme import *


class SettingsPage(ctk.CTkFrame):

    def __init__(self, master):

        super().__init__(master, fg_color="transparent")

        self.grid_columnconfigure(0, weight=1)

        title = ctk.CTkLabel(
            self,
            text="Settings",
            font=(FONT, 30, "bold"),
            text_color=TEXT
        )

        title.grid(row=0, column=0, sticky="w", padx=20, pady=(20, 10))

        description = ctk.CTkLabel(
            self,
            text="Application settings and environment status.",
            font=(FONT, 16),
            text_color=MUTED
        )

        description.grid(row=1, column=0, sticky="w", padx=20, pady=(0, 20))

        section = ctk.CTkFrame(self, fg_color=CARD, border_width=1, border_color=BORDER, corner_radius=15)
        section.grid(row=2, column=0, sticky="nsew", padx=20, pady=(0, 20))

        section.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            section,
            text="Environment",
            font=(FONT, 18, "bold"),
            text_color=TEXT,
        ).grid(row=0, column=0, sticky="w", padx=18, pady=(18, 10))

        self.status_text = ctk.CTkTextbox(section, height=220, fg_color="transparent")
        self.status_text.grid(row=1, column=0, sticky="nsew", padx=18, pady=(0, 18))

        self.refresh_status()

    def refresh_status(self):
        project_root = Path(__file__).resolve().parents[2]
        env_path = project_root / ".env"
        env_exists = env_path.exists()
        token_present = bool(os.getenv("GITHUB_TOKEN"))

        lines = [
            f"Project root: {project_root}",
            f"Environment file: {'present' if env_exists else 'missing'}",
            f"GitHub token: {'configured' if token_present else 'not configured'}",
            f"Inventory folder: {'present' if (project_root / 'inventory').exists() else 'missing'}",
            f"Images folder: {'present' if (project_root / 'images').exists() else 'missing'}",
            f"Output folder: {'present' if (project_root / 'output').exists() else 'missing'}",
        ]

        self.status_text.delete("1.0", "end")
        self.status_text.insert("end", "\n".join(lines))
        self.status_text.configure(state="disabled")