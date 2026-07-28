import customtkinter as ctk
from collections import Counter

from gui.theme import *
from inventory_service import load_inventory_rows


class StatisticsPage(ctk.CTkFrame):

    def __init__(self, master):

        super().__init__(master, fg_color="transparent")

        self.grid_columnconfigure((0, 1, 2), weight=1)
        self.grid_rowconfigure(3, weight=1)

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

        self.summary = ctk.CTkFrame(self, fg_color=CARD, border_width=1, border_color=BORDER, corner_radius=15)
        self.summary.pack(fill="x", padx=20, pady=(16, 12))

        self.total_label = ctk.CTkLabel(self.summary, text="Total Listings: 0", font=(FONT, 14, "bold"), text_color=TEXT)
        self.total_label.pack(anchor="w", padx=16, pady=(12, 4))

        self.quantity_label = ctk.CTkLabel(self.summary, text="Total Quantity: 0", font=(FONT, 14), text_color=SUBTEXT)
        self.quantity_label.pack(anchor="w", padx=16, pady=2)

        self.value_label = ctk.CTkLabel(self.summary, text="Inventory Value: $0.00", font=(FONT, 14), text_color=SUBTEXT)
        self.value_label.pack(anchor="w", padx=16, pady=(2, 12))

        breakdown_row = ctk.CTkFrame(self, fg_color="transparent")
        breakdown_row.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        breakdown_row.grid_columnconfigure((0, 1), weight=1)
        breakdown_row.grid_rowconfigure(0, weight=1)

        finish_card = ctk.CTkFrame(breakdown_row, fg_color=CARD, border_width=1, border_color=BORDER, corner_radius=15)
        finish_card.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        ctk.CTkLabel(
            finish_card,
            text="Finish Breakdown",
            font=(FONT, 16, "bold"),
            text_color=TEXT,
        ).pack(anchor="w", padx=14, pady=(12, 8))

        self.finish_box = ctk.CTkTextbox(finish_card, fg_color=SUBTEXT)
        self.finish_box.pack(fill="both", expand=True, padx=14, pady=(0, 14))

        rarity_card = ctk.CTkFrame(breakdown_row, fg_color=CARD, border_width=1, border_color=BORDER, corner_radius=15)
        rarity_card.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

        ctk.CTkLabel(
            rarity_card,
            text="Rarity Breakdown",
            font=(FONT, 16, "bold"),
            text_color=TEXT,
        ).pack(anchor="w", padx=14, pady=(12, 8))

        self.rarity_box = ctk.CTkTextbox(rarity_card, fg_color=SUBTEXT)
        self.rarity_box.pack(fill="both", expand=True, padx=14, pady=(0, 14))

        self.refresh()

    def refresh(self):
        rows = load_inventory_rows()

        self.finish_box.configure(state="normal")
        self.rarity_box.configure(state="normal")
        self.finish_box.delete("1.0", "end")
        self.rarity_box.delete("1.0", "end")

        if not rows:
            self.total_label.configure(text="Total Listings: 0")
            self.quantity_label.configure(text="Total Quantity: 0")
            self.value_label.configure(text="Inventory Value: $0.00")
            self.finish_box.insert("end", "No inventory rows found.\n")
            self.rarity_box.insert("end", "No inventory rows found.\n")
            self.finish_box.configure(state="disabled")
            self.rarity_box.configure(state="disabled")
            return

        total_listings = len(rows)
        total_quantity = sum(int(item.get("quantity") or 0) for item in rows)
        inventory_value = sum(float(item.get("price") or 0) * int(item.get("quantity") or 0) for item in rows)

        finish_counts = Counter((item.get("finish") or "Unknown") for item in rows)
        rarity_counts = Counter((item.get("rarity") or "Unknown") for item in rows)

        self.total_label.configure(text=f"Total Listings: {total_listings}")
        self.quantity_label.configure(text=f"Total Quantity: {total_quantity}")
        self.value_label.configure(text=f"Inventory Value: ${inventory_value:,.2f}")

        for finish_name in sorted(finish_counts):
            self.finish_box.insert("end", f"{finish_name:<24} {finish_counts[finish_name]}\n")

        for rarity_name in sorted(rarity_counts):
            self.rarity_box.insert("end", f"{rarity_name:<30} {rarity_counts[rarity_name]}\n")

        self.finish_box.configure(state="disabled")
        self.rarity_box.configure(state="disabled")