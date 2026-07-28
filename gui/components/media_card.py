from pathlib import Path

import customtkinter as ctk
from PIL import Image

from gui.theme import *


class MediaCard(ctk.CTkFrame):

    def __init__(self, master, image_path, callback=None):

        super().__init__(
            master,
            width=170,
            height=260,
            fg_color=CARD,
            border_width=2,
            border_color=BORDER,
            corner_radius=12
        )

        self.grid_propagate(False)

        self.callback = callback
        self.image_path = Path(image_path)
        self.filename = self.image_path.name
        self.preview = None

        # -------------------------
        # Load Image
        # -------------------------

        try:

            with Image.open(self.image_path) as source_image:
                image = source_image.convert("RGBA")

            self.preview = ctk.CTkImage(
                light_image=image,
                dark_image=image,
                size=(120, 168)
            )

        except Exception:
            self.preview = None

        # -------------------------
        # Thumbnail
        # -------------------------

        self.thumbnail = ctk.CTkLabel(
            self,
            image=self.preview,
            text="" if self.preview else "No Preview",
            width=130,
            height=170,
            fg_color="#252525",
            corner_radius=10
        )

        self.thumbnail.pack(pady=(15, 10))

        # -------------------------
        # Filename
        # -------------------------

        self.name = ctk.CTkLabel(
            self,
            text=self.filename,
            wraplength=145,
            font=(FONT, 12),
            text_color=TEXT
        )

        self.name.pack(pady=(0, 5))

        # -------------------------
        # Status
        # -------------------------

        self.status = ctk.CTkLabel(
            self,
            text="LOCAL",
            font=(FONT, 11),
            text_color=SUCCESS
        )

        self.status.pack()

        # -------------------------
        # Click Events
        # -------------------------

        for widget in (self, self.thumbnail, self.name, self.status):
            widget.bind("<Button-1>", self.clicked)

    def clicked(self, event=None):

        if self.callback:
            self.callback(self.image_path)

    def select(self):

        self.configure(border_color=ACCENT)

    def deselect(self):

        self.configure(border_color=BORDER)