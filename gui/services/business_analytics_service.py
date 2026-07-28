from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
import csv

from openpyxl import Workbook

from database.service import DatabaseService


class BusinessAnalyticsService:
    """Read-only business analytics service backed by the existing SQLite database."""

    def __init__(self):
        self.db_service = DatabaseService()
        self._cache = {}

    # -------------------------
    # Lifecycle
    # -------------------------

    def close(self):
        self.db_service.close()

    # -------------------------
    # Filters
    # -------------------------

    def resolve_date_range(self, preset, start_text="", end_text=""):
        today = date.today()
        preset_text = str(preset or "Lifetime")

        if preset_text == "Today":
            return today.isoformat(), today.isoformat()

        if preset_text == "This Week":
            start = today - timedelta(days=today.weekday())
            return start.isoformat(), today.isoformat()

        if preset_text == "This Month":
            start = today.replace(day=1)
            return start.isoformat(), today.isoformat()

        if preset_text == "Last 30 Days":
            start = today - timedelta(days=29)
            return start.isoformat(), today.isoformat()

        if preset_text == "Custom":
            parsed_start = self._parse_date(start_text)
            parsed_end = self._parse_date(end_text)
            return (
                parsed_start.isoformat() if parsed_start else "",
                parsed_end.isoformat() if parsed_end else "",
            )

        return "", ""

    def _sales_filters(self, filters):
        where = ["s.status = 'Completed'"]
        params = []

        start_date = str(filters.get("start_date") or "")
        end_date = str(filters.get("end_date") or "")
        platform = str(filters.get("platform") or "All")
        set_id = str(filters.get("set_id") or "All")
        card_query = str(filters.get("card_query") or "").strip().lower()
        finish = str(filters.get("finish") or "All")

        if start_date:
            where.append("DATE(s.sale_date) >= DATE(?)")
            params.append(start_date)

        if end_date:
            where.append("DATE(s.sale_date) <= DATE(?)")
            params.append(end_date)

        if platform != "All":
            where.append("LOWER(s.platform) = LOWER(?)")
            params.append(platform)

        if set_id != "All":
            where.append("LOWER(c.set_id) = LOWER(?)")
            params.append(set_id)

        if card_query:
            where.append("(LOWER(c.name) LIKE ? OR LOWER(c.number) LIKE ?)")
            token = f"%{card_query}%"
            params.extend([token, token])

        if finish != "All":
            where.append("LOWER(cf.finish) = LOWER(?)")
            params.append(finish)

        return " AND ".join(where), params

    def _inventory_filters(self, filters):
        where = ["1=1"]
        params = []

        set_id = str(filters.get("set_id") or "All")
        card_query = str(filters.get("card_query") or "").strip().lower()
        finish = str(filters.get("finish") or "All")

        if set_id != "All":
            where.append("LOWER(c.set_id) = LOWER(?)")
            params.append(set_id)

        if card_query:
            where.append("(LOWER(c.name) LIKE ? OR LOWER(c.number) LIKE ?)")
            token = f"%{card_query}%"
            params.extend([token, token])

        if finish != "All":
            where.append("LOWER(cf.finish) = LOWER(?)")
            params.append(finish)

        return " AND ".join(where), params

    # -------------------------
    # Caching
    # -------------------------

    def _cache_key(self, section, filters):
        return (
            section,
            str(filters.get("start_date") or ""),
            str(filters.get("end_date") or ""),
            str(filters.get("platform") or "All"),
            str(filters.get("set_id") or "All"),
            str(filters.get("card_query") or ""),
            str(filters.get("finish") or "All"),
        )

    def _get_cached(self, section, filters):
        key = self._cache_key(section, filters)
        record = self._cache.get(key)
        if record is None:
            return None

        now = datetime.now().timestamp()
        if now - record[0] > 30:
            self._cache.pop(key, None)
            return None

        return record[1]

    def _set_cached(self, section, filters, value):
        key = self._cache_key(section, filters)
        self._cache[key] = (datetime.now().timestamp(), value)

    # -------------------------
    # Option Lists
    # -------------------------

    def get_filter_options(self):
        sets = [dict(row) for row in self.db_service.db.fetchall("SELECT id, name FROM sets ORDER BY release_date DESC, id ASC")]

        platforms = [
            str(row["platform"])
            for row in self.db_service.db.fetchall(
                """
                SELECT DISTINCT platform
                FROM sales
                WHERE status = 'Completed'
                    AND platform IS NOT NULL
                    AND TRIM(platform) != ''
                ORDER BY LOWER(platform) ASC
                """
            )
        ]

        finishes = [
            str(row["finish"])
            for row in self.db_service.db.fetchall(
                """
                SELECT DISTINCT finish
                FROM card_finishes
                WHERE finish IS NOT NULL
                    AND TRIM(finish) != ''
                ORDER BY LOWER(finish) ASC
                """
            )
        ]

        return {
            "sets": sets,
            "platforms": platforms,
            "finishes": finishes,
        }

    # -------------------------
    # Summary Cards
    # -------------------------

    def get_summary_metrics(self, filters):
        cached = self._get_cached("summary", filters)
        if cached is not None:
            return cached

        sales_where, sales_params = self._sales_filters(filters)

        today = date.today().isoformat()
        month_start = date.today().replace(day=1).isoformat()

        row = self.db_service.db.fetchone(
            f"""
            SELECT
                COALESCE(SUM(CASE WHEN DATE(s.sale_date) = DATE(?) THEN s.sale_price ELSE 0 END), 0) AS today_revenue,
                COALESCE(SUM(CASE WHEN DATE(s.sale_date) >= DATE(?) THEN s.sale_price ELSE 0 END), 0) AS week_revenue,
                COALESCE(SUM(CASE WHEN DATE(s.sale_date) >= DATE(?) THEN s.sale_price ELSE 0 END), 0) AS month_revenue,
                COALESCE(SUM(s.sale_price), 0) AS lifetime_revenue,
                COALESCE(SUM(CASE WHEN DATE(s.sale_date) = DATE(?) THEN (s.sale_price - s.fees - s.shipping_cost) ELSE 0 END), 0) AS today_profit,
                COALESCE(SUM(CASE WHEN DATE(s.sale_date) >= DATE(?) THEN (s.sale_price - s.fees - s.shipping_cost) ELSE 0 END), 0) AS month_profit,
                COALESCE(SUM(s.sale_price - s.fees - s.shipping_cost), 0) AS lifetime_profit,
                COALESCE(SUM(s.quantity), 0) AS cards_sold,
                COUNT(DISTINCT COALESCE(NULLIF(TRIM(s.order_number), ''), s.sale_id)) AS orders,
                COALESCE(AVG(NULLIF(s.sale_price, 0)), 0) AS average_sale_price
            FROM sales s
            LEFT JOIN cards c
                ON c.id = s.card_id
            LEFT JOIN card_finishes cf
                ON cf.id = s.finish_id
            WHERE {sales_where}
            """,
            [today, self._week_start_iso(), month_start, today, month_start, *sales_params],
        )

        values = dict(row) if row else {}
        orders = int(values.get("orders") or 0)
        cards_sold = int(values.get("cards_sold") or 0)
        lifetime_revenue = float(values.get("lifetime_revenue") or 0)

        average_order_value = (lifetime_revenue / orders) if orders > 0 else 0.0
        average_sale_price = (lifetime_revenue / cards_sold) if cards_sold > 0 else 0.0

        inventory_values = self.get_inventory_value_totals(filters)

        summary = {
            "today_revenue": float(values.get("today_revenue") or 0),
            "week_revenue": float(values.get("week_revenue") or 0),
            "month_revenue": float(values.get("month_revenue") or 0),
            "lifetime_revenue": lifetime_revenue,
            "today_profit": float(values.get("today_profit") or 0),
            "month_profit": float(values.get("month_profit") or 0),
            "lifetime_profit": float(values.get("lifetime_profit") or 0),
            "cards_sold": cards_sold,
            "orders": orders,
            "average_order_value": average_order_value,
            "average_sale_price": average_sale_price,
            "inventory_value": float(inventory_values.get("sell_value") or 0),
            "potential_listing_value": float(inventory_values.get("potential_listing_value") or 0),
        }

        self._set_cached("summary", filters, summary)
        return summary

    # -------------------------
    # Inventory Analytics
    # -------------------------

    def get_inventory_metrics(self, filters):
        cached = self._get_cached("inventory", filters)
        if cached is not None:
            return cached

        where, params = self._inventory_filters(filters)

        row = self.db_service.db.fetchone(
            f"""
            SELECT
                COUNT(DISTINCT c.id) AS total_cards,
                COUNT(DISTINCT cf.id) AS total_finishes,
                COALESCE(SUM(CASE WHEN COALESCE(fw.quantity, 0) > 0 THEN fw.quantity ELSE 0 END), 0) AS items_in_stock,
                COUNT(CASE WHEN COALESCE(fw.quantity, 0) <= 0 THEN 1 END) AS out_of_stock,
                COUNT(CASE WHEN COALESCE(fw.quantity, 0) > 0
                                AND COALESCE(fw.sell_price, 0) > 0
                                AND TRIM(COALESCE(fw.image_path, cf.image_path, '')) != ''
                                AND TRIM(COALESCE(fw.github_url, cf.github_url, '')) != ''
                           THEN 1 END) AS ready_to_list,
                COUNT(CASE WHEN LOWER(COALESCE(fw.ebay_status, '')) IN ('queued', 'exporting') THEN 1 END) AS queued_for_ebay,
                COUNT(CASE WHEN LOWER(COALESCE(fw.ebay_status, '')) = 'exported' OR TRIM(COALESCE(fw.ebay_listing_id, '')) != '' THEN 1 END) AS listed,
                COUNT(CASE WHEN TRIM(COALESCE(fw.image_path, cf.image_path, '')) != '' THEN 1 END) AS images_complete,
                COUNT(CASE WHEN TRIM(COALESCE(fw.github_url, cf.github_url, '')) != '' THEN 1 END) AS github_uploaded,
                COALESCE(SUM(COALESCE(fw.quantity, 0) * COALESCE(fw.cost_price, 0)), 0) AS cost_value,
                COALESCE(SUM(COALESCE(fw.quantity, 0) * COALESCE(fw.market_price, 0)), 0) AS market_value,
                COALESCE(SUM(COALESCE(fw.quantity, 0) * COALESCE(fw.sell_price, 0)), 0) AS sell_value
            FROM card_finishes cf
            INNER JOIN cards c
                ON c.id = cf.card_id
            LEFT JOIN finish_workspace fw
                ON fw.finish_id = cf.id
            WHERE {where}
            """,
            params,
        )

        metrics = dict(row) if row else {}
        self._set_cached("inventory", filters, metrics)
        return metrics

    def get_inventory_value_totals(self, filters):
        metrics = self.get_inventory_metrics(filters)
        where, params = self._inventory_filters(filters)

        row = self.db_service.db.fetchone(
            f"""
            SELECT
                COALESCE(
                    SUM(
                        CASE
                            WHEN COALESCE(fw.quantity, 0) > 0
                                AND COALESCE(fw.sell_price, 0) > 0
                                AND TRIM(COALESCE(fw.image_path, cf.image_path, '')) != ''
                            THEN COALESCE(fw.quantity, 0) * COALESCE(fw.sell_price, 0)
                            ELSE 0
                        END
                    ),
                    0
                ) AS potential_listing_value
            FROM card_finishes cf
            INNER JOIN cards c
                ON c.id = cf.card_id
            LEFT JOIN finish_workspace fw
                ON fw.finish_id = cf.id
            WHERE {where}
            """,
            params,
        )

        potential = float((dict(row) if row else {}).get("potential_listing_value") or 0)

        return {
            "cost_value": float(metrics.get("cost_value") or 0),
            "market_value": float(metrics.get("market_value") or 0),
            "sell_value": float(metrics.get("sell_value") or 0),
            "potential_listing_value": potential,
        }

    # -------------------------
    # Profit Analytics
    # -------------------------

    def get_profit_metrics(self, filters):
        cached = self._get_cached("profit", filters)
        if cached is not None:
            return cached

        where, params = self._sales_filters(filters)

        row = self.db_service.db.fetchone(
            f"""
            SELECT
                COALESCE(SUM(s.sale_price), 0) AS gross_revenue,
                COALESCE(SUM(s.fees), 0) AS fees,
                COALESCE(SUM(s.shipping_cost), 0) AS shipping,
                COALESCE(SUM(s.sale_price - s.fees - s.shipping_cost), 0) AS net_profit,
                COALESCE(SUM(s.quantity), 0) AS cards_sold,
                COUNT(DISTINCT COALESCE(NULLIF(TRIM(s.order_number), ''), s.sale_id)) AS orders,
                COALESCE(SUM(COALESCE(fw.cost_price, 0) * s.quantity), 0) AS estimated_cogs
            FROM sales s
            LEFT JOIN cards c
                ON c.id = s.card_id
            LEFT JOIN card_finishes cf
                ON cf.id = s.finish_id
            LEFT JOIN finish_workspace fw
                ON fw.finish_id = s.finish_id
            WHERE {where}
            """,
            params,
        )

        values = dict(row) if row else {}
        gross = float(values.get("gross_revenue") or 0)
        net = float(values.get("net_profit") or 0)
        cards = int(values.get("cards_sold") or 0)
        orders = int(values.get("orders") or 0)
        cogs = float(values.get("estimated_cogs") or 0)

        margin = (net / gross * 100.0) if gross > 0 else 0.0
        avg_per_card = (net / cards) if cards > 0 else 0.0
        avg_per_order = (net / orders) if orders > 0 else 0.0

        if cogs > 0:
            roi = ((net - cogs) / cogs) * 100.0
        else:
            roi = 0.0

        metrics = {
            "gross_revenue": gross,
            "fees": float(values.get("fees") or 0),
            "shipping": float(values.get("shipping") or 0),
            "net_profit": net,
            "profit_margin_percent": margin,
            "average_profit_per_card": avg_per_card,
            "average_profit_per_order": avg_per_order,
            "roi_percent": roi,
        }

        self._set_cached("profit", filters, metrics)
        return metrics

    # -------------------------
    # Sales Analytics
    # -------------------------

    def get_time_series(self, filters):
        cached = self._get_cached("series", filters)
        if cached is not None:
            return cached

        where, params = self._sales_filters(filters)

        by_day = [
            dict(row)
            for row in self.db_service.db.fetchall(
                f"""
                SELECT
                    DATE(s.sale_date) AS label,
                    COALESCE(SUM(s.sale_price), 0) AS revenue,
                    COALESCE(SUM(s.sale_price - s.fees - s.shipping_cost), 0) AS profit
                FROM sales s
                LEFT JOIN cards c
                    ON c.id = s.card_id
                LEFT JOIN card_finishes cf
                    ON cf.id = s.finish_id
                WHERE {where}
                GROUP BY DATE(s.sale_date)
                ORDER BY DATE(s.sale_date) ASC
                """,
                params,
            )
        ]

        by_week = [
            dict(row)
            for row in self.db_service.db.fetchall(
                f"""
                SELECT
                    STRFTIME('%Y-W%W', DATE(s.sale_date)) AS label,
                    COALESCE(SUM(s.sale_price), 0) AS revenue
                FROM sales s
                LEFT JOIN cards c
                    ON c.id = s.card_id
                LEFT JOIN card_finishes cf
                    ON cf.id = s.finish_id
                WHERE {where}
                GROUP BY STRFTIME('%Y-W%W', DATE(s.sale_date))
                ORDER BY STRFTIME('%Y-W%W', DATE(s.sale_date)) ASC
                """,
                params,
            )
        ]

        by_month = [
            dict(row)
            for row in self.db_service.db.fetchall(
                f"""
                SELECT
                    STRFTIME('%Y-%m', DATE(s.sale_date)) AS label,
                    COALESCE(SUM(s.sale_price), 0) AS revenue
                FROM sales s
                LEFT JOIN cards c
                    ON c.id = s.card_id
                LEFT JOIN card_finishes cf
                    ON cf.id = s.finish_id
                WHERE {where}
                GROUP BY STRFTIME('%Y-%m', DATE(s.sale_date))
                ORDER BY STRFTIME('%Y-%m', DATE(s.sale_date)) ASC
                """,
                params,
            )
        ]

        series = {
            "by_day": by_day,
            "by_week": by_week,
            "by_month": by_month,
        }

        self._set_cached("series", filters, series)
        return series

    def get_group_breakdowns(self, filters):
        cached = self._get_cached("breakdowns", filters)
        if cached is not None:
            return cached

        where, params = self._sales_filters(filters)

        platforms = self._group_sales(
            where,
            params,
            "COALESCE(NULLIF(TRIM(s.platform), ''), 'Unknown')",
            "platform",
            "revenue DESC",
            20,
        )

        finishes = self._group_sales(
            where,
            params,
            "COALESCE(NULLIF(TRIM(cf.finish), ''), 'Unknown')",
            "finish",
            "revenue DESC",
            20,
        )

        sets = self._group_sales(
            where,
            params,
            "COALESCE(NULLIF(TRIM(c.set_id), ''), 'Unknown')",
            "set_id",
            "revenue DESC",
            50,
        )

        cards = self._group_sales(
            where,
            params,
            "COALESCE(NULLIF(TRIM(c.number || ' ' || c.name), ''), c.id)",
            "card",
            "revenue DESC",
            50,
        )

        top_selling_cards = self._group_sales(
            where,
            params,
            "COALESCE(NULLIF(TRIM(c.number || ' ' || c.name), ''), c.id)",
            "card",
            "cards_sold DESC",
            20,
        )

        top_profitable_cards = self._group_sales(
            where,
            params,
            "COALESCE(NULLIF(TRIM(c.number || ' ' || c.name), ''), c.id)",
            "card",
            "profit DESC",
            20,
        )

        top_revenue_cards = self._group_sales(
            where,
            params,
            "COALESCE(NULLIF(TRIM(c.number || ' ' || c.name), ''), c.id)",
            "card",
            "revenue DESC",
            20,
        )

        breakdowns = {
            "platforms": platforms,
            "finishes": finishes,
            "sets": sets,
            "cards": cards,
            "top_selling_cards": top_selling_cards,
            "top_profitable_cards": top_profitable_cards,
            "top_revenue_cards": top_revenue_cards,
        }

        self._set_cached("breakdowns", filters, breakdowns)
        return breakdowns

    def get_rarity_breakdown(self, filters):
        cached = self._get_cached("rarity", filters)
        if cached is not None:
            return cached

        where, params = self._sales_filters(filters)

        rows = [
            dict(row)
            for row in self.db_service.db.fetchall(
                f"""
                SELECT
                    COALESCE(NULLIF(TRIM(c.rarity), ''), 'Unknown') AS rarity,
                    COALESCE(SUM(s.quantity), 0) AS cards_sold,
                    COALESCE(SUM(s.sale_price), 0) AS revenue,
                    COALESCE(SUM(s.sale_price - s.fees - s.shipping_cost), 0) AS profit
                FROM sales s
                LEFT JOIN cards c
                    ON c.id = s.card_id
                LEFT JOIN card_finishes cf
                    ON cf.id = s.finish_id
                WHERE {where}
                GROUP BY COALESCE(NULLIF(TRIM(c.rarity), ''), 'Unknown')
                ORDER BY revenue DESC
                """,
                params,
            )
        ]

        requested_order = [
            "Common",
            "Uncommon",
            "Rare",
            "Double Rare",
            "Illustration Rare",
            "Special Illustration Rare",
            "Hyper Rare",
            "Promo",
            "Trainer",
            "Energy",
        ]

        grouped = {row["rarity"]: row for row in rows}
        ordered = []

        for rarity in requested_order:
            ordered.append(
                grouped.pop(
                    rarity,
                    {
                        "rarity": rarity,
                        "cards_sold": 0,
                        "revenue": 0.0,
                        "profit": 0.0,
                    },
                )
            )

        for leftover in sorted(grouped):
            ordered.append(grouped[leftover])

        self._set_cached("rarity", filters, ordered)
        return ordered

    # -------------------------
    # Set Analytics
    # -------------------------

    def get_set_analytics(self, filters):
        cached = self._get_cached("set_analytics", filters)
        if cached is not None:
            return cached

        sales_where, sales_params = self._sales_filters(filters)
        inventory_where, inventory_params = self._inventory_filters(filters)

        sales_rows = {
            row["set_id"]: dict(row)
            for row in self.db_service.db.fetchall(
                f"""
                SELECT
                    COALESCE(NULLIF(TRIM(c.set_id), ''), 'Unknown') AS set_id,
                    COALESCE(SUM(s.sale_price), 0) AS revenue,
                    COALESCE(SUM(s.sale_price - s.fees - s.shipping_cost), 0) AS profit,
                    COALESCE(SUM(s.quantity), 0) AS cards_sold,
                    COALESCE(AVG(NULLIF(s.sale_price, 0)), 0) AS average_sale_price
                FROM sales s
                LEFT JOIN cards c
                    ON c.id = s.card_id
                LEFT JOIN card_finishes cf
                    ON cf.id = s.finish_id
                WHERE {sales_where}
                GROUP BY COALESCE(NULLIF(TRIM(c.set_id), ''), 'Unknown')
                """,
                sales_params,
            )
        }

        inventory_rows = {
            row["set_id"]: dict(row)
            for row in self.db_service.db.fetchall(
                f"""
                SELECT
                    COALESCE(NULLIF(TRIM(c.set_id), ''), 'Unknown') AS set_id,
                    COALESCE(SUM(COALESCE(fw.quantity, 0)), 0) AS inventory_remaining,
                    COALESCE(SUM(COALESCE(fw.quantity, 0) * COALESCE(fw.sell_price, 0)), 0) AS inventory_value
                FROM card_finishes cf
                INNER JOIN cards c
                    ON c.id = cf.card_id
                LEFT JOIN finish_workspace fw
                    ON fw.finish_id = cf.id
                WHERE {inventory_where}
                GROUP BY COALESCE(NULLIF(TRIM(c.set_id), ''), 'Unknown')
                """,
                inventory_params,
            )
        }

        all_set_ids = sorted(set(sales_rows.keys()) | set(inventory_rows.keys()))
        merged = []

        for set_id in all_set_ids:
            sales = sales_rows.get(set_id, {})
            inventory = inventory_rows.get(set_id, {})

            cards_sold = float(sales.get("cards_sold") or 0)
            inventory_remaining = float(inventory.get("inventory_remaining") or 0)
            denominator = cards_sold + inventory_remaining
            sell_through = (cards_sold / denominator * 100.0) if denominator > 0 else 0.0

            merged.append(
                {
                    "set_id": set_id,
                    "revenue": float(sales.get("revenue") or 0),
                    "profit": float(sales.get("profit") or 0),
                    "cards_sold": int(cards_sold),
                    "inventory_remaining": int(inventory_remaining),
                    "inventory_value": float(inventory.get("inventory_value") or 0),
                    "average_sale_price": float(sales.get("average_sale_price") or 0),
                    "sell_through_rate": sell_through,
                }
            )

        merged.sort(key=lambda row: row["revenue"], reverse=True)
        self._set_cached("set_analytics", filters, merged)
        return merged

    # -------------------------
    # Export
    # -------------------------

    def get_export_rows(self, filters):
        where, params = self._sales_filters(filters)

        rows = [
            dict(row)
            for row in self.db_service.db.fetchall(
                f"""
                SELECT
                    s.sale_date,
                    COALESCE(NULLIF(TRIM(s.order_number), ''), s.sale_id) AS order_number,
                    s.platform,
                    c.set_id,
                    c.number,
                    c.name AS card_name,
                    cf.finish,
                    c.rarity,
                    s.quantity,
                    s.sale_price,
                    s.fees,
                    s.shipping_cost,
                    (s.sale_price - s.fees - s.shipping_cost) AS net_profit
                FROM sales s
                LEFT JOIN cards c
                    ON c.id = s.card_id
                LEFT JOIN card_finishes cf
                    ON cf.id = s.finish_id
                WHERE {where}
                ORDER BY DATE(s.sale_date) DESC, s.created_at DESC
                """,
                params,
            )
        ]

        return rows

    def export_csv(self, file_path, filters):
        rows = self.get_export_rows(filters)
        output = Path(file_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        fieldnames = [
            "sale_date",
            "order_number",
            "platform",
            "set_id",
            "number",
            "card_name",
            "finish",
            "rarity",
            "quantity",
            "sale_price",
            "fees",
            "shipping_cost",
            "net_profit",
        ]

        with output.open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow(row)

        return {
            "path": str(output),
            "rows": len(rows),
        }

    def export_excel(self, file_path, filters):
        rows = self.get_export_rows(filters)
        output = Path(file_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Business Analytics"

        headers = [
            "Sale Date",
            "Order Number",
            "Platform",
            "Set",
            "Number",
            "Card Name",
            "Finish",
            "Rarity",
            "Quantity",
            "Sale Price",
            "Fees",
            "Shipping",
            "Net Profit",
        ]
        sheet.append(headers)

        for row in rows:
            sheet.append(
                [
                    row.get("sale_date"),
                    row.get("order_number"),
                    row.get("platform"),
                    row.get("set_id"),
                    row.get("number"),
                    row.get("card_name"),
                    row.get("finish"),
                    row.get("rarity"),
                    row.get("quantity"),
                    row.get("sale_price"),
                    row.get("fees"),
                    row.get("shipping_cost"),
                    row.get("net_profit"),
                ]
            )

        workbook.save(output)

        return {
            "path": str(output),
            "rows": len(rows),
        }

    # -------------------------
    # Helpers
    # -------------------------

    def _group_sales(self, where, params, label_expression, label_name, order_by, limit):
        return [
            dict(row)
            for row in self.db_service.db.fetchall(
                f"""
                SELECT
                    {label_expression} AS {label_name},
                    COALESCE(SUM(s.quantity), 0) AS cards_sold,
                    COALESCE(SUM(s.sale_price), 0) AS revenue,
                    COALESCE(SUM(s.sale_price - s.fees - s.shipping_cost), 0) AS profit
                FROM sales s
                LEFT JOIN cards c
                    ON c.id = s.card_id
                LEFT JOIN card_finishes cf
                    ON cf.id = s.finish_id
                WHERE {where}
                GROUP BY {label_expression}
                ORDER BY {order_by}
                LIMIT {int(limit)}
                """,
                params,
            )
        ]

    def _parse_date(self, text):
        value = str(text or "").strip()
        if not value:
            return None

        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError:
            return None

    def _week_start_iso(self):
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        return week_start.isoformat()
