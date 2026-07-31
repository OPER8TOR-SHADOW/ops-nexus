import uuid
import threading
import json
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET
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
        self._detail_preview_image = None

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

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
            text="Seller Hub style listing workspace. Data is loaded from local cache and synchronized by Marketplace Sync.",
            font=(FONT, 14),
            text_color=MUTED,
        )
        subtitle.grid(row=1, column=0, sticky="w", padx=20, pady=(0, 12))

        actions = ctk.CTkFrame(self, fg_color=CARD, border_width=1, border_color=BORDER, corner_radius=14)
        actions.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 10))
        actions.grid_columnconfigure(0, weight=1)
        actions.grid_columnconfigure(1, weight=1)
        actions.grid_columnconfigure(2, weight=1)
        actions.grid_columnconfigure(3, weight=0)
        actions.grid_columnconfigure(4, weight=0)
        actions.grid_columnconfigure(5, weight=0)
        actions.grid_columnconfigure(6, weight=0)
        actions.grid_columnconfigure(7, weight=0)
        actions.grid_columnconfigure(8, weight=0)

        self.search_var = ctk.StringVar(value="")
        self.search_entry = ctk.CTkEntry(
            actions,
            textvariable=self.search_var,
            placeholder_text="Search title, item ID, SKU, status, format",
        )
        self.search_entry.grid(row=0, column=0, sticky="ew", padx=(14, 8), pady=12)
        self.search_entry.bind("<Return>", lambda _event: self.apply_filters())
        self.search_var.trace_add("write", lambda *_args: self.apply_filters())

        self.status_filter_var = ctk.StringVar(value="All")
        self.status_filter = ctk.CTkOptionMenu(
            actions,
            values=["All", "Active", "Completed", "Ended", "Unknown"],
            variable=self.status_filter_var,
            width=150,
            command=lambda _value: self.apply_filters(),
        )
        self.status_filter.grid(row=0, column=1, sticky="ew", padx=(0, 8), pady=12)

        self.sort_options = [
            "Last Synced (Newest)",
            "Last Synced (Oldest)",
            "Title (A-Z)",
            "Price (High-Low)",
            "Price (Low-High)",
            "Quantity (High-Low)",
            "Sync Status",
        ]
        self.sort_var = ctk.StringVar(value=self.sort_options[0])
        self.sort_selector = ctk.CTkOptionMenu(
            actions,
            values=self.sort_options,
            variable=self.sort_var,
            width=180,
            command=lambda _value: self.apply_filters(),
        )
        self.sort_selector.grid(row=0, column=2, sticky="ew", padx=(0, 8), pady=12)

        ctk.CTkButton(actions, text="Refresh", width=110, command=self.sync_marketplace).grid(
            row=0,
            column=3,
            padx=(0, 12),
            pady=12,
        )

        ctk.CTkLabel(actions, text="Last Sync:", font=(FONT, 11, "bold"), text_color=SUBTEXT).grid(
            row=0,
            column=4,
            padx=(0, 6),
            pady=12,
            sticky="e",
        )
        self.last_sync_var = ctk.StringVar(value="—")
        ctk.CTkLabel(actions, textvariable=self.last_sync_var, font=(FONT, 11), text_color=TEXT).grid(
            row=0,
            column=5,
            padx=(0, 12),
            pady=12,
            sticky="w",
        )

        ctk.CTkLabel(actions, text="Count:", font=(FONT, 11, "bold"), text_color=SUBTEXT).grid(
            row=0,
            column=6,
            padx=(0, 6),
            pady=12,
            sticky="e",
        )
        self.count_var = ctk.StringVar(value="0")
        ctk.CTkLabel(actions, textvariable=self.count_var, font=(FONT, 11), text_color=TEXT).grid(
            row=0,
            column=7,
            padx=(0, 14),
            pady=12,
            sticky="w",
        )

        self.status_message = ctk.CTkLabel(actions, text="", font=(FONT, 12), text_color=MUTED)
        self.status_message.grid(row=1, column=0, columnspan=9, sticky="w", padx=14, pady=(0, 10))

        content = ctk.CTkFrame(self, fg_color="transparent")
        content.grid(row=3, column=0, sticky="nsew", padx=20, pady=(0, 20))
        content.grid_columnconfigure(0, weight=3)
        content.grid_columnconfigure(1, weight=2)
        content.grid_rowconfigure(0, weight=1)

        self._build_listing_table(content)
        self._build_detail_panel(content)

    def _build_listing_table(self, parent):
        section = ctk.CTkFrame(parent, fg_color=CARD, border_width=1, border_color=BORDER, corner_radius=14)
        section.grid(row=0, column=0, sticky="nsew", padx=(0, 10), pady=0)
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
            columns=(
                "Title",
                "Item ID",
                "SKU",
                "Price",
                "Quantity",
                "Status",
                "Format",
                "Duration",
                "Sync",
                "Last Synced",
            ),
            show="tree headings",
            style="Marketplace.Treeview",
            selectmode="browse",
        )
        self.table.grid(row=0, column=0, sticky="nsew")
        self.table.heading("#0", text="Thumbnail")
        self.table.heading("Title", text="Title")
        self.table.heading("Item ID", text="Item ID")
        self.table.heading("SKU", text="SKU")
        self.table.heading("Price", text="Price")
        self.table.heading("Quantity", text="Quantity")
        self.table.heading("Status", text="Status")
        self.table.heading("Format", text="Format")
        self.table.heading("Duration", text="Duration")
        self.table.heading("Sync", text="Sync Status")
        self.table.heading("Last Synced", text="Last Synced")
        self.table.column("#0", width=92, minwidth=92, stretch=False, anchor="center")
        self.table.column("Title", width=330, minwidth=220, stretch=True, anchor="w")
        self.table.column("Item ID", width=130, minwidth=120, stretch=False, anchor="w")
        self.table.column("SKU", width=130, minwidth=110, stretch=False, anchor="w")
        self.table.column("Price", width=100, minwidth=90, stretch=False, anchor="e")
        self.table.column("Quantity", width=90, minwidth=80, stretch=False, anchor="center")
        self.table.column("Status", width=110, minwidth=95, stretch=False, anchor="center")
        self.table.column("Format", width=115, minwidth=100, stretch=False, anchor="center")
        self.table.column("Duration", width=90, minwidth=80, stretch=False, anchor="center")
        self.table.column("Sync", width=105, minwidth=95, stretch=False, anchor="center")
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

    def _build_detail_panel(self, parent):
        section = ctk.CTkFrame(parent, fg_color=CARD, border_width=1, border_color=BORDER, corner_radius=14)
        section.grid(row=0, column=1, sticky="nsew", padx=(10, 0), pady=0)
        section.grid_columnconfigure(0, weight=1)
        section.grid_rowconfigure(3, weight=1)

        ctk.CTkLabel(section, text="Listing Details", font=(FONT, 18, "bold"), text_color=TEXT).grid(
            row=0,
            column=0,
            sticky="w",
            padx=14,
            pady=(12, 8),
        )

        self.detail_image = ctk.CTkLabel(section, text="No Image", text_color=MUTED, width=220, height=170)
        self.detail_image.grid(row=1, column=0, sticky="n", padx=14, pady=(0, 10))

        details_frame = ctk.CTkFrame(section, fg_color="transparent")
        details_frame.grid(row=2, column=0, sticky="ew", padx=14)
        details_frame.grid_columnconfigure(1, weight=1)

        fields = [
            ("Title", "title"),
            ("Price", "price"),
            ("Quantity", "quantity"),
            ("SKU", "sku"),
            ("Item ID", "item_id"),
            ("Status", "status"),
            ("Last Sync", "last_sync"),
            ("Format", "format"),
            ("Duration", "duration"),
            ("Sync Status", "sync_status"),
            ("Thumbnail Path", "thumbnail_path"),
        ]

        self.detail_values = {}
        for row_index, (label_text, key) in enumerate(fields):
            ctk.CTkLabel(details_frame, text=label_text, font=(FONT, 11, "bold"), text_color=SUBTEXT).grid(
                row=row_index,
                column=0,
                sticky="nw",
                padx=(0, 8),
                pady=2,
            )
            value_var = ctk.StringVar(value="—")
            self.detail_values[key] = value_var
            ctk.CTkLabel(
                details_frame,
                textvariable=value_var,
                font=(FONT, 11),
                text_color=TEXT,
                justify="left",
                wraplength=360,
            ).grid(row=row_index, column=1, sticky="w", pady=2)

        ctk.CTkLabel(section, text="Metadata", font=(FONT, 13, "bold"), text_color=TEXT).grid(
            row=3,
            column=0,
            sticky="sw",
            padx=14,
            pady=(8, 4),
        )

        self.metadata_box = ctk.CTkTextbox(section, height=170, fg_color="#171717", border_width=1, border_color=BORDER)
        self.metadata_box.grid(row=4, column=0, sticky="nsew", padx=14, pady=(0, 12))
        self.metadata_box.insert("1.0", "Select a listing to inspect metadata from local cache.")
        self.metadata_box.configure(state="disabled")

    def refresh_listings(self):
        rows = self.repository.list_listings()
        self.listings = [self._enrich_listing(dict(row)) for row in rows]
        self.status_message.configure(text=f"Loaded {len(self.listings)} listing(s) from SQLite.", text_color=SUCCESS)
        self._update_toolbar_summary()
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
        status_filter = self.status_filter_var.get().strip()

        rows = []
        for item in self.listings:
            if status_filter != "All" and str(item.get("status") or "Unknown") != status_filter:
                continue

            if search:
                blob = str(item.get("search_blob") or "")
                if search not in blob:
                    continue

            rows.append(item)

        rows = self._sort_rows(rows)
        self.filtered = rows
        self._render_table()
        self.count_label.configure(text=f"{len(self.filtered)} listing(s)")
        self.count_var.set(str(len(self.filtered)))

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
                str(item.get("item_id") or item.get("listing_id") or ""),
                str(item.get("sku") or ""),
                f"${float(item.get('price') or 0):.2f}",
                str(int(item.get("quantity") or 0)),
                str(item.get("status") or ""),
                str(item.get("listing_format") or "—"),
                str(item.get("listing_duration") or "—"),
                str(item.get("sync_status") or "Unknown"),
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

    def _load_detail_preview(self, thumbnail_path):
        if not thumbnail_path:
            self._detail_preview_image = None
            self.detail_image.configure(image=None, text="No Image")
            return

        cache_key = f"detail:{thumbnail_path}"
        image = self._thumbnail_cache.get(cache_key)
        if image is None:
            try:
                from tkinter import PhotoImage

                raw_image = PhotoImage(file=str(thumbnail_path))
                scale = max(1, int(max(raw_image.width(), raw_image.height()) / 180))
                image = raw_image.subsample(scale, scale) if scale > 1 else raw_image
                self._thumbnail_cache[cache_key] = image
            except Exception:
                image = None

        self._detail_preview_image = image
        if image is None:
            self.detail_image.configure(image=None, text="No Image")
        else:
            self.detail_image.configure(image=image, text="")

    def _on_row_selected(self, _event=None):
        selection = self.table.selection()
        if not selection:
            self.selected_listing = None
            self._reset_detail_panel()
            return

        listing = self._row_lookup.get(selection[0])
        if listing is None:
            return

        self.selected_listing = listing
        self._update_detail_panel(listing)
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

    def _update_detail_panel(self, listing):
        self._load_detail_preview(listing.get("thumbnail_path"))

        values = {
            "title": str(listing.get("title") or "—"),
            "price": f"${float(listing.get('price') or 0):.2f}",
            "quantity": str(int(listing.get("quantity") or 0)),
            "sku": str(listing.get("sku") or "—"),
            "item_id": str(listing.get("item_id") or listing.get("listing_id") or "—"),
            "status": str(listing.get("status") or "—"),
            "last_sync": str(listing.get("last_synced") or listing.get("updated_at") or "—"),
            "format": str(listing.get("listing_format") or "—"),
            "duration": str(listing.get("listing_duration") or "—"),
            "sync_status": str(listing.get("sync_status") or "Unknown"),
            "thumbnail_path": str(listing.get("thumbnail_path") or "—"),
        }

        for key, value_var in self.detail_values.items():
            value_var.set(values.get(key, "—"))

        metadata = {
            "id": listing.get("id"),
            "listing_id": listing.get("listing_id"),
            "item_id": listing.get("item_id"),
            "marketplace": listing.get("marketplace"),
            "url": listing.get("url"),
            "image_url": listing.get("image_url"),
            "created_at": listing.get("created_at"),
            "updated_at": listing.get("updated_at"),
            "payload_source": listing.get("payload_source"),
            "seller_username": listing.get("seller_username"),
        }
        metadata_text = json.dumps(metadata, indent=2, ensure_ascii=True, default=str)
        self.metadata_box.configure(state="normal")
        self.metadata_box.delete("1.0", "end")
        self.metadata_box.insert("1.0", metadata_text)
        self.metadata_box.configure(state="disabled")

    def _reset_detail_panel(self):
        self._detail_preview_image = None
        self.detail_image.configure(image=None, text="No Image")
        for value_var in self.detail_values.values():
            value_var.set("—")
        self.metadata_box.configure(state="normal")
        self.metadata_box.delete("1.0", "end")
        self.metadata_box.insert("1.0", "Select a listing to inspect metadata from local cache.")
        self.metadata_box.configure(state="disabled")

    def _enrich_listing(self, listing):
        payload_data = self._decode_payload(listing.get("payload"))
        listing_payload = payload_data.get("payload") if isinstance(payload_data.get("payload"), dict) else {}
        item_xml = listing_payload.get("item_xml") or ""

        listing_format = self._extract_xml_text(item_xml, "ListingType")
        listing_duration = self._extract_xml_text(item_xml, "ListingDuration")
        seller = listing_payload.get("seller") if isinstance(listing_payload.get("seller"), dict) else {}
        payload_source = listing_payload.get("source") or payload_data.get("source")
        sync_status = self._compute_sync_status(listing.get("last_synced"))

        listing["listing_format"] = listing_format or "—"
        listing["listing_duration"] = listing_duration or "—"
        listing["sync_status"] = sync_status
        listing["payload_source"] = str(payload_source or "—")
        listing["seller_username"] = str(seller.get("username") or seller.get("user_id") or "—")

        search_fields = [
            listing.get("title"),
            listing.get("item_id"),
            listing.get("listing_id"),
            listing.get("sku"),
            listing.get("status"),
            listing.get("listing_format"),
            listing.get("listing_duration"),
            listing.get("sync_status"),
        ]
        listing["search_blob"] = " ".join(str(part or "") for part in search_fields).lower()
        return listing

    def _decode_payload(self, payload_text):
        if payload_text is None:
            return {}
        if isinstance(payload_text, dict):
            return payload_text
        try:
            return json.loads(str(payload_text))
        except Exception:
            return {}

    def _extract_xml_text(self, xml_text, field_name):
        if not xml_text:
            return ""
        try:
            root = ET.fromstring(xml_text)
        except Exception:
            return ""

        for child in root.iter():
            tag = str(child.tag)
            local_name = tag.rsplit("}", 1)[-1] if "}" in tag else tag
            if local_name == field_name:
                return str(child.text or "").strip()
        return ""

    def _compute_sync_status(self, last_synced):
        sync_dt = self._parse_datetime(last_synced)
        if sync_dt is None:
            return "Unknown"

        now_utc = datetime.utcnow()
        age = now_utc - sync_dt
        if age <= timedelta(minutes=20):
            return "Fresh"
        if age <= timedelta(hours=2):
            return "Aging"
        return "Stale"

    def _parse_datetime(self, value):
        if not value:
            return None

        text = str(value).strip()
        if not text:
            return None

        candidates = [text]
        if text.endswith("Z"):
            candidates.append(text.replace("Z", "+00:00"))

        for candidate in candidates:
            try:
                parsed = datetime.fromisoformat(candidate)
                if parsed.tzinfo is not None:
                    parsed = parsed.astimezone().replace(tzinfo=None)
                return parsed
            except Exception:
                continue

        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
            try:
                return datetime.strptime(text, fmt)
            except Exception:
                continue

        return None

    def _sort_rows(self, rows):
        selected_sort = self.sort_var.get().strip()

        if selected_sort == "Last Synced (Oldest)":
            return sorted(rows, key=lambda item: self._parse_datetime(item.get("last_synced")) or datetime.min)

        if selected_sort == "Title (A-Z)":
            return sorted(rows, key=lambda item: str(item.get("title") or "").lower())

        if selected_sort == "Price (High-Low)":
            return sorted(rows, key=lambda item: float(item.get("price") or 0), reverse=True)

        if selected_sort == "Price (Low-High)":
            return sorted(rows, key=lambda item: float(item.get("price") or 0))

        if selected_sort == "Quantity (High-Low)":
            return sorted(rows, key=lambda item: int(item.get("quantity") or 0), reverse=True)

        if selected_sort == "Sync Status":
            priority = {"Fresh": 0, "Aging": 1, "Stale": 2, "Unknown": 3}
            return sorted(
                rows,
                key=lambda item: (
                    priority.get(str(item.get("sync_status") or "Unknown"), 3),
                    -(float(item.get("price") or 0)),
                ),
            )

        return sorted(
            rows,
            key=lambda item: self._parse_datetime(item.get("last_synced")) or datetime.min,
            reverse=True,
        )

    def _update_toolbar_summary(self):
        latest_sync = None
        for listing in self.listings:
            current = self._parse_datetime(listing.get("last_synced"))
            if current is None:
                continue
            if latest_sync is None or current > latest_sync:
                latest_sync = current

        self.last_sync_var.set(latest_sync.strftime("%Y-%m-%d %H:%M:%S") if latest_sync else "—")
        self.count_var.set(str(len(self.listings)))

    # -------------------------
    # Lifecycle
    # -------------------------

    def destroy(self):
        self.repository.close()
        super().destroy()
