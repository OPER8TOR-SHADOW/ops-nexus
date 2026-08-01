from __future__ import annotations

import base64
import ctypes
from ctypes import wintypes
from datetime import datetime, timedelta
import hashlib
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import ipaddress
import json
import os
from pathlib import Path
from queue import Empty, Queue
import secrets
import threading
import time
from urllib.parse import parse_qs, urlparse
import webbrowser
import xml.etree.ElementTree as ET

import requests

from settings_manager import load_settings, save_settings


class EbayApiError(Exception):
    pass


class _DataBlob(ctypes.Structure):
    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_byte)),
    ]


class _OAuthCallbackReceiver:
    def __init__(self, host: str, port: int, callback_path: str, exchange_redeemer=None):
        self.host = host
        self.port = port
        self.callback_path = callback_path
        self.exchange_redeemer = exchange_redeemer
        self._queue: Queue = Queue(maxsize=1)
        self._server = None
        self._thread = None

    def start(self):
        receiver = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                receiver._handle_post(self)

            def do_OPTIONS(self):
                receiver._handle_options(self)

            def log_message(self, _format, *_args):
                return

        self._server = ThreadingHTTPServer((self.host, self.port), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def wait_for_payload(self, timeout_seconds: int):
        try:
            return self._queue.get(timeout=max(1, int(timeout_seconds)))
        except Empty:
            raise EbayApiError("Sign In timed out or was cancelled before OAuth callback was received.")

    def close(self):
        if self._server is None:
            return
        try:
            self._server.shutdown()
            self._server.server_close()
        finally:
            self._server = None

    def _handle_post(self, handler: BaseHTTPRequestHandler):
        if handler.path != self.callback_path:
            self._write_json(handler, 404, {"status": "error", "message": "Not found"})
            return

        if not self._is_loopback_client(handler):
            print("[OAuth Callback] 403-A: POST rejected before payload validation")
            self._log_reject_403(handler, "Client address is not loopback")
            self._write_json(handler, 403, {"status": "error", "message": "Forbidden"})
            return

        content_length = int(handler.headers.get("content-length") or 0)
        if content_length <= 0 or content_length > 65536:
            self._write_json(handler, 400, {"status": "error", "message": "Invalid body"})
            return

        raw = handler.rfile.read(content_length)
        print("[OAuth Callback] Raw POST body:")
        print(raw.decode("utf-8", errors="replace"))
        try:
            payload = json.loads(raw.decode("utf-8"))
        except Exception:
            self._write_json(handler, 400, {"status": "error", "message": "Invalid JSON"})
            return

        if self._is_exchange_url_payload(payload):
            print("[OAuth Callback] Detected exchange_url payload")
            print(f"[OAuth Callback] exchange_url: {str(payload.get('exchange_url') or '').strip()}")
            if not callable(self.exchange_redeemer):
                self._write_json(handler, 400, {"status": "error", "message": "Exchange redeemer unavailable"})
                return
            try:
                payload = self.exchange_redeemer(payload)
            except EbayApiError as exc:
                self._write_json(handler, 400, {"status": "error", "message": str(exc)})
                return
            except Exception:
                self._write_json(handler, 400, {"status": "error", "message": "Exchange redemption failed"})
                return

        print("[OAuth Callback] Redeemed payload keys:")
        for key in payload.keys():
            print(key)
        print(f"[OAuth Callback] Scope present: {bool(str(payload.get('scope') or '').strip())}")
        try:
            normalized = EbayApiService.validate_oauth_callback_payload(payload)
            print("[OAuth Callback] Validation passed")
        except EbayApiError as exc:
            self._write_json(handler, 400, {"status": "error", "message": str(exc)})
            return

        if self._queue.empty():
            self._queue.put(normalized)

        self._write_json(handler, 200, {"status": "ok"})

    def _handle_options(self, handler: BaseHTTPRequestHandler):
        if handler.path != self.callback_path:
            self._write_json(handler, 404, {"status": "error", "message": "Not found"})
            return

        if not self._is_loopback_client(handler):
            print("[OAuth Callback] 403-B: OPTIONS rejected before preflight response")
            self._log_reject_403(handler, "Preflight client address is not loopback")
            self._write_json(handler, 403, {"status": "error", "message": "Forbidden"})
            return

        handler.send_response(204)
        handler.send_header("access-control-allow-origin", "*")
        handler.send_header("access-control-allow-methods", "POST, OPTIONS")
        handler.send_header("access-control-allow-headers", "content-type")
        handler.send_header("access-control-allow-private-network", "true")
        handler.send_header("cache-control", "no-store")
        handler.send_header("content-length", "0")
        handler.end_headers()

    def _write_json(self, handler: BaseHTTPRequestHandler, status_code: int, body: dict):
        payload = json.dumps(body).encode("utf-8")
        if int(status_code) == 403:
            print("[OAuth Callback] 403-C: _write_json sending HTTP 403")
            print(f"Client Address: {handler.client_address}")
            print(f"HTTP Method: {handler.command}")
            print(f"Request Path: {handler.path}")
        handler.send_response(status_code)
        handler.send_header("access-control-allow-origin", "*")
        handler.send_header("access-control-allow-methods", "POST, OPTIONS")
        handler.send_header("access-control-allow-headers", "content-type")
        handler.send_header("access-control-allow-private-network", "true")
        handler.send_header("content-type", "application/json; charset=utf-8")
        handler.send_header("cache-control", "no-store")
        handler.send_header("content-length", str(len(payload)))
        handler.end_headers()
        handler.wfile.write(payload)

    def _is_loopback_client(self, handler: BaseHTTPRequestHandler) -> bool:
        client_ip = str(handler.client_address[0] or "").strip()
        if not client_ip:
            return False

        try:
            parsed_ip = ipaddress.ip_address(client_ip)
            return parsed_ip.is_loopback
        except ValueError:
            return False

    def _log_reject_403(self, handler: BaseHTTPRequestHandler, reason: str):
        client_ip = str(handler.client_address[0] or "")
        print("[OAuth Callback]")
        print(f"Client IP: {client_ip}")
        print(f"Client Address: {handler.client_address}")
        print(f"Callback Path: {self.callback_path}")
        print(f"Request Path: {handler.path}")
        print(f"HTTP Method: {handler.command}")
        print(f"Reject Reason: {reason}")

    def _is_exchange_url_payload(self, payload) -> bool:
        if not isinstance(payload, dict):
            return False
        exchange_url = str(payload.get("exchange_url") or "").strip()
        return bool(exchange_url)


class EbayApiService:
    SETTINGS_CLIENT_ID = "ebay_client_id"
    SETTINGS_ENV = "ebay_environment"
    SETTINGS_REDIRECT_URI = "ebay_redirect_uri"
    SETTINGS_STATE_SECRET = "ebay_oauth_state_secret"

    DEFAULT_ENV = "sandbox"
    DEFAULT_REDIRECT_URI = "urn:ebay:oauth:redirect_uri"
    OAUTH_CALLBACK_HOST = "127.0.0.1"
    OAUTH_CALLBACK_PORT = 49872
    OAUTH_CALLBACK_PATH = "/oauth/callback"
    OAUTH_CALLBACK_TIMEOUT_SECONDS = 300
    OAUTH_STATE_TTL_SECONDS = 600

    SCOPES = [
        "https://api.ebay.com/oauth/api_scope",
        "https://api.ebay.com/oauth/api_scope/sell.account.readonly",
        "https://api.ebay.com/oauth/api_scope/sell.inventory.readonly",
    ]

    AUTH_ENDPOINTS = {
        "sandbox": "https://auth.sandbox.ebay.com/oauth2/authorize",
        "production": "https://auth.ebay.com/oauth2/authorize",
    }

    TOKEN_ENDPOINTS = {
        "sandbox": "https://api.sandbox.ebay.com/identity/v1/oauth2/token",
        "production": "https://api.ebay.com/identity/v1/oauth2/token",
    }

    API_BASES = {
        "sandbox": "https://api.sandbox.ebay.com",
        "production": "https://api.ebay.com",
    }

    def __init__(self):
        self.project_root = Path(__file__).resolve().parents[2]
        self.secret_dir = self.project_root / ".secrets"
        self.secret_dir.mkdir(parents=True, exist_ok=True)
        self.token_file = self.secret_dir / "ebay_oauth.bin"

        self._listings_cache = None
        self._listings_cache_time = 0.0
        self._status_cache = None
        self._status_cache_time = 0.0

        self._last_api_ok = None
        self._last_error = ""
        self._last_latency_ms = None

    # -------------------------
    # Settings
    # -------------------------

    def get_config(self):
        settings = load_settings()

        changed = False
        if self.SETTINGS_CLIENT_ID not in settings:
            settings[self.SETTINGS_CLIENT_ID] = ""
            changed = True

        if self.SETTINGS_ENV not in settings:
            settings[self.SETTINGS_ENV] = self.DEFAULT_ENV
            changed = True

        if self.SETTINGS_REDIRECT_URI not in settings:
            settings[self.SETTINGS_REDIRECT_URI] = self.DEFAULT_REDIRECT_URI
            changed = True

        if self.SETTINGS_STATE_SECRET not in settings:
            settings[self.SETTINGS_STATE_SECRET] = ""
            changed = True

        if changed:
            save_settings(settings)

        return {
            "client_id": str(settings.get(self.SETTINGS_CLIENT_ID) or "").strip(),
            "environment": str(settings.get(self.SETTINGS_ENV) or self.DEFAULT_ENV).strip().lower(),
            "redirect_uri": str(settings.get(self.SETTINGS_REDIRECT_URI) or self.DEFAULT_REDIRECT_URI).strip(),
            "oauth_state_secret": str(settings.get(self.SETTINGS_STATE_SECRET) or "").strip(),
        }

    def update_config(self, client_id=None, environment=None, redirect_uri=None, oauth_state_secret=None):
        settings = load_settings()

        if client_id is not None:
            settings[self.SETTINGS_CLIENT_ID] = str(client_id).strip()

        if environment is not None:
            env_text = str(environment).strip().lower()
            if env_text not in self.AUTH_ENDPOINTS:
                raise EbayApiError("Environment must be Sandbox or Production.")
            settings[self.SETTINGS_ENV] = env_text

        if redirect_uri is not None:
            settings[self.SETTINGS_REDIRECT_URI] = str(redirect_uri).strip()

        if oauth_state_secret is not None:
            settings[self.SETTINGS_STATE_SECRET] = str(oauth_state_secret).strip()

        save_settings(settings)

    # -------------------------
    # OAuth
    # -------------------------

    def get_authorize_url(self, state=None):
        config = self.get_config()
        client_id = config["client_id"]

        if not client_id:
            raise EbayApiError("Client ID is required before Sign In.")

        environment = config["environment"]
        if environment not in self.AUTH_ENDPOINTS:
            raise EbayApiError("Invalid eBay environment configured.")

        state_value = str(state or "").strip()
        if not state_value:
            raise EbayApiError("Signed OAuth state is required.")

        params = {
            "client_id": client_id,
            "redirect_uri": config["redirect_uri"],
            "response_type": "code",
            "scope": " ".join(self.SCOPES),
            "state": state_value,
            "prompt": "login",
        }

        query = "&".join([f"{k}={requests.utils.quote(v, safe='')}" for k, v in params.items()])
        endpoint = self.AUTH_ENDPOINTS[environment]
        print(f"Environment: {environment}")
        print(f"Endpoint: {endpoint}")
        print(f"Client ID: {client_id}")
        print(f"Redirect URI: {config['redirect_uri']}")
        print(f"State: {state_value}")
        print(f"Scopes: {self.SCOPES}")
        print(f"Query: {query}")
        url = f"{endpoint}?{query}"
        print(f"URL repr: {repr(url)}")
        print(f"URL: {url}")
        return url

    def complete_sign_in(self, token_payload):
        print("[OAuth Callback] Calling complete_sign_in()")
        normalized = self.validate_oauth_callback_payload(token_payload)
        self._save_tokens(normalized)
        self._status_cache = None

        profile = self.fetch_account_profile(force=True)
        print("[OAuth Callback] Connected state updated")
        config = self.get_config()
        return {
            "connected": True,
            "username": profile.get("username") or "Unknown",
            "environment": config["environment"],
        }

    def sign_in(self, timeout_seconds=None):
        timeout = int(timeout_seconds or self.OAUTH_CALLBACK_TIMEOUT_SECONDS)
        callback_url = self._desktop_callback_url()
        receiver = _OAuthCallbackReceiver(
            self.OAUTH_CALLBACK_HOST,
            self.OAUTH_CALLBACK_PORT,
            self.OAUTH_CALLBACK_PATH,
            exchange_redeemer=self._redeem_exchange_payload,
        )

        try:
            receiver.start()
        except OSError as exc:
            raise EbayApiError(f"Unable to start OAuth callback listener on {callback_url}: {exc}")

        try:
            state = self._build_signed_state(callback_url)
            auth_url = self.get_authorize_url(state=state)
            config = self.get_config()
            print("\n==============================")
            print("OAUTH DEBUG")
            print("==============================")
            print("Authorize URL:")
            print(auth_url)
            print(f"Environment: {config['environment']}")
            print(f"Client ID: {config['client_id']}")
            print(f"Redirect URI: {config['redirect_uri']}")
            print(f"Browser URL: {auth_url}")
            print("==============================")
            webbrowser.open(auth_url)
            token_payload = receiver.wait_for_payload(timeout)
        finally:
            receiver.close()

        return self.complete_sign_in(token_payload)

    def _redeem_exchange_payload(self, payload):
        exchange_url = str((payload or {}).get("exchange_url") or "").strip()
        if not exchange_url:
            raise EbayApiError("OAuth callback missing exchange_url.")

        print(f"[OAuth Callback] Received exchange_url: {exchange_url}")
        print("[OAuth Callback] Redeeming exchange...")
        print(f"[OAuth Callback] Redeeming exchange URL: {exchange_url}")
        self._validate_exchange_url(exchange_url)
        response = requests.get(
            exchange_url,
            headers={"Accept": "application/json"},
            timeout=30,
        )

        if response.status_code != 200:
            raise EbayApiError(self._friendly_error(response, "Secure exchange redemption failed."))

        try:
            payload = response.json() or {}
        except Exception:
            raise EbayApiError("Secure exchange response was not valid JSON.")

        print("[OAuth Callback] Redeemed payload keys:")
        for key in payload.keys():
            print(key)
        print(f"[OAuth Callback] Scope present: {bool(str(payload.get('scope') or '').strip())}")

        return payload

    def _validate_exchange_url(self, exchange_url):
        try:
            parsed = urlparse(exchange_url)
        except Exception:
            raise EbayApiError("Secure exchange URL is invalid.")

        scheme = (parsed.scheme or "").lower()
        host = (parsed.hostname or "").strip().lower()
        path = parsed.path or ""
        query = parse_qs(parsed.query or "", keep_blank_values=False)
        grant_values = query.get("grant") or []
        has_grant = any(str(value).strip() for value in grant_values)

        if scheme not in ("https", "http"):
            raise EbayApiError("Secure exchange URL must use HTTPS (or localhost HTTP for development).")

        if scheme == "http" and host not in ("localhost", "127.0.0.1", "::1"):
            raise EbayApiError("Secure exchange URL using HTTP must target localhost.")

        if path != "/oauth/exchange":
            raise EbayApiError("Secure exchange URL path is invalid.")

        if not has_grant:
            raise EbayApiError("Secure exchange URL is missing grant.")

    @classmethod
    def validate_oauth_callback_payload(cls, payload):
        if not isinstance(payload, dict):
            raise EbayApiError("OAuth callback payload must be a JSON object.")

        provider = str(payload.get("provider") or "").strip().lower()
        if provider != "ebay":
            raise EbayApiError("OAuth callback provider must be 'ebay'.")

        access_token = str(payload.get("access_token") or "").strip()
        refresh_token = str(payload.get("refresh_token") or "").strip()
        token_type = str(payload.get("token_type") or "").strip()
        scope = str(payload.get("scope") or "").strip()
        normalized_scope = scope or " ".join(cls.SCOPES)

        if not access_token:
            raise EbayApiError("OAuth callback missing access_token.")
        if not refresh_token:
            raise EbayApiError("OAuth callback missing refresh_token.")
        if not token_type:
            raise EbayApiError("OAuth callback missing token_type.")

        try:
            expires_in = int(payload.get("expires_in") or 0)
            refresh_expires_in = int(payload.get("refresh_token_expires_in") or 0)
        except Exception:
            raise EbayApiError("OAuth callback expiry values must be integers.")

        if expires_in <= 0 or refresh_expires_in <= 0:
            raise EbayApiError("OAuth callback expiry values must be greater than zero.")

        return {
            "provider": "ebay",
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_in": expires_in,
            "refresh_token_expires_in": refresh_expires_in,
            "token_type": token_type,
            "scope": normalized_scope,
        }

    def _desktop_callback_url(self):
        return f"http://localhost:{self.OAUTH_CALLBACK_PORT}{self.OAUTH_CALLBACK_PATH}"

    def _build_signed_state(self, desktop_callback_url):
        config = self.get_config()
        state_secret = config["oauth_state_secret"]
        secret_exists = bool(state_secret)
        secret_len = len(state_secret)
        secret_head = state_secret[:8] if secret_len else ""
        secret_tail = state_secret[-8:] if secret_len else ""
        print("[OAuth State Desktop] Secret source: settings.json key 'ebay_oauth_state_secret' via get_config().")
        print(f"[OAuth State Desktop] Secret exists: {secret_exists}")
        print(f"[OAuth State Desktop] Secret length: {secret_len}")
        print(f"[OAuth State Desktop] Secret preview: {secret_head}...{secret_tail}" if secret_exists else "[OAuth State Desktop] Secret preview: (missing)")
        if not state_secret:
            raise EbayApiError(
                "Missing required Marketplace setting: OAuth State Secret (ebay_oauth_state_secret). "
                "Set it in Settings before Sign In."
            )

        now = int(time.time())
        payload = {
            "desktop_callback_url": desktop_callback_url,
            "iat": now,
            "exp": now + self.OAUTH_STATE_TTL_SECONDS,
            "nonce": secrets.token_urlsafe(16),
        }
        payload_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        payload_b64 = self._encode_base64url(payload_bytes)
        signed_data = f"v1.{payload_b64}"
        print(f"[OAuth State Desktop] payloadB64: {payload_b64}")
        print(f"[OAuth State Desktop] signedData: {signed_data}")
        signature = hmac.new(state_secret.encode("utf-8"), signed_data.encode("utf-8"), hashlib.sha256).digest()
        sig_b64 = self._encode_base64url(signature)
        print(f"[OAuth State Desktop] sigB64: {sig_b64}")
        return f"{signed_data}.{sig_b64}"

    def _encode_base64url(self, value):
        return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")

    def sign_out(self):
        if self.token_file.exists():
            self.token_file.unlink()

        self._listings_cache = None
        self._status_cache = None

    def _client_secret(self):
        return str(os.getenv("EBAY_CLIENT_SECRET") or "").strip()

    def _basic_auth(self, client_id, client_secret):
        raw = f"{client_id}:{client_secret}".encode("utf-8")
        return "Basic " + base64.b64encode(raw).decode("ascii")

    def _load_tokens(self):
        if not self.token_file.exists():
            return {}

        encrypted = self.token_file.read_bytes()
        if not encrypted:
            return {}

        try:
            raw = self._dpapi_unprotect(encrypted)
            return json.loads(raw.decode("utf-8"))
        except Exception as exc:
            raise EbayApiError(f"Unable to load secure OAuth tokens: {exc}")

    def _save_tokens(self, token_payload):
        now = datetime.utcnow()
        expires_in = int(token_payload.get("expires_in") or 0)
        expires_at = now + timedelta(seconds=expires_in)

        existing = self._load_tokens() if self.token_file.exists() else {}

        data = {
            "access_token": str(token_payload.get("access_token") or ""),
            "refresh_token": str(token_payload.get("refresh_token") or existing.get("refresh_token") or ""),
            "token_type": str(token_payload.get("token_type") or "Bearer"),
            "scope": str(token_payload.get("scope") or ""),
            "environment": self.get_config()["environment"],
            "expires_at": expires_at.isoformat(),
            "last_successful_connection": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "account_profile": existing.get("account_profile") or {},
        }

        raw = json.dumps(data).encode("utf-8")
        encrypted = self._dpapi_protect(raw)
        self.token_file.write_bytes(encrypted)

    def _save_profile(self, profile):
        data = self._load_tokens()
        if not data:
            return

        data["account_profile"] = profile
        raw = json.dumps(data).encode("utf-8")
        self.token_file.write_bytes(self._dpapi_protect(raw))

    def _is_expired(self, token_data):
        expires_at = str(token_data.get("expires_at") or "")
        if not expires_at:
            return True

        try:
            dt = datetime.fromisoformat(expires_at)
        except ValueError:
            return True

        return datetime.utcnow() >= (dt - timedelta(seconds=60))

    def _refresh_access_token(self):
        token_data = self._load_tokens()
        refresh_token = str(token_data.get("refresh_token") or "")

        if not refresh_token:
            raise EbayApiError("No refresh token available. Please Sign In again.")

        config = self.get_config()
        client_id = config["client_id"]
        client_secret = self._client_secret()

        if not client_id or not client_secret:
            raise EbayApiError("Client credentials are missing for token refresh.")

        token_url = self.TOKEN_ENDPOINTS[config["environment"]]
        auth_header = self._basic_auth(client_id, client_secret)

        response = requests.post(
            token_url,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "scope": " ".join(self.SCOPES),
            },
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Authorization": auth_header,
            },
            timeout=30,
        )

        if response.status_code != 200:
            raise EbayApiError(self._friendly_error(response, "Token refresh failed."))

        self._save_tokens(response.json() or {})

    def _valid_access_token(self):
        token_data = self._load_tokens()
        if not token_data:
            raise EbayApiError("Not connected. Please Sign In.")

        if self._is_expired(token_data):
            self._refresh_access_token()
            token_data = self._load_tokens()

        access_token = str(token_data.get("access_token") or "")
        if not access_token:
            raise EbayApiError("Access token missing. Please Sign In again.")

        return access_token

    # -------------------------
    # Connection / Status
    # -------------------------

    def get_connection_status(self, force=False):
        if not force and self._status_cache is not None and (time.time() - self._status_cache_time) < 20:
            return self._status_cache

        config = self.get_config()
        token_data = self._load_tokens() if self.token_file.exists() else {}

        connected = bool(token_data.get("access_token"))
        oauth_status = "Disconnected"

        if connected:
            oauth_status = "Connected"
            if self._is_expired(token_data):
                oauth_status = "Refreshing"

        profile = token_data.get("account_profile") or {}

        status = {
            "connection_status": "Connected" if connected else "Disconnected",
            "seller_username": profile.get("username") or "—",
            "store_name": profile.get("store_name") or "—",
            "marketplace_region": profile.get("marketplace_region") or "—",
            "last_successful_connection": token_data.get("last_successful_connection") or "—",
            "api_status": "Online" if self._last_api_ok else ("Unknown" if self._last_api_ok is None else "Error"),
            "oauth_status": oauth_status,
            "environment": config["environment"],
            "latency_ms": self._last_latency_ms,
            "last_error": self._last_error,
        }

        self._status_cache = status
        self._status_cache_time = time.time()
        return status

    def test_connection(self):
        start = time.perf_counter()

        try:
            profile = self.fetch_account_profile(force=True)
            self._last_api_ok = True
            self._last_error = ""
            ok = True
            message = "Connection successful."
        except Exception as exc:
            self._last_api_ok = False
            self._last_error = str(exc)
            profile = {}
            ok = False
            message = str(exc)

        self._last_latency_ms = int((time.perf_counter() - start) * 1000)
        self._status_cache = None

        status = self.get_connection_status(force=True)

        return {
            "ok": ok,
            "message": message,
            "latency_ms": self._last_latency_ms,
            "environment": status["environment"],
            "profile": profile,
        }

    # -------------------------
    # eBay API Read-Only Calls
    # -------------------------

    def fetch_account_profile(self, force=False):
        token_data = self._load_tokens() if self.token_file.exists() else {}
        if not force and token_data.get("account_profile"):
            return token_data.get("account_profile") or {}

        access_token = self._valid_access_token()
        environment = self.get_config()["environment"]
        api_base = self.API_BASES[environment]
        request_url = f"{api_base}/commerce/identity/v1/user"

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }
        safe_headers = {
            "Authorization": "Bearer [redacted]",
            "Accept": headers["Accept"],
        }

        print("[eBay Profile] HTTP method: GET")
        print(f"[eBay Profile] Request URL: {request_url}")
        print(f"[eBay Profile] Environment: {environment}")
        print(f"[eBay Profile] Headers: {safe_headers}")

        # Official eBay Identity API (user profile)
        response = requests.get(request_url, headers=headers, timeout=30)
        response_text = response.text
        print(f"[eBay Profile] Response status: {response.status_code}")
        print(f"[eBay Profile] Response reason: {response.reason}")
        print(f"[eBay Profile] Response URL: {response.url}")
        print(f"[eBay Profile] Response headers: {dict(response.headers)}")
        print(f"[eBay Profile] Response body: {response_text}")

        if response.status_code != 200:
            if environment == "sandbox" and response.status_code == 404:
                print("[eBay Profile] Identity API unavailable in Sandbox; skipping profile load and keeping OAuth connected.")
                return {}
            raise EbayApiError(self._friendly_error(response, "Unable to load account profile."))

        try:
            payload = response.json() or {}
        except Exception as exc:
            raise EbayApiError(f"Unable to parse account profile response JSON: {exc}")

        store_name = "—"
        business = payload.get("businessAccount") or {}
        if isinstance(business, dict):
            store_name = str(business.get("name") or "—")

        profile = {
            "username": str(payload.get("username") or payload.get("userId") or "—"),
            "store_name": store_name,
            "marketplace_region": str(payload.get("registrationMarketplaceId") or "—"),
        }

        self._save_profile(profile)
        return profile

    def get_active_listings(self, force_refresh=False):
        if not force_refresh and self._listings_cache is not None and (time.time() - self._listings_cache_time) < 120:
            return self._listings_cache

        access_token = self._valid_access_token()
        environment = self.get_config()["environment"]
        api_base = self.API_BASES[environment]

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        safe_headers = {
            "Authorization": "Bearer [redacted]",
            "Accept": headers["Accept"],
            "Content-Type": headers["Content-Type"],
        }

        offers = []
        offset = 0
        limit = 200

        while True:
            request_url = f"{api_base}/sell/inventory/v1/offer"
            request_params = {"limit": limit, "offset": offset}
            print("[eBay Offers] HTTP method: GET")
            print(f"[eBay Offers] Request URL: {request_url}")
            print(f"[eBay Offers] Environment: {environment}")
            print(f"[eBay Offers] Headers: {safe_headers}")
            print(f"[eBay Offers] Params: {request_params}")
            response = requests.get(
                request_url,
                headers=headers,
                params=request_params,
                timeout=45,
            )
            prepared_headers = dict(response.request.headers)
            if "Authorization" in prepared_headers:
                prepared_headers["Authorization"] = "Bearer [redacted]"
            print(f"[eBay Offers] Final request method: {response.request.method}")
            print(f"[eBay Offers] Final request URL: {response.request.url}")
            print(f"[eBay Offers] Final request headers: {prepared_headers}")
            print(f"[eBay Offers] Response status: {response.status_code}")
            print(f"[eBay Offers] Response body: {response.text}")

            if response.status_code != 200:
                raise EbayApiError(self._friendly_error(response, "Unable to load active listings."))

            payload = response.json() or {}
            chunk = payload.get("offers") or []

            if not chunk:
                break

            offers.extend(chunk)

            if len(chunk) < limit:
                break

            offset += limit
            if offset >= 2000:
                break

        mapped = []
        for offer in offers:
            listing = offer.get("listing") or {}
            pricing = offer.get("pricingSummary") or {}
            price_obj = pricing.get("price") or {}

            mapped.append(
                {
                    "title": str(offer.get("listingDescription") or offer.get("title") or offer.get("sku") or "Untitled"),
                    "item_id": str(listing.get("listingId") or offer.get("offerId") or ""),
                    "sku": str(offer.get("sku") or ""),
                    "price": float(price_obj.get("value") or 0),
                    "quantity": int(offer.get("availableQuantity") or 0),
                    "status": str(offer.get("status") or ""),
                    "listing_type": str(offer.get("format") or ""),
                    "start_date": str(listing.get("listingStartDate") or ""),
                    "last_updated": str(offer.get("lastModifiedDate") or ""),
                    "marketplace_id": str(offer.get("marketplaceId") or ""),
                }
            )

        self._listings_cache = mapped
        self._listings_cache_time = time.time()
        self._last_api_ok = True
        self._last_error = ""

        return mapped

    # -------------------------
    # eBay API Write Calls
    # -------------------------

    def revise_listing_price(self, item_id, new_price):
        item_id_text = str(item_id or "").strip()
        if not item_id_text:
            raise EbayApiError("Item ID is required to revise price.")

        price_value = float(new_price)
        if price_value <= 0:
            raise EbayApiError("Price must be greater than zero.")

        request_xml = (
            "<?xml version=\"1.0\" encoding=\"utf-8\"?>"
            "<ReviseInventoryStatusRequest xmlns=\"urn:ebay:apis:eBLBaseComponents\">"
            "<InventoryStatus>"
            f"<ItemID>{item_id_text}</ItemID>"
            f"<StartPrice>{price_value:.2f}</StartPrice>"
            "</InventoryStatus>"
            "</ReviseInventoryStatusRequest>"
        )

        self._post_trading_call("ReviseInventoryStatus", request_xml)
        return {"ok": True, "item_id": item_id_text, "price": f"{price_value:.2f}"}

    def revise_listing_quantity(self, item_id, new_quantity):
        item_id_text = str(item_id or "").strip()
        if not item_id_text:
            raise EbayApiError("Item ID is required to revise quantity.")

        quantity_value = int(new_quantity)
        if quantity_value < 0:
            raise EbayApiError("Quantity must be zero or greater.")

        request_xml = (
            "<?xml version=\"1.0\" encoding=\"utf-8\"?>"
            "<ReviseInventoryStatusRequest xmlns=\"urn:ebay:apis:eBLBaseComponents\">"
            "<InventoryStatus>"
            f"<ItemID>{item_id_text}</ItemID>"
            f"<Quantity>{quantity_value}</Quantity>"
            "</InventoryStatus>"
            "</ReviseInventoryStatusRequest>"
        )

        self._post_trading_call("ReviseInventoryStatus", request_xml)
        return {"ok": True, "item_id": item_id_text, "quantity": quantity_value}

    def end_listing(self, item_id, reason="NotAvailable"):
        item_id_text = str(item_id or "").strip()
        if not item_id_text:
            raise EbayApiError("Item ID is required to end listing.")

        ending_reason = str(reason or "NotAvailable").strip() or "NotAvailable"

        fixed_price_request = (
            "<?xml version=\"1.0\" encoding=\"utf-8\"?>"
            "<EndFixedPriceItemRequest xmlns=\"urn:ebay:apis:eBLBaseComponents\">"
            f"<ItemID>{item_id_text}</ItemID>"
            f"<EndingReason>{ending_reason}</EndingReason>"
            "</EndFixedPriceItemRequest>"
        )

        try:
            self._post_trading_call("EndFixedPriceItem", fixed_price_request)
            return {"ok": True, "item_id": item_id_text, "method": "EndFixedPriceItem"}
        except EbayApiError:
            end_item_request = (
                "<?xml version=\"1.0\" encoding=\"utf-8\"?>"
                "<EndItemRequest xmlns=\"urn:ebay:apis:eBLBaseComponents\">"
                f"<ItemID>{item_id_text}</ItemID>"
                f"<EndingReason>{ending_reason}</EndingReason>"
                "</EndItemRequest>"
            )
            self._post_trading_call("EndItem", end_item_request)
            return {"ok": True, "item_id": item_id_text, "method": "EndItem"}

    def _post_trading_call(self, call_name, request_xml):
        access_token = self._valid_access_token()
        environment = self.get_config()["environment"]
        api_base = self.API_BASES[environment]
        endpoint = f"{api_base}/ws/api.dll"

        headers = {
            "X-EBAY-API-CALL-NAME": str(call_name),
            "X-EBAY-API-IAF-TOKEN": access_token,
            "X-EBAY-API-SITEID": str(self._resolve_trading_site_id()),
            "X-EBAY-API-COMPATIBILITY-LEVEL": "1455",
            "Content-Type": "text/xml",
            "Accept": "text/xml",
        }

        response = requests.post(endpoint, headers=headers, data=request_xml.encode("utf-8"), timeout=45)
        if response.status_code != 200:
            raise EbayApiError(self._friendly_error(response, f"{call_name} failed."))

        self._validate_trading_response(call_name, response.text)
        self._last_api_ok = True
        self._last_error = ""

    def _validate_trading_response(self, call_name, response_text):
        try:
            root = ET.fromstring(response_text)
        except Exception as exc:
            raise EbayApiError(f"{call_name} failed: invalid XML response ({exc}).")

        ack = self._xml_text_local(root, "Ack").strip().lower()
        if ack in {"success", "warning"}:
            return

        short_message = self._xml_text_local(root, "ShortMessage")
        long_message = self._xml_text_local(root, "LongMessage")
        error_message = long_message or short_message or f"{call_name} failed."
        raise EbayApiError(error_message)

    def _resolve_trading_site_id(self):
        token_data = self._load_tokens() if self.token_file.exists() else {}
        profile = token_data.get("account_profile") or {}
        marketplace = str(profile.get("marketplace_region") or "").strip().upper()
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
        return mapping.get(marketplace, 0)

    def _xml_text_local(self, root, local_name):
        for node in root.iter():
            tag = str(node.tag)
            current_name = tag.rsplit("}", 1)[-1] if "}" in tag else tag
            if current_name == local_name:
                return str(node.text or "").strip()
        return ""

    # -------------------------
    # Security helpers (Windows DPAPI)
    # -------------------------

    def _dpapi_protect(self, plaintext):
        if os.name != "nt":
            raise EbayApiError("Secure token storage is only supported on Windows in this build.")

        if not isinstance(plaintext, (bytes, bytearray)):
            plaintext = bytes(str(plaintext), "utf-8")

        in_blob = _DataBlob()
        in_blob.cbData = len(plaintext)
        in_blob.pbData = ctypes.cast(ctypes.create_string_buffer(bytes(plaintext)), ctypes.POINTER(ctypes.c_byte))

        out_blob = _DataBlob()

        crypt32 = ctypes.windll.crypt32
        kernel32 = ctypes.windll.kernel32

        if not crypt32.CryptProtectData(
            ctypes.byref(in_blob),
            "OPS Nexus eBay OAuth",
            None,
            None,
            None,
            0,
            ctypes.byref(out_blob),
        ):
            raise EbayApiError("Failed to secure OAuth tokens with DPAPI.")

        try:
            return ctypes.string_at(out_blob.pbData, out_blob.cbData)
        finally:
            kernel32.LocalFree(out_blob.pbData)

    def _dpapi_unprotect(self, ciphertext):
        if os.name != "nt":
            raise EbayApiError("Secure token storage is only supported on Windows in this build.")

        in_blob = _DataBlob()
        in_blob.cbData = len(ciphertext)
        in_blob.pbData = ctypes.cast(ctypes.create_string_buffer(ciphertext), ctypes.POINTER(ctypes.c_byte))

        out_blob = _DataBlob()

        crypt32 = ctypes.windll.crypt32
        kernel32 = ctypes.windll.kernel32

        if not crypt32.CryptUnprotectData(
            ctypes.byref(in_blob),
            None,
            None,
            None,
            None,
            0,
            ctypes.byref(out_blob),
        ):
            raise EbayApiError("Failed to decrypt OAuth tokens from secure storage.")

        try:
            return ctypes.string_at(out_blob.pbData, out_blob.cbData)
        finally:
            kernel32.LocalFree(out_blob.pbData)

    # -------------------------
    # Utility
    # -------------------------

    def _friendly_error(self, response, fallback):
        try:
            payload = response.json() or {}
        except Exception:
            payload = {}

        message = fallback
        if isinstance(payload, dict):
            if "error_description" in payload:
                message = str(payload.get("error_description"))
            elif "errors" in payload and payload["errors"]:
                first = payload["errors"][0]
                message = str(first.get("message") or first.get("longMessage") or fallback)
            elif "message" in payload:
                message = str(payload.get("message"))

        return f"{message} (HTTP {response.status_code})"
