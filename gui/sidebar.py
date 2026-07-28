import customtkinter as ctk

from gui.theme import *


class Sidebar(ctk.CTkFrame):

    def __init__(self, master, page_manager):

        super().__init__(
            master,
            width=240,
            fg_color=SIDEBAR,
            corner_radius=0
        )

        self.page_manager = page_manager
        self.buttons = {}

        self.grid_propagate(False)
        self.grid_rowconfigure(1, weight=1)

        # ---------------- Logo ----------------

        self.logo = ctk.CTkLabel(
            self,
            text="OPS\nNEXUS",
            font=(FONT, 28, "bold"),
            text_color=TEXT,
            justify="center"
        )

        self.logo.grid(
            row=0,
            column=0,
            pady=(35, 30),
            padx=20
        )

        # ---------------- Navigation ----------------

        self.menu = ctk.CTkFrame(
            self,
            fg_color="transparent"
        )

        self.menu.grid(
            row=1,
            column=0,
            sticky="n"
        )

        pages = [
            ("🏠 Dashboard", self.page_manager.show_dashboard),
            ("🗂 Sets", self.page_manager.show_set_manager),
            ("🃏 Card Manager", self.page_manager.show_card_manager),
            ("🚀 Build Listing", self.page_manager.show_build),
            ("📦 Inventory", self.page_manager.show_inventory),
            ("🧾 Sales", self.page_manager.show_sales),
            ("📈 Business Analytics", self.page_manager.show_business_analytics),
            ("🧠 Operations Center", self.page_manager.show_operations_center),
            ("🖼 Images", self.page_manager.show_images),
            ("💰 Pricing", self.page_manager.show_pricing),
            ("📊 Statistics", self.page_manager.show_statistics),
            ("⚙ Settings", self.page_manager.show_settings),
        ]

        for text, command in pages:

            button = ctk.CTkButton(
                self.menu,
                text=text,
                command=lambda t=text, c=command: self.select_page(t, c),
                width=190,
                height=42,
                anchor="w",
                corner_radius=10,
                fg_color="transparent",
                hover_color="#242424",
                text_color=TEXT,
                border_width=1,
                border_color=BORDER
            )

            button.pack(
                pady=5,
                padx=10
            )

            self.buttons[text] = button

        # Highlight Dashboard initially
        self.select_page(
            "🏠 Dashboard",
            self.page_manager.show_dashboard
        )

        # ---------------- Footer ----------------

        self.footer = ctk.CTkFrame(
            self,
            fg_color="transparent"
        )

        self.footer.grid(
            row=2,
            column=0,
            pady=25
        )

        ctk.CTkLabel(
            self.footer,
            text="● SYSTEM READY",
            text_color=SUCCESS,
            font=(FONT, 12, "bold")
        ).pack()

        ctk.CTkLabel(
            self.footer,
            text="OPS Nexus v1.0",
            text_color=SUBTEXT,
            font=(FONT, 11)
        ).pack(pady=(8, 0))

    # --------------------------------------------------
    # Navigation
    # --------------------------------------------------

    def select_page(self, selected, command):

        for name, button in self.buttons.items():

            if name == selected:
                button.configure(
                    fg_color=ACCENT
                )
            else:
                button.configure(
                    fg_color="transparent"
                )

        command()