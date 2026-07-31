from __future__ import annotations

import hashlib
from io import BytesIO
from datetime import datetime, timedelta
from pathlib import Path
import xml.etree.ElementTree as ET

import requests

from database.repository import DatabaseRepository
from gui.services.ebay_api_service import EbayApiError, EbayApiService


class MarketplaceSyncService:

    def __init__(self, ebay_service=None, repository=None):
        self.ebay_service = ebay_service or EbayApiService()
        self.repository = repository or DatabaseRepository()
        self.project_root = Path(__file__).resolve().parents[2]
        self.thumbnail_dir = self.project_root / ".cache" / "marketplace_thumbnails"
        self.thumbnail_dir.mkdir(parents=True, exist_ok=True)

    def sync_marketplace_cache(self, force_refresh=False):
        seller = self._fetch_seller_identity(force_refresh=force_refresh)
        listings = self._download_active_listings(seller)
        written = self.repository.replace_marketplace_cache(listings)

        return {
            "ok": True,
            "written": written,
            "seller": seller,
            "source": "trading.getSellerList",
        }

    def clear_marketplace_cache(self):
        self.repository.clear_marketplace_cache()

    def _fetch_seller_identity(self, force_refresh=False):
        access_token = self.ebay_service._valid_access_token()
        environment = self.ebay_service.get_config()["environment"]
        api_base = self.ebay_service.API_BASES[environment]

        response = requests.get(
            f"{api_base}/commerce/identity/v1/user",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
            },
            timeout=30,
        )

        if response.status_code != 200:
            raise EbayApiError("Unable to load seller identity for marketplace sync.")

        payload = response.json() or {}
        business = payload.get("businessAccount") or {}
        store_name = business.get("name") if isinstance(business, dict) else None

        return {
            "user_id": str(payload.get("userId") or "").strip(),
            "username": str(payload.get("username") or payload.get("userId") or "").strip(),
            "store_name": str(store_name or "").strip(),
            "environment": environment,
            "api_base": api_base,
            "access_token": access_token,
            "site_id": self._resolve_site_id(payload.get("registrationMarketplaceId")),
        }

    def _download_active_listings(self, seller):
        response_items = self._request_trading_page(seller)
        return [self._normalize_item(item, seller) for item in response_items]

    def _request_trading_page(self, seller):
        access_token = seller["access_token"]
        api_base = seller["api_base"]
        site_id = seller.get("site_id", 0)
        endpoint = f"{api_base}/ws/api.dll"

        headers = {
            "X-EBAY-API-CALL-NAME": "GetSellerList",
            "X-EBAY-API-IAF-TOKEN": access_token,
            "X-EBAY-API-SITEID": str(site_id),
            "X-EBAY-API-COMPATIBILITY-LEVEL": "1455",
            "Content-Type": "text/xml",
            "Accept": "text/xml",
        }

        end_from, end_to = self._trading_end_time_window()
        page_number = 1
        entries_per_page = 200
        items = []

        while True:
            body = self._build_get_seller_list_request(end_from, end_to, page_number, entries_per_page)
            response = requests.post(endpoint, headers=headers, data=body, timeout=60)
            if response.status_code != 200:
                raise EbayApiError(self._friendly_trading_error(response))

            payload = self._parse_trading_response(response.text)
            items.extend(payload["items"])

            if not payload["has_more_items"]:
                break

            total_pages = payload["total_pages"]
            if total_pages and page_number >= total_pages:
                break

            returned_count = payload["returned_item_count"]
            if returned_count < entries_per_page:
                break

            page_number += 1
            if page_number > 10:
                break

        return items

    def _build_get_seller_list_request(self, end_from, end_to, page_number, entries_per_page):
        root = ET.Element("GetSellerListRequest", xmlns="urn:ebay:apis:eBLBaseComponents")
        ET.SubElement(root, "GranularityLevel").text = "Medium"
        ET.SubElement(root, "IncludeVariations").text = "true"
        pagination = ET.SubElement(root, "Pagination")
        ET.SubElement(pagination, "EntriesPerPage").text = str(entries_per_page)
        ET.SubElement(pagination, "PageNumber").text = str(page_number)
        ET.SubElement(root, "EndTimeFrom").text = end_from
        ET.SubElement(root, "EndTimeTo").text = end_to
        ET.SubElement(root, "WarningLevel").text = "Low"
        return ET.tostring(root, encoding="utf-8", xml_declaration=True)

    def _parse_trading_response(self, response_text):
        root = ET.fromstring(response_text)
        ack = self._xml_text(root, "Ack")
        if ack and ack.lower() not in {"success", "warning"}:
            raise EbayApiError(self._extract_trading_errors(root))

        item_array = self._xml_child(root, "ItemArray")
        items = self._xml_children(item_array, "Item") if item_array is not None else []

        return {
            "items": items,
            "has_more_items": self._xml_bool(root, "HasMoreItems"),
            "total_pages": self._xml_int_path(root, ["PaginationResult", "TotalNumberOfPages"]),
            "returned_item_count": self._xml_int(root, "ReturnedItemCountActual"),
        }

    def _normalize_item(self, item, seller):
        item_id = self._xml_text(item, "ItemID")
        listing_details = self._xml_child(item, "ListingDetails")
        selling_status = self._xml_child(item, "SellingStatus")
        picture_details = self._xml_child(item, "PictureDetails")
        variations = self._xml_child(item, "Variations")

        image_url = self._first_non_empty_text(picture_details, ["GalleryURL", "PictureURL"])

        quantity = self._listing_quantity(item, selling_status, variations)
        price = self._listing_price(item, selling_status, variations)
        status = self._xml_text(selling_status, "ListingStatus") or "Active"
        thumbnail_path = self._download_thumbnail(item_id or status, image_url)

        return {
            "id": item_id or hashlib.sha1(ET.tostring(item, encoding="utf-8")).hexdigest(),
            "listing_id": item_id,
            "item_id": item_id,
            "title": self._xml_text(item, "Title") or "Untitled",
            "sku": self._xml_text(item, "SKU"),
            "quantity": quantity,
            "price": price,
            "status": status,
            "thumbnail_path": thumbnail_path,
            "image_url": image_url,
            "marketplace": self._xml_text(item, "Site") or "eBay",
            "url": self._xml_text(listing_details, "ViewItemURL") or self._xml_text(listing_details, "ViewItemURLForNaturalSearch"),
            "last_synced": self._now_text(),
            "payload": {
                "source": "trading.getSellerList",
                "item_xml": ET.tostring(item, encoding="unicode"),
                "seller": seller,
            },
        }

    def _listing_quantity(self, item, selling_status, variations):
        quantity = self._xml_int(item, "Quantity")
        quantity_sold = self._xml_int(selling_status, "QuantitySold")
        if quantity:
            return max(quantity - quantity_sold, 0)

        if variations is not None:
            total = 0
            for variation in self._xml_children(variations, "Variation"):
                variation_quantity = self._xml_int(variation, "Quantity")
                variation_sold = self._xml_int_path(variation, ["SellingStatus", "QuantitySold"])
                total += max(variation_quantity - variation_sold, 0)
            return total

        return 0

    def _listing_price(self, item, selling_status, variations):
        current_price = self._xml_decimal_path(selling_status, ["CurrentPrice"])
        if current_price is not None:
            return current_price

        if variations is not None:
            lowest_price = None
            for variation in self._xml_children(variations, "Variation"):
                variation_price = self._xml_decimal(variation, "StartPrice")
                if variation_price is None:
                    continue
                if lowest_price is None or variation_price < lowest_price:
                    lowest_price = variation_price
            if lowest_price is not None:
                return lowest_price

        start_price = self._xml_decimal(item, "StartPrice")
        if start_price is not None:
            return start_price

        return 0.0

    def _friendly_trading_error(self, response):
        return f"Unable to synchronize marketplace listings (status {response.status_code}): {response.text.strip()}"

    def _extract_trading_errors(self, root):
        short_message = self._xml_text_path(root, ["Errors", "ShortMessage"])
        long_message = self._xml_text_path(root, ["Errors", "LongMessage"])
        if short_message or long_message:
            return "; ".join(part for part in [short_message, long_message] if part)
        return "Unable to synchronize marketplace listings from Trading API."

    def _trading_end_time_window(self):
        end_from = datetime.utcnow().replace(microsecond=0).isoformat(sep="T") + "Z"
        end_to = (datetime.utcnow() + timedelta(days=119)).replace(microsecond=0).isoformat(sep="T") + "Z"
        return end_from, end_to

    def _resolve_site_id(self, marketplace_id):
        mapping = {
            "EBAY_US": 0,
            "EBAY_CA": 2,
            "EBAY_GB": 3,
            "EBAY_AU": 15,
            "EBAY_AT": 16,
            "EBAY_BE": 23,
            "EBAY_FR": 71,
            "EBAY_DE": 77,
            "EBAY_IT": 101,
            "EBAY_NL": 146,
            "EBAY_ES": 186,
            "EBAY_CH": 193,
            "EBAY_IE": 205,
        }

        return mapping.get(str(marketplace_id or "").strip().upper(), 0)

    def _xml_child(self, parent, name):
        if parent is None:
            return None

        for child in list(parent):
            if self._xml_local_name(child.tag) == name:
                return child
        return None

    def _xml_children(self, parent, name):
        if parent is None:
            return []

        return [child for child in list(parent) if self._xml_local_name(child.tag) == name]

    def _xml_text(self, parent, name, default=""):
        child = self._xml_child(parent, name)
        if child is None or child.text is None:
            return default
        return child.text.strip()

    def _xml_text_path(self, parent, path, default=""):
        current = parent
        for name in path:
            current = self._xml_child(current, name)
            if current is None:
                return default

        if current.text is None:
            return default
        return current.text.strip()

    def _xml_int(self, parent, name, default=0):
        value = self._xml_text(parent, name)
        if not value:
            return default
        try:
            return int(float(value))
        except Exception:
            return default

    def _xml_int_path(self, parent, path, default=0):
        value = self._xml_text_path(parent, path)
        if not value:
            return default
        try:
            return int(float(value))
        except Exception:
            return default

    def _xml_bool(self, parent, name, default=False):
        value = self._xml_text(parent, name)
        if not value:
            return default
        return value.lower() in {"true", "1", "yes"}

    def _xml_decimal(self, parent, name, default=None):
        value = self._xml_text(parent, name)
        if not value:
            return default
        try:
            return float(value)
        except Exception:
            return default

    def _xml_decimal_path(self, parent, path, default=None):
        value = self._xml_text_path(parent, path)
        if not value:
            return default
        try:
            return float(value)
        except Exception:
            return default

    def _xml_local_name(self, tag):
        if "}" in tag:
            return tag.rsplit("}", 1)[1]
        return tag

    def _first_non_empty_text(self, parent, names):
        for name in names:
            value = self._xml_text(parent, name)
            if value:
                return value
        return ""

    def _download_thumbnail(self, item_id, image_url):
        if not image_url:
            return None

        digest = hashlib.sha1(f"{item_id}:{image_url}".encode("utf-8")).hexdigest()
        file_path = self.thumbnail_dir / f"{digest}.png"
        if file_path.exists():
            return str(file_path)

        response = requests.get(image_url, timeout=45)
        if response.status_code != 200 or not response.content:
            return None

        try:
            from PIL import Image

            with Image.open(BytesIO(response.content)) as image:
                image = image.convert("RGBA")
                image.thumbnail((256, 256))
                image.save(file_path, format="PNG")
        except Exception:
            return None

        return str(file_path)

    def _now_text(self):
        return datetime.utcnow().replace(microsecond=0).isoformat(sep=" ")