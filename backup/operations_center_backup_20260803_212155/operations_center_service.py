from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from database.service import DatabaseService


class OperationsCenterService:
    LOW_STOCK_THRESHOLD = 2

    def __init__(self):
        self.db_service = DatabaseService()
        self._cache = {}

    # -------------------------
    # Lifecycle
    # -------------------------

    def close(self):
        self.db_service.close()

    # -------------------------
    # Cache
    # -------------------------

    def _cache_get(self, key):
        item = self._cache.get(key)
        if item is None:
            return None

        timestamp, value = item
        if datetime.now().timestamp() - timestamp > 60:
            self._cache.pop(key, None)
            return None

        return value

    def _cache_set(self, key, value):
        self._cache[key] = (datetime.now().timestamp(), value)

    # -------------------------
    # Public API
    # -------------------------

    def get_operations_snapshot(self):
        cached = self._cache_get("snapshot")
        if cached is not None:
            return cached

        snapshot = {
            "inventory_health": self._inventory_health(),
            "sales_insights": self._sales_insights(),
            "pricing_suggestions": self._pricing_suggestions(),
            "listing_opportunities": self._listing_opportunities(),
            "business_alerts": self._business_alerts(),
        }
        snapshot["daily_score"] = self._daily_score(snapshot)

        self._cache_set("snapshot", snapshot)
        return snapshot

    def get_dashboard_widget(self):
        cached = self._cache_get("dashboard_widget")
        if cached is not None:
            return cached

        ready_count_row = self.db_service.db.fetchone(
            """
            SELECT COUNT(*) AS total
            FROM card_finishes cf
            INNER JOIN cards c
                ON c.id = cf.card_id
            LEFT JOIN finish_workspace fw
                ON fw.finish_id = cf.id
            WHERE COALESCE(fw.quantity, 0) > 0
                AND COALESCE(fw.sell_price, 0) > 0
                AND TRIM(COALESCE(fw.image_path, cf.image_path, '')) != ''
                AND TRIM(COALESCE(fw.github_url, cf.github_url, '')) != ''
                AND LOWER(COALESCE(fw.ebay_status, '')) NOT IN ('queued', 'exporting', 'exported')
            """
        )

        missing_images_row = self.db_service.db.fetchone(
            """
            SELECT COUNT(*) AS total
            FROM card_finishes cf
            LEFT JOIN finish_workspace fw
                ON fw.finish_id = cf.id
            WHERE COALESCE(fw.quantity, 0) > 0
                AND TRIM(COALESCE(fw.image_path, cf.image_path, '')) = ''
            """
        )

        pricing_issues_row = self.db_service.db.fetchone(
            """
            SELECT COUNT(*) AS total
            FROM card_finishes cf
            LEFT JOIN finish_workspace fw
                ON fw.finish_id = cf.id
            WHERE COALESCE(fw.quantity, 0) > 0
                AND COALESCE(fw.sell_price, 0) <= 0
            """
        )

        widget = {
            "ready_to_list": int(ready_count_row["total"] if ready_count_row else 0),
            "missing_images": int(missing_images_row["total"] if missing_images_row else 0),
            "pricing_issues": int(pricing_issues_row["total"] if pricing_issues_row else 0),
        }

        self._cache_set("dashboard_widget", widget)
        return widget

    # -------------------------
    # Rule Sections
    # -------------------------

    def _inventory_health(self):
        rows = []

        rows.extend(self._rule_running_low())
        rows.extend(self._rule_out_of_stock())
        rows.extend(self._rule_no_images())
        rows.extend(self._rule_no_pricing())
        rows.extend(self._rule_not_ready())
        rows.extend(self._rule_not_uploaded())
        rows.extend(self._rule_queued_too_long())
        rows.extend(self._rule_never_listed())

        return rows

    def _sales_insights(self):
        rows = []

        rows.extend(self._rule_best_selling_cards())
        rows.extend(self._rule_fastest_selling_sets())
        rows.extend(self._rule_highest_profit_cards())
        rows.extend(self._rule_highest_revenue_sets())
        rows.extend(self._rule_cards_with_no_sales())
        rows.extend(self._rule_cards_sitting_too_long())

        return rows

    def _pricing_suggestions(self):
        rows = []

        rows.extend(self._rule_priced_below_average())
        rows.extend(self._rule_zero_pricing())
        rows.extend(self._rule_unusually_high_pricing())
        rows.extend(self._rule_low_profit_margin())
        rows.extend(self._rule_discount_candidates())

        return rows

    def _listing_opportunities(self):
        rows = []

        rows.extend(self._rule_ready_to_publish_today())
        rows.extend(self._rule_high_value_unpublished_inventory())
        rows.extend(self._rule_sets_ready_for_completion())
        rows.extend(self._rule_missing_images_blocking_listing())
        rows.extend(self._rule_highest_revenue_potential_waiting())

        return rows

    def _business_alerts(self):
        rows = []

        rows.extend(self._alert_inventory_below_threshold())
        rows.extend(self._alert_no_sales_in_days())
        rows.extend(self._alert_github_upload_failures())
        rows.extend(self._alert_export_failures())
        rows.extend(self._alert_large_pricing_inconsistencies())
        rows.extend(self._alert_duplicate_cards())
        rows.extend(self._alert_missing_images())
        rows.extend(self._alert_backup_overdue())

        return rows

    # -------------------------
    # Daily Score
    # -------------------------

    def _daily_score(self, snapshot):
        total_finishes_row = self.db_service.db.fetchone("SELECT COUNT(*) AS total FROM card_finishes")
        total_finishes = int(total_finishes_row["total"] if total_finishes_row else 0)
        total_finishes = max(1, total_finishes)

        inventory_bad = len([r for r in snapshot["inventory_health"] if r["severity"] == "high"])
        image_missing = len([r for r in snapshot["inventory_health"] if r["rule"] == "no_images"])
        pricing_bad = len([r for r in snapshot["pricing_suggestions"] if r["severity"] != "low"])

        ready_row = self.db_service.db.fetchone(
            """
            SELECT COUNT(*) AS total
            FROM card_finishes cf
            LEFT JOIN finish_workspace fw
                ON fw.finish_id = cf.id
            WHERE COALESCE(fw.quantity, 0) > 0
                AND COALESCE(fw.sell_price, 0) > 0
                AND TRIM(COALESCE(fw.image_path, cf.image_path, '')) != ''
            """
        )
        ready_count = int(ready_row["total"] if ready_row else 0)

        sales_week_row = self.db_service.db.fetchone(
            """
            SELECT COUNT(*) AS total
            FROM sales
            WHERE status = 'Completed'
                AND DATE(sale_date) >= DATE('now', '-7 day')
            """
        )
        sales_week = int(sales_week_row["total"] if sales_week_row else 0)

        inventory_health_score = max(0, min(100, int(100 - (inventory_bad * 3))))
        listing_readiness_score = max(0, min(100, int((ready_count / total_finishes) * 100)))
        pricing_quality_score = max(0, min(100, int(100 - (pricing_bad * 4))))
        image_coverage_score = max(0, min(100, int(100 - (image_missing * 3))))
        sales_activity_score = max(0, min(100, int(min(100, sales_week * 8))))

        overall = int(
            (
                inventory_health_score
                + listing_readiness_score
                + pricing_quality_score
                + image_coverage_score
                + sales_activity_score
            )
            / 5
        )

        return {
            "inventory_health": inventory_health_score,
            "listing_readiness": listing_readiness_score,
            "pricing_quality": pricing_quality_score,
            "image_coverage": image_coverage_score,
            "sales_activity": sales_activity_score,
            "overall_business_health": overall,
        }

    # -------------------------
    # Rule Implementations
    # -------------------------

    def _rule_running_low(self):
        rows = self.db_service.db.fetchall(
            """
            SELECT
                cf.id AS finish_id,
                c.set_id,
                c.number,
                c.name,
                cf.finish,
                COALESCE(fw.quantity, 0) AS quantity
            FROM card_finishes cf
            INNER JOIN cards c ON c.id = cf.card_id
            LEFT JOIN finish_workspace fw ON fw.finish_id = cf.id
            WHERE COALESCE(fw.quantity, 0) > 0
                AND COALESCE(fw.quantity, 0) <= ?
            ORDER BY COALESCE(fw.quantity, 0) ASC, c.set_id ASC, c.number ASC
            LIMIT 12
            """,
            (self.LOW_STOCK_THRESHOLD,),
        )

        return [
            self._rec(
                "running_low",
                "medium",
                f"Low stock: {row['set_id'].upper()} #{row['number']} {row['name']} ({row['finish']})",
                f"Only {int(row['quantity'])} left in inventory.",
                "Open Card",
                {"action": "open_card", "set_id": row["set_id"], "finish_id": row["finish_id"]},
            )
            for row in rows
        ]

    def _rule_out_of_stock(self):
        rows = self.db_service.db.fetchall(
            """
            SELECT cf.id AS finish_id, c.set_id, c.number, c.name, cf.finish
            FROM card_finishes cf
            INNER JOIN cards c ON c.id = cf.card_id
            LEFT JOIN finish_workspace fw ON fw.finish_id = cf.id
            WHERE COALESCE(fw.quantity, 0) <= 0
            ORDER BY c.set_id ASC, c.number ASC
            LIMIT 12
            """
        )

        return [
            self._rec(
                "out_of_stock",
                "high",
                f"Out of stock: {row['set_id'].upper()} #{row['number']} {row['name']} ({row['finish']})",
                "No inventory quantity available.",
                "Open Inventory",
                {"action": "open_inventory", "set_id": row["set_id"], "finish_id": row["finish_id"]},
            )
            for row in rows
        ]

    def _rule_no_images(self):
        rows = self.db_service.db.fetchall(
            """
            SELECT cf.id AS finish_id, c.set_id, c.number, c.name, cf.finish
            FROM card_finishes cf
            INNER JOIN cards c ON c.id = cf.card_id
            LEFT JOIN finish_workspace fw ON fw.finish_id = cf.id
            WHERE COALESCE(fw.quantity, 0) > 0
                AND TRIM(COALESCE(fw.image_path, cf.image_path, '')) = ''
            ORDER BY c.set_id ASC, c.number ASC
            LIMIT 12
            """
        )

        return [
            self._rec(
                "no_images",
                "high",
                f"Missing image: {row['set_id'].upper()} #{row['number']} {row['name']} ({row['finish']})",
                "Image is required before listing.",
                "Open Images",
                {"action": "open_images", "set_id": row["set_id"], "finish_id": row["finish_id"]},
            )
            for row in rows
        ]

    def _rule_no_pricing(self):
        rows = self.db_service.db.fetchall(
            """
            SELECT cf.id AS finish_id, c.set_id, c.number, c.name, cf.finish
            FROM card_finishes cf
            INNER JOIN cards c ON c.id = cf.card_id
            LEFT JOIN finish_workspace fw ON fw.finish_id = cf.id
            WHERE COALESCE(fw.quantity, 0) > 0
                AND COALESCE(fw.sell_price, 0) <= 0
            ORDER BY c.set_id ASC, c.number ASC
            LIMIT 12
            """
        )

        return [
            self._rec(
                "no_pricing",
                "high",
                f"No pricing: {row['set_id'].upper()} #{row['number']} {row['name']} ({row['finish']})",
                "Set sell price to enable listing.",
                "Open Pricing",
                {"action": "open_pricing", "set_id": row["set_id"], "finish_id": row["finish_id"]},
            )
            for row in rows
        ]

    def _rule_not_ready(self):
        rows = self.db_service.db.fetchall(
            """
            SELECT cf.id AS finish_id, c.set_id, c.number, c.name, cf.finish
            FROM card_finishes cf
            INNER JOIN cards c ON c.id = cf.card_id
            LEFT JOIN finish_workspace fw ON fw.finish_id = cf.id
            WHERE COALESCE(fw.quantity, 0) > 0
                AND (
                    COALESCE(fw.sell_price, 0) <= 0
                    OR TRIM(COALESCE(fw.image_path, cf.image_path, '')) = ''
                    OR TRIM(COALESCE(fw.github_url, cf.github_url, '')) = ''
                )
            ORDER BY c.set_id ASC, c.number ASC
            LIMIT 12
            """
        )

        return [
            self._rec(
                "not_ready",
                "medium",
                f"Not ready: {row['set_id'].upper()} #{row['number']} {row['name']} ({row['finish']})",
                "Complete pricing/image/upload requirements.",
                "Open Card",
                {"action": "open_card", "set_id": row["set_id"], "finish_id": row["finish_id"]},
            )
            for row in rows
        ]

    def _rule_not_uploaded(self):
        rows = self.db_service.db.fetchall(
            """
            SELECT cf.id AS finish_id, c.set_id, c.number, c.name, cf.finish
            FROM card_finishes cf
            INNER JOIN cards c ON c.id = cf.card_id
            LEFT JOIN finish_workspace fw ON fw.finish_id = cf.id
            WHERE COALESCE(fw.quantity, 0) > 0
                AND COALESCE(fw.sell_price, 0) > 0
                AND TRIM(COALESCE(fw.image_path, cf.image_path, '')) != ''
                AND TRIM(COALESCE(fw.github_url, cf.github_url, '')) = ''
            ORDER BY c.set_id ASC, c.number ASC
            LIMIT 12
            """
        )

        return [
            self._rec(
                "not_uploaded",
                "medium",
                f"Not uploaded to GitHub: {row['set_id'].upper()} #{row['number']} {row['name']} ({row['finish']})",
                "Upload image to GitHub before eBay export.",
                "Open Card",
                {"action": "open_card", "set_id": row["set_id"], "finish_id": row["finish_id"]},
            )
            for row in rows
        ]

    def _rule_queued_too_long(self):
        rows = self.db_service.db.fetchall(
            """
            SELECT
                cf.id AS finish_id,
                c.set_id,
                c.number,
                c.name,
                cf.finish,
                fw.queued_at
            FROM card_finishes cf
            INNER JOIN cards c ON c.id = cf.card_id
            LEFT JOIN finish_workspace fw ON fw.finish_id = cf.id
            WHERE LOWER(COALESCE(fw.ebay_status, '')) IN ('queued', 'exporting')
                AND fw.queued_at IS NOT NULL
                AND TRIM(fw.queued_at) != ''
                AND DATETIME(fw.queued_at) < DATETIME('now', '-2 day')
            ORDER BY DATETIME(fw.queued_at) ASC
            LIMIT 12
            """
        )

        return [
            self._rec(
                "queued_too_long",
                "medium",
                f"Queued too long: {row['set_id'].upper()} #{row['number']} {row['name']} ({row['finish']})",
                f"Queued at {row['queued_at']}.",
                "Generate CSV",
                {"action": "generate_csv", "set_id": row["set_id"], "finish_id": row["finish_id"]},
            )
            for row in rows
        ]

    def _rule_never_listed(self):
        rows = self.db_service.db.fetchall(
            """
            SELECT cf.id AS finish_id, c.set_id, c.number, c.name, cf.finish
            FROM card_finishes cf
            INNER JOIN cards c ON c.id = cf.card_id
            LEFT JOIN finish_workspace fw ON fw.finish_id = cf.id
            WHERE COALESCE(fw.quantity, 0) > 0
                AND COALESCE(fw.sell_price, 0) > 0
                AND TRIM(COALESCE(fw.image_path, cf.image_path, '')) != ''
                AND TRIM(COALESCE(fw.github_url, cf.github_url, '')) != ''
                AND TRIM(COALESCE(fw.ebay_listing_id, '')) = ''
                AND LOWER(COALESCE(fw.ebay_status, '')) NOT IN ('queued', 'exporting', 'exported')
            ORDER BY c.set_id ASC, c.number ASC
            LIMIT 12
            """
        )

        return [
            self._rec(
                "never_listed",
                "low",
                f"Never listed: {row['set_id'].upper()} #{row['number']} {row['name']} ({row['finish']})",
                "Meets requirements and can be queued now.",
                "Queue for eBay",
                {"action": "queue_ebay", "set_id": row["set_id"], "finish_id": row["finish_id"]},
            )
            for row in rows
        ]

    def _rule_best_selling_cards(self):
        rows = self.db_service.db.fetchall(
            """
            SELECT
                c.set_id,
                c.number,
                c.name,
                COALESCE(SUM(s.quantity), 0) AS qty
            FROM sales s
            INNER JOIN cards c ON c.id = s.card_id
            WHERE s.status = 'Completed'
            GROUP BY c.id, c.set_id, c.number, c.name
            ORDER BY qty DESC
            LIMIT 10
            """
        )

        return [
            self._rec(
                "best_selling_cards",
                "low",
                f"Best seller: {row['set_id'].upper()} #{row['number']} {row['name']}",
                f"{int(row['qty'])} sold.",
                "Record Sale",
                {"action": "record_sale", "set_id": row["set_id"]},
            )
            for row in rows
        ]

    def _rule_fastest_selling_sets(self):
        rows = self.db_service.db.fetchall(
            """
            SELECT
                c.set_id,
                COALESCE(SUM(s.quantity), 0) AS qty,
                CAST(
                    COALESCE(SUM(s.quantity), 0)
                    /
                    CASE
                        WHEN JULIANDAY(MAX(DATE(s.sale_date))) - JULIANDAY(MIN(DATE(s.sale_date))) + 1 <= 0
                            THEN 1
                        ELSE JULIANDAY(MAX(DATE(s.sale_date))) - JULIANDAY(MIN(DATE(s.sale_date))) + 1
                    END
                    AS REAL
                ) AS velocity
            FROM sales s
            INNER JOIN cards c ON c.id = s.card_id
            WHERE s.status = 'Completed'
            GROUP BY c.set_id
            HAVING qty > 0
            ORDER BY velocity DESC
            LIMIT 8
            """
        )

        return [
            self._rec(
                "fastest_selling_sets",
                "low",
                f"Fast set: {str(row['set_id']).upper()}",
                f"Velocity {float(row['velocity']):.2f} cards/day ({int(row['qty'])} sold).",
                "Open Card",
                {"action": "open_card", "set_id": row["set_id"]},
            )
            for row in rows
        ]

    def _rule_highest_profit_cards(self):
        rows = self.db_service.db.fetchall(
            """
            SELECT
                c.set_id,
                c.number,
                c.name,
                COALESCE(SUM(s.sale_price - s.fees - s.shipping_cost), 0) AS profit
            FROM sales s
            INNER JOIN cards c ON c.id = s.card_id
            WHERE s.status = 'Completed'
            GROUP BY c.id, c.set_id, c.number, c.name
            ORDER BY profit DESC
            LIMIT 10
            """
        )

        return [
            self._rec(
                "highest_profit_cards",
                "low",
                f"High profit card: {row['set_id'].upper()} #{row['number']} {row['name']}",
                f"Net profit ${float(row['profit']):,.2f}.",
                "Open Pricing",
                {"action": "open_pricing", "set_id": row["set_id"]},
            )
            for row in rows
        ]

    def _rule_highest_revenue_sets(self):
        rows = self.db_service.db.fetchall(
            """
            SELECT
                c.set_id,
                COALESCE(SUM(s.sale_price), 0) AS revenue
            FROM sales s
            INNER JOIN cards c ON c.id = s.card_id
            WHERE s.status = 'Completed'
            GROUP BY c.set_id
            ORDER BY revenue DESC
            LIMIT 8
            """
        )

        return [
            self._rec(
                "highest_revenue_sets",
                "low",
                f"High revenue set: {str(row['set_id']).upper()}",
                f"Revenue ${float(row['revenue']):,.2f}.",
                "Open Card",
                {"action": "open_card", "set_id": row["set_id"]},
            )
            for row in rows
        ]

    def _rule_cards_with_no_sales(self):
        rows = self.db_service.db.fetchall(
            """
            SELECT
                cf.id AS finish_id,
                c.set_id,
                c.number,
                c.name,
                cf.finish,
                COALESCE(fw.quantity, 0) AS quantity
            FROM card_finishes cf
            INNER JOIN cards c ON c.id = cf.card_id
            LEFT JOIN finish_workspace fw ON fw.finish_id = cf.id
            LEFT JOIN sales s
                ON s.finish_id = cf.id
                AND s.status = 'Completed'
            WHERE s.sale_id IS NULL
                AND COALESCE(fw.quantity, 0) > 0
            ORDER BY COALESCE(fw.quantity, 0) DESC, c.set_id ASC
            LIMIT 12
            """
        )

        return [
            self._rec(
                "cards_with_no_sales",
                "medium",
                f"No sales yet: {row['set_id'].upper()} #{row['number']} {row['name']} ({row['finish']})",
                f"Stock on hand: {int(row['quantity'])}.",
                "Open Pricing",
                {"action": "open_pricing", "set_id": row["set_id"], "finish_id": row["finish_id"]},
            )
            for row in rows
        ]

    def _rule_cards_sitting_too_long(self):
        rows = self.db_service.db.fetchall(
            """
            SELECT
                cf.id AS finish_id,
                c.set_id,
                c.number,
                c.name,
                cf.finish,
                COALESCE(fw.quantity, 0) AS quantity,
                MAX(DATE(s.sale_date)) AS last_sale_date
            FROM card_finishes cf
            INNER JOIN cards c ON c.id = cf.card_id
            LEFT JOIN finish_workspace fw ON fw.finish_id = cf.id
            LEFT JOIN sales s
                ON s.finish_id = cf.id
                AND s.status = 'Completed'
            WHERE COALESCE(fw.quantity, 0) > 0
            GROUP BY cf.id, c.set_id, c.number, c.name, cf.finish, fw.quantity
            HAVING last_sale_date IS NULL
                OR DATE(last_sale_date) < DATE('now', '-60 day')
            ORDER BY COALESCE(fw.quantity, 0) DESC
            LIMIT 12
            """
        )

        suggestions = []
        for row in rows:
            last_sale = row["last_sale_date"] or "Never"
            suggestions.append(
                self._rec(
                    "cards_sitting_too_long",
                    "medium",
                    f"Slow mover: {row['set_id'].upper()} #{row['number']} {row['name']} ({row['finish']})",
                    f"Last sale: {last_sale}. Quantity: {int(row['quantity'])}.",
                    "Open Pricing",
                    {"action": "open_pricing", "set_id": row["set_id"], "finish_id": row["finish_id"]},
                )
            )

        return suggestions

    def _rule_priced_below_average(self):
        rows = self.db_service.db.fetchall(
            """
            SELECT
                cf.id AS finish_id,
                c.set_id,
                c.number,
                c.name,
                cf.finish,
                COALESCE(fw.sell_price, 0) AS sell_price,
                stats.avg_price
            FROM card_finishes cf
            INNER JOIN cards c ON c.id = cf.card_id
            LEFT JOIN finish_workspace fw ON fw.finish_id = cf.id
            INNER JOIN (
                SELECT
                    c2.rarity,
                    cf2.finish,
                    AVG(s2.sale_price / CASE WHEN s2.quantity <= 0 THEN 1 ELSE s2.quantity END) AS avg_price,
                    COUNT(*) AS count_rows
                FROM sales s2
                INNER JOIN cards c2 ON c2.id = s2.card_id
                INNER JOIN card_finishes cf2 ON cf2.id = s2.finish_id
                WHERE s2.status = 'Completed'
                GROUP BY c2.rarity, cf2.finish
                HAVING count_rows >= 3
            ) stats
                ON stats.rarity = c.rarity
                AND stats.finish = cf.finish
            WHERE COALESCE(fw.quantity, 0) > 0
                AND COALESCE(fw.sell_price, 0) > 0
                AND COALESCE(fw.sell_price, 0) < stats.avg_price * 0.7
            ORDER BY (stats.avg_price - COALESCE(fw.sell_price, 0)) DESC
            LIMIT 10
            """
        )

        return [
            self._rec(
                "priced_below_average",
                "medium",
                f"Underpriced: {row['set_id'].upper()} #{row['number']} {row['name']} ({row['finish']})",
                f"Current ${float(row['sell_price']):.2f} vs avg ${float(row['avg_price']):.2f}.",
                "Open Pricing",
                {"action": "open_pricing", "set_id": row["set_id"], "finish_id": row["finish_id"]},
            )
            for row in rows
        ]

    def _rule_zero_pricing(self):
        return self._rule_no_pricing()

    def _rule_unusually_high_pricing(self):
        rows = self.db_service.db.fetchall(
            """
            SELECT
                cf.id AS finish_id,
                c.set_id,
                c.number,
                c.name,
                cf.finish,
                COALESCE(fw.sell_price, 0) AS sell_price,
                stats.avg_price
            FROM card_finishes cf
            INNER JOIN cards c ON c.id = cf.card_id
            LEFT JOIN finish_workspace fw ON fw.finish_id = cf.id
            INNER JOIN (
                SELECT
                    c2.rarity,
                    cf2.finish,
                    AVG(s2.sale_price / CASE WHEN s2.quantity <= 0 THEN 1 ELSE s2.quantity END) AS avg_price,
                    COUNT(*) AS count_rows
                FROM sales s2
                INNER JOIN cards c2 ON c2.id = s2.card_id
                INNER JOIN card_finishes cf2 ON cf2.id = s2.finish_id
                WHERE s2.status = 'Completed'
                GROUP BY c2.rarity, cf2.finish
                HAVING count_rows >= 3
            ) stats
                ON stats.rarity = c.rarity
                AND stats.finish = cf.finish
            WHERE COALESCE(fw.quantity, 0) > 0
                AND COALESCE(fw.sell_price, 0) > stats.avg_price * 1.5
            ORDER BY COALESCE(fw.sell_price, 0) DESC
            LIMIT 10
            """
        )

        return [
            self._rec(
                "unusually_high_pricing",
                "medium",
                f"Overpriced: {row['set_id'].upper()} #{row['number']} {row['name']} ({row['finish']})",
                f"Current ${float(row['sell_price']):.2f} vs avg ${float(row['avg_price']):.2f}.",
                "Open Pricing",
                {"action": "open_pricing", "set_id": row["set_id"], "finish_id": row["finish_id"]},
            )
            for row in rows
        ]

    def _rule_low_profit_margin(self):
        rows = self.db_service.db.fetchall(
            """
            SELECT
                cf.id AS finish_id,
                c.set_id,
                c.number,
                c.name,
                cf.finish,
                COALESCE(SUM(s.sale_price), 0) AS revenue,
                COALESCE(SUM(s.sale_price - s.fees - s.shipping_cost), 0) AS profit
            FROM sales s
            INNER JOIN card_finishes cf ON cf.id = s.finish_id
            INNER JOIN cards c ON c.id = cf.card_id
            WHERE s.status = 'Completed'
            GROUP BY cf.id, c.set_id, c.number, c.name, cf.finish
            HAVING revenue > 0
                AND (profit / revenue) < 0.15
            ORDER BY (profit / revenue) ASC
            LIMIT 10
            """
        )

        recs = []
        for row in rows:
            margin = (float(row["profit"]) / float(row["revenue"])) * 100 if float(row["revenue"]) > 0 else 0
            recs.append(
                self._rec(
                    "low_profit_margin",
                    "medium",
                    f"Low margin: {row['set_id'].upper()} #{row['number']} {row['name']} ({row['finish']})",
                    f"Margin {margin:.2f}%.",
                    "Open Pricing",
                    {"action": "open_pricing", "set_id": row["set_id"], "finish_id": row["finish_id"]},
                )
            )

        return recs

    def _rule_discount_candidates(self):
        rows = self.db_service.db.fetchall(
            """
            SELECT
                cf.id AS finish_id,
                c.set_id,
                c.number,
                c.name,
                cf.finish,
                COALESCE(fw.quantity, 0) AS quantity,
                COALESCE(fw.sell_price, 0) AS sell_price,
                MAX(DATE(s.sale_date)) AS last_sale_date
            FROM card_finishes cf
            INNER JOIN cards c ON c.id = cf.card_id
            LEFT JOIN finish_workspace fw ON fw.finish_id = cf.id
            LEFT JOIN sales s
                ON s.finish_id = cf.id
                AND s.status = 'Completed'
            WHERE COALESCE(fw.quantity, 0) >= 5
                AND COALESCE(fw.sell_price, 0) > 0
            GROUP BY cf.id, c.set_id, c.number, c.name, cf.finish, fw.quantity, fw.sell_price
            HAVING last_sale_date IS NULL OR DATE(last_sale_date) < DATE('now', '-45 day')
            ORDER BY COALESCE(fw.quantity, 0) DESC
            LIMIT 10
            """
        )

        return [
            self._rec(
                "discount_candidates",
                "low",
                f"Discount candidate: {row['set_id'].upper()} #{row['number']} {row['name']} ({row['finish']})",
                f"Qty {int(row['quantity'])}, no recent sales.",
                "Open Pricing",
                {"action": "open_pricing", "set_id": row["set_id"], "finish_id": row["finish_id"]},
            )
            for row in rows
        ]

    def _rule_ready_to_publish_today(self):
        rows = self.db_service.db.fetchall(
            """
            SELECT cf.id AS finish_id, c.set_id, c.number, c.name, cf.finish
            FROM card_finishes cf
            INNER JOIN cards c ON c.id = cf.card_id
            LEFT JOIN finish_workspace fw ON fw.finish_id = cf.id
            WHERE COALESCE(fw.quantity, 0) > 0
                AND COALESCE(fw.sell_price, 0) > 0
                AND TRIM(COALESCE(fw.image_path, cf.image_path, '')) != ''
                AND TRIM(COALESCE(fw.github_url, cf.github_url, '')) != ''
                AND LOWER(COALESCE(fw.ebay_status, '')) NOT IN ('queued', 'exporting', 'exported')
            ORDER BY c.set_id ASC, c.number ASC
            LIMIT 12
            """
        )

        return [
            self._rec(
                "ready_to_publish_today",
                "low",
                f"Ready to publish: {row['set_id'].upper()} #{row['number']} {row['name']} ({row['finish']})",
                "All listing requirements complete.",
                "Queue for eBay",
                {"action": "queue_ebay", "set_id": row["set_id"], "finish_id": row["finish_id"]},
            )
            for row in rows
        ]

    def _rule_high_value_unpublished_inventory(self):
        rows = self.db_service.db.fetchall(
            """
            SELECT
                cf.id AS finish_id,
                c.set_id,
                c.number,
                c.name,
                cf.finish,
                COALESCE(fw.quantity, 0) AS quantity,
                COALESCE(fw.sell_price, 0) AS sell_price,
                (COALESCE(fw.quantity, 0) * COALESCE(fw.sell_price, 0)) AS value_total
            FROM card_finishes cf
            INNER JOIN cards c ON c.id = cf.card_id
            LEFT JOIN finish_workspace fw ON fw.finish_id = cf.id
            WHERE COALESCE(fw.quantity, 0) > 0
                AND COALESCE(fw.sell_price, 0) > 0
                AND LOWER(COALESCE(fw.ebay_status, '')) NOT IN ('queued', 'exporting', 'exported')
            ORDER BY value_total DESC
            LIMIT 10
            """
        )

        return [
            self._rec(
                "high_value_unpublished_inventory",
                "medium",
                f"High value waiting: {row['set_id'].upper()} #{row['number']} {row['name']} ({row['finish']})",
                f"Unpublished value ${float(row['value_total']):,.2f}.",
                "Queue for eBay",
                {"action": "queue_ebay", "set_id": row["set_id"], "finish_id": row["finish_id"]},
            )
            for row in rows
        ]

    def _rule_sets_ready_for_completion(self):
        rows = self.db_service.db.fetchall(
            """
            SELECT
                c.set_id,
                COUNT(*) AS total,
                SUM(
                    CASE
                        WHEN COALESCE(fw.quantity, 0) > 0
                            AND COALESCE(fw.sell_price, 0) > 0
                            AND TRIM(COALESCE(fw.image_path, cf.image_path, '')) != ''
                            AND TRIM(COALESCE(fw.github_url, cf.github_url, '')) != ''
                        THEN 1
                        ELSE 0
                    END
                ) AS ready
            FROM card_finishes cf
            INNER JOIN cards c ON c.id = cf.card_id
            LEFT JOIN finish_workspace fw ON fw.finish_id = cf.id
            GROUP BY c.set_id
            HAVING total > 0
                AND (CAST(ready AS REAL) / total) >= 0.8
                AND ready < total
            ORDER BY (CAST(ready AS REAL) / total) DESC
            LIMIT 8
            """
        )

        recs = []
        for row in rows:
            pct = (float(row["ready"]) / float(row["total"])) * 100 if float(row["total"]) > 0 else 0
            recs.append(
                self._rec(
                    "sets_ready_for_completion",
                    "low",
                    f"Set near completion: {str(row['set_id']).upper()}",
                    f"{int(row['ready'])}/{int(row['total'])} ready ({pct:.1f}%).",
                    "Open Card",
                    {"action": "open_card", "set_id": row["set_id"]},
                )
            )

        return recs

    def _rule_missing_images_blocking_listing(self):
        rows = self.db_service.db.fetchall(
            """
            SELECT cf.id AS finish_id, c.set_id, c.number, c.name, cf.finish
            FROM card_finishes cf
            INNER JOIN cards c ON c.id = cf.card_id
            LEFT JOIN finish_workspace fw ON fw.finish_id = cf.id
            WHERE COALESCE(fw.quantity, 0) > 0
                AND COALESCE(fw.sell_price, 0) > 0
                AND TRIM(COALESCE(fw.image_path, cf.image_path, '')) = ''
            ORDER BY c.set_id ASC, c.number ASC
            LIMIT 12
            """
        )

        return [
            self._rec(
                "missing_images_blocking_listing",
                "high",
                f"Image blocking listing: {row['set_id'].upper()} #{row['number']} {row['name']} ({row['finish']})",
                "Add image to unlock publish readiness.",
                "Open Images",
                {"action": "open_images", "set_id": row["set_id"], "finish_id": row["finish_id"]},
            )
            for row in rows
        ]

    def _rule_highest_revenue_potential_waiting(self):
        rows = self.db_service.db.fetchall(
            """
            SELECT
                cf.id AS finish_id,
                c.set_id,
                c.number,
                c.name,
                cf.finish,
                (COALESCE(fw.quantity, 0) * COALESCE(fw.sell_price, 0)) AS value_total
            FROM card_finishes cf
            INNER JOIN cards c ON c.id = cf.card_id
            LEFT JOIN finish_workspace fw ON fw.finish_id = cf.id
            WHERE COALESCE(fw.quantity, 0) > 0
                AND COALESCE(fw.sell_price, 0) > 0
                AND TRIM(COALESCE(fw.image_path, cf.image_path, '')) != ''
                AND TRIM(COALESCE(fw.github_url, cf.github_url, '')) != ''
                AND LOWER(COALESCE(fw.ebay_status, '')) NOT IN ('queued', 'exporting', 'exported')
            ORDER BY value_total DESC
            LIMIT 10
            """
        )

        return [
            self._rec(
                "highest_revenue_potential_waiting",
                "medium",
                f"Revenue potential waiting: {row['set_id'].upper()} #{row['number']} {row['name']} ({row['finish']})",
                f"Potential ${float(row['value_total']):,.2f}.",
                "Queue for eBay",
                {"action": "queue_ebay", "set_id": row["set_id"], "finish_id": row["finish_id"]},
            )
            for row in rows
        ]

    def _alert_inventory_below_threshold(self):
        row = self.db_service.db.fetchone(
            """
            SELECT COALESCE(SUM(COALESCE(fw.quantity, 0)), 0) AS total_quantity
            FROM finish_workspace fw
            """
        )

        total = int(row["total_quantity"] if row else 0)
        if total >= 100:
            return []

        return [
            self._rec(
                "alert_inventory_below_threshold",
                "high",
                "Inventory below threshold",
                f"Total finish quantity is {total}.",
                "Open Inventory",
                {"action": "open_inventory"},
            )
        ]

    def _alert_no_sales_in_days(self):
        row = self.db_service.db.fetchone(
            """
            SELECT MAX(DATE(sale_date)) AS last_sale
            FROM sales
            WHERE status = 'Completed'
            """
        )

        last_sale = row["last_sale"] if row else None
        if not last_sale:
            return [
                self._rec(
                    "alert_no_sales_in_days",
                    "high",
                    "No completed sales recorded",
                    "Record your first sale to track performance.",
                    "Record Sale",
                    {"action": "record_sale"},
                )
            ]

        try:
            last_date = datetime.strptime(str(last_sale), "%Y-%m-%d").date()
            days = (date.today() - last_date).days
        except ValueError:
            days = 0

        if days < 7:
            return []

        return [
            self._rec(
                "alert_no_sales_in_days",
                "medium" if days < 14 else "high",
                f"No sales in {days} day(s)",
                f"Last completed sale was on {last_sale}.",
                "Record Sale",
                {"action": "record_sale"},
            )
        ]

    def _alert_github_upload_failures(self):
        row = self.db_service.db.fetchone(
            """
            SELECT COUNT(*) AS total
            FROM finish_workspace
            WHERE TRIM(COALESCE(github_url, '')) = ''
                AND COALESCE(quantity, 0) > 0
                AND COALESCE(sell_price, 0) > 0
                AND TRIM(COALESCE(image_path, '')) != ''
            """
        )

        count = int(row["total"] if row else 0)
        if count == 0:
            return []

        return [
            self._rec(
                "alert_github_upload_failures",
                "medium",
                "GitHub upload gaps detected",
                f"{count} listable finish(es) have no GitHub URL.",
                "Open Images",
                {"action": "open_images"},
            )
        ]

    def _alert_export_failures(self):
        row = self.db_service.db.fetchone(
            """
            SELECT COUNT(*) AS total
            FROM finish_workspace
            WHERE LOWER(COALESCE(ebay_status, '')) = 'failed'
            """
        )

        count = int(row["total"] if row else 0)
        if count == 0:
            return []

        return [
            self._rec(
                "alert_export_failures",
                "high",
                "eBay export failures detected",
                f"{count} finish(es) currently marked failed.",
                "Generate CSV",
                {"action": "generate_csv"},
            )
        ]

    def _alert_large_pricing_inconsistencies(self):
        row = self.db_service.db.fetchone(
            """
            SELECT COUNT(*) AS total
            FROM finish_workspace
            WHERE COALESCE(market_price, 0) > 0
                AND (
                    COALESCE(sell_price, 0) > market_price * 1.8
                    OR COALESCE(sell_price, 0) < market_price * 0.5
                )
            """
        )

        count = int(row["total"] if row else 0)
        if count == 0:
            return []

        return [
            self._rec(
                "alert_large_pricing_inconsistencies",
                "medium",
                "Large pricing inconsistencies",
                f"{count} finish(es) diverge strongly from market price.",
                "Open Pricing",
                {"action": "open_pricing"},
            )
        ]

    def _alert_duplicate_cards(self):
        row = self.db_service.db.fetchone(
            """
            SELECT COUNT(*) AS total
            FROM (
                SELECT set_id, number, name, COUNT(*) AS cnt
                FROM cards
                GROUP BY set_id, number, name
                HAVING cnt > 1
            ) d
            """
        )

        count = int(row["total"] if row else 0)
        if count == 0:
            return []

        return [
            self._rec(
                "alert_duplicate_cards",
                "high",
                "Duplicate cards detected",
                f"{count} duplicate card group(s) found.",
                "Open Card",
                {"action": "open_card"},
            )
        ]

    def _alert_missing_images(self):
        row = self.db_service.db.fetchone(
            """
            SELECT COUNT(*) AS total
            FROM card_finishes cf
            LEFT JOIN finish_workspace fw ON fw.finish_id = cf.id
            WHERE COALESCE(fw.quantity, 0) > 0
                AND TRIM(COALESCE(fw.image_path, cf.image_path, '')) = ''
            """
        )

        count = int(row["total"] if row else 0)
        if count == 0:
            return []

        return [
            self._rec(
                "alert_missing_images",
                "high",
                "Missing images in active inventory",
                f"{count} in-stock finish(es) are missing images.",
                "Open Images",
                {"action": "open_images"},
            )
        ]

    def _alert_backup_overdue(self):
        database_path = Path(__file__).resolve().parents[2] / "database"
        backup_candidates = list(database_path.glob("*.bak")) + list(database_path.glob("*backup*.db"))

        if not backup_candidates:
            return [
                self._rec(
                    "alert_backup_overdue",
                    "medium",
                    "Database backup overdue",
                    "No backup files found in database folder.",
                    "Open Inventory",
                    {"action": "open_inventory"},
                )
            ]

        newest = max(backup_candidates, key=lambda path: path.stat().st_mtime)
        age_days = int((datetime.now().timestamp() - newest.stat().st_mtime) / 86400)

        if age_days < 7:
            return []

        return [
            self._rec(
                "alert_backup_overdue",
                "medium",
                "Database backup overdue",
                f"Latest backup is {age_days} day(s) old: {newest.name}",
                "Open Inventory",
                {"action": "open_inventory"},
            )
        ]

    # -------------------------
    # Helpers
    # -------------------------

    def _rec(self, rule, severity, title, detail, action_label, action_payload):
        return {
            "rule": rule,
            "severity": severity,
            "title": title,
            "detail": detail,
            "action_label": action_label,
            "action": action_payload,
        }
