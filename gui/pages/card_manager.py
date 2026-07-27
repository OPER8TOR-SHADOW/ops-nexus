import customtkinter as ctk
from PIL import Image
from tkinter import filedialog

from database.service import DatabaseService, build_workflow_status
from gui.theme import *


class CardManagerPage(ctk.CTkFrame):

    def __init__(self, master, page_manager=None, selected_set=None):

        super().__init__(master, fg_color=BACKGROUND)

        self.page_manager = page_manager
        self.db = DatabaseService()
        self.selected_set = selected_set
        self.cards = []
        self.display_cards = []
        self.selected_card = None
        self.selected_finish_id = None
        self.selected_finish_by_card = {}
        self.finish_chip_buttons = {}
        self.preview_image_ref = None
        self.reveal_image_button = None
        self.card_row_headers = {}
        self.github_status_label = None
        self.github_repo_path_label = None
        self.github_last_upload_label = None
        self.github_remote_url_label = None
        self.github_source_label = None
        self.github_error_label = None
        self.github_progress_label = None
        self.ebay_status_label = None
        self.ebay_reason_label = None
        self.ebay_progress_label = None
        self.ebay_queue_progress_bar = None
        self.ebay_queue_filter = "All"
        self.ebay_filter_buttons = {}
        self.ebay_queue_table_frame = None
        self.readiness_filter = "All"
        self.readiness_buttons = {}
        self.readiness_rows = []
        self.readiness_by_finish = {}
        self.readiness_by_card = {}
        self.readiness_summary = {
            "total_finishes": 0,
            "ready": 0,
            "missing_inventory": 0,
            "missing_pricing": 0,
            "missing_images": 0,
            "ready_for_publishing": 0,
        }
        self.readiness_value_labels = {}
        self.selected_finish_readiness_label = None

        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=2)
        self.grid_rowconfigure(3, weight=1)

        self.build_ui()

        if self.selected_set:
            self.load_set(self.selected_set)
        else:
            self.show_empty_state()

    def build_ui(self):

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, columnspan=2, sticky="ew", padx=24, pady=(20, 12))

        title = ctk.CTkLabel(
            header,
            text="Card Manager",
            font=(FONT, 28, "bold"),
            text_color=TEXT,
        )
        title.pack(anchor="w")

        subtitle = ctk.CTkLabel(
            header,
            text="Browse cards for a single selected set and prepare for future inventory, pricing, and eBay workflows.",
            font=(FONT, 14),
            text_color=MUTED,
        )
        subtitle.pack(anchor="w", pady=(4, 0))

        toolbar = ctk.CTkFrame(self, fg_color="transparent")
        toolbar.grid(row=1, column=0, columnspan=2, sticky="ew", padx=24, pady=(0, 12))

        self.search_var = ctk.StringVar(value="")
        self.search_box = ctk.CTkEntry(
            toolbar,
            placeholder_text="Search cards",
            textvariable=self.search_var,
        )
        self.search_box.pack(side="left", fill="x", expand=True)
        self.search_box.bind("<Return>", lambda _event: self.refresh_list())
        self.search_box.bind("<KeyRelease>", lambda _event: self.refresh_list())

        self.rarity_var = ctk.StringVar(value="All")
        self.rarity_filter = ctk.CTkOptionMenu(
            toolbar,
            values=["All"],
            variable=self.rarity_var,
            width=140,
            command=lambda *_: self.refresh_list(),
        )
        self.rarity_filter.pack(side="left", padx=(10, 0))

        self.sort_var = ctk.StringVar(value="number")
        self.sort_selector = ctk.CTkOptionMenu(
            toolbar,
            values=["number", "name", "rarity", "inventory", "finish_count"],
            variable=self.sort_var,
            width=140,
            command=lambda *_: self.refresh_list(),
        )
        self.sort_selector.pack(side="left", padx=(10, 0))

        refresh_button = ctk.CTkButton(
            toolbar,
            text="Refresh",
            command=self.refresh_list,
            width=90,
        )
        refresh_button.pack(side="left", padx=(10, 0))

        dashboard = ctk.CTkFrame(self, fg_color=CARD, border_width=1, border_color=BORDER, corner_radius=14)
        dashboard.grid(row=2, column=0, columnspan=2, sticky="ew", padx=24, pady=(0, 12))

        summary_row = ctk.CTkFrame(dashboard, fg_color="transparent")
        summary_row.pack(fill="x", padx=14, pady=(12, 6))

        readiness_fields = [
            ("total_finishes", "Total Finishes"),
            ("ready", "Ready"),
            ("missing_inventory", "Missing Inventory"),
            ("missing_pricing", "Missing Pricing"),
            ("missing_images", "Missing Images"),
            ("ready_for_publishing", "Ready For Publishing"),
        ]

        for key, label in readiness_fields:
            block = ctk.CTkFrame(summary_row, fg_color=SUBTEXT, corner_radius=10)
            block.pack(side="left", fill="x", expand=True, padx=(0, 8))
            ctk.CTkLabel(block, text=label, font=(FONT, 11), text_color=MUTED).pack(anchor="w", padx=10, pady=(8, 0))
            value = ctk.CTkLabel(block, text="0", font=(FONT, 16, "bold"), text_color=TEXT)
            value.pack(anchor="w", padx=10, pady=(0, 8))
            self.readiness_value_labels[key] = value

        filter_row = ctk.CTkFrame(dashboard, fg_color="transparent")
        filter_row.pack(fill="x", padx=14, pady=(0, 12))

        ctk.CTkLabel(
            filter_row,
            text="Readiness Filters:",
            font=(FONT, 12, "bold"),
            text_color=SUBTEXT,
        ).pack(side="left", padx=(0, 8))

        filter_options = [
            "All",
            "Ready",
            "Missing Inventory",
            "Missing Pricing",
            "Missing Images",
        ]

        for option in filter_options:
            button = ctk.CTkButton(
                filter_row,
                text=option,
                width=132,
                height=30,
                corner_radius=8,
                border_width=1,
                command=lambda selected=option: self.select_readiness_filter(selected),
            )
            button.pack(side="left", padx=(0, 8))
            self.readiness_buttons[option] = button

        self._update_readiness_filter_highlight()

        left_panel = ctk.CTkFrame(self, fg_color="transparent")
        left_panel.grid(row=3, column=0, sticky="nsew", padx=(24, 10), pady=(0, 24))

        left_panel.grid_columnconfigure(0, weight=1)
        left_panel.grid_rowconfigure(0, weight=0)
        left_panel.grid_rowconfigure(1, weight=1)

        self.list_header = ctk.CTkLabel(
            left_panel,
            text="Cards (0)",
            font=(FONT, 18, "bold"),
            text_color=TEXT,
        )
        self.list_header.grid(row=0, column=0, sticky="w", pady=(0, 8))

        self.card_list = ctk.CTkScrollableFrame(left_panel, fg_color="transparent")
        self.card_list.grid(row=1, column=0, sticky="nsew")
        self.card_list.grid_columnconfigure(0, weight=1)

        right_panel = ctk.CTkFrame(self, fg_color="transparent")
        right_panel.grid(row=3, column=1, sticky="nsew", padx=(10, 24), pady=(0, 24))

        right_panel.grid_columnconfigure(0, weight=1)
        right_panel.grid_rowconfigure(0, weight=1)

        self.detail_container = ctk.CTkScrollableFrame(
            right_panel,
            fg_color="transparent",
        )
        self.detail_container.grid(row=0, column=0, sticky="nsew")
        self.detail_container.grid_columnconfigure(0, weight=1)

    def load_set(self, set_id):
        self.selected_set = set_id
        self.cards = self.db.get_card_workspace(set_id)
        self.refresh_readiness_cache()
        self.populate_rarity_filter()
        self.refresh_list()

    def populate_rarity_filter(self):
        rarities = sorted({card.get("rarity") for card in self.cards if card.get("rarity")})
        values = ["All"] + rarities
        self.rarity_filter.configure(values=values)
        if self.rarity_var.get() not in values:
            self.rarity_var.set("All")

    def refresh_list(self):
        self.card_row_headers = {}
        for child in self.card_list.winfo_children():
            child.destroy()

        query = self.search_var.get().strip().lower()
        rarity_filter = self.rarity_var.get()
        sort_key = self.sort_var.get()

        visible_cards = []
        for card in self.cards:
            if rarity_filter != "All" and str(card.get("rarity", "")).lower() != rarity_filter.lower():
                continue

            if not self._card_matches_readiness_filter(card):
                continue

            if query:
                text_blob = " ".join(
                    [
                        str(card.get("number", "")),
                        str(card.get("name", "")),
                        str(card.get("rarity", "")),
                    ]
                ).lower()

                if query not in text_blob:
                    continue

            visible_cards.append(card)

        self.display_cards = self.sort_cards(visible_cards, sort_key)

        # update header count
        try:
            self.list_header.configure(text=f"Cards ({len(self.display_cards)})")
        except Exception:
            pass

        if not self.display_cards:
            self.show_empty_state()
            return

        for card in self.display_cards:
            row = ctk.CTkFrame(self.card_list, fg_color="transparent")
            row.pack(fill="x", pady=6)
            row.configure(cursor="hand2")

            header = ctk.CTkFrame(row, fg_color=CARD, border_width=1, border_color=BORDER, corner_radius=12)
            header.pack(fill="x")
            self.card_row_headers[self._card_identifier(card)] = header

            body = ctk.CTkFrame(header, fg_color="transparent")
            body.pack(fill="x", padx=12, pady=10)

            left = ctk.CTkFrame(body, fg_color="transparent")
            left.pack(side="left", fill="y")

            ctk.CTkLabel(
                left,
                text=str(card.get("number", "—")),
                font=(FONT, 13, "bold"),
                text_color=TEXT,
                width=60,
            ).pack(anchor="w")

            ctk.CTkLabel(
                left,
                text=str(card.get("name", "Untitled Card")),
                font=(FONT, 13, "bold"),
                text_color=TEXT,
            ).pack(anchor="w", padx=(8, 0))

            ctk.CTkLabel(
                left,
                text=f"{card.get('rarity') or 'Unknown'}",
                font=(FONT, 11),
                text_color=MUTED,
            ).pack(anchor="w", pady=(4, 0))

            right = ctk.CTkFrame(body, fg_color="transparent")
            right.pack(side="right", anchor="n")

            card_readiness = self.readiness_by_card.get(self._card_identifier(card), {})
            ready_count = int(card_readiness.get("ready", 0) or 0)
            total_count = int(card_readiness.get("total", 0) or 0)
            readiness_text = f"Ready: {ready_count}/{total_count}" if total_count > 0 else "Ready: 0/0"
            readiness_color = SUCCESS if total_count > 0 and ready_count == total_count else WARNING

            ctk.CTkLabel(
                right,
                text=readiness_text,
                font=(FONT, 12, "bold"),
                text_color=readiness_color,
            ).pack(anchor="e", pady=(0, 2))

            ctk.CTkLabel(
                right,
                text=f"Inventory: {card.get('inventory_quantity', 0)}",
                font=(FONT, 12),
                text_color=SUBTEXT,
            ).pack(anchor="e")

            status = build_workflow_status(card)
            badges = ctk.CTkFrame(right, fg_color="transparent")
            badges.pack(anchor="e", pady=(6, 0))

            # compact badges
            if status.get("imported"):
                ctk.CTkLabel(badges, text="Imported", font=(FONT, 10, "bold"), fg_color=SUBTEXT, text_color=TEXT, corner_radius=8, padx=8, pady=2).pack(side="right", padx=(6, 0))
            if status.get("images"):
                ctk.CTkLabel(badges, text="Images", font=(FONT, 10), fg_color=SUBTEXT, text_color=TEXT, corner_radius=8, padx=8, pady=2).pack(side="right", padx=(6, 0))
            if status.get("inventory"):
                ctk.CTkLabel(badges, text="Inventory", font=(FONT, 10), fg_color=SUBTEXT, text_color=TEXT, corner_radius=8, padx=8, pady=2).pack(side="right", padx=(6, 0))
            if status.get("pricing"):
                ctk.CTkLabel(badges, text="Pricing", font=(FONT, 10), fg_color=SUBTEXT, text_color=TEXT, corner_radius=8, padx=8, pady=2).pack(side="right", padx=(6, 0))
            if status.get("ebay"):
                ctk.CTkLabel(badges, text="eBay", font=(FONT, 10), fg_color=SUBTEXT, text_color=TEXT, corner_radius=8, padx=8, pady=2).pack(side="right", padx=(6, 0))

            self._bind_card_row_click(row, card)

            # highlight selected
            try:
                if self.selected_card and self._card_identifier(self.selected_card) == self._card_identifier(card):
                    header.configure(border_width=2, border_color=ACCENT)
            except Exception:
                pass

        if self.selected_card is None:
            self.select_card(self.display_cards[0])
        else:
            current_ids = {self._card_identifier(card) for card in self.display_cards}
            if self._card_identifier(self.selected_card) not in current_ids:
                self.select_card(self.display_cards[0])
            else:
                self._update_card_selection_highlight()

    def sort_cards(self, cards, sort_key):
        def sort_value(card):
            if sort_key == "name":
                return str(card.get("name", "")).lower()
            if sort_key == "rarity":
                return str(card.get("rarity", "")).lower()
            if sort_key == "inventory":
                return int(card.get("inventory_quantity", 0) or 0)
            if sort_key == "finish_count":
                return int(card.get("finish_count", 0) or 0)
            return self.card_number_sort_value(card.get("number", ""))

        return sorted(cards, key=sort_value)

    def card_number_sort_value(self, value):
        try:
            return (0, int(str(value).strip()))
        except (TypeError, ValueError):
            return (1, str(value).lower())

    def select_card(self, card):
        self.selected_card = card
        self._sync_selected_finish_for_card(card)
        self._update_card_selection_highlight()
        self.render_detail(card)

    def _bind_card_row_click(self, widget, card):
        widget.bind("<Button-1>", lambda _event, selected=card: self.select_card(selected))
        for child in widget.winfo_children():
            self._bind_card_row_click(child, card)

    def _update_card_selection_highlight(self):
        selected_id = self._card_identifier(self.selected_card) if self.selected_card else None

        for card_id, header in self.card_row_headers.items():
            if card_id == selected_id:
                header.configure(border_width=2, border_color=ACCENT)
            else:
                header.configure(border_width=1, border_color=BORDER)

    def render_detail(self, card):
        self.preview_image_ref = None
        for child in self.detail_container.winfo_children():
            child.destroy()

        finishes = self.db.get_finishes_for_card(self._card_identifier(card))
        self._sync_selected_finish_for_card(card, finishes=finishes)
        image_info = self.db.get_finish_image(self.selected_set, card, self.selected_finish_id)

        content = ctk.CTkFrame(self.detail_container, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=18, pady=18)

        header = ctk.CTkFrame(content, fg_color=CARD, border_width=1, border_color=BORDER, corner_radius=16)
        header.pack(fill="x", pady=(0, 12), padx=0)

        header_inner = ctk.CTkFrame(header, fg_color="transparent")
        header_inner.pack(fill="x", padx=18, pady=12)

        # image preview panel
        img_preview = ctk.CTkFrame(header_inner, fg_color=SUBTEXT, width=120, height=160, corner_radius=8)
        img_preview.pack(side="left")
        img_preview.pack_propagate(False)

        preview_image = self._build_preview_image(image_info.get("path"), 110, 150)
        if preview_image is None:
            ctk.CTkLabel(
                img_preview,
                text="No Image Available",
                font=(FONT, 11),
                text_color=MUTED,
                justify="center",
            ).pack(expand=True)
        else:
            preview_label = ctk.CTkLabel(
                img_preview,
                text="",
                image=preview_image,
                fg_color="transparent",
            )
            # Keep a widget-owned strong reference for the displayed image lifecycle.
            preview_label._ops_preview_image_ref = preview_image
            preview_label.pack(expand=True)
            self.preview_image_ref = preview_image

        # info column
        info_col = ctk.CTkFrame(header_inner, fg_color="transparent")
        info_col.pack(side="left", fill="both", expand=True, padx=(12, 0))

        ctk.CTkLabel(
            info_col,
            text=card.get("name", "Untitled Card"),
            font=(FONT, 22, "bold"),
            text_color=TEXT,
        ).pack(anchor="w", pady=(2, 2))

        sub_row = ctk.CTkFrame(info_col, fg_color="transparent")
        sub_row.pack(fill="x")

        ctk.CTkLabel(
            sub_row,
            text=f"{card.get('number', '—')} • {card.get('rarity') or 'Unknown'}",
            font=(FONT, 14),
            text_color=MUTED,
        ).pack(side="left")

        finish_row = ctk.CTkFrame(info_col, fg_color="transparent")
        finish_row.pack(anchor="w", pady=(8, 0))

        ctk.CTkLabel(
            finish_row,
            text="Finish:",
            font=(FONT, 12, "bold"),
            text_color=SUBTEXT,
        ).pack(side="left", padx=(0, 8))

        chips = ctk.CTkFrame(finish_row, fg_color="transparent")
        chips.pack(side="left")

        self.finish_chip_buttons = {}
        for finish in finishes:
            finish_id = finish.get("id")
            finish_text = str(finish.get("finish") or "Unknown")
            chip = ctk.CTkButton(
                chips,
                text=finish_text,
                width=max(80, 10 * len(finish_text)),
                height=28,
                corner_radius=8,
                border_width=1,
                command=lambda selected_id=finish_id: self.select_finish(selected_id),
            )
            chip.pack(side="left", padx=(0, 8))
            self.finish_chip_buttons[finish_id] = chip

        self._update_finish_chip_highlight()

        readiness_badge_row = ctk.CTkFrame(info_col, fg_color="transparent")
        readiness_badge_row.pack(anchor="w", pady=(8, 0))

        self.selected_finish_readiness_label = ctk.CTkLabel(
            readiness_badge_row,
            text="",
            font=(FONT, 11, "bold"),
            corner_radius=8,
            padx=8,
            pady=4,
        )
        self.selected_finish_readiness_label.pack(side="left", padx=(0, 8))
        self._update_selected_finish_readiness_badge()

        # workflow badges in header
        status = build_workflow_status(card)
        status["images"] = bool(image_info.get("found"))
        badge_row = ctk.CTkFrame(info_col, fg_color="transparent")
        badge_row.pack(anchor="w", pady=(8, 0))

        image_status_text = image_info.get("status_badge", "🟡 Missing Image")
        image_status_bg = "#1C3A28" if image_info.get("status") == "ready" else ("#3A2020" if image_info.get("status") == "invalid" else "#3A3520")
        image_status_fg = SUCCESS if image_info.get("status") == "ready" else (ERROR if image_info.get("status") == "invalid" else WARNING)
        ctk.CTkLabel(
            badge_row,
            text=image_status_text,
            font=(FONT, 11, "bold"),
            fg_color=image_status_bg,
            text_color=image_status_fg,
            corner_radius=8,
            padx=8,
            pady=4,
        ).pack(side="left", padx=(0, 8))

        if image_info.get("status") == "ready":
            ctk.CTkLabel(badge_row, text="Images", font=(FONT, 11), fg_color=SUBTEXT, text_color=TEXT, corner_radius=8, padx=8, pady=4).pack(side="left", padx=(0, 8))
        if status.get("inventory"):
            ctk.CTkLabel(badge_row, text="Inventory", font=(FONT, 11), fg_color=SUBTEXT, text_color=TEXT, corner_radius=8, padx=8, pady=4).pack(side="left", padx=(0, 8))
        if status.get("pricing"):
            ctk.CTkLabel(badge_row, text="Pricing", font=(FONT, 11), fg_color=SUBTEXT, text_color=TEXT, corner_radius=8, padx=8, pady=4).pack(side="left", padx=(0, 8))
        if status.get("ebay"):
            ctk.CTkLabel(badge_row, text="eBay", font=(FONT, 11), fg_color=SUBTEXT, text_color=TEXT, corner_radius=8, padx=8, pady=4).pack(side="left", padx=(0, 8))

        self.add_section(
            content,
            "Card Information",
            [
                ("Set", self.selected_set or "Unknown"),
                ("Card Number", card.get("number", "—")),
                ("Rarity", card.get("rarity") or "Unknown"),
                ("Finish Count", card.get("finish_count", 0)),
                ("Inventory", card.get("inventory_quantity", 0)),
            ],
        )
        self.add_image_workspace_section(content, image_info)
        self.add_inventory_section(content, card)
        self.add_pricing_section(content, card)
        self.add_github_section(content, card)
        self.add_ebay_queue_section(content, card)

        ebay_status = self.db.get_finish_ebay_status(self.selected_finish_id)
        self.add_section(
            content,
            "eBay",
            [
                ("Listing Status", ebay_status.get("status") or "Not Queued"),
                ("Listing ID", card.get("listing_id") or "Pending"),
            ],
        )

    def add_inventory_section(self, parent, card):
        section = ctk.CTkFrame(
            parent,
            fg_color=CARD,
            border_width=1,
            border_color=BORDER,
            corner_radius=14,
        )
        section.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(
            section,
            text="Inventory",
            font=(FONT, 15, "bold"),
            text_color=TEXT,
        ).pack(anchor="w", padx=14, pady=(12, 8))

        body = ctk.CTkFrame(section, fg_color="transparent")
        body.pack(fill="x", padx=14, pady=(0, 12))

        finish_inventory = self.db.get_finish_inventory(self.selected_finish_id, fallback_card_data=card)

        quantity_var = ctk.StringVar(value=str(finish_inventory.get("quantity", 0) or 0))
        cost_var = ctk.StringVar(value=f"{finish_inventory.get('cost_price', 0) or 0:.2f}")
        sell_var = ctk.StringVar(value=f"{card.get('sell_price', 0) or 0:.2f}")
        error_label = ctk.CTkLabel(section, text="", font=(FONT, 11), text_color=ERROR)
        error_label.pack(anchor="w", padx=14, pady=(0, 8))

        for label, var in [("Quantity", quantity_var), ("Cost Price", cost_var), ("Sell Price", sell_var)]:
            row = ctk.CTkFrame(body, fg_color="transparent")
            row.pack(fill="x", pady=3)

            ctk.CTkLabel(
                row,
                text=f"{label}:",
                font=(FONT, 12, "bold"),
                text_color=SUBTEXT,
                width=110,
            ).pack(side="left")

            ctk.CTkEntry(
                row,
                textvariable=var,
                width=260,
            ).pack(side="left", padx=(8, 0))

        def save_inventory():
            error_label.configure(text="")

            try:
                quantity = int(quantity_var.get().strip())
            except ValueError:
                error_label.configure(text="Quantity must be zero or greater.")
                return

            if quantity < 0:
                error_label.configure(text="Quantity must be zero or greater.")
                return

            try:
                cost_price = float(cost_var.get().strip())
            except ValueError:
                error_label.configure(text="Cost Price must be numeric.")
                return

            self.db.save_finish_inventory(self.selected_finish_id, quantity, cost_price)
            self.refresh_readiness_cache()

            if self.selected_card is not None:
                self.render_detail(self.selected_card)

            self.refresh_list()

        ctk.CTkButton(
            body,
            text="Save",
            width=90,
            command=save_inventory,
        ).pack(anchor="w", pady=(10, 0))

    def add_section(self, parent, title, rows):
        section = ctk.CTkFrame(
            parent,
            fg_color=CARD,
            border_width=1,
            border_color=BORDER,
            corner_radius=14,
        )
        section.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(
            section,
            text=title,
            font=(FONT, 15, "bold"),
            text_color=TEXT,
        ).pack(anchor="w", padx=14, pady=(12, 8))

        body = ctk.CTkFrame(section, fg_color="transparent")
        body.pack(fill="x", padx=14, pady=(0, 12))

        for label, value in rows:
            row = ctk.CTkFrame(body, fg_color="transparent")
            row.pack(fill="x", pady=3)

            ctk.CTkLabel(
                row,
                text=f"{label}:",
                font=(FONT, 12, "bold"),
                text_color=SUBTEXT,
                width=110,
            ).pack(side="left")

            ctk.CTkLabel(
                row,
                text=str(value),
                font=(FONT, 12),
                text_color=TEXT,
                justify="left",
                wraplength=360,
            ).pack(side="left", padx=(8, 0))

    def add_pricing_section(self, parent, card):
        section = ctk.CTkFrame(
            parent,
            fg_color=CARD,
            border_width=1,
            border_color=BORDER,
            corner_radius=14,
        )
        section.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(
            section,
            text="Pricing",
            font=(FONT, 15, "bold"),
            text_color=TEXT,
        ).pack(anchor="w", padx=14, pady=(12, 8))

        body = ctk.CTkFrame(section, fg_color="transparent")
        body.pack(fill="x", padx=14, pady=(0, 12))

        finish_pricing = self.db.get_finish_pricing(self.selected_finish_id, fallback_card_data=card)

        sell_var = ctk.StringVar(value=f"{finish_pricing.get('sell_price', 0) or 0:.2f}")
        market_var = ctk.StringVar(value=f"{finish_pricing.get('market_price', 0) or 0:.2f}")
        error_label = ctk.CTkLabel(section, text="", font=(FONT, 11), text_color=ERROR)
        error_label.pack(anchor="w", padx=14, pady=(0, 8))

        for label, var in [("Sell Price", sell_var), ("Market Price", market_var)]:
            row = ctk.CTkFrame(body, fg_color="transparent")
            row.pack(fill="x", pady=3)

            ctk.CTkLabel(
                row,
                text=f"{label}:",
                font=(FONT, 12, "bold"),
                text_color=SUBTEXT,
                width=110,
            ).pack(side="left")

            ctk.CTkEntry(
                row,
                textvariable=var,
                width=260,
            ).pack(side="left", padx=(8, 0))

        def save_pricing():
            error_label.configure(text="")

            try:
                sell_price = float(sell_var.get().strip())
            except ValueError:
                error_label.configure(text="Sell Price must be numeric.")
                return

            try:
                market_price = float(market_var.get().strip())
            except ValueError:
                error_label.configure(text="Market Price must be numeric.")
                return

            self.db.save_finish_pricing(self.selected_finish_id, sell_price, market_price)
            self.refresh_readiness_cache()

            if self.selected_card is not None:
                self.render_detail(self.selected_card)

            self.refresh_list()

        ctk.CTkButton(
            body,
            text="Save",
            width=90,
            command=save_pricing,
        ).pack(anchor="w", pady=(10, 0))

    def add_github_section(self, parent, card):
        section = ctk.CTkFrame(
            parent,
            fg_color=CARD,
            border_width=1,
            border_color=BORDER,
            corner_radius=14,
        )
        section.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(
            section,
            text="GitHub",
            font=(FONT, 15, "bold"),
            text_color=TEXT,
        ).pack(anchor="w", padx=14, pady=(12, 8))

        body = ctk.CTkFrame(section, fg_color="transparent")
        body.pack(fill="x", padx=14, pady=(0, 8))

        github_status = self.db.get_finish_github_status(self.selected_finish_id)
        queue_status = self.db.refresh_queue_status()
        progress = queue_status.get("progress", {})

        rows = [
            ("GitHub Status", github_status.get("status") or "Pending"),
            ("Repository Path", github_status.get("repository_path") or "Not available"),
            ("Last Upload Time", github_status.get("last_upload_time") or "Not uploaded"),
            ("Remote URL", github_status.get("remote_url") or "Not uploaded"),
            ("Publishing Source", github_status.get("publishing_source") or "Unknown"),
        ]

        labels_by_key = {}
        for label_text, value in rows:
            row = ctk.CTkFrame(body, fg_color="transparent")
            row.pack(fill="x", pady=3)

            ctk.CTkLabel(
                row,
                text=f"{label_text}:",
                font=(FONT, 12, "bold"),
                text_color=SUBTEXT,
                width=130,
            ).pack(side="left")

            value_label = ctk.CTkLabel(
                row,
                text=str(value),
                font=(FONT, 12),
                text_color=TEXT,
                justify="left",
                wraplength=520,
            )
            value_label.pack(side="left", padx=(8, 0))
            labels_by_key[label_text] = value_label

        self.github_status_label = labels_by_key.get("GitHub Status")
        self.github_repo_path_label = labels_by_key.get("Repository Path")
        self.github_last_upload_label = labels_by_key.get("Last Upload Time")
        self.github_remote_url_label = labels_by_key.get("Remote URL")
        self.github_source_label = labels_by_key.get("Publishing Source")

        self.github_error_label = ctk.CTkLabel(
            section,
            text=github_status.get("error_message") or "",
            font=(FONT, 11),
            text_color=ERROR,
            wraplength=620,
            justify="left",
        )
        self.github_error_label.pack(anchor="w", padx=14, pady=(0, 8))

        progress_text = (
            f"Current: {self._queue_current_label(progress.get('current_upload'))}   "
            f"Completed: {progress.get('completed', 0)}   "
            f"Remaining: {progress.get('remaining', 0)}   "
            f"Failed: {progress.get('failed', 0)}"
        )
        self.github_progress_label = ctk.CTkLabel(
            section,
            text=progress_text,
            font=(FONT, 11, "bold"),
            text_color=SUBTEXT,
        )
        self.github_progress_label.pack(anchor="w", padx=14, pady=(0, 8))

        actions = ctk.CTkFrame(section, fg_color="transparent")
        actions.pack(fill="x", padx=14, pady=(0, 12))

        ctk.CTkButton(
            actions,
            text="Publish Selected Finish",
            width=170,
            command=self.publish_selected_finish,
        ).pack(side="left")

        ctk.CTkButton(
            actions,
            text="Publish Ready Finishes",
            width=170,
            command=self.publish_ready_finishes,
        ).pack(side="left", padx=(8, 0))

        ctk.CTkButton(
            actions,
            text="Retry Failed",
            width=120,
            command=self.retry_failed_uploads,
        ).pack(side="left", padx=(8, 0))

        ctk.CTkButton(
            actions,
            text="Cancel Queue",
            width=110,
            command=self.cancel_github_queue,
        ).pack(side="left", padx=(8, 0))

        ctk.CTkButton(
            actions,
            text="Refresh Status",
            width=120,
            command=self.refresh_github_status,
        ).pack(side="left", padx=(8, 0))

    def add_ebay_queue_section(self, parent, card):
        section = ctk.CTkFrame(
            parent,
            fg_color=CARD,
            border_width=1,
            border_color=BORDER,
            corner_radius=14,
        )
        section.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(
            section,
            text="eBay Queue",
            font=(FONT, 15, "bold"),
            text_color=TEXT,
        ).pack(anchor="w", padx=14, pady=(12, 8))

        queue_status = self.db.refresh_ebay_queue_status(
            set_id=self.selected_set,
            queue_filter=self.ebay_queue_filter,
        )
        progress = queue_status.get("progress", {})
        summary = queue_status.get("summary", {})
        queue_rows = queue_status.get("queue", [])
        finish_status = self.db.get_finish_ebay_status(self.selected_finish_id)

        body = ctk.CTkFrame(section, fg_color="transparent")
        body.pack(fill="x", padx=14, pady=(0, 8))

        status_rows = [
            ("Finish Status", finish_status.get("status") or "Not Queued"),
            ("Export Batch", finish_status.get("export_batch") or "Not assigned"),
            ("Queued At", finish_status.get("queued_at") or "Not queued"),
            ("Exported At", finish_status.get("exported_at") or "Not exported"),
        ]

        labels_by_key = {}
        for label_text, value in status_rows:
            row = ctk.CTkFrame(body, fg_color="transparent")
            row.pack(fill="x", pady=2)

            ctk.CTkLabel(
                row,
                text=f"{label_text}:",
                font=(FONT, 12, "bold"),
                text_color=SUBTEXT,
                width=130,
            ).pack(side="left")

            value_label = ctk.CTkLabel(
                row,
                text=str(value),
                font=(FONT, 12),
                text_color=TEXT,
                justify="left",
                wraplength=520,
            )
            value_label.pack(side="left", padx=(8, 0))
            labels_by_key[label_text] = value_label

        self.ebay_status_label = labels_by_key.get("Finish Status")

        self.ebay_reason_label = ctk.CTkLabel(
            section,
            text=finish_status.get("reason") or "",
            font=(FONT, 11),
            text_color=ERROR,
            wraplength=620,
            justify="left",
        )
        self.ebay_reason_label.pack(anchor="w", padx=14, pady=(0, 8))

        progress_text = (
            f"Queued: {summary.get('queued', 0)}   "
            f"Exported: {summary.get('exported', 0)}   "
            f"Failed: {summary.get('failed', 0)}   "
            f"Remaining: {progress.get('remaining', 0)}   "
            f"Current Export: {self._ebay_current_label(progress.get('current_export'))}"
        )
        self.ebay_progress_label = ctk.CTkLabel(
            section,
            text=progress_text,
            font=(FONT, 11, "bold"),
            text_color=SUBTEXT,
        )
        self.ebay_progress_label.pack(anchor="w", padx=14, pady=(0, 8))

        progress_bar = ctk.CTkProgressBar(section, width=620)
        total = max(1, int(progress.get("total", 0) or 0))
        completed = int(progress.get("completed", 0) or 0)
        progress_value = min(1.0, max(0.0, completed / total))
        progress_bar.set(progress_value)
        progress_bar.pack(anchor="w", padx=14, pady=(0, 8))
        self.ebay_queue_progress_bar = progress_bar

        metrics_row = ctk.CTkFrame(section, fg_color="transparent")
        metrics_row.pack(fill="x", padx=14, pady=(0, 8))

        metrics = [
            ("Completed", progress.get("completed", 0)),
            ("Remaining", progress.get("remaining", 0)),
            ("Failed", progress.get("failed", 0)),
            ("Elapsed Time", progress.get("elapsed_time", "00:00:00")),
        ]

        for key, value in metrics:
            block = ctk.CTkFrame(metrics_row, fg_color=SUBTEXT, corner_radius=10)
            block.pack(side="left", fill="x", expand=True, padx=(0, 8))
            ctk.CTkLabel(block, text=key, font=(FONT, 11), text_color=MUTED).pack(anchor="w", padx=10, pady=(8, 0))
            ctk.CTkLabel(block, text=str(value), font=(FONT, 16, "bold"), text_color=TEXT).pack(anchor="w", padx=10, pady=(0, 8))

        actions = ctk.CTkFrame(section, fg_color="transparent")
        actions.pack(fill="x", padx=14, pady=(0, 8))

        ctk.CTkButton(
            actions,
            text="Queue Selected Finish",
            width=170,
            command=self.queue_selected_finish_for_ebay,
        ).pack(side="left")

        ctk.CTkButton(
            actions,
            text="Queue Ready Finishes",
            width=170,
            command=self.queue_ready_finishes_for_ebay,
        ).pack(side="left", padx=(8, 0))

        ctk.CTkButton(
            actions,
            text="Export Queue",
            width=130,
            command=self.export_ebay_queue,
        ).pack(side="left", padx=(8, 0))

        ctk.CTkButton(
            actions,
            text="Retry Failed",
            width=120,
            command=self.retry_failed_ebay_exports,
        ).pack(side="left", padx=(8, 0))

        ctk.CTkButton(
            actions,
            text="Cancel Queue",
            width=120,
            command=self.cancel_ebay_queue,
        ).pack(side="left", padx=(8, 0))

        actions_two = ctk.CTkFrame(section, fg_color="transparent")
        actions_two.pack(fill="x", padx=14, pady=(0, 8))

        ctk.CTkButton(
            actions_two,
            text="Refresh Queue",
            width=130,
            command=self.refresh_ebay_queue,
        ).pack(side="left")

        ctk.CTkButton(
            actions_two,
            text="Clear Completed",
            width=130,
            command=self.clear_completed_ebay_queue,
        ).pack(side="left", padx=(8, 0))

        filter_row = ctk.CTkFrame(section, fg_color="transparent")
        filter_row.pack(fill="x", padx=14, pady=(0, 8))

        ctk.CTkLabel(
            filter_row,
            text="Queue Filters:",
            font=(FONT, 12, "bold"),
            text_color=SUBTEXT,
        ).pack(side="left", padx=(0, 8))

        self.ebay_filter_buttons = {}
        for option in ["All", "Queued", "Exported", "Failed", "Ready", "Not Ready"]:
            button = ctk.CTkButton(
                filter_row,
                text=option,
                width=96,
                height=28,
                corner_radius=8,
                border_width=1,
                command=lambda selected=option: self.select_ebay_queue_filter(selected),
            )
            button.pack(side="left", padx=(0, 8))
            self.ebay_filter_buttons[option] = button

        self._update_ebay_filter_highlight()

        table_section = ctk.CTkFrame(section, fg_color="transparent")
        table_section.pack(fill="both", expand=True, padx=14, pady=(0, 12))

        header_row = ctk.CTkFrame(table_section, fg_color=SUBTEXT, corner_radius=8)
        header_row.pack(fill="x", pady=(0, 4))

        columns = [
            ("Card", 140),
            ("Finish", 100),
            ("Quantity", 80),
            ("Price", 80),
            ("GitHub", 90),
            ("Status", 100),
            ("Export Batch", 120),
        ]

        for title, width in columns:
            ctk.CTkLabel(
                header_row,
                text=title,
                font=(FONT, 11, "bold"),
                text_color=TEXT,
                width=width,
                anchor="w",
            ).pack(side="left", padx=(8, 0), pady=6)

        table_body = ctk.CTkScrollableFrame(table_section, fg_color="transparent", height=180)
        table_body.pack(fill="both", expand=True)
        self.ebay_queue_table_frame = table_body

        for row in queue_rows:
            item = ctk.CTkFrame(table_body, fg_color="transparent")
            item.pack(fill="x", pady=2)

            values = [
                f"{row.get('card_number') or '?'} {row.get('card_name') or ''}".strip(),
                row.get("finish") or "",
                str(row.get("quantity") or 0),
                f"${float(row.get('price') or 0):.2f}",
                row.get("github_status") or "Pending",
                row.get("status") or "Not Queued",
                row.get("export_batch") or "",
            ]

            for idx, value in enumerate(values):
                width = columns[idx][1]
                ctk.CTkLabel(
                    item,
                    text=str(value),
                    font=(FONT, 11),
                    text_color=TEXT,
                    width=width,
                    anchor="w",
                    justify="left",
                    wraplength=width + 20,
                ).pack(side="left", padx=(8, 0), pady=3)

    def add_image_workspace_section(self, parent, image_info):
        section = ctk.CTkFrame(
            parent,
            fg_color=CARD,
            border_width=1,
            border_color=BORDER,
            corner_radius=14,
        )
        section.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(
            section,
            text="Image Workspace",
            font=(FONT, 15, "bold"),
            text_color=TEXT,
        ).pack(anchor="w", padx=14, pady=(12, 8))

        body = ctk.CTkFrame(section, fg_color="transparent")
        body.pack(fill="x", padx=14, pady=(0, 12))

        status_row = ctk.CTkFrame(body, fg_color="transparent")
        status_row.pack(fill="x", pady=(0, 8))

        image_status = image_info.get("status")
        status_text = image_info.get("status_badge", "🟡 Missing Image")
        status_bg = "#1C3A28" if image_status == "ready" else ("#3A2020" if image_status == "invalid" else "#3A3520")
        status_fg = SUCCESS if image_status == "ready" else (ERROR if image_status == "invalid" else WARNING)

        ctk.CTkLabel(
            status_row,
            text=status_text,
            font=(FONT, 11, "bold"),
            fg_color=status_bg,
            text_color=status_fg,
            corner_radius=8,
            padx=8,
            pady=4,
        ).pack(side="left")

        if image_info.get("path"):
            rows = [
                ("Filename", image_info.get("filename")),
                ("Resolution", image_info.get("resolution") or "Unknown"),
                ("Last Modified", image_info.get("last_modified") or "Unknown"),
                ("Image Format", image_info.get("format") or "Unknown"),
            ]

            for label, value in rows:
                row = ctk.CTkFrame(body, fg_color="transparent")
                row.pack(fill="x", pady=3)

                ctk.CTkLabel(
                    row,
                    text=f"{label}:",
                    font=(FONT, 12, "bold"),
                    text_color=SUBTEXT,
                    width=110,
                ).pack(side="left")

                ctk.CTkLabel(
                    row,
                    text=str(value),
                    font=(FONT, 12),
                    text_color=TEXT,
                    justify="left",
                    wraplength=360,
                ).pack(side="left", padx=(8, 0))

        actions = ctk.CTkFrame(body, fg_color="transparent")
        actions.pack(fill="x", pady=(10, 0))

        ctk.CTkButton(
            actions,
            text="Refresh",
            width=90,
            command=self.refresh_current_card_image,
        ).pack(side="left")

        ctk.CTkButton(
            actions,
            text="Open Folder",
            width=110,
            command=self.open_current_image_folder,
        ).pack(side="left", padx=(8, 0))

        reveal_button = ctk.CTkButton(
            actions,
            text="Reveal File",
            width=110,
            command=self.reveal_current_image,
            state="normal" if image_info.get("path") else "disabled",
        )
        reveal_button.pack(side="left", padx=(8, 0))
        self.reveal_image_button = reveal_button

        ctk.CTkButton(
            actions,
            text="Browse...",
            width=100,
            command=self.browse_current_image,
        ).pack(side="left", padx=(8, 0))

        ctk.CTkButton(
            actions,
            text="Remove Image",
            width=120,
            command=self.remove_current_image,
        ).pack(side="left", padx=(8, 0))

    def _card_identifier(self, card):
        return card.get("id") or card.get("card_id")

    def _sync_selected_finish_for_card(self, card, finishes=None):
        card_id = self._card_identifier(card)
        if not card_id:
            self.selected_finish_id = None
            return

        finishes = finishes if finishes is not None else self.db.get_finishes_for_card(card_id)
        if not finishes:
            self.selected_finish_id = None
            self.selected_finish_by_card.pop(card_id, None)
            return

        finish_ids = [finish.get("id") for finish in finishes]
        last_selected = self.selected_finish_by_card.get(card_id)

        if last_selected in finish_ids:
            self.selected_finish_id = last_selected
        else:
            self.selected_finish_id = finish_ids[0]

        self.selected_finish_by_card[card_id] = self.selected_finish_id

    def select_finish(self, finish_id):
        if not finish_id:
            return

        self.selected_finish_id = finish_id

        if self.selected_card is not None:
            card_id = self._card_identifier(self.selected_card)
            if card_id:
                self.selected_finish_by_card[card_id] = finish_id

        self._update_finish_chip_highlight()
        self._update_selected_finish_readiness_badge()

        # Phase 6.3: inventory fields depend on selected finish.
        if self.selected_card is not None:
            self.render_detail(self.selected_card)

    def _update_finish_chip_highlight(self):
        for finish_id, chip in self.finish_chip_buttons.items():
            if finish_id == self.selected_finish_id:
                chip.configure(
                    fg_color=ACCENT,
                    border_color=ACCENT,
                    text_color=TEXT,
                )
            else:
                chip.configure(
                    fg_color=SUBTEXT,
                    border_color=BORDER,
                    text_color=TEXT,
                )

    def _build_preview_image(self, image_path, max_width, max_height):
        if not image_path:
            return None

        try:
            image = Image.open(image_path)
            image = image.convert("RGBA")
            width, height = image.size
            if width <= 0 or height <= 0:
                return None

            scale = min(max_width / width, max_height / height)
            resized_size = (max(1, int(width * scale)), max(1, int(height * scale)))
            resized = image.resize(resized_size, Image.Resampling.LANCZOS)
            return ctk.CTkImage(light_image=resized, dark_image=resized, size=resized_size)
        except Exception:
            return None

    def refresh_current_card_image(self):
        if not self.selected_card:
            return

        self.db.refresh_finish_image(self.selected_set, self.selected_card, self.selected_finish_id)
        self.refresh_readiness_cache()
        self.render_detail(self.selected_card)
        self.refresh_list()

    def open_current_image_folder(self):
        self.db.open_image_folder(self.selected_set)

    def reveal_current_image(self):
        if not self.selected_card:
            return

        image_info = self.db.get_finish_image(self.selected_set, self.selected_card, self.selected_finish_id)
        if image_info.get("path"):
            self.db.reveal_image(image_info.get("path"))

    def browse_current_image(self):
        if not self.selected_card or not self.selected_finish_id:
            return

        selected = filedialog.askopenfilename(
            title="Select Local Image",
            filetypes=[
                ("Image Files", "*.png *.jpg *.jpeg *.webp"),
                ("All Files", "*.*"),
            ],
        )

        if not selected:
            return

        self.db.set_finish_image(self.selected_finish_id, selected)
        self.refresh_readiness_cache()
        self.render_detail(self.selected_card)
        self.refresh_list()

    def remove_current_image(self):
        if not self.selected_card or not self.selected_finish_id:
            return

        self.db.remove_finish_image(self.selected_finish_id)
        self.refresh_readiness_cache()
        self.render_detail(self.selected_card)
        self.refresh_list()

    def publish_selected_finish(self):
        if not self.selected_finish_id:
            return

        self.db.publish_finish_image(self.selected_finish_id)
        self.refresh_github_status()

    def publish_ready_finishes(self):
        if not self.selected_set:
            return

        self.db.publish_ready_finishes(self.selected_set)
        self.refresh_github_status()

    def retry_failed_uploads(self):
        queue_status = self.db.refresh_queue_status()
        queue = queue_status.get("queue", [])
        for upload in queue:
            if upload.get("status") == "Failed":
                self.db.retry_failed_upload(upload.get("upload_id"))

        self.db.process_upload_queue()
        self.refresh_github_status()

    def cancel_github_queue(self):
        self.db.cancel_queue()
        self.refresh_github_status()

    def refresh_github_status(self):
        if self.selected_card is not None:
            self.render_detail(self.selected_card)

    def queue_selected_finish_for_ebay(self):
        if not self.selected_finish_id:
            return

        self.db.queue_finish_for_ebay(self.selected_finish_id, listing_group=self.selected_set)
        self.refresh_ebay_queue()

    def queue_ready_finishes_for_ebay(self):
        if not self.selected_set:
            return

        self.db.queue_all_ready_finishes(self.selected_set)
        self.refresh_ebay_queue()

    def export_ebay_queue(self):
        self.db.export_queue_to_csv(set_id=self.selected_set)
        self.refresh_ebay_queue()

    def retry_failed_ebay_exports(self):
        self.db.retry_failed_exports(set_id=self.selected_set)
        self.refresh_ebay_queue()

    def cancel_ebay_queue(self):
        self.db.cancel_ebay_queue(set_id=self.selected_set)
        self.refresh_ebay_queue()

    def clear_completed_ebay_queue(self):
        self.db.clear_completed_queue(set_id=self.selected_set)
        self.refresh_ebay_queue()

    def refresh_ebay_queue(self):
        if self.selected_card is not None:
            self.render_detail(self.selected_card)

    def select_ebay_queue_filter(self, queue_filter):
        self.ebay_queue_filter = queue_filter
        self._update_ebay_filter_highlight()
        self.refresh_ebay_queue()

    def _update_ebay_filter_highlight(self):
        for option, button in self.ebay_filter_buttons.items():
            if option == self.ebay_queue_filter:
                button.configure(
                    fg_color=ACCENT,
                    border_color=ACCENT,
                    text_color=TEXT,
                )
            else:
                button.configure(
                    fg_color=SUBTEXT,
                    border_color=BORDER,
                    text_color=TEXT,
                )

    def _ebay_current_label(self, current_export):
        if not current_export:
            return "None"

        number = current_export.get("card_number") or "?"
        finish = current_export.get("finish") or "Finish"
        return f"{number} ({finish})"

    def _queue_current_label(self, current_upload):
        if not current_upload:
            return "None"

        number = current_upload.get("card_number") or "?"
        finish = current_upload.get("finish") or "Finish"
        return f"{number} ({finish})"

    def refresh_readiness_cache(self):
        if not self.selected_set:
            self.readiness_rows = []
            self.readiness_by_finish = {}
            self.readiness_by_card = {}
            self.readiness_summary = {
                "total_finishes": 0,
                "ready": 0,
                "missing_inventory": 0,
                "missing_pricing": 0,
                "missing_images": 0,
                "ready_for_publishing": 0,
            }
            self._update_readiness_dashboard()
            self._update_selected_finish_readiness_badge()
            return

        rows = self.db.get_set_readiness(self.selected_set)
        self.readiness_rows = rows
        self.readiness_by_finish = {row.get("finish_id"): row for row in rows}

        by_card = {}
        for row in rows:
            card_id = row.get("card_id")
            if not card_id:
                continue

            card_summary = by_card.setdefault(
                card_id,
                {
                    "total": 0,
                    "ready": 0,
                    "missing_inventory": 0,
                    "missing_pricing": 0,
                    "missing_images": 0,
                },
            )

            card_summary["total"] += 1
            if row.get("is_ready"):
                card_summary["ready"] += 1
            if row.get("missing_inventory"):
                card_summary["missing_inventory"] += 1
            if row.get("missing_pricing"):
                card_summary["missing_pricing"] += 1
            if row.get("missing_images"):
                card_summary["missing_images"] += 1

        self.readiness_by_card = by_card
        self.readiness_summary = self.db.calculate_readiness_summary(self.selected_set, readiness_rows=rows)
        self._update_readiness_dashboard()
        self._update_selected_finish_readiness_badge()

    def _update_readiness_dashboard(self):
        for key, label in self.readiness_value_labels.items():
            label.configure(text=str(self.readiness_summary.get(key, 0)))

    def select_readiness_filter(self, readiness_filter):
        self.readiness_filter = readiness_filter
        self._update_readiness_filter_highlight()
        self.refresh_list()

    def _update_readiness_filter_highlight(self):
        for option, button in self.readiness_buttons.items():
            if option == self.readiness_filter:
                button.configure(
                    fg_color=ACCENT,
                    border_color=ACCENT,
                    text_color=TEXT,
                )
            else:
                button.configure(
                    fg_color=SUBTEXT,
                    border_color=BORDER,
                    text_color=TEXT,
                )

    def _card_matches_readiness_filter(self, card):
        if self.readiness_filter == "All":
            return True

        card_id = self._card_identifier(card)
        if not card_id:
            return False

        card_summary = self.readiness_by_card.get(card_id)
        if not card_summary:
            return False

        if self.readiness_filter == "Ready":
            return int(card_summary.get("ready", 0) or 0) > 0
        if self.readiness_filter == "Missing Inventory":
            return int(card_summary.get("missing_inventory", 0) or 0) > 0
        if self.readiness_filter == "Missing Pricing":
            return int(card_summary.get("missing_pricing", 0) or 0) > 0
        if self.readiness_filter == "Missing Images":
            return int(card_summary.get("missing_images", 0) or 0) > 0

        return True

    def _update_selected_finish_readiness_badge(self):
        if self.selected_finish_readiness_label is not None:
            try:
                if not self.selected_finish_readiness_label.winfo_exists():
                    self.selected_finish_readiness_label = None
            except Exception:
                self.selected_finish_readiness_label = None

        if self.selected_finish_readiness_label is None:
            return

        readiness = self.readiness_by_finish.get(self.selected_finish_id)
        if readiness is None:
            self.selected_finish_readiness_label.configure(
                text="Readiness Unknown",
                fg_color=SUBTEXT,
                text_color=MUTED,
            )
            return

        code = readiness.get("readiness_code")
        text = readiness.get("readiness_label", "Readiness Unknown")
        if code == "ready":
            fg_color = "#1C3A28"
            text_color = SUCCESS
        elif code == "missing_inventory":
            fg_color = "#3A2020"
            text_color = ERROR
        elif code == "missing_pricing":
            fg_color = "#3A2A18"
            text_color = WARNING
        else:
            fg_color = "#3A3520"
            text_color = WARNING

        self.selected_finish_readiness_label.configure(
            text=text,
            fg_color=fg_color,
            text_color=text_color,
        )

    def _refresh_after_inventory_save(self):
        self.cards = self.db.get_card_workspace(self.selected_set)
        self.populate_rarity_filter()
        self.refresh_list()

    def show_empty_state(self):
        for child in self.card_list.winfo_children():
            child.destroy()

        # update header count
        try:
            self.list_header.configure(text="Cards (0)")
        except Exception:
            pass

        if self.selected_set:
            ctk.CTkLabel(
                self.card_list,
                text="Select a set to begin browsing cards.",
                font=(FONT, 14),
                text_color=MUTED,
                justify="left",
            ).pack(anchor="w", padx=6, pady=6)
        else:
            ctk.CTkLabel(
                self.card_list,
                text="No Set Selected",
                font=(FONT, 14, "bold"),
                text_color=TEXT,
                justify="left",
            ).pack(anchor="w", padx=6, pady=(6, 2))

            ctk.CTkLabel(
                self.card_list,
                text="Open a set from the Sets page to begin.",
                font=(FONT, 13),
                text_color=MUTED,
                justify="left",
            ).pack(anchor="w", padx=6, pady=(0, 6))

        for child in self.detail_container.winfo_children():
            child.destroy()

        if self.selected_set:
            ctk.CTkLabel(
                self.detail_container,
                text="No card selected",
                font=(FONT, 18, "bold"),
                text_color=TEXT,
            ).pack(anchor="w", padx=18, pady=18)
        else:
            empty = ctk.CTkFrame(self.detail_container, fg_color="transparent")
            empty.pack(fill="both", expand=True, padx=18, pady=18)

            ctk.CTkLabel(
                empty,
                text="No Set Selected",
                font=(FONT, 22, "bold"),
                text_color=TEXT,
            ).pack(anchor="w", pady=(0, 6))

            ctk.CTkLabel(
                empty,
                text="Open a set from the Sets page to begin.",
                font=(FONT, 14),
                text_color=MUTED,
            ).pack(anchor="w", pady=(0, 12))

            ctk.CTkButton(
                empty,
                text="Open Sets",
                width=120,
                command=self._open_sets_page,
            ).pack(anchor="w")

    def _open_sets_page(self):
        if self.page_manager and hasattr(self.page_manager, "show_set_manager"):
            self.page_manager.show_set_manager()

    def destroy(self):
        if getattr(self, "db", None) is not None:
            self.db.close()
        super().destroy()
