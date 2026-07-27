import csv
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from database.service import DatabaseService


class SalesService:
    STATUS_COMPLETED = "Completed"
    STATUS_UNDONE = "Undone"
    STATUS_DELETED = "Deleted"

    def __init__(self):
        self.db_service = DatabaseService()
        self._ensure_sales_table()

    def _ensure_sales_table(self):
        self.db_service.db.execute(
            """
            CREATE TABLE IF NOT EXISTS sales (
                sale_id TEXT PRIMARY KEY,
                order_number TEXT,
                sale_date TEXT,
                platform TEXT,
                buyer TEXT,
                card_id TEXT,
                finish_id INTEGER,
                quantity INTEGER DEFAULT 0,
                sale_price REAL DEFAULT 0,
                fees REAL DEFAULT 0,
                shipping_cost REAL DEFAULT 0,
                status TEXT DEFAULT 'Completed',
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(card_id) REFERENCES cards(id),
                FOREIGN KEY(finish_id) REFERENCES card_finishes(id)
            )
            """
        )

    def record_sale(
        self,
        order_number,
        sale_date,
        platform,
        buyer,
        finish_id,
        quantity,
        sale_price,
        fees=0,
        shipping_cost=0,
        notes="",
    ):
        finish = self._get_finish_row(finish_id)
        if finish is None:
            return {"ok": False, "reason": "Unknown finish", "sale": None}

        try:
            sale_qty = int(quantity)
        except (TypeError, ValueError):
            return {"ok": False, "reason": "Quantity must be numeric", "sale": None}

        if sale_qty <= 0:
            return {"ok": False, "reason": "Quantity must be greater than 0", "sale": None}

        if self._is_duplicate_order(order_number, finish_id):
            return {"ok": False, "reason": "Duplicate order number", "sale": None}

        finish_inventory = self.db_service.get_finish_inventory(finish_id, fallback_card_data={})
        current_quantity = int(finish_inventory.get("quantity") or 0)
        if current_quantity < sale_qty:
            return {
                "ok": False,
                "reason": "Insufficient inventory for this finish",
                "sale": None,
            }

        sale_id = str(uuid.uuid4())
        sale_date_text = str(sale_date or datetime.now().strftime("%Y-%m-%d"))
        platform_text = str(platform or "Manual")
        order_text = str(order_number or f"MANUAL-{datetime.now().strftime('%Y%m%d%H%M%S')}")

        self.db_service.db.execute(
            """
            INSERT INTO sales (
                sale_id,
                order_number,
                sale_date,
                platform,
                buyer,
                card_id,
                finish_id,
                quantity,
                sale_price,
                fees,
                shipping_cost,
                status,
                notes,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                sale_id,
                order_text,
                sale_date_text,
                platform_text,
                str(buyer or ""),
                finish.get("card_id"),
                finish_id,
                sale_qty,
                float(sale_price or 0),
                float(fees or 0),
                float(shipping_cost or 0),
                self.STATUS_COMPLETED,
                str(notes or ""),
                self._now_text(),
            ),
        )

        next_quantity = current_quantity - sale_qty
        self.db_service.save_finish_inventory(
            finish_id,
            next_quantity,
            float(finish_inventory.get("cost_price") or 0),
        )
        self._sync_finish_state(finish_id)

        sale = self._get_sale_by_id(sale_id)
        return {"ok": True, "reason": None, "sale": sale}

    def import_sales_csv(self, csv_path, column_map=None, default_platform="CSV"):
        file_path = Path(csv_path)
        if not file_path.exists() or not file_path.is_file():
            return {
                "ok": False,
                "reason": "CSV file not found",
                "summary": None,
            }

        with file_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            rows = list(reader)

        mapping = self._default_column_mapping(rows[0].keys() if rows else [])
        if column_map:
            mapping.update(column_map)

        imported = 0
        skipped_duplicates = 0
        skipped_unknown = 0
        failed = 0
        failures = []

        for index, row in enumerate(rows, start=2):
            finish = self._resolve_finish_from_row(row, mapping)
            if finish is None:
                skipped_unknown += 1
                failures.append({"row": index, "reason": "Unknown card/finish"})
                continue

            order_number = self._mapped_value(row, mapping, "order_number") or ""
            if self._is_duplicate_order(order_number, finish.get("finish_id")):
                skipped_duplicates += 1
                failures.append({"row": index, "reason": "Duplicate order number"})
                continue

            try:
                quantity = int(float(self._mapped_value(row, mapping, "quantity") or 0))
                sale_price = float(self._mapped_value(row, mapping, "sale_price") or 0)
                fees = float(self._mapped_value(row, mapping, "fees") or 0)
                shipping = float(self._mapped_value(row, mapping, "shipping_cost") or 0)
            except ValueError:
                failed += 1
                failures.append({"row": index, "reason": "Invalid numeric value"})
                continue

            result = self.record_sale(
                order_number=order_number,
                sale_date=self._mapped_value(row, mapping, "sale_date") or datetime.now().strftime("%Y-%m-%d"),
                platform=self._mapped_value(row, mapping, "platform") or default_platform,
                buyer=self._mapped_value(row, mapping, "buyer") or "",
                finish_id=finish.get("finish_id"),
                quantity=quantity,
                sale_price=sale_price,
                fees=fees,
                shipping_cost=shipping,
                notes=self._mapped_value(row, mapping, "notes") or "",
            )

            if result.get("ok"):
                imported += 1
            else:
                failed += 1
                failures.append({"row": index, "reason": result.get("reason") or "Import error"})

        summary = {
            "rows": len(rows),
            "imported": imported,
            "skipped_duplicates": skipped_duplicates,
            "skipped_unknown": skipped_unknown,
            "failed": failed,
            "failures": failures,
            "column_map": mapping,
        }

        return {"ok": True, "reason": None, "summary": summary}

    def undo_sale(self, sale_id):
        sale = self._get_sale_by_id(sale_id)
        if sale is None:
            return {"ok": False, "reason": "Sale not found"}

        if sale.get("status") != self.STATUS_COMPLETED:
            return {"ok": False, "reason": "Only completed sales can be undone"}

        finish_id = sale.get("finish_id")
        if not finish_id:
            return {"ok": False, "reason": "Sale has no finish"}

        finish_inventory = self.db_service.get_finish_inventory(finish_id, fallback_card_data={})
        current_quantity = int(finish_inventory.get("quantity") or 0)
        next_quantity = current_quantity + int(sale.get("quantity") or 0)

        self.db_service.save_finish_inventory(
            finish_id,
            next_quantity,
            float(finish_inventory.get("cost_price") or 0),
        )

        self.db_service.db.execute(
            """
            UPDATE sales
            SET
                status = ?,
                notes = ?,
                created_at = created_at
            WHERE sale_id = ?
            """,
            (
                self.STATUS_UNDONE,
                self._append_note(sale.get("notes"), "Undone"),
                sale_id,
            ),
        )

        self._sync_finish_state(finish_id)
        return {"ok": True, "reason": None}

    def delete_sale(self, sale_id):
        sale = self._get_sale_by_id(sale_id)
        if sale is None:
            return {"ok": False, "reason": "Sale not found"}

        finish_id = sale.get("finish_id")
        if sale.get("status") == self.STATUS_COMPLETED and finish_id:
            finish_inventory = self.db_service.get_finish_inventory(finish_id, fallback_card_data={})
            current_quantity = int(finish_inventory.get("quantity") or 0)
            next_quantity = current_quantity + int(sale.get("quantity") or 0)
            self.db_service.save_finish_inventory(
                finish_id,
                next_quantity,
                float(finish_inventory.get("cost_price") or 0),
            )
            self._sync_finish_state(finish_id)

        self.db_service.db.execute(
            """
            UPDATE sales
            SET
                status = ?,
                notes = ?
            WHERE sale_id = ?
            """,
            (
                self.STATUS_DELETED,
                self._append_note(sale.get("notes"), "Deleted"),
                sale_id,
            ),
        )

        return {"ok": True, "reason": None}

    def get_sales(
        self,
        period="All",
        platform="All",
        card_query="",
        finish="All",
        include_deleted=False,
        limit=200,
    ):
        sql = """
            SELECT
                s.sale_id,
                s.order_number,
                s.sale_date,
                s.platform,
                s.buyer,
                s.card_id,
                s.finish_id,
                s.quantity,
                s.sale_price,
                s.fees,
                s.shipping_cost,
                s.status,
                s.notes,
                s.created_at,
                c.number AS card_number,
                c.name AS card_name,
                cf.finish,
                (COALESCE(s.sale_price, 0) - COALESCE(s.fees, 0) - COALESCE(s.shipping_cost, 0)) AS net_profit
            FROM sales s
            LEFT JOIN cards c
                ON c.id = s.card_id
            LEFT JOIN card_finishes cf
                ON cf.id = s.finish_id
            WHERE 1 = 1
        """
        params = []

        if not include_deleted:
            sql += " AND s.status != ?"
            params.append(self.STATUS_DELETED)

        period_start = self._period_start(period)
        if period_start:
            sql += " AND s.sale_date >= ?"
            params.append(period_start)

        if platform and platform != "All":
            sql += " AND s.platform = ?"
            params.append(platform)

        if card_query:
            sql += " AND (LOWER(c.name) LIKE ? OR LOWER(c.number) LIKE ? OR LOWER(s.card_id) LIKE ?)"
            pattern = f"%{str(card_query).strip().lower()}%"
            params.extend([pattern, pattern, pattern])

        if finish and finish != "All":
            sql += " AND cf.finish = ?"
            params.append(finish)

        sql += " ORDER BY s.sale_date DESC, s.created_at DESC LIMIT ?"
        params.append(int(limit))

        rows = self.db_service.db.fetchall(sql, tuple(params))
        return [dict(row) for row in rows]

    def get_sales_summary(self, period="All", platform="All", card_query="", finish="All"):
        rows = self.get_sales(
            period=period,
            platform=platform,
            card_query=card_query,
            finish=finish,
            include_deleted=False,
            limit=100000,
        )

        completed_rows = [row for row in rows if row.get("status") == self.STATUS_COMPLETED]
        revenue = sum(float(row.get("sale_price") or 0) for row in completed_rows)
        fees = sum(float(row.get("fees") or 0) for row in completed_rows)
        shipping = sum(float(row.get("shipping_cost") or 0) for row in completed_rows)
        cards_sold = sum(int(row.get("quantity") or 0) for row in completed_rows)

        today_rows = self.get_sales(period="Today", include_deleted=False, limit=100000)
        week_rows = self.get_sales(period="This Week", include_deleted=False, limit=100000)
        month_rows = self.get_sales(period="This Month", include_deleted=False, limit=100000)

        return {
            "today_sales": len([row for row in today_rows if row.get("status") == self.STATUS_COMPLETED]),
            "week_sales": len([row for row in week_rows if row.get("status") == self.STATUS_COMPLETED]),
            "month_sales": len([row for row in month_rows if row.get("status") == self.STATUS_COMPLETED]),
            "total_revenue": revenue,
            "fees": fees,
            "shipping": shipping,
            "net_revenue": revenue - fees - shipping,
            "cards_sold": cards_sold,
            "inventory_removed": cards_sold,
        }

    def get_inventory_adjustments(self, limit=200):
        rows = self.get_sales(include_deleted=True, limit=limit)
        adjustments = []
        for row in rows:
            status = row.get("status")
            quantity = int(row.get("quantity") or 0)
            if status == self.STATUS_COMPLETED:
                delta = -quantity
            elif status == self.STATUS_UNDONE:
                delta = quantity
            else:
                delta = 0

            adjustments.append(
                {
                    "sale_id": row.get("sale_id"),
                    "order_number": row.get("order_number"),
                    "sale_date": row.get("sale_date"),
                    "card": row.get("card_name") or row.get("card_id"),
                    "finish": row.get("finish") or "Unknown",
                    "status": status,
                    "inventory_delta": delta,
                }
            )

        return adjustments

    def recalculate_inventory(self, finish_id=None):
        finish_ids = [finish_id] if finish_id else self._all_finish_ids()
        recalculated = 0

        for fid in finish_ids:
            if not fid:
                continue
            self._sync_finish_state(fid)
            recalculated += 1

        return {"ok": True, "recalculated": recalculated}

    def rebuild_inventory(self, starting_quantities=None):
        starting_quantities = starting_quantities or {}

        for fid, qty in starting_quantities.items():
            finish_inventory = self.db_service.get_finish_inventory(fid, fallback_card_data={})
            self.db_service.save_finish_inventory(
                fid,
                max(0, int(qty or 0)),
                float(finish_inventory.get("cost_price") or 0),
            )

        completed_sales = self.db_service.db.fetchall(
            """
            SELECT finish_id, SUM(quantity) AS sold_qty
            FROM sales
            WHERE status = ?
            GROUP BY finish_id
            """,
            (self.STATUS_COMPLETED,),
        )

        for row in completed_sales:
            fid = row["finish_id"]
            sold_qty = int(row["sold_qty"] or 0)
            finish_inventory = self.db_service.get_finish_inventory(fid, fallback_card_data={})
            current_qty = int(finish_inventory.get("quantity") or 0)
            next_qty = max(0, current_qty - sold_qty)
            self.db_service.save_finish_inventory(
                fid,
                next_qty,
                float(finish_inventory.get("cost_price") or 0),
            )

        self.recalculate_inventory()
        return {
            "ok": True,
            "rebuild_count": len(completed_sales),
        }

    def _sync_finish_state(self, finish_id):
        readiness = self.db_service.get_finish_readiness(finish_id) or {}
        workspace = self.db_service.get_finish_workspace(finish_id) or {}
        quantity = int(readiness.get("quantity") or 0)

        self.db_service.db.execute(
            """
            UPDATE finish_workspace
            SET
                is_ready_for_listing = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE finish_id = ?
            """,
            (1 if readiness.get("is_ready") else 0, finish_id),
        )

        details = self._get_finish_row(finish_id) or {}
        card_id = details.get("card_id")

        if quantity <= 0:
            status = str(workspace.get("ebay_status") or self.db_service.EBAY_STATUS_NOT_QUEUED)
            if status in (self.db_service.EBAY_STATUS_QUEUED, self.db_service.EBAY_STATUS_EXPORTING):
                self.db_service._save_ebay_queue_fields(
                    finish_id,
                    ebay_status=self.db_service.EBAY_STATUS_CANCELLED,
                    ebay_error="Out of Stock",
                )
            self.db_service.db.execute(
                """
                INSERT INTO ebay (card_id, listed, last_sync)
                VALUES (?, 0, ?)
                ON CONFLICT(card_id) DO UPDATE SET
                    listed = 0,
                    last_sync = excluded.last_sync
                """,
                (card_id, self._now_text()),
            )
        else:
            if readiness.get("is_ready"):
                status = str(workspace.get("ebay_status") or "")
                error = str(workspace.get("ebay_error") or "")
                if status == self.db_service.EBAY_STATUS_CANCELLED and "out of stock" in error.lower():
                    self.db_service._save_ebay_queue_fields(
                        finish_id,
                        ebay_status=self.db_service.EBAY_STATUS_NOT_QUEUED,
                        ebay_error="",
                    )

    def _get_finish_row(self, finish_id):
        row = self.db_service.db.fetchone(
            """
            SELECT
                cf.id AS finish_id,
                cf.card_id,
                cf.finish,
                c.set_id,
                c.number,
                c.name
            FROM card_finishes cf
            INNER JOIN cards c
                ON c.id = cf.card_id
            WHERE cf.id = ?
            """,
            (finish_id,),
        )
        return dict(row) if row else None

    def _resolve_finish_from_row(self, row, mapping):
        finish_id_raw = self._mapped_value(row, mapping, "finish_id")
        if finish_id_raw:
            try:
                finish_id = int(float(finish_id_raw))
                finish = self._get_finish_row(finish_id)
                if finish:
                    return finish
            except ValueError:
                pass

        card_id = self._mapped_value(row, mapping, "card_id")
        finish_name = self._mapped_value(row, mapping, "finish")
        card_number = self._mapped_value(row, mapping, "card_number")
        card_name = self._mapped_value(row, mapping, "card_name")

        if card_id and finish_name:
            lookup = self.db_service.db.fetchone(
                """
                SELECT
                    cf.id AS finish_id,
                    cf.card_id,
                    cf.finish,
                    c.set_id,
                    c.number,
                    c.name
                FROM card_finishes cf
                INNER JOIN cards c
                    ON c.id = cf.card_id
                WHERE LOWER(cf.card_id) = LOWER(?)
                    AND LOWER(cf.finish) = LOWER(?)
                """,
                (str(card_id), str(finish_name)),
            )
            if lookup:
                return dict(lookup)

        if card_number and finish_name:
            lookup = self.db_service.db.fetchone(
                """
                SELECT
                    cf.id AS finish_id,
                    cf.card_id,
                    cf.finish,
                    c.set_id,
                    c.number,
                    c.name
                FROM card_finishes cf
                INNER JOIN cards c
                    ON c.id = cf.card_id
                WHERE LOWER(c.number) = LOWER(?)
                    AND LOWER(cf.finish) = LOWER(?)
                """,
                (str(card_number), str(finish_name)),
            )
            if lookup:
                return dict(lookup)

        if card_name and finish_name:
            lookup = self.db_service.db.fetchone(
                """
                SELECT
                    cf.id AS finish_id,
                    cf.card_id,
                    cf.finish,
                    c.set_id,
                    c.number,
                    c.name
                FROM card_finishes cf
                INNER JOIN cards c
                    ON c.id = cf.card_id
                WHERE LOWER(c.name) = LOWER(?)
                    AND LOWER(cf.finish) = LOWER(?)
                """,
                (str(card_name), str(finish_name)),
            )
            if lookup:
                return dict(lookup)

        return None

    def _is_duplicate_order(self, order_number, finish_id):
        if not order_number:
            return False

        row = self.db_service.db.fetchone(
            """
            SELECT sale_id
            FROM sales
            WHERE order_number = ?
                AND finish_id = ?
                AND status != ?
            """,
            (str(order_number), finish_id, self.STATUS_DELETED),
        )

        return row is not None

    def _get_sale_by_id(self, sale_id):
        row = self.db_service.db.fetchone(
            """
            SELECT *
            FROM sales
            WHERE sale_id = ?
            """,
            (sale_id,),
        )
        return dict(row) if row else None

    def _default_column_mapping(self, columns):
        by_normalized = {str(name).strip().lower(): name for name in columns}

        synonyms = {
            "order_number": ["order_number", "order", "order #", "order id", "ordernumber"],
            "sale_date": ["sale_date", "date", "sold_at", "order_date"],
            "platform": ["platform", "channel", "source"],
            "buyer": ["buyer", "customer", "customer_name"],
            "card_id": ["card_id", "sku", "card"],
            "finish_id": ["finish_id", "finishid"],
            "card_number": ["card_number", "number", "card no", "card_no"],
            "card_name": ["card_name", "name", "title"],
            "finish": ["finish", "variant"],
            "quantity": ["quantity", "qty", "sold_qty"],
            "sale_price": ["sale_price", "price", "amount", "gross"],
            "fees": ["fees", "fee", "platform_fees"],
            "shipping_cost": ["shipping_cost", "shipping", "postage"],
            "notes": ["notes", "memo", "comment"],
        }

        mapping = {}
        for target, aliases in synonyms.items():
            selected = ""
            for alias in aliases:
                candidate = by_normalized.get(alias.lower())
                if candidate:
                    selected = candidate
                    break
            mapping[target] = selected

        return mapping

    def _mapped_value(self, row, mapping, key):
        source = mapping.get(key)
        if not source:
            return ""
        return str(row.get(source, "") or "").strip()

    def _period_start(self, period):
        now = datetime.now()
        selected = str(period or "All")

        if selected == "Today":
            return now.strftime("%Y-%m-%d")
        if selected == "This Week":
            start = now - timedelta(days=now.weekday())
            return start.strftime("%Y-%m-%d")
        if selected == "This Month":
            start = now.replace(day=1)
            return start.strftime("%Y-%m-%d")

        return None

    def _all_finish_ids(self):
        rows = self.db_service.db.fetchall("SELECT id FROM card_finishes")
        return [row["id"] for row in rows]

    def _append_note(self, existing, text):
        existing_text = str(existing or "").strip()
        if not existing_text:
            return text
        if text.lower() in existing_text.lower():
            return existing_text
        return f"{existing_text} | {text}"

    def _now_text(self):
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
