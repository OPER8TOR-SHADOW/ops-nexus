import csv
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from gui.theme import *
from sales_service import SalesService


class SalesPage(ctk.CTkFrame):

    def __init__(self, master, page_manager=None):
        super().__init__(master, fg_color="transparent")

        self.page_manager = page_manager
        self.service = SalesService()

        self.sales_rows = []
        self.finish_lookup = {}
        self.selected_csv_path = ""
        self.csv_rows = []
        self.csv_columns = []
        self.mapping_vars = {}

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(5, weight=1)

        self._build_ui()
        self.refresh_data()

    def _build_ui(self):
        title = ctk.CTkLabel(
            self,
            text="Sales & Inventory Sync",
            font=(FONT, 30, "bold"),
            text_color=TEXT,
        )
        title.grid(row=0, column=0, sticky="w", padx=20, pady=(20, 8))

        subtitle = ctk.CTkLabel(
            self,
            text="Process completed sales and synchronize finish inventory, readiness, and eBay queue state.",
            font=(FONT, 14),
            text_color=MUTED,
        )
        subtitle.grid(row=1, column=0, sticky="w", padx=20, pady=(0, 12))

        self._build_filters()
        self._build_summary()
        self._build_manual_entry()
        self._build_import_wizard()
        self._build_sales_table()
        self._build_adjustments_panel()

    def _build_filters(self):
        section = ctk.CTkFrame(self, fg_color=CARD, border_width=1, border_color=BORDER, corner_radius=14)
        section.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 10))

        ctk.CTkLabel(
            section,
            text="Filters",
            font=(FONT, 16, "bold"),
            text_color=TEXT,
        ).pack(anchor="w", padx=14, pady=(12, 8))

        row = ctk.CTkFrame(section, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=(0, 12))

        self.period_var = ctk.StringVar(value="Today")
        self.period_menu = ctk.CTkOptionMenu(
            row,
            values=["Today", "This Week", "This Month", "All"],
            variable=self.period_var,
            width=130,
            command=lambda *_: self.refresh_data(),
        )
        self.period_menu.pack(side="left", padx=(0, 8))

        self.platform_var = ctk.StringVar(value="All")
        self.platform_menu = ctk.CTkOptionMenu(
            row,
            values=["All", "Manual", "CSV", "eBay", "Shopify"],
            variable=self.platform_var,
            width=130,
            command=lambda *_: self.refresh_data(),
        )
        self.platform_menu.pack(side="left", padx=(0, 8))

        self.finish_filter_var = ctk.StringVar(value="All")
        self.finish_filter_menu = ctk.CTkOptionMenu(
            row,
            values=["All"],
            variable=self.finish_filter_var,
            width=140,
            command=lambda *_: self.refresh_data(),
        )
        self.finish_filter_menu.pack(side="left", padx=(0, 8))

        self.card_filter_var = ctk.StringVar(value="")
        self.card_filter_entry = ctk.CTkEntry(
            row,
            placeholder_text="Card name / number",
            textvariable=self.card_filter_var,
            width=220,
        )
        self.card_filter_entry.pack(side="left", padx=(0, 8))
        self.card_filter_entry.bind("<Return>", lambda _event: self.refresh_data())

        ctk.CTkButton(
            row,
            text="Apply",
            width=90,
            command=self.refresh_data,
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            row,
            text="Clear",
            width=90,
            command=self.clear_filters,
        ).pack(side="left")

    def _build_summary(self):
        section = ctk.CTkFrame(self, fg_color=CARD, border_width=1, border_color=BORDER, corner_radius=14)
        section.grid(row=3, column=0, sticky="ew", padx=20, pady=(0, 10))

        ctk.CTkLabel(
            section,
            text="Sales Summary",
            font=(FONT, 16, "bold"),
            text_color=TEXT,
        ).pack(anchor="w", padx=14, pady=(12, 8))

        row = ctk.CTkFrame(section, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=(0, 12))

        self.summary_labels = {}
        metrics = [
            ("today_sales", "Today's Sales"),
            ("week_sales", "Week"),
            ("month_sales", "Month"),
            ("total_revenue", "Total Revenue"),
            ("fees", "Fees"),
            ("shipping", "Shipping"),
            ("net_revenue", "Net Revenue"),
            ("cards_sold", "Cards Sold"),
            ("inventory_removed", "Inventory Removed"),
        ]

        for key, label in metrics:
            block = ctk.CTkFrame(row, fg_color=SUBTEXT, corner_radius=10)
            block.pack(side="left", fill="x", expand=True, padx=(0, 8))
            ctk.CTkLabel(block, text=label, font=(FONT, 11), text_color=MUTED).pack(anchor="w", padx=10, pady=(8, 0))
            value = ctk.CTkLabel(block, text="0", font=(FONT, 14, "bold"), text_color=TEXT)
            value.pack(anchor="w", padx=10, pady=(0, 8))
            self.summary_labels[key] = value

    def _build_manual_entry(self):
        section = ctk.CTkFrame(self, fg_color=CARD, border_width=1, border_color=BORDER, corner_radius=14)
        section.grid(row=4, column=0, sticky="ew", padx=20, pady=(0, 10))

        ctk.CTkLabel(
            section,
            text="Manual Sale Entry",
            font=(FONT, 16, "bold"),
            text_color=TEXT,
        ).pack(anchor="w", padx=14, pady=(12, 8))

        row = ctk.CTkFrame(section, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=(0, 8))

        self.order_var = ctk.StringVar(value="")
        self.sale_date_var = ctk.StringVar(value="")
        self.platform_entry_var = ctk.StringVar(value="Manual")
        self.buyer_var = ctk.StringVar(value="")
        self.quantity_var = ctk.StringVar(value="1")
        self.sale_price_var = ctk.StringVar(value="0")
        self.fees_var = ctk.StringVar(value="0")
        self.shipping_var = ctk.StringVar(value="0")
        self.notes_var = ctk.StringVar(value="")

        self.finish_var = ctk.StringVar(value="")
        self.finish_menu = ctk.CTkOptionMenu(
            row,
            values=[""],
            variable=self.finish_var,
            width=280,
        )
        self.finish_menu.pack(side="left", padx=(0, 8))

        ctk.CTkEntry(row, placeholder_text="Order #", textvariable=self.order_var, width=120).pack(side="left", padx=(0, 8))
        ctk.CTkEntry(row, placeholder_text="Date (YYYY-MM-DD)", textvariable=self.sale_date_var, width=140).pack(side="left", padx=(0, 8))
        ctk.CTkEntry(row, placeholder_text="Platform", textvariable=self.platform_entry_var, width=100).pack(side="left", padx=(0, 8))
        ctk.CTkEntry(row, placeholder_text="Buyer", textvariable=self.buyer_var, width=120).pack(side="left", padx=(0, 8))

        row_two = ctk.CTkFrame(section, fg_color="transparent")
        row_two.pack(fill="x", padx=14, pady=(0, 12))

        ctk.CTkEntry(row_two, placeholder_text="Quantity", textvariable=self.quantity_var, width=90).pack(side="left", padx=(0, 8))
        ctk.CTkEntry(row_two, placeholder_text="Sale Price", textvariable=self.sale_price_var, width=110).pack(side="left", padx=(0, 8))
        ctk.CTkEntry(row_two, placeholder_text="Fees", textvariable=self.fees_var, width=90).pack(side="left", padx=(0, 8))
        ctk.CTkEntry(row_two, placeholder_text="Shipping", textvariable=self.shipping_var, width=90).pack(side="left", padx=(0, 8))
        ctk.CTkEntry(row_two, placeholder_text="Notes", textvariable=self.notes_var, width=250).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            row_two,
            text="Record Sale",
            width=120,
            command=self.record_manual_sale,
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            row_two,
            text="Recalculate",
            width=110,
            command=self.recalculate_inventory,
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            row_two,
            text="Rebuild",
            width=90,
            command=self.rebuild_inventory,
        ).pack(side="left")

        self.manual_status_label = ctk.CTkLabel(section, text="", font=(FONT, 11), text_color=SUBTEXT)
        self.manual_status_label.pack(anchor="w", padx=14, pady=(0, 10))

    def _build_import_wizard(self):
        section = ctk.CTkFrame(self, fg_color=CARD, border_width=1, border_color=BORDER, corner_radius=14)
        section.grid(row=5, column=0, sticky="nsew", padx=20, pady=(0, 10))
        section.grid_columnconfigure(0, weight=1)
        section.grid_rowconfigure(3, weight=1)

        ctk.CTkLabel(
            section,
            text="Import CSV",
            font=(FONT, 16, "bold"),
            text_color=TEXT,
        ).grid(row=0, column=0, sticky="w", padx=14, pady=(12, 6))

        steps = "Select CSV  ->  Preview Rows  ->  Map Columns  ->  Validate  ->  Import  ->  Show Results"
        ctk.CTkLabel(
            section,
            text=steps,
            font=(FONT, 11),
            text_color=MUTED,
        ).grid(row=1, column=0, sticky="w", padx=14, pady=(0, 8))

        action_row = ctk.CTkFrame(section, fg_color="transparent")
        action_row.grid(row=2, column=0, sticky="ew", padx=14, pady=(0, 8))

        ctk.CTkButton(
            action_row,
            text="Select CSV",
            width=110,
            command=self.select_csv,
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            action_row,
            text="Validate",
            width=100,
            command=self.validate_csv,
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            action_row,
            text="Import",
            width=90,
            command=self.import_csv,
        ).pack(side="left", padx=(0, 8))

        self.csv_path_label = ctk.CTkLabel(action_row, text="No CSV selected", font=(FONT, 11), text_color=SUBTEXT)
        self.csv_path_label.pack(side="left", padx=(8, 0))

        split = ctk.CTkFrame(section, fg_color="transparent")
        split.grid(row=3, column=0, sticky="nsew", padx=14, pady=(0, 12))
        split.grid_columnconfigure(0, weight=2)
        split.grid_columnconfigure(1, weight=1)
        split.grid_rowconfigure(0, weight=1)

        self.csv_preview = ctk.CTkTextbox(split, fg_color=SUBTEXT)
        self.csv_preview.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        mapping_panel = ctk.CTkScrollableFrame(split, fg_color="transparent")
        mapping_panel.grid(row=0, column=1, sticky="nsew")

        self.mapping_fields = [
            "order_number",
            "sale_date",
            "platform",
            "buyer",
            "card_id",
            "finish_id",
            "card_number",
            "card_name",
            "finish",
            "quantity",
            "sale_price",
            "fees",
            "shipping_cost",
            "notes",
        ]

        for field in self.mapping_fields:
            row = ctk.CTkFrame(mapping_panel, fg_color="transparent")
            row.pack(fill="x", pady=2)

            ctk.CTkLabel(
                row,
                text=field,
                font=(FONT, 11, "bold"),
                text_color=SUBTEXT,
                width=120,
                anchor="w",
            ).pack(side="left")

            var = ctk.StringVar(value="")
            menu = ctk.CTkOptionMenu(row, values=[""], variable=var, width=160)
            menu.pack(side="left", padx=(8, 0))

            self.mapping_vars[field] = {
                "var": var,
                "menu": menu,
            }

        self.import_result_label = ctk.CTkLabel(section, text="", font=(FONT, 11), text_color=SUBTEXT)
        self.import_result_label.grid(row=4, column=0, sticky="w", padx=14, pady=(0, 10))

    def _build_sales_table(self):
        section = ctk.CTkFrame(self, fg_color=CARD, border_width=1, border_color=BORDER, corner_radius=14)
        section.grid(row=6, column=0, sticky="nsew", padx=20, pady=(0, 10))
        section.grid_columnconfigure(0, weight=1)
        section.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            section,
            text="Recent Sales",
            font=(FONT, 16, "bold"),
            text_color=TEXT,
        ).grid(row=0, column=0, sticky="w", padx=14, pady=(12, 8))

        table_header = ctk.CTkFrame(section, fg_color=SUBTEXT, corner_radius=8)
        table_header.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 4))

        columns = [
            ("Date", 90),
            ("Order #", 110),
            ("Platform", 90),
            ("Card", 200),
            ("Finish", 90),
            ("Quantity", 70),
            ("Sale Price", 90),
            ("Fees", 70),
            ("Shipping", 80),
            ("Net Profit", 90),
            ("Status", 90),
        ]
        self.table_columns = columns

        for text, width in columns:
            ctk.CTkLabel(
                table_header,
                text=text,
                font=(FONT, 11, "bold"),
                text_color=TEXT,
                width=width,
                anchor="w",
            ).pack(side="left", padx=(8, 0), pady=6)

        self.sales_table = ctk.CTkScrollableFrame(section, fg_color="transparent", height=220)
        self.sales_table.grid(row=2, column=0, sticky="nsew", padx=14, pady=(0, 10))

    def _build_adjustments_panel(self):
        section = ctk.CTkFrame(self, fg_color=CARD, border_width=1, border_color=BORDER, corner_radius=14)
        section.grid(row=7, column=0, sticky="ew", padx=20, pady=(0, 20))

        ctk.CTkLabel(
            section,
            text="Inventory Adjustments",
            font=(FONT, 16, "bold"),
            text_color=TEXT,
        ).pack(anchor="w", padx=14, pady=(12, 8))

        self.adjustments_text = ctk.CTkTextbox(section, height=120, fg_color=SUBTEXT)
        self.adjustments_text.pack(fill="x", padx=14, pady=(0, 12))

    def clear_filters(self):
        self.period_var.set("Today")
        self.platform_var.set("All")
        self.finish_filter_var.set("All")
        self.card_filter_var.set("")
        self.refresh_data()

    def refresh_data(self):
        self._refresh_finish_options()

        finish_filter = self.finish_filter_var.get()
        rows = self.service.get_sales(
            period=self.period_var.get(),
            platform=self.platform_var.get(),
            card_query=self.card_filter_var.get().strip(),
            finish=finish_filter,
            include_deleted=False,
            limit=300,
        )
        self.sales_rows = rows

        self._render_sales_table()
        self._render_summary()
        self._render_adjustments()

    def _refresh_finish_options(self):
        finish_rows = self.service.db_service.db.fetchall(
            """
            SELECT
                cf.id,
                c.number,
                c.name,
                cf.finish
            FROM card_finishes cf
            INNER JOIN cards c
                ON c.id = cf.card_id
            ORDER BY c.number ASC, cf.id ASC
            """
        )

        self.finish_lookup = {}
        finish_values = []

        for row in finish_rows:
            option = f"{row['id']} | {row['number']} {row['name']} | {row['finish']}"
            finish_values.append(option)
            self.finish_lookup[option] = row["id"]

        manual_values = finish_values if finish_values else [""]
        self.finish_menu.configure(values=manual_values)
        if self.finish_var.get() not in self.finish_lookup:
            self.finish_var.set(manual_values[0])

        filter_values = ["All"] + sorted({row["finish"] for row in finish_rows})
        self.finish_filter_menu.configure(values=filter_values)
        if self.finish_filter_var.get() not in filter_values:
            self.finish_filter_var.set("All")

    def record_manual_sale(self):
        selected_finish = self.finish_var.get()
        finish_id = self.finish_lookup.get(selected_finish)
        if not finish_id:
            self.manual_status_label.configure(text="Select a valid finish.", text_color=ERROR)
            return

        result = self.service.record_sale(
            order_number=self.order_var.get().strip(),
            sale_date=self.sale_date_var.get().strip(),
            platform=self.platform_entry_var.get().strip() or "Manual",
            buyer=self.buyer_var.get().strip(),
            finish_id=finish_id,
            quantity=self.quantity_var.get().strip(),
            sale_price=self.sale_price_var.get().strip(),
            fees=self.fees_var.get().strip(),
            shipping_cost=self.shipping_var.get().strip(),
            notes=self.notes_var.get().strip(),
        )

        if result.get("ok"):
            self.manual_status_label.configure(text="Sale recorded and inventory synchronized.", text_color=SUCCESS)
            self.quantity_var.set("1")
            self.sale_price_var.set("0")
            self.fees_var.set("0")
            self.shipping_var.set("0")
            self.notes_var.set("")
            self.refresh_data()
        else:
            self.manual_status_label.configure(text=result.get("reason") or "Sale failed.", text_color=ERROR)

    def select_csv(self):
        selected = filedialog.askopenfilename(
            title="Select Sales CSV",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if not selected:
            return

        self.selected_csv_path = selected
        self.csv_path_label.configure(text=selected)
        self._load_csv_preview()

    def _load_csv_preview(self):
        self.csv_rows = []
        self.csv_columns = []

        try:
            with Path(self.selected_csv_path).open("r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                self.csv_columns = list(reader.fieldnames or [])
                for row in reader:
                    self.csv_rows.append(row)
                    if len(self.csv_rows) >= 20:
                        break
        except Exception as exc:
            self.import_result_label.configure(text=f"Failed to read CSV: {exc}", text_color=ERROR)
            return

        self._refresh_mapping_options()
        self._render_csv_preview()
        self.import_result_label.configure(text=f"Preview loaded ({len(self.csv_rows)} rows shown)", text_color=SUBTEXT)

    def _refresh_mapping_options(self):
        defaults = self.service._default_column_mapping(self.csv_columns)
        values = [""] + self.csv_columns

        for key in self.mapping_fields:
            mapping = self.mapping_vars.get(key)
            if not mapping:
                continue
            mapping["menu"].configure(values=values)
            default_value = defaults.get(key, "")
            mapping["var"].set(default_value if default_value in values else "")

    def _render_csv_preview(self):
        self.csv_preview.delete("1.0", "end")
        if not self.csv_columns:
            self.csv_preview.insert("end", "No preview available.\n")
            return

        self.csv_preview.insert("end", "Columns:\n")
        self.csv_preview.insert("end", " | ".join(self.csv_columns) + "\n\n")
        self.csv_preview.insert("end", "Rows:\n")

        for row in self.csv_rows:
            values = [str(row.get(col, "")) for col in self.csv_columns]
            self.csv_preview.insert("end", " | ".join(values) + "\n")

    def _current_column_map(self):
        mapping = {}
        for key, entry in self.mapping_vars.items():
            mapping[key] = entry["var"].get().strip()
        return mapping

    def validate_csv(self):
        if not self.selected_csv_path:
            self.import_result_label.configure(text="Select a CSV file first.", text_color=ERROR)
            return

        mapping = self._current_column_map()
        valid = 0
        unknown = 0

        for row in self.csv_rows:
            finish = self.service._resolve_finish_from_row(row, mapping)
            if finish:
                valid += 1
            else:
                unknown += 1

        self.import_result_label.configure(
            text=f"Validation complete: {valid} resolvable row(s), {unknown} unknown row(s).",
            text_color=SUBTEXT,
        )

    def import_csv(self):
        if not self.selected_csv_path:
            self.import_result_label.configure(text="Select a CSV file first.", text_color=ERROR)
            return

        result = self.service.import_sales_csv(
            self.selected_csv_path,
            column_map=self._current_column_map(),
            default_platform="CSV",
        )

        if not result.get("ok"):
            self.import_result_label.configure(text=result.get("reason") or "Import failed", text_color=ERROR)
            return

        summary = result.get("summary") or {}
        self.import_result_label.configure(
            text=(
                f"Imported: {summary.get('imported', 0)} | "
                f"Duplicates: {summary.get('skipped_duplicates', 0)} | "
                f"Unknown: {summary.get('skipped_unknown', 0)} | "
                f"Failed: {summary.get('failed', 0)}"
            ),
            text_color=SUCCESS,
        )
        self.refresh_data()

    def recalculate_inventory(self):
        result = self.service.recalculate_inventory()
        if result.get("ok"):
            self.manual_status_label.configure(
                text=f"Recalculated finish states: {result.get('recalculated', 0)}",
                text_color=SUCCESS,
            )
        self.refresh_data()

    def rebuild_inventory(self):
        result = self.service.rebuild_inventory()
        if result.get("ok"):
            self.manual_status_label.configure(
                text=f"Rebuild complete for {result.get('rebuild_count', 0)} finish record(s)",
                text_color=SUCCESS,
            )
        self.refresh_data()

    def _render_summary(self):
        summary = self.service.get_sales_summary(
            period=self.period_var.get(),
            platform=self.platform_var.get(),
            card_query=self.card_filter_var.get().strip(),
            finish=self.finish_filter_var.get(),
        )

        for key, label in self.summary_labels.items():
            value = summary.get(key, 0)
            if key in ("total_revenue", "fees", "shipping", "net_revenue"):
                label.configure(text=f"${float(value):.2f}")
            else:
                label.configure(text=str(value))

    def _render_sales_table(self):
        for child in self.sales_table.winfo_children():
            child.destroy()

        for row in self.sales_rows:
            item = ctk.CTkFrame(self.sales_table, fg_color="transparent")
            item.pack(fill="x", pady=2)

            net_profit = float(row.get("sale_price") or 0) - float(row.get("fees") or 0) - float(row.get("shipping_cost") or 0)
            values = [
                row.get("sale_date") or "",
                row.get("order_number") or "",
                row.get("platform") or "",
                f"{row.get('card_number') or ''} {row.get('card_name') or row.get('card_id') or ''}".strip(),
                row.get("finish") or "",
                str(int(row.get("quantity") or 0)),
                f"${float(row.get('sale_price') or 0):.2f}",
                f"${float(row.get('fees') or 0):.2f}",
                f"${float(row.get('shipping_cost') or 0):.2f}",
                f"${net_profit:.2f}",
                row.get("status") or "",
            ]

            for idx, value in enumerate(values):
                width = self.table_columns[idx][1]
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

    def _render_adjustments(self):
        adjustments = self.service.get_inventory_adjustments(limit=100)
        self.adjustments_text.delete("1.0", "end")

        if not adjustments:
            self.adjustments_text.insert("end", "No inventory adjustments yet.\n")
            return

        for row in adjustments:
            delta = int(row.get("inventory_delta") or 0)
            sign = "+" if delta > 0 else ""
            self.adjustments_text.insert(
                "end",
                (
                    f"{row.get('sale_date')} | {row.get('order_number')} | "
                    f"{row.get('card')} [{row.get('finish')}] | "
                    f"Status: {row.get('status')} | Delta: {sign}{delta}\n"
                ),
            )
