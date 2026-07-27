import customtkinter as ctk

from gui.theme import setup_theme
from gui.sidebar import Sidebar
from gui.header import Header
from gui.page_manager import PageManager


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