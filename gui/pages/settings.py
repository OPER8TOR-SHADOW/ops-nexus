import os
from pathlib import Path
import threading

import customtkinter as ctk

from gui.theme import *
from gui.services.ebay_api_service import EbayApiService


class SettingsPage(ctk.CTkFrame):

    def __init__(self, master, page_manager=None):

        super().__init__(master, fg_color="transparent")

        self.page_manager = page_manager
        self.ebay_service = EbayApiService()

        self.grid_columnconfigure(0, weight=1)

        title = ctk.CTkLabel(
            self,
            text="Settings",
            font=(FONT, 30, "bold"),
            text_color=TEXT
        )

        title.grid(row=0, column=0, sticky="w", padx=20, pady=(20, 10))

        description = ctk.CTkLabel(
            self,
            text="Application settings and environment status.",
            font=(FONT, 16),
            text_color=MUTED
        )

        description.grid(row=1, column=0, sticky="w", padx=20, pady=(0, 20))

        section = ctk.CTkFrame(self, fg_color=CARD, border_width=1, border_color=BORDER, corner_radius=15)
        section.grid(row=2, column=0, sticky="nsew", padx=20, pady=(0, 20))

        section.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            section,
            text="Environment",
            font=(FONT, 18, "bold"),
            text_color=TEXT,
        ).grid(row=0, column=0, sticky="w", padx=18, pady=(18, 10))

        self.status_text = ctk.CTkTextbox(section, height=220, fg_color="transparent")
        self.status_text.grid(row=1, column=0, sticky="nsew", padx=18, pady=(0, 18))

        marketplace = ctk.CTkFrame(self, fg_color=CARD, border_width=1, border_color=BORDER, corner_radius=15)
        marketplace.grid(row=3, column=0, sticky="nsew", padx=20, pady=(0, 20))

        marketplace.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            marketplace,
            text="Marketplace",
            font=(FONT, 18, "bold"),
            text_color=TEXT,
        ).grid(row=0, column=0, columnspan=3, sticky="w", padx=18, pady=(18, 10))

        config = self.ebay_service.get_config()

        ctk.CTkLabel(marketplace, text="Client ID", text_color=SUBTEXT, font=(FONT, 12, "bold")).grid(row=1, column=0, sticky="w", padx=18, pady=4)
        self.client_id_var = ctk.StringVar(value=config.get("client_id") or "")
        self.client_id_entry = ctk.CTkEntry(marketplace, textvariable=self.client_id_var)
        self.client_id_entry.grid(row=1, column=1, sticky="ew", padx=10, pady=4)

        ctk.CTkLabel(marketplace, text="Environment", text_color=SUBTEXT, font=(FONT, 12, "bold")).grid(row=2, column=0, sticky="w", padx=18, pady=4)
        env_value = "Sandbox" if config.get("environment") == "sandbox" else "Production"
        self.environment_var = ctk.StringVar(value=env_value)
        self.environment_menu = ctk.CTkOptionMenu(marketplace, values=["Sandbox", "Production"], variable=self.environment_var)
        self.environment_menu.grid(row=2, column=1, sticky="w", padx=10, pady=4)

        ctk.CTkLabel(marketplace, text="Redirect URI", text_color=SUBTEXT, font=(FONT, 12, "bold")).grid(row=3, column=0, sticky="w", padx=18, pady=4)
        self.redirect_var = ctk.StringVar(value=config.get("redirect_uri") or "")
        self.redirect_entry = ctk.CTkEntry(marketplace, textvariable=self.redirect_var)
        self.redirect_entry.grid(row=3, column=1, sticky="ew", padx=10, pady=4)

        ctk.CTkLabel(marketplace, text="OAuth State Secret", text_color=SUBTEXT, font=(FONT, 12, "bold")).grid(row=4, column=0, sticky="w", padx=18, pady=4)
        self.state_secret_var = ctk.StringVar(value=config.get("oauth_state_secret") or "")
        self.state_secret_entry = ctk.CTkEntry(marketplace, textvariable=self.state_secret_var, show="*")
        self.state_secret_entry.grid(row=4, column=1, sticky="ew", padx=10, pady=4)

        ctk.CTkLabel(marketplace, text="OAuth Status", text_color=SUBTEXT, font=(FONT, 12, "bold")).grid(row=5, column=0, sticky="w", padx=18, pady=4)
        self.oauth_label = ctk.CTkLabel(marketplace, text="Disconnected", text_color=TEXT, font=(FONT, 12))
        self.oauth_label.grid(row=5, column=1, sticky="w", padx=10, pady=4)

        controls = ctk.CTkFrame(marketplace, fg_color="transparent")
        controls.grid(row=6, column=0, columnspan=3, sticky="ew", padx=18, pady=(10, 14))

        ctk.CTkButton(controls, text="Save", width=90, command=self.save_marketplace).pack(side="left")
        ctk.CTkButton(controls, text="Reconnect", width=110, command=self.reconnect_marketplace).pack(side="left", padx=(8, 0))
        ctk.CTkButton(controls, text="Disconnect", width=110, command=self.disconnect_marketplace).pack(side="left", padx=(8, 0))
        ctk.CTkButton(controls, text="Manual Refresh", width=120, command=self.manual_refresh_marketplace).pack(side="left", padx=(8, 0))
        ctk.CTkButton(controls, text="Open Marketplace", width=130, command=self.open_marketplace_page).pack(side="left", padx=(8, 0))

        self.marketplace_message = ctk.CTkLabel(marketplace, text="", text_color=MUTED, font=(FONT, 11))
        self.marketplace_message.grid(row=7, column=0, columnspan=3, sticky="w", padx=18, pady=(0, 14))

        self.refresh_status()
        self._refresh_marketplace_status()

    def refresh_status(self):
        project_root = Path(__file__).resolve().parents[2]
        env_path = project_root / ".env"
        env_exists = env_path.exists()
        token_present = bool(os.getenv("GITHUB_TOKEN"))

        lines = [
            f"Project root: {project_root}",
            f"Environment file: {'present' if env_exists else 'missing'}",
            f"GitHub token: {'configured' if token_present else 'not configured'}",
            f"Inventory folder: {'present' if (project_root / 'inventory').exists() else 'missing'}",
            f"Images folder: {'present' if (project_root / 'images').exists() else 'missing'}",
            f"Output folder: {'present' if (project_root / 'output').exists() else 'missing'}",
        ]

        self.status_text.delete("1.0", "end")
        self.status_text.insert("end", "\n".join(lines))
        self.status_text.configure(state="disabled")

    def _run_async(self, func, done):
        def worker():
            try:
                result = func()
                error = None
            except Exception as exc:
                result = None
                error = exc
            self.after(0, lambda: done(result, error))

        threading.Thread(target=worker, daemon=True).start()

    def _refresh_marketplace_status(self):
        try:
            status = self.ebay_service.get_connection_status(force=True)
            self.oauth_label.configure(text=str(status.get("oauth_status") or "Disconnected"))
        except Exception as exc:
            self.oauth_label.configure(text="Error")
            self.marketplace_message.configure(text=str(exc), text_color=ERROR)

    def save_marketplace(self):
        try:
            env = "sandbox" if self.environment_var.get().strip().lower().startswith("sand") else "production"
            self.ebay_service.update_config(
                client_id=self.client_id_var.get().strip(),
                environment=env,
                redirect_uri=self.redirect_var.get().strip(),
                oauth_state_secret=self.state_secret_var.get().strip(),
            )
            self.marketplace_message.configure(text="Marketplace settings saved.", text_color=SUCCESS)
        except Exception as exc:
            self.marketplace_message.configure(text=str(exc), text_color=ERROR)

    def reconnect_marketplace(self):
        self.save_marketplace()

        def do_connect():
            return self.ebay_service.sign_in()

        def done(_result, error):
            if error:
                self.marketplace_message.configure(text=str(error), text_color=ERROR)
            else:
                self.marketplace_message.configure(text="Connected to eBay.", text_color=SUCCESS)
            self._refresh_marketplace_status()

        self._run_async(do_connect, done)

    def disconnect_marketplace(self):
        try:
            self.ebay_service.sign_out()
            self.marketplace_message.configure(text="Disconnected from eBay.", text_color=SUCCESS)
        except Exception as exc:
            self.marketplace_message.configure(text=str(exc), text_color=ERROR)
        self._refresh_marketplace_status()

    def manual_refresh_marketplace(self):
        def do_refresh():
            return self.ebay_service.test_connection()

        def done(result, error):
            if error:
                self.marketplace_message.configure(text=str(error), text_color=ERROR)
            else:
                if result.get("ok"):
                    self.marketplace_message.configure(
                        text=f"Connection OK ({result.get('latency_ms')} ms).",
                        text_color=SUCCESS,
                    )
                else:
                    self.marketplace_message.configure(text=result.get("message") or "Connection failed.", text_color=ERROR)
            self._refresh_marketplace_status()

        self._run_async(do_refresh, done)

    def open_marketplace_page(self):
        if self.page_manager is not None and hasattr(self.page_manager, "show_marketplace_manager"):
            self.page_manager.show_marketplace_manager()