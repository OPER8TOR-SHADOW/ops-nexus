import customtkinter as ctk

from gui.theme import *
from inventory_service import load_inventory_rows


class InventoryPage(ctk.CTkFrame):

    def __init__(self, master):

        super().__init__(master, fg_color="transparent")

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        title = ctk.CTkLabel(
            self,
            text="Inventory",
            font=(FONT, 30, "bold"),
            text_color=TEXT
        )

        title.grid(row=0, column=0, sticky="w", padx=20, pady=(20, 10))

        description = ctk.CTkLabel(
            self,
            text="Review your current inventory workbook.",
            font=(FONT, 16),
            text_color=MUTED
        )

        description.grid(row=1, column=0, sticky="w", padx=20, pady=(0, 10))

        self.summary = ctk.CTkFrame(self, fg_color=CARD, border_width=1, border_color=BORDER, corner_radius=15)
        self.summary.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 12))

        self.summary_label = ctk.CTkLabel(
            self.summary,
            text="",
            font=(FONT, 14),
            text_color=TEXT,
            justify="left",
        )
        self.summary_label.pack(anchor="w", padx=18, pady=14)

        self.listbox = ctk.CTkTextbox(self, height=400, fg_color=CARD)
        self.listbox.grid(row=3, column=0, sticky="nsew", padx=20, pady=(0, 20))

        self.refresh()

    def refresh(self):
        rows = load_inventory_rows()
        self.listbox.configure(state="normal")
        self.listbox.delete("1.0", "end")

        if not rows:
            self.summary_label.configure(text="No inventory workbook found yet.")
            self.listbox.insert("end", "No inventory rows available.\n")
            return

        self.summary_label.configure(
            text=f"{len(rows)} SKU(s) loaded • {sum(item['quantity'] for item in rows)} total quantity"
        )

        for item in rows:
            self.listbox.insert(
                "end",
                f"{item['sku']} | {item['card_name']} | {item['finish']} | Qty {item['quantity']} | ${item['price']:.2f}\n",
            )

        self.listbox.configure(state="disabled")