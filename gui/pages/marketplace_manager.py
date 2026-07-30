import threading

import customtkinter as ctk

from gui.theme import *
from gui.services.ebay_api_service import EbayApiError, EbayApiService


class MarketplaceManagerPage(ctk.CTkFrame):

    def __init__(self, master, page_manager=None):
        super().__init__(master, fg_color="transparent")

        self.page_manager = page_manager
        self.service = EbayApiService()

        self.listings = []
        self.filtered = []

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        self._build_ui()
        self.refresh_status()

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
            text="Secure eBay OAuth connection and read-only active listings.",
            font=(FONT, 14),
            text_color=MUTED,
        )
        subtitle.grid(row=1, column=0, sticky="w", padx=20, pady=(0, 12))

        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 10))

        ctk.CTkButton(actions, text="Sign In", width=100, command=self.sign_in).pack(side="left")
        ctk.CTkButton(actions, text="Sign Out", width=100, command=self.sign_out).pack(side="left", padx=(8, 0))
        ctk.CTkButton(actions, text="Test Connection", width=130, command=self.test_connection).pack(side="left", padx=(8, 0))
        ctk.CTkButton(actions, text="Refresh Listings", width=130, command=self.refresh_listings).pack(side="left", padx=(8, 0))

        self.status_message = ctk.CTkLabel(actions, text="", font=(FONT, 12), text_color=MUTED)
        self.status_message.pack(side="right")

        body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        body.grid(row=3, column=0, sticky="nsew", padx=20, pady=(0, 20))
        body.grid_columnconfigure(0, weight=1)

        self._build_connection_section(body)
        self._build_filters(body)
        self._build_listing_table(body)

    def _build_connection_section(self, parent):
        section = ctk.CTkFrame(parent, fg_color=CARD, border_width=1, border_color=BORDER, corner_radius=14)
        section.pack(fill="x", pady=(0, 12))

        ctk.CTkLabel(section, text="Connection Status", font=(FONT, 18, "bold"), text_color=TEXT).pack(anchor="w", padx=14, pady=(12, 8))

        self.status_labels = {}
        fields = [
            ("connection_status", "Connected / Disconnected"),
            ("seller_username", "Seller Username"),
            ("store_name", "Store Name"),
            ("marketplace_region", "Marketplace Region"),
            ("last_successful_connection", "Last Successful Connection"),
            ("api_status", "API Status"),
            ("oauth_status", "OAuth Status"),
            ("environment", "Current Environment"),
            ("latency_ms", "Last Test Latency"),
        ]

        for key, label in fields:
            row = ctk.CTkFrame(section, fg_color="transparent")
            row.pack(fill="x", padx=14, pady=3)

            ctk.CTkLabel(row, text=f"{label}:", font=(FONT, 12, "bold"), text_color=SUBTEXT, width=220, anchor="w").pack(side="left")
            value_label = ctk.CTkLabel(row, text="—", font=(FONT, 12), text_color=TEXT, anchor="w")
            value_label.pack(side="left")
            self.status_labels[key] = value_label

        self.connection_error = ctk.CTkLabel(section, text="", font=(FONT, 11), text_color=ERROR, wraplength=900, justify="left")
        self.connection_error.pack(anchor="w", padx=14, pady=(6, 12))

    def _build_filters(self, parent):
        section = ctk.CTkFrame(parent, fg_color=CARD, border_width=1, border_color=BORDER, corner_radius=14)
        section.pack(fill="x", pady=(0, 12))

        ctk.CTkLabel(section, text="Active Listings", font=(FONT, 18, "bold"), text_color=TEXT).pack(anchor="w", padx=14, pady=(12, 8))

        row = ctk.CTkFrame(section, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=(0, 12))

        self.search_var = ctk.StringVar(value="")
        self.search_entry = ctk.CTkEntry(row, textvariable=self.search_var, placeholder_text="Search title, item ID, or SKU", width=300)
        self.search_entry.pack(side="left", padx=(0, 8))
        self.search_entry.bind("<Return>", lambda _event: self.apply_filters())

        self.status_filter_var = ctk.StringVar(value="All")
        self.status_filter_menu = ctk.CTkOptionMenu(row, values=["All"], variable=self.status_filter_var, width=140, command=lambda *_: self.apply_filters())
        self.status_filter_menu.pack(side="left", padx=(0, 8))

        self.sort_var = ctk.StringVar(value="Last Updated")
        self.sort_menu = ctk.CTkOptionMenu(
            row,
            values=["Last Updated", "Start Date", "Price", "Quantity", "Title", "Item ID"],
            variable=self.sort_var,
            width=140,
            command=lambda *_: self.apply_filters(),
        )
        self.sort_menu.pack(side="left", padx=(0, 8))

        ctk.CTkButton(row, text="Search", width=90, command=self.apply_filters).pack(side="left")

        self.count_label = ctk.CTkLabel(row, text="0 listing(s)", font=(FONT, 11), text_color=MUTED)
        self.count_label.pack(side="right")

    def _build_listing_table(self, parent):
        section = ctk.CTkFrame(parent, fg_color=CARD, border_width=1, border_color=BORDER, corner_radius=14)
        section.pack(fill="both", expand=True, pady=(0, 12))

        header = ctk.CTkFrame(section, fg_color=SUBTEXT, corner_radius=8)
        header.pack(fill="x", padx=14, pady=(12, 4))

        self.columns = [
            ("Title", 240),
            ("Item ID", 110),
            ("SKU", 130),
            ("Price", 90),
            ("Quantity", 80),
            ("Status", 90),
            ("Listing Type", 95),
            ("Start Date", 140),
            ("Last Updated", 140),
        ]

        for title, width in self.columns:
            ctk.CTkLabel(header, text=title, font=(FONT, 11, "bold"), text_color=TEXT, width=width, anchor="w").pack(side="left", padx=(8, 0), pady=6)

        self.table = ctk.CTkScrollableFrame(section, fg_color="transparent", height=360)
        self.table.pack(fill="both", expand=True, padx=14, pady=(0, 12))

    # -------------------------
    # Background helpers
    # -------------------------

    def _run_async(self, func, on_done, busy_text):
        self.status_message.configure(text=busy_text, text_color=WARNING)

        def worker():
            try:
                result = func()
                error = None
            except Exception as exc:
                result = None
                error = exc

            self.after(0, lambda: on_done(result, error))

        threading.Thread(target=worker, daemon=True).start()

    # -------------------------
    # OAuth actions
    # -------------------------

    def sign_in(self):
        def do_sign_in():
            return self.service.sign_in()

        def done(result, error):
            if error:
                self.status_message.configure(text=str(error), text_color=ERROR)
            else:
                self.status_message.configure(text="Sign In successful.", text_color=SUCCESS)
                self.refresh_status()
                self.refresh_listings()

        self._run_async(do_sign_in, done, "Finalizing OAuth...")

    def sign_out(self):
        try:
            self.service.sign_out()
            self.status_message.configure(text="Signed out.", text_color=SUCCESS)
        except Exception as exc:
            self.status_message.configure(text=str(exc), text_color=ERROR)
        self.listings = []
        self.apply_filters()
        self.refresh_status()

    def test_connection(self):
        def do_test():
            return self.service.test_connection()

        def done(result, error):
            if error:
                self.status_message.configure(text=str(error), text_color=ERROR)
            else:
                if result.get("ok"):
                    self.status_message.configure(
                        text=f"Connection OK ({result.get('latency_ms')} ms, {result.get('environment')}).",
                        text_color=SUCCESS,
                    )
                else:
                    self.status_message.configure(text=result.get("message") or "Connection failed.", text_color=ERROR)
            self.refresh_status()

        self._run_async(do_test, done, "Testing eBay connection...")

    # -------------------------
    # Listings
    # -------------------------

    def refresh_listings(self):
        def do_load():
            return self.service.get_active_listings(force_refresh=True)

        def done(result, error):
            if error:
                self.status_message.configure(text=str(error), text_color=ERROR)
                self.listings = []
            else:
                self.listings = list(result or [])
                self.status_message.configure(text=f"Loaded {len(self.listings)} listing(s).", text_color=SUCCESS)
            self._refresh_filter_options()
            self.apply_filters()
            self.refresh_status()

        self._run_async(do_load, done, "Downloading active listings...")

    def _refresh_filter_options(self):
        statuses = sorted({str(item.get("status") or "Unknown") for item in self.listings})
        values = ["All"] + statuses
        self.status_filter_menu.configure(values=values)
        if self.status_filter_var.get() not in values:
            self.status_filter_var.set("All")

    def apply_filters(self):
        search = self.search_var.get().strip().lower()
        status_filter = self.status_filter_var.get()

        rows = []
        for item in self.listings:
            if status_filter != "All" and str(item.get("status") or "") != status_filter:
                continue

            if search:
                blob = " ".join(
                    [
                        str(item.get("title") or ""),
                        str(item.get("item_id") or ""),
                        str(item.get("sku") or ""),
                    ]
                ).lower()
                if search not in blob:
                    continue

            rows.append(item)

        sort_key = self.sort_var.get()
        self.filtered = sorted(rows, key=lambda x: self._sort_value(x, sort_key), reverse=self._sort_reverse(sort_key))

        self._render_table()
        self.count_label.configure(text=f"{len(self.filtered)} listing(s)")

    def _sort_reverse(self, sort_key):
        return sort_key in ("Price", "Quantity", "Last Updated", "Start Date")

    def _sort_value(self, item, sort_key):
        if sort_key == "Price":
            return float(item.get("price") or 0)
        if sort_key == "Quantity":
            return int(item.get("quantity") or 0)
        if sort_key == "Title":
            return str(item.get("title") or "").lower()
        if sort_key == "Item ID":
            return str(item.get("item_id") or "")
        if sort_key == "Start Date":
            return str(item.get("start_date") or "")
        return str(item.get("last_updated") or "")

    def _render_table(self):
        for child in self.table.winfo_children():
            child.destroy()

        if not self.filtered:
            ctk.CTkLabel(self.table, text="No listings found.", text_color=MUTED, font=(FONT, 12)).pack(anchor="w", pady=8)
            return

        for item in self.filtered:
            row = ctk.CTkFrame(self.table, fg_color="transparent")
            row.pack(fill="x", pady=2)

            values = [
                str(item.get("title") or ""),
                str(item.get("item_id") or ""),
                str(item.get("sku") or ""),
                f"${float(item.get('price') or 0):.2f}",
                str(int(item.get("quantity") or 0)),
                str(item.get("status") or ""),
                str(item.get("listing_type") or ""),
                str(item.get("start_date") or ""),
                str(item.get("last_updated") or ""),
            ]

            for idx, value in enumerate(values):
                width = self.columns[idx][1]
                ctk.CTkLabel(
                    row,
                    text=value,
                    font=(FONT, 11),
                    text_color=TEXT,
                    width=width,
                    anchor="w",
                    justify="left",
                    wraplength=width + 24,
                ).pack(side="left", padx=(8, 0), pady=2)

    # -------------------------
    # Status
    # -------------------------

    def refresh_status(self):
        try:
            status = self.service.get_connection_status(force=True)
        except Exception as exc:
            self.status_message.configure(text=str(exc), text_color=ERROR)
            return

        for key, label in self.status_labels.items():
            value = status.get(key)
            if key == "latency_ms":
                text = "—" if value in (None, "") else f"{value} ms"
            else:
                text = str(value or "—")
            label.configure(text=text)

        error_text = str(status.get("last_error") or "")
        self.connection_error.configure(text=error_text)

    # -------------------------
    # Lifecycle
    # -------------------------

    def destroy(self):
        super().destroy()
