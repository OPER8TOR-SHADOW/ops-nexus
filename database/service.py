from .database import Database
from pathlib import Path
import os
import subprocess
from datetime import datetime
import uuid
import base64

import requests

from config import GITHUB_OWNER, GITHUB_REPO, GITHUB_BRANCH


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
    def __init__(self):
        self.db = Database()
        self.db.create()
        self.initialize_finish_workspace()
        self.upload_queue = []
        self.upload_index = {}
        self.upload_processing = False
        self.upload_cancel_requested = False

    # -----------------
    # Sets
    # -----------------

    def add_set(self, set_data):
        self.db.execute(
            """
            INSERT OR REPLACE INTO sets
            (id, name, series, release_date, printed_total)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                set_data["id"],
                set_data["name"],
                set_data.get("series"),
                set_data.get("releaseDate"),
                set_data.get("printedTotal"),
            ),
        )

    def get_sets(self):
        return self.db.fetchall(
            "SELECT * FROM sets ORDER BY release_date DESC"
        )

    # -----------------
    # Cards
    # -----------------
    def add_card(self, card):
        self.db.execute(
        """
        INSERT OR REPLACE INTO cards
        (id, set_id, number, name, rarity)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            card["id"],
            card["set"]["id"],
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
                MAX(cf.image_path) AS image_path,
                MAX(cf.github_url) AS github_url,
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

    def cancel_queue(self):
        self.upload_cancel_requested = True
        for upload in self.upload_queue:
            if upload.get("status") == "Pending":
                upload["status"] = "Cancelled"
                upload["completed_at"] = self._now_text()

        return self.get_queue_progress()

    def refresh_queue_status(self):
        return {
            "queue": [dict(upload) for upload in self.upload_queue],
            "progress": self.get_queue_progress(),
        }

    def get_queue_progress(self):
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
                is_image_verified,
                is_ready_for_listing,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(finish_id) DO UPDATE SET
                quantity = excluded.quantity,
                cost_price = excluded.cost_price,
                sell_price = excluded.sell_price,
                market_price = excluded.market_price,
                image_path = excluded.image_path,
                github_url = excluded.github_url,
                ebay_listing_id = excluded.ebay_listing_id,
                ebay_status = excluded.ebay_status,
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

