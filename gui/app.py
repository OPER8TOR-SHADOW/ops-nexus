import customtkinter as ctk
import threading
import tkinter as tk

from gui.theme import setup_theme
from gui.sidebar import Sidebar
from gui.header import Header
from gui.page_manager import PageManager
from gui.pages.marketplace_manager import MarketplaceManagerPage
from gui.services.marketplace_sync_service import MarketplaceSyncService


def _patch_customtkinter_destroy_compat():
    # Python 3.14 can raise TclError during OptionMenu trace_remove teardown.
    if getattr(ctk, "_ops_destroy_compat_patched", False):
        return

    ctk._ops_destroy_compat_patched = True

    try:
        optionmenu_cls = ctk.CTkOptionMenu
        original_optionmenu_destroy = optionmenu_cls.destroy

        def safe_optionmenu_destroy(self):
            try:
                original_optionmenu_destroy(self)
            except Exception as exc:
                message = str(exc)
                if "trace remove variable" not in message:
                    raise
                dropdown = getattr(self, "_dropdown_menu", None)
                if dropdown is not None:
                    try:
                        dropdown.destroy()
                    except Exception:
                        try:
                            tk.Menu.destroy(dropdown)
                        except Exception:
                            pass
                    try:
                        self._dropdown_menu = None
                    except Exception:
                        pass
                try:
                    tk.Frame.destroy(self)
                except Exception:
                    pass

        optionmenu_cls.destroy = safe_optionmenu_destroy
    except Exception:
        pass

    try:
        from customtkinter.windows.widgets.core_widget_classes.dropdown_menu import DropdownMenu

        original_dropdown_destroy = DropdownMenu.destroy

        def safe_dropdown_destroy(self):
            try:
                original_dropdown_destroy(self)
            except AttributeError as exc:
                if "_font" not in str(exc):
                    raise
                try:
                    tk.Menu.destroy(self)
                except Exception:
                    pass

        DropdownMenu.destroy = safe_dropdown_destroy
    except Exception:
        pass


_patch_customtkinter_destroy_compat()


class OPSNexus(ctk.CTk):

    def __init__(self):

        super().__init__()

        setup_theme()

        # ---------------- Window ----------------

        self.title("OPS Nexus")
        self.geometry("1600x900")
        self.minsize(1400, 850)
        self.configure(fg_color="#0E0E0E")

        # ---------------- Root Grid ----------------

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ---------------- Main ----------------

        self.main = ctk.CTkFrame(
            self,
            fg_color="transparent"
        )

        self.main.grid(
            row=0,
            column=1,
            sticky="nsew",
            padx=20,
            pady=20
        )

        self.main.grid_columnconfigure(0, weight=1)
        self.main.grid_rowconfigure(1, weight=1)

        # ---------------- Header ----------------

        self.header = Header(self.main)

        self.header.grid(
            row=0,
            column=0,
            sticky="ew",
            pady=(0, 20)
        )

        # ---------------- Page Container ----------------

        self.page_container = ctk.CTkFrame(
            self.main,
            fg_color="transparent"
        )

        self.page_container.grid(
            row=1,
            column=0,
            sticky="nsew"
        )

        # ---------------- Page Manager ----------------

        self.pages = PageManager(self.page_container)
        self.marketplace_sync_service = MarketplaceSyncService()
        self.pages.marketplace_sync_service = self.marketplace_sync_service
        self._marketplace_sync_after_id = None
        self._is_shutting_down = False

        # ---------------- Sidebar ----------------

        self.sidebar = Sidebar(
            self,
            self.pages
        )

        self.sidebar.grid(
            row=0,
            column=0,
            sticky="ns"
        )

        # ---------------- Default Page ----------------

        self.pages.show_dashboard()
        self._marketplace_sync_after_id = self.after(1000, self._start_marketplace_sync_loop)

    def _start_marketplace_sync_loop(self):
        if self._is_shutting_down:
            return
        self._run_marketplace_sync()

    def _run_marketplace_sync(self):
        if self._is_shutting_down:
            return

        def worker():
            try:
                result = self.marketplace_sync_service.sync_marketplace_cache()
                error = None
            except Exception as exc:
                result = None
                error = exc

            if self._is_shutting_down:
                return

            try:
                self.after(0, lambda: self._finish_marketplace_sync(result, error))
            except Exception:
                return

        threading.Thread(target=worker, daemon=True).start()

    def _finish_marketplace_sync(self, result, error):
        if self._is_shutting_down:
            return

        current_page = getattr(self.pages, "current_page", None)
        if error is None and result and result.get("ok") and isinstance(current_page, MarketplaceManagerPage):
            current_page.refresh_listings()

        self._marketplace_sync_after_id = self.after(15 * 60 * 1000, self._run_marketplace_sync)

    def destroy(self):
        self._is_shutting_down = True

        if self._marketplace_sync_after_id is not None:
            try:
                self.after_cancel(self._marketplace_sync_after_id)
            except Exception:
                pass
            self._marketplace_sync_after_id = None

        try:
            pending_after_ids = list(self.tk.call("after", "info"))
        except Exception:
            pending_after_ids = []

        for after_id in pending_after_ids:
            try:
                self.after_cancel(after_id)
            except Exception:
                pass

        try:
            super().destroy()
        except tk.TclError as exc:
            message = str(exc)
            if "can't delete Tcl command" not in message and "application has been destroyed" not in message:
                raise