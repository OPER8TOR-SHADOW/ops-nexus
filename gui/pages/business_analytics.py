import tkinter as tk
from tkinter import filedialog

import customtkinter as ctk

from gui.theme import *
from gui.services.business_analytics_service import BusinessAnalyticsService


class MiniChart(ctk.CTkFrame):

    def __init__(self, master, title, chart_type="bar"):
        super().__init__(master, fg_color=CARD, border_width=1, border_color=BORDER, corner_radius=14)

        self.title = ctk.CTkLabel(self, text=title, font=(FONT, 14, "bold"), text_color=TEXT)
        self.title.pack(anchor="w", padx=12, pady=(10, 6))

        self.canvas = tk.Canvas(self, bg="#171717", highlightthickness=0, height=170)
        self.canvas.pack(fill="x", padx=12, pady=(0, 10))

        self.chart_type = chart_type

    def draw(self, points, value_key="revenue", label_key="label"):
        self.canvas.delete("all")

        width = max(500, int(self.canvas.winfo_width() or 500))
        height = 170
        self.canvas.config(width=width, height=height)

        if not points:
            self.canvas.create_text(12, height // 2, anchor="w", fill="#9CA3AF", text="No data for current filters")
            return

        values = [float(item.get(value_key, 0) or 0) for item in points]
        max_value = max(values) if values else 0
        if max_value <= 0:
            max_value = 1

        if self.chart_type == "line":
            self._draw_line(points, values, max_value, width, height)
        else:
            self._draw_bar(points, values, max_value, width, height, label_key)

    def _draw_line(self, points, values, max_value, width, height):
        left = 16
        right = width - 16
        top = 14
        bottom = height - 24

        count = len(values)
        if count == 1:
            x_positions = [left + (right - left) // 2]
        else:
            step = (right - left) / (count - 1)
            x_positions = [left + i * step for i in range(count)]

        y_positions = []
        for value in values:
            ratio = value / max_value
            y_positions.append(bottom - (bottom - top) * ratio)

        self.canvas.create_line(left, bottom, right, bottom, fill="#2B2B2B", width=1)

        for i in range(1, len(x_positions)):
            self.canvas.create_line(
                x_positions[i - 1],
                y_positions[i - 1],
                x_positions[i],
                y_positions[i],
                fill="#E00000",
                width=2,
            )

        for x, y, value in zip(x_positions, y_positions, values):
            self.canvas.create_oval(x - 3, y - 3, x + 3, y + 3, fill="#FFC83D", outline="")
            self.canvas.create_text(x, y - 10, fill="#A8A8A8", text=f"${value:,.0f}", font=("Segoe UI", 8))

    def _draw_bar(self, points, values, max_value, width, height, label_key):
        left = 16
        right = width - 16
        top = 14
        bottom = height - 26

        count = len(values)
        bar_space = max(1, count)
        bar_width = (right - left) / bar_space

        self.canvas.create_line(left, bottom, right, bottom, fill="#2B2B2B", width=1)

        for idx, (point, value) in enumerate(zip(points, values)):
            x0 = left + idx * bar_width + 4
            x1 = left + (idx + 1) * bar_width - 4
            ratio = value / max_value
            y0 = bottom - (bottom - top) * ratio
            y1 = bottom

            self.canvas.create_rectangle(x0, y0, x1, y1, fill="#E00000", outline="")

            label = str(point.get(label_key, ""))
            if len(label) > 8:
                label = label[:8] + "..."

            self.canvas.create_text((x0 + x1) / 2, bottom + 10, fill="#A8A8A8", text=label, font=("Segoe UI", 7))


class BusinessAnalyticsPage(ctk.CTkFrame):

    def __init__(self, master, page_manager=None):
        super().__init__(master, fg_color="transparent")

        self.page_manager = page_manager
        self.service = BusinessAnalyticsService()

        self.summary_labels = {}
        self.inventory_labels = {}
        self.profit_labels = {}

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._build_header()
        self._build_body()

        self.filter_options = self.service.get_filter_options()
        self._load_filter_options()
        self.apply_filters()

    # -------------------------
    # UI Build
    # -------------------------

    def _build_header(self):
        title_row = ctk.CTkFrame(self, fg_color="transparent")
        title_row.grid(row=0, column=0, sticky="ew", padx=20, pady=(16, 8))

        ctk.CTkLabel(
            title_row,
            text="Business Analytics",
            font=(FONT, 30, "bold"),
            text_color=TEXT,
        ).pack(side="left")

        self.status_label = ctk.CTkLabel(
            title_row,
            text="",
            font=(FONT, 12),
            text_color=MUTED,
        )
        self.status_label.pack(side="right")

    def _build_body(self):
        self.body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.body.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 20))
        self.body.grid_columnconfigure(0, weight=1)

        self._build_filters(self.body)
        self._build_summary_cards(self.body)
        self._build_inventory_cards(self.body)
        self._build_profit_cards(self.body)
        self._build_charts(self.body)
        self._build_sales_breakdowns(self.body)
        self._build_rarity_section(self.body)
        self._build_set_analytics(self.body)

    def _build_filters(self, parent):
        section = ctk.CTkFrame(parent, fg_color=CARD, border_width=1, border_color=BORDER, corner_radius=14)
        section.pack(fill="x", pady=(0, 12))

        ctk.CTkLabel(section, text="Filters", font=(FONT, 16, "bold"), text_color=TEXT).pack(anchor="w", padx=14, pady=(12, 8))

        row = ctk.CTkFrame(section, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=(0, 8))

        row_two = ctk.CTkFrame(section, fg_color="transparent")
        row_two.pack(fill="x", padx=14, pady=(0, 12))

        self.date_preset_var = ctk.StringVar(value="This Month")
        self.date_preset = ctk.CTkOptionMenu(
            row,
            values=["Today", "This Week", "This Month", "Last 30 Days", "Lifetime", "Custom"],
            variable=self.date_preset_var,
            width=130,
        )
        self.date_preset.pack(side="left", padx=(0, 8))

        self.start_date_var = ctk.StringVar(value="")
        self.end_date_var = ctk.StringVar(value="")
        self.start_date_entry = ctk.CTkEntry(row, textvariable=self.start_date_var, placeholder_text="Start YYYY-MM-DD", width=120)
        self.end_date_entry = ctk.CTkEntry(row, textvariable=self.end_date_var, placeholder_text="End YYYY-MM-DD", width=120)
        self.start_date_entry.pack(side="left", padx=(0, 8))
        self.end_date_entry.pack(side="left", padx=(0, 8))

        self.platform_var = ctk.StringVar(value="All")
        self.platform_menu = ctk.CTkOptionMenu(row, values=["All"], variable=self.platform_var, width=105)
        self.platform_menu.pack(side="left", padx=(0, 8))

        self.set_var = ctk.StringVar(value="All")
        self.set_menu = ctk.CTkOptionMenu(row, values=["All"], variable=self.set_var, width=105)
        self.set_menu.pack(side="left", padx=(0, 8))

        self.finish_var = ctk.StringVar(value="All")
        self.finish_menu = ctk.CTkOptionMenu(row, values=["All"], variable=self.finish_var, width=105)
        self.finish_menu.pack(side="left", padx=(0, 8))

        self.card_query_var = ctk.StringVar(value="")
        self.card_query_entry = ctk.CTkEntry(row_two, textvariable=self.card_query_var, placeholder_text="Card name/number", width=300)
        self.card_query_entry.pack(side="left", padx=(0, 8))

        ctk.CTkButton(row_two, text="Apply", width=90, command=self.apply_filters).pack(side="left", padx=(0, 8))
        ctk.CTkButton(row_two, text="Export CSV", width=100, command=self.export_csv).pack(side="left", padx=(0, 8))
        ctk.CTkButton(row_two, text="Export Excel", width=110, command=self.export_excel).pack(side="left")

    def _build_summary_cards(self, parent):
        section = ctk.CTkFrame(parent, fg_color="transparent")
        section.pack(fill="x", pady=(0, 12))

        ctk.CTkLabel(section, text="Summary", font=(FONT, 18, "bold"), text_color=TEXT).pack(anchor="w", pady=(0, 8))

        grid = ctk.CTkFrame(section, fg_color="transparent")
        grid.pack(fill="x")

        keys = [
            ("today_revenue", "Today's Revenue", True),
            ("week_revenue", "This Week", True),
            ("month_revenue", "This Month", True),
            ("lifetime_revenue", "Lifetime Revenue", True),
            ("today_profit", "Today's Profit", True),
            ("month_profit", "Monthly Profit", True),
            ("lifetime_profit", "Lifetime Profit", True),
            ("cards_sold", "Cards Sold", False),
            ("orders", "Orders", False),
            ("average_order_value", "Average Order Value", True),
            ("average_sale_price", "Average Sale Price", True),
            ("inventory_value", "Inventory Value", True),
            ("potential_listing_value", "Potential Listing Value", True),
        ]

        for idx, (key, label, currency) in enumerate(keys):
            card = ctk.CTkFrame(grid, fg_color=CARD, border_width=1, border_color=BORDER, corner_radius=12)
            card.grid(row=idx // 4, column=idx % 4, padx=6, pady=6, sticky="ew")
            grid.grid_columnconfigure(idx % 4, weight=1)

            ctk.CTkLabel(card, text=label, font=(FONT, 12), text_color=MUTED).pack(anchor="w", padx=10, pady=(8, 2))
            value = ctk.CTkLabel(card, text="0", font=(FONT, 18, "bold"), text_color=TEXT)
            value.pack(anchor="w", padx=10, pady=(0, 10))
            self.summary_labels[key] = (value, currency)

    def _build_inventory_cards(self, parent):
        section = ctk.CTkFrame(parent, fg_color="transparent")
        section.pack(fill="x", pady=(0, 12))

        ctk.CTkLabel(section, text="Inventory Analytics", font=(FONT, 18, "bold"), text_color=TEXT).pack(anchor="w", pady=(0, 8))

        grid = ctk.CTkFrame(section, fg_color="transparent")
        grid.pack(fill="x")

        keys = [
            ("total_cards", "Total Cards", False),
            ("total_finishes", "Total Finishes", False),
            ("items_in_stock", "Items In Stock", False),
            ("out_of_stock", "Out Of Stock", False),
            ("ready_to_list", "Ready To List", False),
            ("queued_for_ebay", "Queued For eBay", False),
            ("listed", "Listed", False),
            ("images_complete", "Images Complete", False),
            ("github_uploaded", "GitHub Uploaded", False),
            ("cost_value", "Inventory Value (Cost)", True),
            ("market_value", "Inventory Value (Market)", True),
            ("sell_value", "Inventory Value (Selling Price)", True),
        ]

        for idx, (key, label, currency) in enumerate(keys):
            card = ctk.CTkFrame(grid, fg_color=CARD, border_width=1, border_color=BORDER, corner_radius=12)
            card.grid(row=idx // 4, column=idx % 4, padx=6, pady=6, sticky="ew")
            grid.grid_columnconfigure(idx % 4, weight=1)

            ctk.CTkLabel(card, text=label, font=(FONT, 12), text_color=MUTED).pack(anchor="w", padx=10, pady=(8, 2))
            value = ctk.CTkLabel(card, text="0", font=(FONT, 18, "bold"), text_color=TEXT)
            value.pack(anchor="w", padx=10, pady=(0, 10))
            self.inventory_labels[key] = (value, currency)

    def _build_profit_cards(self, parent):
        section = ctk.CTkFrame(parent, fg_color="transparent")
        section.pack(fill="x", pady=(0, 12))

        ctk.CTkLabel(section, text="Profit Analytics", font=(FONT, 18, "bold"), text_color=TEXT).pack(anchor="w", pady=(0, 8))

        row = ctk.CTkFrame(section, fg_color="transparent")
        row.pack(fill="x")

        keys = [
            ("gross_revenue", "Gross Revenue", True),
            ("fees", "Fees", True),
            ("shipping", "Shipping", True),
            ("net_profit", "Net Profit", True),
            ("profit_margin_percent", "Profit Margin %", False),
            ("average_profit_per_card", "Average Profit Per Card", True),
            ("average_profit_per_order", "Average Profit Per Order", True),
            ("roi_percent", "ROI %", False),
        ]

        for idx, (key, label, currency) in enumerate(keys):
            card = ctk.CTkFrame(row, fg_color=CARD, border_width=1, border_color=BORDER, corner_radius=12)
            card.grid(row=0, column=idx, padx=6, pady=6, sticky="ew")
            row.grid_columnconfigure(idx, weight=1)

            ctk.CTkLabel(card, text=label, font=(FONT, 12), text_color=MUTED).pack(anchor="w", padx=10, pady=(8, 2))
            value = ctk.CTkLabel(card, text="0", font=(FONT, 17, "bold"), text_color=TEXT)
            value.pack(anchor="w", padx=10, pady=(0, 10))
            self.profit_labels[key] = (value, currency)

    def _build_charts(self, parent):
        section = ctk.CTkFrame(parent, fg_color="transparent")
        section.pack(fill="x", pady=(0, 12))

        ctk.CTkLabel(section, text="Charts", font=(FONT, 18, "bold"), text_color=TEXT).pack(anchor="w", pady=(0, 8))

        grid = ctk.CTkFrame(section, fg_color="transparent")
        grid.pack(fill="x")

        self.chart_revenue_time = MiniChart(grid, "Revenue Over Time", chart_type="line")
        self.chart_profit_time = MiniChart(grid, "Profit Over Time", chart_type="line")
        self.chart_platform = MiniChart(grid, "Sales by Platform")
        self.chart_inventory_value = MiniChart(grid, "Inventory Value")
        self.chart_revenue_set = MiniChart(grid, "Revenue by Set")
        self.chart_top_sets = MiniChart(grid, "Top Selling Sets")
        self.chart_top_cards = MiniChart(grid, "Top Selling Cards")

        charts = [
            self.chart_revenue_time,
            self.chart_profit_time,
            self.chart_platform,
            self.chart_inventory_value,
            self.chart_revenue_set,
            self.chart_top_sets,
            self.chart_top_cards,
        ]

        for idx, chart in enumerate(charts):
            chart.grid(row=idx // 2, column=idx % 2, padx=6, pady=6, sticky="ew")
            grid.grid_columnconfigure(idx % 2, weight=1)

    def _build_sales_breakdowns(self, parent):
        section = ctk.CTkFrame(parent, fg_color=CARD, border_width=1, border_color=BORDER, corner_radius=14)
        section.pack(fill="x", pady=(0, 12))

        ctk.CTkLabel(section, text="Sales Analytics", font=(FONT, 18, "bold"), text_color=TEXT).pack(anchor="w", padx=14, pady=(12, 8))

        self.sales_breakdown_text = ctk.CTkTextbox(section, height=220, fg_color=SUBTEXT)
        self.sales_breakdown_text.pack(fill="x", padx=14, pady=(0, 12))

        self.top_cards_text = ctk.CTkTextbox(section, height=230, fg_color=SUBTEXT)
        self.top_cards_text.pack(fill="x", padx=14, pady=(0, 12))

    def _build_rarity_section(self, parent):
        section = ctk.CTkFrame(parent, fg_color=CARD, border_width=1, border_color=BORDER, corner_radius=14)
        section.pack(fill="x", pady=(0, 12))

        ctk.CTkLabel(section, text="Rarity Analytics", font=(FONT, 18, "bold"), text_color=TEXT).pack(anchor="w", padx=14, pady=(12, 8))

        self.rarity_text = ctk.CTkTextbox(section, height=180, fg_color=SUBTEXT)
        self.rarity_text.pack(fill="x", padx=14, pady=(0, 12))

    def _build_set_analytics(self, parent):
        section = ctk.CTkFrame(parent, fg_color=CARD, border_width=1, border_color=BORDER, corner_radius=14)
        section.pack(fill="x", pady=(0, 18))

        ctk.CTkLabel(section, text="Set Analytics", font=(FONT, 18, "bold"), text_color=TEXT).pack(anchor="w", padx=14, pady=(12, 8))

        self.set_text = ctk.CTkTextbox(section, height=280, fg_color=SUBTEXT)
        self.set_text.pack(fill="x", padx=14, pady=(0, 12))

    # -------------------------
    # Filters
    # -------------------------

    def _load_filter_options(self):
        platform_values = ["All"] + self.filter_options.get("platforms", [])
        finish_values = ["All"] + self.filter_options.get("finishes", [])

        set_values = ["All"]
        self.set_lookup = {}
        for item in self.filter_options.get("sets", []):
            label = f"{item['id'].upper()} - {item['name']}"
            set_values.append(label)
            self.set_lookup[label] = item["id"]

        self.platform_menu.configure(values=platform_values)
        self.finish_menu.configure(values=finish_values)
        self.set_menu.configure(values=set_values)

        self.platform_var.set("All")
        self.finish_var.set("All")
        self.set_var.set("All")

    def _current_filters(self):
        start_date, end_date = self.service.resolve_date_range(
            self.date_preset_var.get(),
            self.start_date_var.get(),
            self.end_date_var.get(),
        )

        set_value = self.set_var.get()
        if set_value == "All":
            set_id = "All"
        else:
            set_id = self.set_lookup.get(set_value, "All")

        return {
            "start_date": start_date,
            "end_date": end_date,
            "platform": self.platform_var.get(),
            "set_id": set_id,
            "card_query": self.card_query_var.get().strip(),
            "finish": self.finish_var.get(),
        }

    # -------------------------
    # Refresh
    # -------------------------

    def apply_filters(self):
        filters = self._current_filters()

        summary = self.service.get_summary_metrics(filters)
        inventory = self.service.get_inventory_metrics(filters)
        profit = self.service.get_profit_metrics(filters)
        series = self.service.get_time_series(filters)
        breakdowns = self.service.get_group_breakdowns(filters)
        rarity = self.service.get_rarity_breakdown(filters)
        set_rows = self.service.get_set_analytics(filters)

        self._update_metric_labels(self.summary_labels, summary)
        self._update_metric_labels(self.inventory_labels, inventory)
        self._update_metric_labels(self.profit_labels, profit)

        self._render_charts(series, breakdowns, inventory, set_rows)
        self._render_sales_breakdown_text(series, breakdowns)
        self._render_rarity_text(rarity)
        self._render_set_text(set_rows)

        range_label = f"{filters['start_date'] or 'Start'} to {filters['end_date'] or 'Now'}"
        self.status_label.configure(text=f"Updated for {range_label}")

    def refresh(self):
        self.filter_options = self.service.get_filter_options()
        self._load_filter_options()
        self.apply_filters()

    def _update_metric_labels(self, labels, values):
        for key, (label, currency) in labels.items():
            value = values.get(key, 0)

            if key.endswith("_percent"):
                label.configure(text=f"{float(value):.2f}%")
                continue

            if currency:
                label.configure(text=f"${float(value):,.2f}")
            else:
                label.configure(text=f"{int(value):,}")

    def _render_charts(self, series, breakdowns, inventory, set_rows):
        by_day = series.get("by_day", [])

        self.chart_revenue_time.draw(by_day, value_key="revenue", label_key="label")
        self.chart_profit_time.draw(by_day, value_key="profit", label_key="label")

        platform_rows = [
            {"label": row.get("platform", "Unknown"), "revenue": row.get("revenue", 0)}
            for row in breakdowns.get("platforms", [])
        ]
        self.chart_platform.draw(platform_rows, value_key="revenue", label_key="label")

        inventory_rows = [
            {"label": "Cost", "value": float(inventory.get("cost_value") or 0)},
            {"label": "Market", "value": float(inventory.get("market_value") or 0)},
            {"label": "Sell", "value": float(inventory.get("sell_value") or 0)},
        ]
        self.chart_inventory_value.draw(inventory_rows, value_key="value", label_key="label")

        set_revenue = [
            {"label": row.get("set_id", "Unknown"), "revenue": row.get("revenue", 0)}
            for row in set_rows[:20]
        ]
        self.chart_revenue_set.draw(set_revenue, value_key="revenue", label_key="label")

        top_sets = [
            {"label": row.get("set_id", "Unknown"), "cards_sold": row.get("cards_sold", 0)}
            for row in sorted(set_rows, key=lambda item: item.get("cards_sold", 0), reverse=True)[:20]
        ]
        self.chart_top_sets.draw(top_sets, value_key="cards_sold", label_key="label")

        top_cards = [
            {"label": row.get("card", "Unknown"), "cards_sold": row.get("cards_sold", 0)}
            for row in breakdowns.get("top_selling_cards", [])[:20]
        ]
        self.chart_top_cards.draw(top_cards, value_key="cards_sold", label_key="label")

    def _render_sales_breakdown_text(self, series, breakdowns):
        self.sales_breakdown_text.configure(state="normal")
        self.sales_breakdown_text.delete("1.0", "end")

        def write_section(title, rows, label_key):
            self.sales_breakdown_text.insert("end", title + "\n")
            self.sales_breakdown_text.insert("end", "-" * len(title) + "\n")
            for row in rows:
                label = str(row.get(label_key, "Unknown"))
                revenue = float(row.get("revenue") or 0)
                cards = int(row.get("cards_sold") or 0)
                self.sales_breakdown_text.insert("end", f"{label:<30} {cards:>6} cards  ${revenue:>10,.2f}\n")
            self.sales_breakdown_text.insert("end", "\n")

        write_section("Revenue by Month", series.get("by_month", []), "label")
        write_section("Revenue by Week", series.get("by_week", []), "label")
        write_section("Revenue by Day", series.get("by_day", []), "label")
        write_section("Sales by Platform", breakdowns.get("platforms", []), "platform")
        write_section("Sales by Finish", breakdowns.get("finishes", []), "finish")
        write_section("Sales by Set", breakdowns.get("sets", []), "set_id")
        write_section("Sales by Card", breakdowns.get("cards", [])[:20], "card")

        self.top_cards_text.configure(state="normal")
        self.top_cards_text.delete("1.0", "end")

        def write_top(title, rows):
            self.top_cards_text.insert("end", title + "\n")
            self.top_cards_text.insert("end", "-" * len(title) + "\n")
            for row in rows:
                card = str(row.get("card", "Unknown"))
                cards = int(row.get("cards_sold") or 0)
                revenue = float(row.get("revenue") or 0)
                profit = float(row.get("profit") or 0)
                self.top_cards_text.insert("end", f"{card:<36} Sold {cards:>4}  Rev ${revenue:>9,.2f}  Profit ${profit:>9,.2f}\n")
            self.top_cards_text.insert("end", "\n")

        write_top("Top 20 Best Selling Cards", breakdowns.get("top_selling_cards", []))
        write_top("Top 20 Most Profitable Cards", breakdowns.get("top_profitable_cards", []))
        write_top("Top 20 Highest Revenue Cards", breakdowns.get("top_revenue_cards", []))

        self.sales_breakdown_text.configure(state="disabled")
        self.top_cards_text.configure(state="disabled")

    def _render_rarity_text(self, rows):
        self.rarity_text.configure(state="normal")
        self.rarity_text.delete("1.0", "end")

        self.rarity_text.insert("end", f"{'Rarity':<30}{'Cards Sold':>12}{'Revenue':>14}{'Profit':>14}\n")
        self.rarity_text.insert("end", "-" * 75 + "\n")

        for row in rows:
            rarity = str(row.get("rarity", "Unknown"))
            sold = int(row.get("cards_sold") or 0)
            revenue = float(row.get("revenue") or 0)
            profit = float(row.get("profit") or 0)
            self.rarity_text.insert("end", f"{rarity:<30}{sold:>12}${revenue:>13,.2f}${profit:>13,.2f}\n")

        self.rarity_text.configure(state="disabled")

    def _render_set_text(self, rows):
        self.set_text.configure(state="normal")
        self.set_text.delete("1.0", "end")

        self.set_text.insert(
            "end",
            f"{'Set':<10}{'Revenue':>14}{'Profit':>14}{'Sold':>8}{'Remain':>10}{'Inv Value':>14}{'Avg Price':>12}{'Sell Through':>14}\n",
        )
        self.set_text.insert("end", "-" * 110 + "\n")

        for row in rows:
            self.set_text.insert(
                "end",
                (
                    f"{str(row.get('set_id', 'Unknown')):<10}"
                    f"${float(row.get('revenue') or 0):>13,.2f}"
                    f"${float(row.get('profit') or 0):>13,.2f}"
                    f"{int(row.get('cards_sold') or 0):>8}"
                    f"{int(row.get('inventory_remaining') or 0):>10}"
                    f"${float(row.get('inventory_value') or 0):>13,.2f}"
                    f"${float(row.get('average_sale_price') or 0):>11,.2f}"
                    f"{float(row.get('sell_through_rate') or 0):>13.2f}%\n"
                ),
            )

        self.set_text.configure(state="disabled")

    # -------------------------
    # Export
    # -------------------------

    def export_csv(self):
        filters = self._current_filters()
        file_path = filedialog.asksaveasfilename(
            title="Export Business Analytics CSV",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")],
            initialfile="business_analytics_report.csv",
        )
        if not file_path:
            return

        result = self.service.export_csv(file_path, filters)
        self.status_label.configure(text=f"CSV exported: {result['rows']} rows")

    def export_excel(self):
        filters = self._current_filters()
        file_path = filedialog.asksaveasfilename(
            title="Export Business Analytics Excel",
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx")],
            initialfile="business_analytics_report.xlsx",
        )
        if not file_path:
            return

        result = self.service.export_excel(file_path, filters)
        self.status_label.configure(text=f"Excel exported: {result['rows']} rows")

    # -------------------------
    # Lifecycle
    # -------------------------

    def destroy(self):
        service = getattr(self, "service", None)
        if service is not None:
            service.close()
        super().destroy()
