from .repository import DatabaseRepository
from pathlib import Path
import os
import subprocess
from datetime import datetime
import uuid
import base64

import requests

from config import GITHUB_OWNER, GITHUB_REPO, GITHUB_BRANCH
from ebay_variation_exporter import export_cards


IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp")


def build_workflow_status(card_data=None):
    card_data = card_data or {}

    return {
        "imported": True,
        "images": bool(card_data.get("images") or card_data.get("image_path")),
        "github": bool(card_data.get("github_url")),
        "inventory": bool(card_data.get("inventory_quantity") or card_data.get("quantity")),
        "pricing": bool(card_data.get("price") or card_data.get("sell_price")),
        "ebay": bool(card_data.get("listing_id") or card_data.get("listed")),
    }


class DatabaseService:
    EBAY_STATUS_NOT_QUEUED = "Not Queued"
    EBAY_STATUS_QUEUED = "Queued"
    EBAY_STATUS_EXPORTING = "Exporting"
    EBAY_STATUS_EXPORTED = "Exported"
    EBAY_STATUS_FAILED = "Failed"
    EBAY_STATUS_CANCELLED = "Cancelled"

    def __init__(self):
        self.db = DatabaseRepository()
        self._ensure_sets_columns()
        self._normalize_set_aliases()
        self._ensure_finish_workspace_columns()
        self.initialize_finish_workspace()
        self.upload_queue = []
        self.upload_index = {}
        self.upload_processing = False
        self.upload_cancel_requested = False
        self.ebay_cancel_requested = False

    def _ensure_sets_columns(self):
        existing_columns = {
            str(row["name"])
            for row in self.db.fetchall("PRAGMA table_info(sets)")
        }

        if "api_set" not in existing_columns:
            self.db.execute("ALTER TABLE sets ADD COLUMN api_set TEXT")

        # Backfill legacy rows so build modules can resolve API set ids from DB.
        self.db.execute(
            """
            UPDATE sets
            SET api_set = LOWER(id)
            WHERE api_set IS NULL OR TRIM(api_set) = ''
            """
        )

    def _normalize_set_aliases(self):
        rows = [dict(row) for row in self.db.fetchall(
            """
            SELECT id, name, api_set
            FROM sets
            ORDER BY release_date DESC, id ASC
            """
        )]

        groups = {}
        for row in rows:
            api_set = str(row.get("api_set") or row.get("id") or "").strip().lower()
            if not api_set:
                continue
            groups.setdefault(api_set, []).append(row)

        for api_set, group in groups.items():
            if len(group) < 2:
                continue

            canonical = next(
                (row for row in group if str(row.get("id") or "").strip().lower() != api_set),
                group[0],
            )
            canonical_id = str(canonical.get("id") or "").strip().lower()

            for row in group:
                current_id = str(row.get("id") or "").strip().lower()
                if not current_id or current_id == canonical_id:
                    continue

                self.db.execute(
                    "UPDATE cards SET set_id = ? WHERE LOWER(set_id) = LOWER(?)",
                    (canonical_id, current_id),
                )
                self.db.execute(
                    "DELETE FROM sets WHERE LOWER(id) = LOWER(?)",
                    (current_id,),
                )

    def _ensure_finish_workspace_columns(self):
        existing_columns = {
            str(row["name"])
            for row in self.db.fetchall("PRAGMA table_info(finish_workspace)")
        }

        required_columns = {
            "queued_at": "TEXT",
            "exported_at": "TEXT",
            "listing_group": "TEXT",
            "listing_type": "TEXT",
            "export_batch": "TEXT",
            "listing_title_override": "TEXT",
            "ebay_error": "TEXT",
        }

        for column_name, column_type in required_columns.items():
            if column_name in existing_columns:
                continue

            self.db.execute(
                f"ALTER TABLE finish_workspace ADD COLUMN {column_name} {column_type}"
            )

    # -----------------
    # Sets
    # -----------------

    def add_set(self, set_data):
        self.db.execute(
            """
            INSERT OR REPLACE INTO sets
            (id, name, series, release_date, printed_total, api_set)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                set_data["id"],
                set_data["name"],
                set_data.get("series"),
                set_data.get("releaseDate"),
                set_data.get("printedTotal"),
                str(set_data.get("api_set") or set_data.get("id") or "").strip().lower(),
            ),
        )

    def delete_set(self, set_id):
        normalized_set_id = str(set_id or "").strip().lower()
        if not normalized_set_id:
            raise ValueError("Set ID is required")

        connection = self.db.db.connection
        cursor = connection.cursor()

        try:
            cursor.execute("BEGIN")

            card_rows = cursor.execute(
                "SELECT id FROM cards WHERE LOWER(set_id) = LOWER(?)",
                (normalized_set_id,),
            ).fetchall()
            card_ids = [str(row[0]) for row in card_rows]

            finish_ids = []
            if card_ids:
                placeholders = ",".join("?" for _ in card_ids)
                finish_rows = cursor.execute(
                    f"SELECT id FROM card_finishes WHERE card_id IN ({placeholders})",
                    card_ids,
                ).fetchall()
                finish_ids = [int(row[0]) for row in finish_rows]

            if finish_ids:
                finish_placeholders = ",".join("?" for _ in finish_ids)
                cursor.execute(
                    f"DELETE FROM finish_workspace WHERE finish_id IN ({finish_placeholders})",
                    finish_ids,
                )

            if card_ids:
                card_placeholders = ",".join("?" for _ in card_ids)
                finish_placeholders = ",".join("?" for _ in finish_ids) if finish_ids else None

                if finish_placeholders:
                    cursor.execute(
                        f"DELETE FROM sales WHERE card_id IN ({card_placeholders}) OR finish_id IN ({finish_placeholders})",
                        [*card_ids, *finish_ids],
                    )
                    cursor.execute(
                        f"DELETE FROM orders WHERE card_id IN ({card_placeholders}) OR finish_id IN ({finish_placeholders})",
                        [*card_ids, *finish_ids],
                    )
                    cursor.execute(
                        f"DELETE FROM listings WHERE card_id IN ({card_placeholders}) OR finish_id IN ({finish_placeholders})",
                        [*card_ids, *finish_ids],
                    )
                else:
                    cursor.execute(
                        f"DELETE FROM sales WHERE card_id IN ({card_placeholders})",
                        card_ids,
                    )
                    cursor.execute(
                        f"DELETE FROM orders WHERE card_id IN ({card_placeholders})",
                        card_ids,
                    )
                    cursor.execute(
                        f"DELETE FROM listings WHERE card_id IN ({card_placeholders})",
                        card_ids,
                    )

                cursor.execute(
                    f"DELETE FROM ebay WHERE card_id IN ({card_placeholders})",
                    card_ids,
                )
                cursor.execute(
                    f"DELETE FROM inventory WHERE card_id IN ({card_placeholders})",
                    card_ids,
                )
                cursor.execute(
                    f"DELETE FROM card_finishes WHERE card_id IN ({card_placeholders})",
                    card_ids,
                )
                cursor.execute(
                    f"DELETE FROM cards WHERE id IN ({card_placeholders})",
                    card_ids,
                )

            deleted_sets = cursor.execute(
                "DELETE FROM sets WHERE LOWER(id) = LOWER(?)",
                (normalized_set_id,),
            ).rowcount

            connection.commit()

            return {
                "set_id": normalized_set_id,
                "deleted_sets": int(deleted_sets or 0),
                "deleted_cards": len(card_ids),
                "deleted_finishes": len(finish_ids),
            }
        except Exception:
            connection.rollback()
            raise

    def get_sets(self):
        return self.db.fetchall(
            "SELECT * FROM sets ORDER BY release_date DESC"
        )

    def get_set(self, set_id):
        return self.db.fetchone(
            """
            SELECT
                id,
                name,
                series,
                release_date,
                printed_total,
                COALESCE(NULLIF(TRIM(api_set), ''), id) AS api_set
            FROM sets
            WHERE LOWER(id) = LOWER(?)
            LIMIT 1
            """,
            (set_id,),
        )

    # -----------------
    # Cards
    # -----------------
    def add_card(self, card, set_id_override=None):
        resolved_set_id = str(set_id_override or card["set"]["id"] or "").strip().lower()
        self.db.execute(
        """
        INSERT OR REPLACE INTO cards
        (id, set_id, number, name, rarity)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            card["id"],
            resolved_set_id,
            card["number"],
            card["name"],
            card.get("rarity"),
        ),
    )


    def add_finish(
        self,
        card_id,
        finish,
        image_path="",
        github_url="",
    ):
        self.db.execute(
            """
            INSERT OR IGNORE INTO card_finishes
            (card_id, finish, image_path, github_url)
            VALUES (?, ?, ?, ?)
            """,
            (
                card_id,
                finish,
                image_path,
                github_url,
            ),
        )

        row = self.db.fetchone(
            """
            SELECT id
            FROM card_finishes
            WHERE card_id = ?
                AND finish = ?
            """,
            (card_id, finish),
        )

        return row["id"] if row else None

    def get_cards(self, set_id):
        return self.db.fetchall(
            """
            SELECT *
            FROM cards
            WHERE set_id=?
            ORDER BY number
            """,
            (set_id,),
        )

    def get_finishes_for_card(self, card_id):
        if not card_id:
            return []

        rows = self.db.fetchall(
            """
            SELECT
                id,
                card_id,
                finish,
                image_path,
                github_url
            FROM card_finishes
            WHERE card_id = ?
            ORDER BY id ASC
            """,
            (card_id,),
        )

        return [dict(row) for row in rows]

    def get_default_finish(self, card_id):
        finishes = self.get_finishes_for_card(card_id)
        return finishes[0] if finishes else None

    # -----------------
    # Workspace
    # -----------------

    def get_card_workspace(self, set_id):
        rows = self.db.fetchall(
            """
            SELECT
                c.id AS id,
                c.id AS card_id,
                c.set_id,
                c.number,
                c.name,
                c.rarity,
                COUNT(DISTINCT cf.id) AS finish_count,
                COALESCE(i.quantity, 0) AS inventory_quantity,
                COALESCE(i.cost_price, 0) AS cost_price,
                COALESCE(i.sell_price, 0) AS sell_price,
                COALESCE(
                    (
                        SELECT cf_first.image_path
                        FROM card_finishes cf_first
                        WHERE cf_first.card_id = c.id
                        ORDER BY cf_first.id ASC
                        LIMIT 1
                    ),
                    ''
                ) AS image_path,
                COALESCE(
                    (
                        SELECT cf_first.github_url
                        FROM card_finishes cf_first
                        WHERE cf_first.card_id = c.id
                        ORDER BY cf_first.id ASC
                        LIMIT 1
                    ),
                    ''
                ) AS github_url,
                e.listing_id,
                e.listed
            FROM cards c
            LEFT JOIN card_finishes cf
                ON cf.card_id = c.id
            LEFT JOIN inventory i
                ON i.card_id = c.id
            LEFT JOIN ebay e
                ON e.card_id = c.id
            WHERE c.set_id = ?
            GROUP BY
                c.id,
                c.set_id,
                c.number,
                c.name,
                c.rarity,
                i.quantity,
                i.cost_price,
                i.sell_price,
                e.listing_id,
                e.listed
            ORDER BY c.number
            """,
            (set_id,),
        )

        workspace = []
        for row in rows:
            workspace.append(dict(row))

        return workspace

    # -----------------
    # Readiness
    # -----------------

    def get_finish_readiness(self, finish_id):
        if not finish_id:
            return None

        row = self.db.fetchone(
            """
            SELECT
                cf.id AS finish_id,
                cf.card_id,
                cf.finish,
                c.set_id,
                c.number,
                c.name,
                c.rarity,
                COALESCE(i.quantity, 0) AS card_quantity,
                COALESCE(i.cost_price, 0) AS card_cost_price,
                COALESCE(i.sell_price, 0) AS card_sell_price,
                fw.quantity AS finish_quantity,
                fw.cost_price AS finish_cost_price,
                fw.sell_price AS finish_sell_price,
                fw.market_price AS finish_market_price
            FROM card_finishes cf
            INNER JOIN cards c
                ON c.id = cf.card_id
            LEFT JOIN inventory i
                ON i.card_id = c.id
            LEFT JOIN finish_workspace fw
                ON fw.finish_id = cf.id
            WHERE cf.id = ?
            """,
            (finish_id,),
        )

        if row is None:
            return None

        return self._build_finish_readiness_from_row(dict(row))

    def get_set_readiness(self, set_id):
        if not set_id:
            return []

        rows = self.db.fetchall(
            """
            SELECT
                cf.id AS finish_id,
                cf.card_id,
                cf.finish,
                c.set_id,
                c.number,
                c.name,
                c.rarity,
                COALESCE(i.quantity, 0) AS card_quantity,
                COALESCE(i.cost_price, 0) AS card_cost_price,
                COALESCE(i.sell_price, 0) AS card_sell_price,
                fw.quantity AS finish_quantity,
                fw.cost_price AS finish_cost_price,
                fw.sell_price AS finish_sell_price,
                fw.market_price AS finish_market_price
            FROM card_finishes cf
            INNER JOIN cards c
                ON c.id = cf.card_id
            LEFT JOIN inventory i
                ON i.card_id = c.id
            LEFT JOIN finish_workspace fw
                ON fw.finish_id = cf.id
            WHERE c.set_id = ?
            ORDER BY c.number ASC, cf.id ASC
            """,
            (set_id,),
        )

        readiness = []
        for row in rows:
            readiness.append(self._build_finish_readiness_from_row(dict(row)))

        return readiness

    def calculate_readiness_summary(self, set_id, readiness_rows=None):
        rows = readiness_rows if readiness_rows is not None else self.get_set_readiness(set_id)

        summary = {
            "total_finishes": 0,
            "ready": 0,
            "missing_inventory": 0,
            "missing_pricing": 0,
            "missing_images": 0,
            "ready_for_publishing": 0,
        }

        for row in rows:
            summary["total_finishes"] += 1
            if row.get("is_ready"):
                summary["ready"] += 1
                summary["ready_for_publishing"] += 1
            if row.get("missing_inventory"):
                summary["missing_inventory"] += 1
            if row.get("missing_pricing"):
                summary["missing_pricing"] += 1
            if row.get("missing_images"):
                summary["missing_images"] += 1

        return summary

    def _build_finish_readiness_from_row(self, row):
        finish_id = row.get("finish_id")
        set_id = row.get("set_id")

        card_data = {
            "id": row.get("card_id"),
            "card_id": row.get("card_id"),
            "number": row.get("number"),
            "name": row.get("name"),
            "rarity": row.get("rarity"),
            "inventory_quantity": row.get("card_quantity"),
            "cost_price": row.get("card_cost_price"),
            "sell_price": row.get("card_sell_price"),
        }

        if row.get("finish_quantity") is None:
            quantity = int(row.get("card_quantity") or 0)
        else:
            quantity = int(row.get("finish_quantity") or 0)

        finish_sell = float(row.get("finish_sell_price") or 0)
        finish_market = float(row.get("finish_market_price") or 0)
        card_sell = float(row.get("card_sell_price") or 0)
        if finish_sell == 0 and finish_market == 0 and card_sell != 0:
            sell_price = card_sell
            pricing_source = "card"
        else:
            sell_price = finish_sell
            pricing_source = "finish"

        image_info = self.get_finish_image(set_id, card_data, finish_id)
        image_ready = image_info.get("status") == "ready"

        missing_inventory = quantity <= 0
        missing_pricing = sell_price <= 0
        missing_images = not image_ready
        is_ready = (not missing_inventory) and (not missing_pricing) and (not missing_images)

        if is_ready:
            readiness_label = "🟢 Ready"
            readiness_code = "ready"
        elif missing_inventory:
            readiness_label = "🔴 Out of Stock"
            readiness_code = "missing_inventory"
        elif missing_pricing:
            readiness_label = "🟠 Missing Pricing"
            readiness_code = "missing_pricing"
        else:
            readiness_label = "🟡 Missing Image"
            readiness_code = "missing_images"

        return {
            "finish_id": finish_id,
            "card_id": row.get("card_id"),
            "set_id": set_id,
            "card_number": row.get("number"),
            "card_name": row.get("name"),
            "finish": row.get("finish"),
            "quantity": quantity,
            "sell_price": sell_price,
            "pricing_source": pricing_source,
            "image_status": image_info.get("status"),
            "image_source": image_info.get("source"),
            "missing_inventory": missing_inventory,
            "missing_pricing": missing_pricing,
            "missing_images": missing_images,
            "is_ready": is_ready,
            "readiness_label": readiness_label,
            "readiness_code": readiness_code,
        }

    # -----------------
    # GitHub Publishing
    # -----------------

    def queue_finish_upload(self, finish_id):
        details = self._get_finish_upload_details(finish_id)
        if details is None:
            return {
                "queued": False,
                "reason": "Finish not found",
                "upload": None,
            }

        image_info = self.get_finish_image(details["set_id"], details, finish_id)
        if image_info.get("status") != "ready":
            return {
                "queued": False,
                "reason": "Finish image is not ready",
                "upload": None,
            }

        upload = {
            "upload_id": str(uuid.uuid4()),
            "finish_id": finish_id,
            "set_id": details["set_id"],
            "card_id": details["card_id"],
            "card_number": details.get("number"),
            "card_name": details.get("name"),
            "finish": details.get("finish"),
            "local_image_path": image_info.get("path"),
            "publishing_source": image_info.get("source"),
            "repository_path": self._build_repository_path(details["set_id"], image_info.get("path")),
            "status": "Pending",
            "remote_url": None,
            "error_message": None,
            "created_at": self._now_text(),
            "started_at": None,
            "completed_at": None,
        }

        self.upload_queue.append(upload)
        self.upload_index[upload["upload_id"]] = upload

        return {
            "queued": True,
            "reason": None,
            "upload": dict(upload),
        }

    def publish_finish_image(self, finish_id):
        queued = self.queue_finish_upload(finish_id)
        if not queued.get("queued"):
            return queued

        upload_id = queued["upload"]["upload_id"]
        self._process_upload(upload_id)
        return {
            "queued": True,
            "upload": dict(self.upload_index[upload_id]),
        }

    def publish_ready_finishes(self, set_id):
        readiness_rows = self.get_set_readiness(set_id)
        queued_uploads = []
        skipped = []

        for row in readiness_rows:
            finish_id = row.get("finish_id")
            if not finish_id:
                continue

            if not row.get("is_ready"):
                skipped.append(
                    {
                        "finish_id": finish_id,
                        "reason": "Finish is not ready",
                    }
                )
                continue

            queued = self.queue_finish_upload(finish_id)
            if queued.get("queued"):
                queued_uploads.append(queued["upload"])
            else:
                skipped.append(
                    {
                        "finish_id": finish_id,
                        "reason": queued.get("reason") or "Not eligible",
                    }
                )

        if queued_uploads:
            self.process_upload_queue()

        return {
            "queued": queued_uploads,
            "skipped": skipped,
        }

    def process_upload_queue(self):
        if self.upload_processing:
            return self.get_queue_progress()

        self.upload_processing = True
        self.upload_cancel_requested = False
        try:
            for upload in self.upload_queue:
                if upload.get("status") != "Pending":
                    continue

                if self.upload_cancel_requested:
                    upload["status"] = "Cancelled"
                    upload["completed_at"] = self._now_text()
                    continue

                self._process_upload(upload["upload_id"])
        finally:
            self.upload_processing = False

        return self.get_queue_progress()

    def cancel_upload(self, upload_id):
        upload = self.upload_index.get(upload_id)
        if upload is None:
            return False

        if upload.get("status") == "Pending":
            upload["status"] = "Cancelled"
            upload["completed_at"] = self._now_text()
            return True

        if upload.get("status") == "Uploading":
            self.upload_cancel_requested = True
            return True

        return False

    def retry_failed_upload(self, upload_id):
        upload = self.upload_index.get(upload_id)
        if upload is None or upload.get("status") != "Failed":
            return {
                "queued": False,
                "reason": "Upload is not failed",
                "upload": None,
            }

        upload["status"] = "Cancelled"
        upload["error_message"] = None
        upload["completed_at"] = self._now_text()

        return self.queue_finish_upload(upload.get("finish_id"))

    def cancel_queue(self, queue_name="github", set_id=None):
        if str(queue_name).lower() == "ebay":
            return self.cancel_ebay_queue(set_id=set_id)

        self.upload_cancel_requested = True
        for upload in self.upload_queue:
            if upload.get("status") == "Pending":
                upload["status"] = "Cancelled"
                upload["completed_at"] = self._now_text()

        return self.get_queue_progress()

    def refresh_queue_status(self, queue_name="github", set_id=None, queue_filter="All"):
        if str(queue_name).lower() == "ebay":
            return self.refresh_ebay_queue_status(set_id=set_id, queue_filter=queue_filter)

        return {
            "queue": [dict(upload) for upload in self.upload_queue],
            "progress": self.get_queue_progress(),
        }

    def get_queue_progress(self, queue_name="github", set_id=None):
        if str(queue_name).lower() == "ebay":
            return self.get_ebay_queue_progress(set_id=set_id)

        completed = 0
        failed = 0
        remaining = 0
        current = None

        for upload in self.upload_queue:
            status = upload.get("status")
            if status == "Uploaded":
                completed += 1
            elif status == "Failed":
                failed += 1
            elif status in ("Pending", "Uploading"):
                remaining += 1

            if status == "Uploading":
                current = upload

        return {
            "current_upload": dict(current) if current else None,
            "completed": completed,
            "remaining": remaining,
            "failed": failed,
            "total": len(self.upload_queue),
        }

    def get_finish_github_status(self, finish_id):
        upload = self._latest_upload_for_finish(finish_id)
        workspace = self.get_finish_workspace(finish_id) or {}
        details = self._get_finish_upload_details(finish_id) or {}
        image_info = self.get_finish_image(details.get("set_id"), details, finish_id) if details else {}

        status = upload.get("status") if upload else ("Uploaded" if workspace.get("github_url") else "Pending")
        repository_path = upload.get("repository_path") if upload else self._build_repository_path(details.get("set_id"), image_info.get("path"))
        last_upload_time = upload.get("completed_at") if upload else workspace.get("updated_at")
        remote_url = upload.get("remote_url") if upload else workspace.get("github_url")
        source = upload.get("publishing_source") if upload else image_info.get("source")
        error_message = upload.get("error_message") if upload else None

        return {
            "status": status,
            "repository_path": repository_path,
            "last_upload_time": last_upload_time,
            "remote_url": remote_url,
            "publishing_source": source,
            "error_message": error_message,
        }

    def _latest_upload_for_finish(self, finish_id):
        latest = None
        for upload in self.upload_queue:
            if upload.get("finish_id") != finish_id:
                continue
            if latest is None:
                latest = upload
                continue
            if str(upload.get("created_at") or "") > str(latest.get("created_at") or ""):
                latest = upload

        return latest

    def _process_upload(self, upload_id):
        upload = self.upload_index.get(upload_id)
        if upload is None:
            return

        if upload.get("status") in ("Cancelled", "Uploaded"):
            return

        upload["status"] = "Uploading"
        upload["started_at"] = self._now_text()
        upload["error_message"] = None

        try:
            remote_url = self._upload_image_to_github(
                upload.get("local_image_path"),
                upload.get("repository_path"),
            )

            if remote_url is None:
                upload["status"] = "Failed"
                upload["error_message"] = "Upload failed"
            else:
                upload["status"] = "Uploaded"
                upload["remote_url"] = remote_url
                self._save_finish_github_url(upload.get("finish_id"), remote_url)
        except Exception as exc:
            upload["status"] = "Failed"
            upload["error_message"] = str(exc)
        finally:
            if upload.get("status") == "Uploading":
                upload["status"] = "Failed"
                upload["error_message"] = upload.get("error_message") or "Upload cancelled"

            upload["completed_at"] = self._now_text()

    def _get_finish_upload_details(self, finish_id):
        if not finish_id:
            return None

        row = self.db.fetchone(
            """
            SELECT
                cf.id AS finish_id,
                cf.card_id,
                cf.finish,
                c.set_id,
                c.number,
                c.name,
                c.rarity,
                COALESCE(i.quantity, 0) AS inventory_quantity,
                COALESCE(i.cost_price, 0) AS cost_price,
                COALESCE(i.sell_price, 0) AS sell_price
            FROM card_finishes cf
            INNER JOIN cards c
                ON c.id = cf.card_id
            LEFT JOIN inventory i
                ON i.card_id = c.id
            WHERE cf.id = ?
            """,
            (finish_id,),
        )

        return dict(row) if row else None

    def _build_repository_path(self, set_id, local_image_path):
        filename = Path(str(local_image_path or "image.png")).name
        return f"cards/{str(set_id or '').upper()}/{filename}"

    def _github_token(self):
        return os.getenv("GITHUB_TOKEN")

    def _upload_image_to_github(self, local_image_path, repository_path):
        if not local_image_path or not repository_path:
            return None

        image_file = Path(str(local_image_path))
        if not image_file.exists() or not image_file.is_file():
            return None

        token = self._github_token()
        if not token:
            raise RuntimeError("GITHUB_TOKEN is not configured")

        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
        }

        content_url = (
            f"https://api.github.com/repos/"
            f"{GITHUB_OWNER}/{GITHUB_REPO}/contents/{repository_path}"
        )

        get_response = requests.get(content_url, headers=headers, timeout=30)
        sha = None
        if get_response.status_code == 200:
            sha = (get_response.json() or {}).get("sha")
        elif get_response.status_code != 404:
            raise RuntimeError(f"GitHub check failed ({get_response.status_code})")

        with image_file.open("rb") as handle:
            encoded = base64.b64encode(handle.read()).decode("utf-8")

        payload = {
            "message": f"Upload {image_file.name}",
            "content": encoded,
            "branch": GITHUB_BRANCH,
        }
        if sha:
            payload["sha"] = sha

        put_response = requests.put(content_url, headers=headers, json=payload, timeout=60)
        if put_response.status_code not in (200, 201):
            raise RuntimeError(f"GitHub upload failed ({put_response.status_code})")

        return (
            f"https://raw.githubusercontent.com/"
            f"{GITHUB_OWNER}/{GITHUB_REPO}/{GITHUB_BRANCH}/{repository_path}"
        )

    def _save_finish_github_url(self, finish_id, github_url):
        if not finish_id:
            return

        self.create_finish_workspace(finish_id)
        self.db.execute(
            """
            UPDATE finish_workspace
            SET
                github_url = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE finish_id = ?
            """,
            (str(github_url or ""), finish_id),
        )

    def _now_text(self):
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # -----------------
    # eBay Publishing Queue
    # -----------------

    def queue_finish_for_ebay(
        self,
        finish_id,
        listing_group="",
        listing_type="Variation",
        listing_title_override="",
    ):
        details = self._get_finish_upload_details(finish_id)
        if details is None:
            return {
                "queued": False,
                "reason": "Finish not found",
                "entry": None,
            }

        self.create_finish_workspace(finish_id)
        workspace = self.get_finish_workspace(finish_id) or {}
        current_status = str(workspace.get("ebay_status") or self.EBAY_STATUS_NOT_QUEUED)

        if current_status in (self.EBAY_STATUS_QUEUED, self.EBAY_STATUS_EXPORTING):
            return {
                "queued": False,
                "reason": "Finish is already queued",
                "entry": self._get_ebay_queue_entry(finish_id),
            }

        if current_status == self.EBAY_STATUS_EXPORTED:
            return {
                "queued": False,
                "reason": "Finish has already been exported",
                "entry": self._get_ebay_queue_entry(finish_id),
            }

        eligibility = self._evaluate_ebay_eligibility(finish_id)
        if not eligibility.get("eligible"):
            reason = "; ".join(eligibility.get("reasons") or ["Finish is not eligible"])
            self._save_ebay_queue_fields(
                finish_id,
                ebay_status=self.EBAY_STATUS_NOT_QUEUED,
                ebay_error=reason,
            )
            return {
                "queued": False,
                "reason": reason,
                "entry": self._get_ebay_queue_entry(finish_id),
            }

        queue_group = str(listing_group or details.get("set_id") or "default").upper()
        queue_type = str(listing_type or "Variation")

        self._save_ebay_queue_fields(
            finish_id,
            ebay_status=self.EBAY_STATUS_QUEUED,
            queued_at=self._now_text(),
            listing_group=queue_group,
            listing_type=queue_type,
            listing_title_override=str(listing_title_override or workspace.get("listing_title_override") or ""),
            export_batch="",
            ebay_error="",
        )

        return {
            "queued": True,
            "reason": None,
            "entry": self._get_ebay_queue_entry(finish_id),
        }

    def queue_all_ready_finishes(self, set_id):
        readiness_rows = self.get_set_readiness(set_id)
        queued = []
        skipped = []

        for row in readiness_rows:
            finish_id = row.get("finish_id")
            if not finish_id:
                continue

            result = self.queue_finish_for_ebay(finish_id, listing_group=row.get("set_id") or set_id)
            if result.get("queued"):
                queued.append(result.get("entry"))
            else:
                skipped.append(
                    {
                        "finish_id": finish_id,
                        "reason": result.get("reason") or "Not eligible",
                    }
                )

        return {
            "queued": queued,
            "skipped": skipped,
        }

    def export_queue_to_csv(self, set_id=None, output_path="output/Ebay_Variation_Upload.csv"):
        self.ebay_cancel_requested = False
        queued_rows = self._get_ebay_queue_rows(set_id=set_id, statuses=[self.EBAY_STATUS_QUEUED])

        if not queued_rows:
            return {
                "exported": 0,
                "failed": 0,
                "skipped": 0,
                "output_file": None,
                "batch_id": None,
                "reason": "No queued finishes",
            }

        batch_id = datetime.now().strftime("%Y%m%d%H%M%S")
        now_text = self._now_text()

        cards_to_export = []
        exportable_finish_ids = []
        failed = []
        skipped = []

        for row in queued_rows:
            finish_id = row.get("finish_id")
            if not finish_id:
                continue

            if self.ebay_cancel_requested:
                self._save_ebay_queue_fields(
                    finish_id,
                    ebay_status=self.EBAY_STATUS_CANCELLED,
                    ebay_error="Export cancelled",
                )
                skipped.append({"finish_id": finish_id, "reason": "Export cancelled"})
                continue

            self._save_ebay_queue_fields(
                finish_id,
                ebay_status=self.EBAY_STATUS_EXPORTING,
                export_batch=batch_id,
                ebay_error="",
            )

            eligibility = self._evaluate_ebay_eligibility(finish_id)
            if not eligibility.get("eligible"):
                reason = "; ".join(eligibility.get("reasons") or ["Finish is not eligible"])
                self._save_ebay_queue_fields(
                    finish_id,
                    ebay_status=self.EBAY_STATUS_FAILED,
                    ebay_error=reason,
                )
                failed.append({"finish_id": finish_id, "reason": reason})
                continue

            readiness = eligibility.get("readiness") or {}
            github_status = eligibility.get("github_status") or {}
            details = eligibility.get("details") or {}

            image_url = github_status.get("remote_url") or details.get("github_url") or ""

            cards_to_export.append(
                {
                    "sku": self._build_ebay_sku(details),
                    "name": str(details.get("name") or ""),
                    "set": str(details.get("set_id") or ""),
                    "number": str(details.get("number") or ""),
                    "finish": str(details.get("finish") or ""),
                    "qty": int(readiness.get("quantity") or 0),
                    "price": float(readiness.get("sell_price") or 0),
                    "image": str(image_url),
                    "listing_group": str(row.get("listing_group") or details.get("set_id") or "default").upper(),
                    "listing_title_override": str(row.get("listing_title_override") or ""),
                }
            )
            exportable_finish_ids.append(finish_id)

        if not cards_to_export:
            return {
                "exported": 0,
                "failed": len(failed),
                "skipped": len(skipped),
                "output_file": None,
                "batch_id": batch_id,
                "reason": "No valid queued finishes",
            }

        try:
            export_result = export_cards(cards_to_export, output_path=output_path)
        except Exception as exc:
            message = str(exc)
            for finish_id in exportable_finish_ids:
                self._save_ebay_queue_fields(
                    finish_id,
                    ebay_status=self.EBAY_STATUS_FAILED,
                    ebay_error=message,
                )

            return {
                "exported": 0,
                "failed": len(exportable_finish_ids) + len(failed),
                "skipped": len(skipped),
                "output_file": None,
                "batch_id": batch_id,
                "reason": message,
            }

        for finish_id in exportable_finish_ids:
            self._save_ebay_queue_fields(
                finish_id,
                ebay_status=self.EBAY_STATUS_EXPORTED,
                exported_at=now_text,
                export_batch=batch_id,
                ebay_error="",
            )

        return {
            "exported": len(exportable_finish_ids),
            "failed": len(failed),
            "skipped": len(skipped),
            "output_file": export_result.get("output_file"),
            "batch_id": batch_id,
            "reason": None,
        }

    def cancel_ebay_queue(self, set_id=None):
        self.ebay_cancel_requested = True
        queued_rows = self._get_ebay_queue_rows(set_id=set_id, statuses=[self.EBAY_STATUS_QUEUED])
        for row in queued_rows:
            finish_id = row.get("finish_id")
            if not finish_id:
                continue

            self._save_ebay_queue_fields(
                finish_id,
                ebay_status=self.EBAY_STATUS_CANCELLED,
                ebay_error="Queue cancelled",
            )

        return self.get_ebay_queue_progress(set_id=set_id)

    def retry_failed_exports(self, set_id=None):
        failed_rows = self._get_ebay_queue_rows(set_id=set_id, statuses=[self.EBAY_STATUS_FAILED])
        queued = []
        skipped = []

        for row in failed_rows:
            finish_id = row.get("finish_id")
            if not finish_id:
                continue

            result = self.queue_finish_for_ebay(
                finish_id,
                listing_group=row.get("listing_group"),
                listing_type=row.get("listing_type") or "Variation",
                listing_title_override=row.get("listing_title_override") or "",
            )
            if result.get("queued"):
                queued.append(result.get("entry"))
            else:
                skipped.append(
                    {
                        "finish_id": finish_id,
                        "reason": result.get("reason") or "Not eligible",
                    }
                )

        return {
            "queued": queued,
            "skipped": skipped,
        }

    def clear_completed_queue(self, set_id=None):
        completed_rows = self._get_ebay_queue_rows(
            set_id=set_id,
            statuses=[self.EBAY_STATUS_EXPORTED, self.EBAY_STATUS_CANCELLED],
        )

        for row in completed_rows:
            finish_id = row.get("finish_id")
            if not finish_id:
                continue

            self._save_ebay_queue_fields(
                finish_id,
                ebay_status=self.EBAY_STATUS_NOT_QUEUED,
                queued_at="",
                export_batch="",
                ebay_error="",
            )

        return {
            "cleared": len(completed_rows),
            "progress": self.get_ebay_queue_progress(set_id=set_id),
        }

    def refresh_ebay_queue_status(self, set_id=None, queue_filter="All", include_eligibility=True):
        queue_rows = self._get_ebay_queue_rows(set_id=set_id)
        entries = []

        for row in queue_rows:
            finish_id = row.get("finish_id")
            if not finish_id:
                continue

            if include_eligibility:
                eligibility = self._evaluate_ebay_eligibility(finish_id)
                readiness = eligibility.get("readiness") or {}
                github_status = eligibility.get("github_status") or {}
                reasons = eligibility.get("reasons") or []
                is_ready = bool(eligibility.get("eligible"))
                reason_text = "; ".join(reasons) if reasons else ""
            else:
                readiness = {}
                github_status = {}
                is_ready = None
                reason_text = ""

            entry = {
                **row,
                "quantity": int(readiness.get("quantity") or 0),
                "price": float(readiness.get("sell_price") or 0),
                "github_status": github_status.get("status") or "Pending",
                "is_ready": is_ready,
                "reason": reason_text,
            }
            entries.append(entry)

        filtered = self._filter_ebay_queue_entries(entries, queue_filter)

        return {
            "queue": filtered,
            "progress": self.get_ebay_queue_progress(set_id=set_id),
            "summary": self.get_export_summary(set_id=set_id),
            "filter": queue_filter,
        }

    def get_ebay_queue_progress(self, set_id=None):
        rows = self._get_ebay_queue_rows(set_id=set_id)

        completed = 0
        failed = 0
        remaining = 0
        current_export = None

        started_markers = []

        for row in rows:
            status = row.get("status")
            if status == self.EBAY_STATUS_EXPORTED:
                completed += 1
            elif status == self.EBAY_STATUS_FAILED:
                failed += 1
            elif status in (self.EBAY_STATUS_QUEUED, self.EBAY_STATUS_EXPORTING):
                remaining += 1

            if status == self.EBAY_STATUS_EXPORTING and current_export is None:
                current_export = row

            marker = row.get("queued_at")
            if marker:
                started_markers.append(marker)

        elapsed = "00:00:00"
        if started_markers:
            try:
                first_start = min(datetime.strptime(value, "%Y-%m-%d %H:%M:%S") for value in started_markers)
                elapsed_seconds = max(0, int((datetime.now() - first_start).total_seconds()))
                hours = elapsed_seconds // 3600
                minutes = (elapsed_seconds % 3600) // 60
                seconds = elapsed_seconds % 60
                elapsed = f"{hours:02}:{minutes:02}:{seconds:02}"
            except Exception:
                elapsed = "00:00:00"

        return {
            "current_export": current_export,
            "completed": completed,
            "remaining": remaining,
            "failed": failed,
            "total": len(rows),
            "elapsed_time": elapsed,
        }

    def get_export_summary(self, set_id=None):
        rows = self._get_ebay_queue_rows(set_id=set_id)

        summary = {
            "queued": 0,
            "exported": 0,
            "failed": 0,
            "cancelled": 0,
            "not_queued": 0,
            "total": len(rows),
        }

        for row in rows:
            status = row.get("status")
            if status == self.EBAY_STATUS_QUEUED:
                summary["queued"] += 1
            elif status == self.EBAY_STATUS_EXPORTING:
                summary["queued"] += 1
            elif status == self.EBAY_STATUS_EXPORTED:
                summary["exported"] += 1
            elif status == self.EBAY_STATUS_FAILED:
                summary["failed"] += 1
            elif status == self.EBAY_STATUS_CANCELLED:
                summary["cancelled"] += 1
            else:
                summary["not_queued"] += 1

        return summary

    def get_finish_ebay_status(self, finish_id):
        entry = self._get_ebay_queue_entry(finish_id) or {}
        eligibility = self._evaluate_ebay_eligibility(finish_id)
        reasons = eligibility.get("reasons") or []

        return {
            "status": entry.get("status") or self.EBAY_STATUS_NOT_QUEUED,
            "queued_at": entry.get("queued_at") or "",
            "exported_at": entry.get("exported_at") or "",
            "export_batch": entry.get("export_batch") or "",
            "listing_group": entry.get("listing_group") or "",
            "listing_type": entry.get("listing_type") or "",
            "reason": "; ".join(reasons) if reasons else (entry.get("ebay_error") or ""),
            "is_ready": bool(eligibility.get("eligible")),
        }

    def _build_ebay_sku(self, details):
        set_id = str(details.get("set_id") or "SET").upper()
        number = str(details.get("number") or "0").strip().replace(" ", "")
        finish = str(details.get("finish") or "normal").strip().lower().replace(" ", "-")
        return f"{set_id}-{number}-{finish}"

    def _get_ebay_queue_entry(self, finish_id):
        rows = self._get_ebay_queue_rows(finish_id=finish_id)
        return rows[0] if rows else None

    def _get_ebay_queue_rows(self, set_id=None, finish_id=None, statuses=None):
        query = """
            SELECT
                cf.id AS finish_id,
                cf.card_id,
                cf.finish,
                c.set_id,
                c.number AS card_number,
                c.name AS card_name,
                fw.github_url,
                COALESCE(NULLIF(fw.ebay_status, ''), ?) AS status,
                fw.queued_at,
                fw.exported_at,
                fw.listing_group,
                fw.listing_type,
                fw.export_batch,
                fw.listing_title_override,
                fw.ebay_error
            FROM card_finishes cf
            INNER JOIN cards c
                ON c.id = cf.card_id
            LEFT JOIN finish_workspace fw
                ON fw.finish_id = cf.id
            WHERE 1 = 1
        """

        params = [self.EBAY_STATUS_NOT_QUEUED]

        if set_id:
            query += " AND c.set_id = ?"
            params.append(set_id)

        if finish_id:
            query += " AND cf.id = ?"
            params.append(finish_id)

        if statuses:
            placeholders = ",".join("?" for _ in statuses)
            query += f" AND COALESCE(NULLIF(fw.ebay_status, ''), ?) IN ({placeholders})"
            params.append(self.EBAY_STATUS_NOT_QUEUED)
            params.extend(statuses)

        query += " ORDER BY c.number ASC, cf.id ASC"

        return [dict(row) for row in self.db.fetchall(query, tuple(params))]

    def _filter_ebay_queue_entries(self, entries, queue_filter):
        selected = str(queue_filter or "All")

        if selected == "All":
            return entries
        if selected == "Queued":
            return [
                row
                for row in entries
                if row.get("status") in (self.EBAY_STATUS_QUEUED, self.EBAY_STATUS_EXPORTING)
            ]
        if selected == "Exported":
            return [row for row in entries if row.get("status") == self.EBAY_STATUS_EXPORTED]
        if selected == "Failed":
            return [row for row in entries if row.get("status") == self.EBAY_STATUS_FAILED]
        if selected == "Ready":
            return [row for row in entries if row.get("is_ready")]
        if selected == "Not Ready":
            return [row for row in entries if not row.get("is_ready")]

        return entries

    def _evaluate_ebay_eligibility(self, finish_id):
        details = self._get_finish_upload_details(finish_id)
        if details is None:
            return {
                "eligible": False,
                "reasons": ["Finish not found"],
                "readiness": None,
                "github_status": None,
                "details": None,
            }

        readiness = self.get_finish_readiness(finish_id) or {}
        github_status = self.get_finish_github_status(finish_id) or {}

        reasons = []

        quantity = int(readiness.get("quantity") or 0)
        if quantity <= 0:
            reasons.append("Inventory Quantity must be greater than 0")

        price = float(readiness.get("sell_price") or 0)
        if price <= 0:
            reasons.append("Sell Price must be greater than 0")

        image_status = str(readiness.get("image_status") or "")
        if image_status != "ready":
            reasons.append("Image Status must be Ready")

        github_state = str(github_status.get("status") or "")
        if github_state != "Uploaded":
            reasons.append("GitHub Status must be Uploaded")

        if not bool(readiness.get("is_ready")):
            reasons.append("Readiness must be Ready")

        return {
            "eligible": len(reasons) == 0,
            "reasons": reasons,
            "readiness": readiness,
            "github_status": github_status,
            "details": details,
        }

    def _save_ebay_queue_fields(
        self,
        finish_id,
        ebay_status=None,
        queued_at=None,
        exported_at=None,
        listing_group=None,
        listing_type=None,
        export_batch=None,
        listing_title_override=None,
        ebay_error=None,
    ):
        if not finish_id:
            return

        self.create_finish_workspace(finish_id)
        workspace = self.get_finish_workspace(finish_id) or {}

        next_status = workspace.get("ebay_status") if ebay_status is None else ebay_status
        next_queued_at = workspace.get("queued_at") if queued_at is None else queued_at
        next_exported_at = workspace.get("exported_at") if exported_at is None else exported_at
        next_listing_group = workspace.get("listing_group") if listing_group is None else listing_group
        next_listing_type = workspace.get("listing_type") if listing_type is None else listing_type
        next_export_batch = workspace.get("export_batch") if export_batch is None else export_batch
        next_title_override = workspace.get("listing_title_override") if listing_title_override is None else listing_title_override
        next_error = workspace.get("ebay_error") if ebay_error is None else ebay_error

        self.db.execute(
            """
            UPDATE finish_workspace
            SET
                ebay_status = ?,
                queued_at = ?,
                exported_at = ?,
                listing_group = ?,
                listing_type = ?,
                export_batch = ?,
                listing_title_override = ?,
                ebay_error = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE finish_id = ?
            """,
            (
                str(next_status or ""),
                str(next_queued_at or ""),
                str(next_exported_at or ""),
                str(next_listing_group or ""),
                str(next_listing_type or ""),
                str(next_export_batch or ""),
                str(next_title_override or ""),
                str(next_error or ""),
                finish_id,
            ),
        )

    # -----------------
    # Inventory
    # -----------------

    def save_inventory(self, card_id, quantity, cost_price, sell_price):
        self.db.execute(
            """
            INSERT INTO inventory (card_id, quantity, cost_price, sell_price)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(card_id) DO UPDATE SET
                quantity = excluded.quantity,
                cost_price = excluded.cost_price,
                sell_price = excluded.sell_price
            """,
            (card_id, quantity, cost_price, sell_price),
        )

    def get_finish_inventory(self, finish_id, fallback_card_data=None):
        fallback_card_data = fallback_card_data or {}

        if not finish_id:
            return {
                "quantity": int(fallback_card_data.get("inventory_quantity", 0) or 0),
                "cost_price": float(fallback_card_data.get("cost_price", 0) or 0),
                "source": "card",
            }

        row = self.db.fetchone(
            """
            SELECT
                quantity,
                cost_price
            FROM finish_workspace
            WHERE finish_id = ?
            """,
            (finish_id,),
        )

        if row is not None:
            return {
                "quantity": int(row["quantity"] or 0),
                "cost_price": float(row["cost_price"] or 0),
                "source": "finish",
            }

        return {
            "quantity": int(fallback_card_data.get("inventory_quantity", 0) or 0),
            "cost_price": float(fallback_card_data.get("cost_price", 0) or 0),
            "source": "card",
        }

    def save_finish_inventory(self, finish_id, quantity, cost_price):
        if not finish_id:
            return None

        self.create_finish_workspace(finish_id)

        self.db.execute(
            """
            UPDATE finish_workspace
            SET
                quantity = ?,
                cost_price = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE finish_id = ?
            """,
            (quantity, cost_price, finish_id),
        )

        return self.get_finish_inventory(finish_id)

    def get_finish_pricing(self, finish_id, fallback_card_data=None):
        fallback_card_data = fallback_card_data or {}

        fallback_sell = float(fallback_card_data.get("sell_price", 0) or 0)
        fallback_market = float(
            fallback_card_data.get("market_price")
            or fallback_card_data.get("price")
            or 0
        )

        if not finish_id:
            return {
                "sell_price": fallback_sell,
                "market_price": fallback_market,
                "source": "card",
            }

        row = self.db.fetchone(
            """
            SELECT
                sell_price,
                market_price
            FROM finish_workspace
            WHERE finish_id = ?
            """,
            (finish_id,),
        )

        if row is None:
            return {
                "sell_price": fallback_sell,
                "market_price": fallback_market,
                "source": "card",
            }

        row_sell = float(row["sell_price"] or 0)
        row_market = float(row["market_price"] or 0)

        # Backward compatibility: treat all-zero finish pricing as not yet migrated.
        if row_sell == 0 and row_market == 0 and (fallback_sell != 0 or fallback_market != 0):
            return {
                "sell_price": fallback_sell,
                "market_price": fallback_market,
                "source": "card",
            }

        return {
            "sell_price": row_sell,
            "market_price": row_market,
            "source": "finish",
        }

    def save_finish_pricing(self, finish_id, sell_price, market_price):
        if not finish_id:
            return None

        self.create_finish_workspace(finish_id)

        self.db.execute(
            """
            UPDATE finish_workspace
            SET
                sell_price = ?,
                market_price = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE finish_id = ?
            """,
            (sell_price, market_price, finish_id),
        )

        return self.get_finish_pricing(finish_id)

    # -----------------
    # Workflow
    # -----------------

    def close(self):
        self.db.close()

    def create_finishes(self, card):

        if card.get("images"):

            finish_id = self.add_finish(card["id"], "Normal")
            self.create_finish_workspace(finish_id)

        if card.get("tcgplayer"):

            finish_id = self.add_finish(card["id"], "Reverse Holo")
            self.create_finish_workspace(finish_id)

    # -----------------
    # Finish Workspace
    # -----------------

    def create_finish_workspace(self, finish_id):
        if not finish_id:
            return None

        self.db.execute(
            """
            INSERT OR IGNORE INTO finish_workspace (finish_id)
            VALUES (?)
            """,
            (finish_id,),
        )

        return self.get_finish_workspace(finish_id)

    def get_finish_workspace(self, finish_id):
        if not finish_id:
            return None

        row = self.db.fetchone(
            """
            SELECT *
            FROM finish_workspace
            WHERE finish_id = ?
            """,
            (finish_id,),
        )

        return dict(row) if row else None

    def save_finish_workspace(
        self,
        finish_id,
        quantity=0,
        cost_price=0,
        sell_price=0,
        market_price=0,
        image_path="",
        github_url="",
        ebay_listing_id="",
        ebay_status="",
        queued_at="",
        exported_at="",
        listing_group="",
        listing_type="",
        export_batch="",
        listing_title_override="",
        ebay_error="",
        is_image_verified=0,
        is_ready_for_listing=0,
    ):
        if not finish_id:
            return None

        self.db.execute(
            """
            INSERT INTO finish_workspace (
                finish_id,
                quantity,
                cost_price,
                sell_price,
                market_price,
                image_path,
                github_url,
                ebay_listing_id,
                ebay_status,
                queued_at,
                exported_at,
                listing_group,
                listing_type,
                export_batch,
                listing_title_override,
                ebay_error,
                is_image_verified,
                is_ready_for_listing,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(finish_id) DO UPDATE SET
                quantity = excluded.quantity,
                cost_price = excluded.cost_price,
                sell_price = excluded.sell_price,
                market_price = excluded.market_price,
                image_path = excluded.image_path,
                github_url = excluded.github_url,
                ebay_listing_id = excluded.ebay_listing_id,
                ebay_status = excluded.ebay_status,
                queued_at = excluded.queued_at,
                exported_at = excluded.exported_at,
                listing_group = excluded.listing_group,
                listing_type = excluded.listing_type,
                export_batch = excluded.export_batch,
                listing_title_override = excluded.listing_title_override,
                ebay_error = excluded.ebay_error,
                is_image_verified = excluded.is_image_verified,
                is_ready_for_listing = excluded.is_ready_for_listing,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                finish_id,
                quantity,
                cost_price,
                sell_price,
                market_price,
                image_path,
                github_url,
                ebay_listing_id,
                ebay_status,
                queued_at,
                exported_at,
                listing_group,
                listing_type,
                export_batch,
                listing_title_override,
                ebay_error,
                is_image_verified,
                is_ready_for_listing,
            ),
        )

        return self.get_finish_workspace(finish_id)

    def initialize_finish_workspace(self, finish_id=None):
        if finish_id is not None:
            return self.create_finish_workspace(finish_id)

        self.db.execute(
            """
            INSERT OR IGNORE INTO finish_workspace (finish_id)
            SELECT cf.id
            FROM card_finishes cf
            """
        )

        return True


    def get_card_count(self, set_id):

        result = self.db.fetchone(
            """
            SELECT COUNT(*)
            FROM cards
            WHERE set_id = ?
            """,
            (set_id,),
        )

        return result[0]

    def get_sets_with_counts(self):
        return self.db.fetchall(
            """
            SELECT
                s.id,
                s.name,
                s.series,
                s.release_date,
                COALESCE(NULLIF(TRIM(s.api_set), ''), s.id) AS api_set,
                COUNT(c.id) AS card_count
            FROM sets s
            LEFT JOIN cards c
                ON s.id = c.set_id
            GROUP BY s.id
            ORDER BY s.release_date DESC
            """
        )

    # -----------------
    # Local Image Workspace
    # -----------------

    IMAGE_STATE_REMOVED = -1
    IMAGE_STATE_UNSET = 0
    IMAGE_STATE_EXPLICIT = 1
    IMAGE_STATE_AUTO = 2

    def get_finish_image(self, set_id, card_data, finish_id):
        card_data = card_data or {}

        finish_row = self.db.fetchone(
            """
            SELECT
                id,
                finish,
                image_path
            FROM card_finishes
            WHERE id = ?
            """,
            (finish_id,),
        )

        if finish_row is None:
            return self.validate_finish_image(None)

        finish_workspace = self.get_finish_workspace(finish_id) or {}
        image_state = int(finish_workspace.get("is_image_verified") or self.IMAGE_STATE_UNSET)

        if image_state == self.IMAGE_STATE_REMOVED:
            return self.validate_finish_image(None, source="removed")

        explicit_path = finish_workspace.get("image_path") or finish_row["image_path"]
        explicit_resolved = self._resolve_image_path(explicit_path)

        if explicit_resolved is not None:
            source = "explicit" if image_state == self.IMAGE_STATE_EXPLICIT else "auto"
            return self.validate_finish_image(str(explicit_resolved), source=source)

        if explicit_path:
            source = "explicit" if image_state == self.IMAGE_STATE_EXPLICIT else "auto"
            return self.validate_finish_image(str(explicit_path), source=source)

        discovered = self._resolve_finish_image_file(
            set_id,
            card_data,
            finish_row["finish"],
        )

        if discovered is not None:
            self._save_finish_image_state(finish_id, str(discovered), self.IMAGE_STATE_AUTO)
            return self.validate_finish_image(str(discovered), source="auto")

        return self.validate_finish_image(None, source="missing")

    def set_finish_image(self, finish_id, image_path):
        if not finish_id:
            return None

        resolved = self._resolve_image_path(image_path)
        resolved_path = str(resolved) if resolved is not None else str(image_path or "")
        self._save_finish_image_state(finish_id, resolved_path, self.IMAGE_STATE_EXPLICIT)

        return self.get_finish_workspace(finish_id)

    def remove_finish_image(self, finish_id):
        if not finish_id:
            return None

        self._save_finish_image_state(finish_id, "", self.IMAGE_STATE_REMOVED)

        return self.get_finish_workspace(finish_id)

    def refresh_finish_image(self, set_id, card_data, finish_id):
        return self.get_finish_image(set_id, card_data, finish_id)

    def validate_finish_image(self, image_path, source="missing"):
        if not image_path:
            return {
                "status": "missing",
                "status_badge": "🟡 Missing Image",
                "is_valid": False,
                "source": source,
                "path": None,
                "filename": None,
                "resolution": None,
                "file_size": None,
                "file_size_bytes": None,
                "format": None,
                "last_modified": None,
            }

        resolved = self._resolve_image_path(image_path)
        if resolved is None:
            return {
                "status": "invalid",
                "status_badge": "🔴 Invalid Image",
                "is_valid": False,
                "source": source,
                "path": str(image_path),
                "filename": Path(str(image_path)).name,
                "resolution": None,
                "file_size": None,
                "file_size_bytes": None,
                "format": None,
                "last_modified": None,
            }

        resolution = None
        image_format = resolved.suffix.replace(".", "").upper()
        is_valid = True
        try:
            from PIL import Image

            with Image.open(resolved) as image:
                resolution = f"{image.width} x {image.height}"
                if image.format:
                    image_format = image.format.upper()
        except Exception:
            is_valid = False

        file_size_bytes = resolved.stat().st_size
        last_modified = self._format_timestamp(resolved.stat().st_mtime)

        if not is_valid:
            return {
                "status": "invalid",
                "status_badge": "🔴 Invalid Image",
                "is_valid": False,
                "source": source,
                "path": str(resolved),
                "filename": resolved.name,
                "resolution": None,
                "file_size": self._format_file_size(file_size_bytes),
                "file_size_bytes": file_size_bytes,
                "format": image_format,
                "last_modified": last_modified,
            }

        return {
            "status": "ready",
            "status_badge": "🟢 Image Ready",
            "is_valid": True,
            "source": source,
            "path": str(resolved),
            "filename": resolved.name,
            "resolution": resolution,
            "file_size": self._format_file_size(file_size_bytes),
            "file_size_bytes": file_size_bytes,
            "format": image_format,
            "last_modified": last_modified,
        }

    def _save_finish_image_state(self, finish_id, image_path, image_state):
        if not finish_id:
            return None

        self.create_finish_workspace(finish_id)
        self.db.execute(
            """
            UPDATE finish_workspace
            SET
                image_path = ?,
                is_image_verified = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE finish_id = ?
            """,
            (str(image_path or ""), int(image_state), finish_id),
        )

        return self.get_finish_workspace(finish_id)

    def get_card_image_info(self, set_id, card_data):
        card_data = card_data or {}
        image_file = self._resolve_card_image_file(set_id, card_data)
        image_folder = self._resolve_image_set_folder(set_id)

        if image_file is None:
            return {
                "found": False,
                "path": None,
                "filename": None,
                "resolution": None,
                "file_size": None,
                "file_size_bytes": None,
                "format": None,
                "folder": str(image_folder) if image_folder else None,
            }

        resolution = None
        image_format = image_file.suffix.replace(".", "").upper()
        try:
            from PIL import Image

            with Image.open(image_file) as image:
                resolution = f"{image.width} x {image.height}"
                if image.format:
                    image_format = image.format.upper()
        except Exception:
            pass

        file_size_bytes = image_file.stat().st_size

        return {
            "found": True,
            "path": str(image_file),
            "filename": image_file.name,
            "resolution": resolution,
            "file_size": self._format_file_size(file_size_bytes),
            "file_size_bytes": file_size_bytes,
            "format": image_format,
            "folder": str(image_file.parent),
        }

    def open_image_folder(self, set_id):
        folder = self._resolve_image_set_folder(set_id)
        if folder is None:
            return False

        try:
            os.startfile(str(folder))
            return True
        except Exception:
            return False

    def reveal_image(self, image_path):
        if not image_path:
            return False

        image_file = Path(image_path)
        if not image_file.exists():
            return False

        try:
            subprocess.run(["explorer", "/select,", str(image_file)], check=False)
            return True
        except Exception:
            return False

    def _workspace_root(self):
        return Path(__file__).resolve().parent.parent

    def _images_root(self):
        return self._workspace_root() / "images"

    def _resolve_image_set_folder(self, set_id):
        images_root = self._images_root()
        if not images_root.exists() or not set_id:
            return None

        set_name = str(set_id).strip()
        direct_candidates = [
            images_root / set_name,
            images_root / set_name.upper(),
            images_root / set_name.lower(),
        ]

        for folder in direct_candidates:
            if folder.exists() and folder.is_dir():
                return folder

        set_name_lower = set_name.lower()
        for child in images_root.iterdir():
            if child.is_dir() and child.name.lower() == set_name_lower:
                return child

        return None

    def _resolve_card_image_file(self, set_id, card_data):
        path_from_workspace = card_data.get("image_path")
        existing_path = self._resolve_image_path(path_from_workspace)
        if existing_path is not None:
            return existing_path

        image_folder = self._resolve_image_set_folder(set_id)
        if image_folder is None:
            return None

        set_name = str(set_id or "").strip()
        card_number = str(card_data.get("number") or "").strip()
        if not set_name or not card_number:
            return None

        number_variants = []
        number_variants.append(card_number)
        if card_number.isdigit():
            number_variants.append(str(int(card_number)))
            number_variants.append(str(int(card_number)).zfill(3))

        seen_numbers = set()
        unique_number_variants = []
        for variant in number_variants:
            normalized = variant.strip()
            if normalized and normalized not in seen_numbers:
                seen_numbers.add(normalized)
                unique_number_variants.append(normalized)

        set_variants = []
        for variant in (set_name, set_name.upper(), set_name.lower()):
            if variant not in set_variants:
                set_variants.append(variant)

        base_names = []
        finish_suffixes = ("N", "RH", "H", "")
        for set_variant in set_variants:
            for number_variant in unique_number_variants:
                for finish in finish_suffixes:
                    if finish:
                        base_names.append(f"{set_variant}-{number_variant}-{finish}")
                    else:
                        base_names.append(f"{set_variant}-{number_variant}")

        # Respect extension priority: PNG, JPG, JPEG, WEBP.
        for extension in IMAGE_EXTENSIONS:
            for base_name in base_names:
                candidate = image_folder / f"{base_name}{extension}"
                if candidate.exists() and candidate.is_file():
                    return candidate

        return None

    def _resolve_finish_image_file(self, set_id, card_data, finish_name):
        image_folder = self._resolve_image_set_folder(set_id)
        if image_folder is None:
            return None

        set_name = str(set_id or "").strip()
        card_number = str(card_data.get("number") or "").strip()
        if not set_name or not card_number:
            return None

        number_variants = [card_number]
        if card_number.isdigit():
            number_variants.append(str(int(card_number)))
            number_variants.append(str(int(card_number)).zfill(3))

        seen_numbers = set()
        unique_number_variants = []
        for variant in number_variants:
            normalized = variant.strip()
            if normalized and normalized not in seen_numbers:
                seen_numbers.add(normalized)
                unique_number_variants.append(normalized)

        set_variants = []
        for variant in (set_name, set_name.upper(), set_name.lower()):
            if variant not in set_variants:
                set_variants.append(variant)

        finish_tokens = self._finish_tokens(finish_name)
        base_names = []
        for set_variant in set_variants:
            for number_variant in unique_number_variants:
                for token in finish_tokens:
                    if token:
                        base_names.append(f"{set_variant}-{number_variant}-{token}")
                    else:
                        base_names.append(f"{set_variant}-{number_variant}")

        for extension in IMAGE_EXTENSIONS:
            for base_name in base_names:
                candidate = image_folder / f"{base_name}{extension}"
                if candidate.exists() and candidate.is_file():
                    return candidate

        return None

    def _finish_tokens(self, finish_name):
        normalized = str(finish_name or "").strip().lower()

        token_map = {
            "normal": ["N", "NORMAL", ""],
            "reverse holo": ["RH", "REVERSEHOLO", "REVERSE_HOLO", "REVERSE-HOLO"],
            "holo": ["H", "HOLO"],
            "master ball": ["MB", "MASTERBALL", "MASTER_BALL", "MASTER-BALL"],
            "poké ball": ["PB", "POKEBALL", "POKE_BALL", "POKE-BALL"],
            "poke ball": ["PB", "POKEBALL", "POKE_BALL", "POKE-BALL"],
            "gold": ["GOLD", "G"],
            "illustration rare": ["IR", "ILLUSTRATIONRARE", "ILLUSTRATION_RARE", "ILLUSTRATION-RARE"],
            "trainer gallery": ["TG", "TRAINERGALLERY", "TRAINER_GALLERY", "TRAINER-GALLERY"],
        }

        tokens = token_map.get(normalized, [])
        fallback = "".join(ch for ch in normalized.upper() if ch.isalnum())
        if fallback and fallback not in tokens:
            tokens.append(fallback)

        if "" not in tokens:
            tokens.append("")

        return tokens

    def _resolve_image_path(self, image_path):
        if not image_path:
            return None

        path = Path(str(image_path))
        candidates = [path]
        if not path.is_absolute():
            candidates.append(self._workspace_root() / path)

        for candidate in candidates:
            if candidate.exists() and candidate.is_file() and candidate.suffix.lower() in IMAGE_EXTENSIONS:
                return candidate

        return None

    def _format_file_size(self, size_bytes):
        value = float(size_bytes)
        units = ["B", "KB", "MB", "GB"]
        unit_index = 0

        while value >= 1024 and unit_index < len(units) - 1:
            value /= 1024
            unit_index += 1

        if unit_index == 0:
            return f"{int(value)} {units[unit_index]}"

        return f"{value:.1f} {units[unit_index]}"

    def _format_timestamp(self, timestamp):
        try:
            return datetime.fromtimestamp(float(timestamp)).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return None

