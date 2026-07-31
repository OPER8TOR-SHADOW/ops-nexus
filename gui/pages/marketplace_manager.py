import uuid
import threading
from tkinter import ttk

import customtkinter as ctk

from gui.theme import *
from database.repository import DatabaseRepository


class MarketplaceManagerPage(ctk.CTkFrame):

    def __init__(self, master, page_manager=None):
        super().__init__(master, fg_color="transparent")

        self.page_manager = page_manager
        self.repository = DatabaseRepository()

        self.listings = []
        self.filtered = []
        self.selected_listing = None
        self._thumbnail_cache = {}
        self._row_lookup = {}

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self._build_ui()
        self.refresh_listings()

    def _build_ui(self):
        title = ctk.CTkLabel(
            self,
            text="Marketplace Manager",
            font=(FONT, 30, "bold"),
            text_color=TEXT,
        )
        title.grid(row=0, column=0, sticky="w", padx=20, pady=(18, 8))

        subtitle = ctk.CTkLabel(
            self,
            text="Live eBay listings dashboard. SQLite is a cache only and refresh will synchronize when sync exists.",
            font=(FONT, 14),
            text_color=MUTED,
        )
        subtitle.grid(row=1, column=0, sticky="w", padx=20, pady=(0, 12))

        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 10))

        self.search_var = ctk.StringVar(value="")
        self.search_entry = ctk.CTkEntry(
            actions,
            textvariable=self.search_var,
            placeholder_text="Search title, SKU, or status",
            width=320,
        )
        self.search_entry.pack(side="left")
        self.search_entry.bind("<Return>", lambda _event: self.apply_filters())
        self.search_var.trace_add("write", lambda *_args: self.apply_filters())

        ctk.CTkButton(actions, text="Refresh", width=110, command=self.sync_marketplace).pack(side="left", padx=(8, 0))

        self.status_message = ctk.CTkLabel(actions, text="", font=(FONT, 12), text_color=MUTED)
        self.status_message.pack(side="right")

        self._build_listing_table(self)

    def _build_listing_table(self, parent):
        section = ctk.CTkFrame(parent, fg_color=CARD, border_width=1, border_color=BORDER, corner_radius=14)
        section.grid(row=3, column=0, sticky="nsew", padx=20, pady=(0, 20))
        section.grid_columnconfigure(0, weight=1)
        section.grid_rowconfigure(2, weight=1)

        summary_row = ctk.CTkFrame(section, fg_color="transparent")
        summary_row.grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 4))
        summary_row.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(summary_row, text="Listings", font=(FONT, 18, "bold"), text_color=TEXT).grid(row=0, column=0, sticky="w")
        self.count_label = ctk.CTkLabel(summary_row, text="0 listing(s)", font=(FONT, 12), text_color=MUTED)
        self.count_label.grid(row=0, column=1, sticky="e")

        table_frame = ctk.CTkFrame(section, fg_color="transparent")
        table_frame.grid(row=2, column=0, sticky="nsew", padx=14, pady=(0, 12))
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Marketplace.Treeview",
            background="#171717",
            fieldbackground="#171717",
            foreground=TEXT,
            rowheight=60,
            borderwidth=0,
            font=(FONT, 10),
        )
        style.configure(
            "Marketplace.Treeview.Heading",
            background="#232323",
            foreground=TEXT,
            font=(FONT, 10, "bold"),
            relief="flat",
        )
        style.map("Marketplace.Treeview", background=[("selected", "#343434")])

        self.table = ttk.Treeview(
            table_frame,
            columns=("Title", "SKU", "Price", "Quantity", "Status", "Last Synced"),
            show="tree headings",
            style="Marketplace.Treeview",
            selectmode="browse",
        )
        self.table.grid(row=0, column=0, sticky="nsew")
        self.table.heading("#0", text="Thumbnail")
        self.table.heading("Title", text="Title")
        self.table.heading("SKU", text="SKU")
        self.table.heading("Price", text="Price")
        self.table.heading("Quantity", text="Quantity")
        self.table.heading("Status", text="Status")
        self.table.heading("Last Synced", text="Last Synced")
        self.table.column("#0", width=92, minwidth=92, stretch=False, anchor="center")
        self.table.column("Title", width=420, minwidth=240, stretch=True, anchor="w")
        self.table.column("SKU", width=160, minwidth=120, stretch=False, anchor="w")
        self.table.column("Price", width=100, minwidth=90, stretch=False, anchor="e")
        self.table.column("Quantity", width=90, minwidth=80, stretch=False, anchor="center")
        self.table.column("Status", width=120, minwidth=100, stretch=False, anchor="center")
        self.table.column("Last Synced", width=170, minwidth=150, stretch=False, anchor="w")
        self.table.bind("<Double-1>", self._on_row_double_click)
        self.table.bind("<<TreeviewSelect>>", self._on_row_selected)

        scrollbar = ctk.CTkScrollbar(table_frame, orientation="vertical", command=self.table.yview)
        scrollbar.grid(row=0, column=1, sticky="ns", padx=(8, 0))
        self.table.configure(yscrollcommand=scrollbar.set)

        self.detail_label = ctk.CTkLabel(
            section,
            text="No marketplace listings available. Click Refresh to synchronize from eBay.",
            font=(FONT, 12),
            text_color=MUTED,
            wraplength=1100,
            justify="left",
        )
        self.detail_label.grid(row=4, column=0, sticky="w", padx=14, pady=(0, 12))

    def refresh_listings(self):
        rows = self.repository.list_listings()
        self.listings = [dict(row) for row in rows]
        self.status_message.configure(text=f"Loaded {len(self.listings)} listing(s) from SQLite.", text_color=SUCCESS)
        self.apply_filters()

    def sync_marketplace(self):
        service = getattr(self.page_manager, "marketplace_sync_service", None)
        if service is None:
            self.refresh_listings()
            return

        self.status_message.configure(text="Syncing marketplace listings...", text_color=MUTED)

        def worker():
            try:
                result = service.sync_marketplace_cache(force_refresh=True)
                error = None
            except Exception as exc:
                result = None
                error = exc

            self.after(0, lambda: self._finish_sync(result, error))

        threading.Thread(target=worker, daemon=True).start()

    def _finish_sync(self, result, error):
        if error is not None:
            self.status_message.configure(text=str(error), text_color=ERROR)
            return

        self.refresh_listings()
        if result and result.get("written") is not None:
            self.status_message.configure(
                text=f"Synced {result.get('written')} listing(s) from eBay.",
                text_color=SUCCESS,
            )

    def apply_filters(self):
        search = self.search_var.get().strip().lower()

        rows = []
        for item in self.listings:
            if search:
                blob = " ".join(
                    [
                        str(item.get("title") or ""),
                        str(item.get("sku") or ""),
                        str(item.get("status") or ""),
                        str(item.get("listing_id") or ""),
                    ]
                ).lower()
                if search not in blob:
                    continue

            rows.append(item)

        self.filtered = rows
        self._render_table()
        self.count_label.configure(text=f"{len(self.filtered)} listing(s)")

    def _render_table(self):
        for item in self.table.get_children():
            self.table.delete(item)

        self._row_lookup.clear()
        self._thumbnail_cache.clear()

        if not self.filtered:
            self.detail_label.configure(text="No marketplace listings available. Click Refresh to synchronize from eBay.")
            return

        for item in self.filtered:
            listing_id = str(item.get("id") or item.get("listing_id") or uuid.uuid4())
            self._row_lookup[listing_id] = item

            thumbnail = self._load_thumbnail(item.get("thumbnail_path"))
            values = (
                str(item.get("title") or ""),
                str(item.get("sku") or ""),
                f"${float(item.get('price') or 0):.2f}",
                str(int(item.get("quantity") or 0)),
                str(item.get("status") or ""),
                str(item.get("last_synced") or item.get("updated_at") or ""),
            )

            self.table.insert(
                "",
                "end",
                iid=listing_id,
                image=thumbnail,
                values=values,
            )

        self.detail_label.configure(text="Double-click a row to select a listing.")

    # -------------------------
    # Selection and thumbnails
    # -------------------------

    def _load_thumbnail(self, thumbnail_path):
        if not thumbnail_path:
            return None

        cache_key = str(thumbnail_path)
        if cache_key in self._thumbnail_cache:
            return self._thumbnail_cache[cache_key]

        try:
            from tkinter import PhotoImage

            image = PhotoImage(file=cache_key)
            scale = max(1, int(max(image.width(), image.height()) / 48))
            if scale > 1:
                image = image.subsample(scale, scale)
        except Exception:
            return None

        self._thumbnail_cache[cache_key] = image
        return image

    def _on_row_selected(self, _event=None):
        selection = self.table.selection()
        if not selection:
            self.selected_listing = None
            return

        listing = self._row_lookup.get(selection[0])
        if listing is None:
            return

        self.selected_listing = listing
        self.detail_label.configure(
            text=f"Selected: {listing.get('title') or 'Listing'} | SKU {listing.get('sku') or '—'} | {listing.get('status') or '—'}"
        )

    def _on_row_double_click(self, event):
        row_id = self.table.identify_row(event.y)
        if not row_id:
            return

        self.table.selection_set(row_id)
        self.table.focus(row_id)
        self._on_row_selected()

    # -------------------------
    # Lifecycle
    # -------------------------

    def destroy(self):
        self.repository.close()
        super().destroy()
