import customtkinter as ctk

from gui.theme import *
from pricing_manager import DEFAULT_PRICES, load_prices, save_prices


class PricingPage(ctk.CTkFrame):

    def __init__(self, master):

        super().__init__(master, fg_color="transparent")

        self.price_vars = {}

        title = ctk.CTkLabel(
            self,
            text="Pricing",
            font=(FONT, 30, "bold"),
            text_color=TEXT
        )

        title.pack(anchor="w", padx=20, pady=(20, 10))

        description = ctk.CTkLabel(
            self,
            text="Manage pricing rules.",
            font=(FONT, 16),
            text_color=MUTED
        )

        description.pack(anchor="w", padx=20)

        toolbar = ctk.CTkFrame(self, fg_color="transparent")
        toolbar.pack(fill="x", padx=20, pady=(14, 10))

        ctk.CTkButton(
            toolbar,
            text="Save Changes",
            width=120,
            command=self.save,
        ).pack(side="left")

        ctk.CTkButton(
            toolbar,
            text="Reset Defaults",
            width=120,
            command=self.reset_defaults,
        ).pack(side="left", padx=(8, 0))

        ctk.CTkButton(
            toolbar,
            text="Reload",
            width=100,
            command=self.load,
        ).pack(side="left", padx=(8, 0))

        self.status_label = ctk.CTkLabel(
            toolbar,
            text="",
            font=(FONT, 12),
            text_color=SUBTEXT,
        )
        self.status_label.pack(side="left", padx=(14, 0))

        card = ctk.CTkFrame(self, fg_color=CARD, border_width=1, border_color=BORDER, corner_radius=15)
        card.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        ctk.CTkLabel(
            card,
            text="Pricing Rules",
            font=(FONT, 18, "bold"),
            text_color=TEXT,
        ).pack(anchor="w", padx=16, pady=(14, 8))

        self.form = ctk.CTkScrollableFrame(card, fg_color="transparent")
        self.form.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        self.load()

    def _render_rows(self, prices):
        for child in self.form.winfo_children():
            child.destroy()

        self.price_vars = {}

        for key in sorted(prices):
            row = ctk.CTkFrame(self.form, fg_color="transparent")
            row.pack(fill="x", pady=4)

            ctk.CTkLabel(
                row,
                text=key,
                font=(FONT, 13, "bold"),
                text_color=TEXT,
                width=260,
                anchor="w",
            ).pack(side="left")

            var = ctk.StringVar(value=f"{float(prices[key]):.2f}")
            self.price_vars[key] = var

            ctk.CTkEntry(
                row,
                textvariable=var,
                width=140,
            ).pack(side="left", padx=(8, 0))

    def load(self):
        prices = load_prices()
        self._render_rows(prices)
        self.status_label.configure(text="Loaded pricing.json", text_color=SUBTEXT)

    def save(self):
        updated = {}

        for key, var in self.price_vars.items():
            text = var.get().strip()
            try:
                value = float(text)
            except ValueError:
                self.status_label.configure(text=f"Invalid numeric value for {key}", text_color=ERROR)
                return

            if value < 0:
                self.status_label.configure(text=f"Price cannot be negative for {key}", text_color=ERROR)
                return

            updated[key] = round(value, 2)

        save_prices(updated)
        self.status_label.configure(text="Pricing saved.", text_color=SUCCESS)

    def reset_defaults(self):
        save_prices(DEFAULT_PRICES.copy())
        self._render_rows(load_prices())
        self.status_label.configure(text="Pricing reset to defaults.", text_color=WARNING)