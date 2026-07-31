from __future__ import annotations

import json
import uuid
from datetime import datetime

from .database import Database


class DatabaseRepository:

    def __init__(self):
        self.db = Database()
        self.create()

    def create(self):
        self.db.create()
        self._migrate_marketplace_cache_table()
        self._ensure_listing_columns()
        self.execute(
            "CREATE INDEX IF NOT EXISTS idx_listings_last_synced ON listings(last_synced)"
        )
        self._remove_demo_listings()

    def close(self):
        self.db.close()

    def execute(self, sql, params=()):
        self.db.execute(sql, params)

    def fetchone(self, sql, params=()):
        return self.db.fetchone(sql, params)

    def fetchall(self, sql, params=()):
        return self.db.fetchall(sql, params)

    def save_listing(self, listing_data):
        return self._upsert_marketplace_cache_row(listing_data)

    def get_listing(self, listing_id):
        return self.fetchone(
            "SELECT * FROM marketplace_listings WHERE id = ? OR listing_id = ?",
            (listing_id, listing_id),
        )

    def list_listings(self, status=None):
        return self.get_cached_marketplace_listings(status=status)

    def replace_marketplace_cache(self, listings):
        self.clear_marketplace_cache()

        inserted = 0
        for listing in listings or []:
            self._upsert_marketplace_cache_row(listing)
            inserted += 1

        return inserted

    def clear_marketplace_cache(self):
        self.execute("DELETE FROM marketplace_listings")

    def get_cached_marketplace_listings(self, status=None):
        if status:
            return self.fetchall(
                """
                SELECT *
                FROM marketplace_listings
                WHERE status = ?
                ORDER BY COALESCE(last_synced, updated_at, created_at) DESC, title ASC
                """,
                (status,),
            )

        return self.fetchall(
            """
            SELECT *
            FROM marketplace_listings
            ORDER BY COALESCE(last_synced, updated_at, created_at) DESC, title ASC
            """
        )

    def save_order(self, order_data):
        order_id = self._resolve_row_id(order_data, fallback_key="order_number")
        payload = self._encode_payload(order_data)

        self.execute(
            """
            INSERT INTO orders (
                id,
                order_number,
                listing_id,
                card_id,
                finish_id,
                buyer,
                quantity,
                subtotal,
                shipping,
                tax,
                total,
                status,
                purchased_at,
                payload,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                order_number = excluded.order_number,
                listing_id = excluded.listing_id,
                card_id = excluded.card_id,
                finish_id = excluded.finish_id,
                buyer = excluded.buyer,
                quantity = excluded.quantity,
                subtotal = excluded.subtotal,
                shipping = excluded.shipping,
                tax = excluded.tax,
                total = excluded.total,
                status = excluded.status,
                purchased_at = excluded.purchased_at,
                payload = excluded.payload,
                updated_at = excluded.updated_at
            """,
            (
                order_id,
                order_data.get("order_number"),
                order_data.get("listing_id"),
                order_data.get("card_id"),
                order_data.get("finish_id"),
                order_data.get("buyer"),
                int(order_data.get("quantity") or 0),
                float(order_data.get("subtotal") or 0),
                float(order_data.get("shipping") or 0),
                float(order_data.get("tax") or 0),
                float(order_data.get("total") or 0),
                str(order_data.get("status") or "Open"),
                order_data.get("purchased_at"),
                payload,
                self._now_text(),
                self._now_text(),
            ),
        )
        return order_id

    def get_order(self, order_number):
        return self.fetchone(
            "SELECT * FROM orders WHERE id = ? OR order_number = ?",
            (order_number, order_number),
        )

    def list_orders(self, status=None):
        if status:
            return self.fetchall(
                "SELECT * FROM orders WHERE status = ? ORDER BY updated_at DESC",
                (status,),
            )

        return self.fetchall("SELECT * FROM orders ORDER BY updated_at DESC")

    def set_setting(self, key, value):
        value_text, value_type = self._encode_value(value)

        self.execute(
            """
            INSERT INTO settings (key, value, value_type, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                value_type = excluded.value_type,
                updated_at = excluded.updated_at
            """,
            (str(key), value_text, value_type, self._now_text()),
        )

    def get_setting(self, key, default=None):
        row = self.fetchone(
            "SELECT value, value_type FROM settings WHERE key = ?",
            (str(key),),
        )

        if row is None:
            return default

        return self._decode_value(row["value"], row["value_type"], default)

    def list_settings(self):
        return self.fetchall("SELECT * FROM settings ORDER BY key ASC")

    def _resolve_row_id(self, row_data, fallback_key):
        row_id = row_data.get("id") or row_data.get(fallback_key)
        return str(row_id or uuid.uuid4())

    def _encode_payload(self, value):
        if value is None:
            return None

        return json.dumps(value, default=str, ensure_ascii=True)

    def _upsert_marketplace_cache_row(self, listing_data):
        listing_id = str(
            listing_data.get("listing_id")
            or listing_data.get("item_id")
            or listing_data.get("id")
            or uuid.uuid4()
        )
        row_id = str(listing_data.get("id") or listing_id or uuid.uuid4())
        payload = self._encode_payload(listing_data)
        now_text = self._now_text()

        self.execute(
            """
            INSERT INTO marketplace_listings (
                id,
                listing_id,
                item_id,
                title,
                sku,
                quantity,
                price,
                status,
                thumbnail_path,
                image_url,
                marketplace,
                url,
                last_synced,
                payload,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(listing_id) DO UPDATE SET
                item_id = excluded.item_id,
                title = excluded.title,
                sku = excluded.sku,
                quantity = excluded.quantity,
                price = excluded.price,
                status = excluded.status,
                thumbnail_path = excluded.thumbnail_path,
                image_url = excluded.image_url,
                marketplace = excluded.marketplace,
                url = excluded.url,
                last_synced = excluded.last_synced,
                payload = excluded.payload,
                updated_at = excluded.updated_at
            """,
            (
                row_id,
                listing_id,
                str(listing_data.get("item_id") or listing_id),
                str(listing_data.get("title") or ""),
                str(listing_data.get("sku") or ""),
                int(listing_data.get("quantity") or 0),
                float(listing_data.get("price") or 0),
                str(listing_data.get("status") or "Active"),
                listing_data.get("thumbnail_path"),
                listing_data.get("image_url"),
                str(listing_data.get("marketplace") or "eBay"),
                listing_data.get("url"),
                str(listing_data.get("last_synced") or now_text),
                payload,
                now_text,
                now_text,
            ),
        )

        return listing_id

    def _migrate_marketplace_cache_table(self):
        tables = {
            str(row["name"])
            for row in self.fetchall("SELECT name FROM sqlite_master WHERE type = 'table'")
        }

        if "marketplace_cache" not in tables or "marketplace_listings" not in tables:
            return

        self.execute(
            """
            INSERT OR IGNORE INTO marketplace_listings (
                id,
                listing_id,
                item_id,
                title,
                sku,
                quantity,
                price,
                status,
                thumbnail_path,
                image_url,
                marketplace,
                url,
                last_synced,
                payload,
                created_at,
                updated_at
            )
            SELECT
                id,
                listing_id,
                item_id,
                title,
                sku,
                quantity,
                price,
                status,
                thumbnail_path,
                image_url,
                marketplace,
                url,
                last_synced,
                payload,
                created_at,
                updated_at
            FROM marketplace_cache
            """
        )

    def _ensure_listing_columns(self):
        existing_columns = {
            str(row["name"])
            for row in self.fetchall("PRAGMA table_info(listings)")
        }

        required_columns = {
            "thumbnail_path": "TEXT",
            "last_synced": "TEXT",
        }

        for column_name, column_type in required_columns.items():
            if column_name in existing_columns:
                continue

            self.execute(
                f"ALTER TABLE listings ADD COLUMN {column_name} {column_type}"
            )

    def _remove_demo_listings(self):
        self.execute(
            "DELETE FROM listings WHERE listing_id LIKE 'sample-%'"
        )

    def _encode_value(self, value):
        if isinstance(value, bool):
            return ("true" if value else "false", "bool")

        if isinstance(value, int) and not isinstance(value, bool):
            return (str(value), "int")

        if isinstance(value, float):
            return (str(value), "float")

        if isinstance(value, (dict, list, tuple)):
            return (json.dumps(value, default=str, ensure_ascii=True), "json")

        if value is None:
            return ("", "text")

        return (str(value), "text")

    def _decode_value(self, value_text, value_type, default=None):
        try:
            if value_type == "bool":
                return value_text.lower() in {"1", "true", "yes", "on"}

            if value_type == "int":
                return int(value_text)

            if value_type == "float":
                return float(value_text)

            if value_type == "json":
                return json.loads(value_text)
        except (TypeError, ValueError, json.JSONDecodeError):
            return default

        return value_text

    def _now_text(self):
        return datetime.utcnow().replace(microsecond=0).isoformat(sep=" ")


def initialize_database():
    repository = DatabaseRepository()
    return repository