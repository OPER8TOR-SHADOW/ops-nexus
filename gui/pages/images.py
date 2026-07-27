import customtkinter as ctk

from gui.components.image_gallery import ImageGallery
from gui.services.image_service import get_sets, get_images
from gui.theme import *


class ImagesPage(ctk.CTkFrame):

    def __init__(self, master):

        super().__init__(master, fg_color="transparent")

        self.selected_set = ctk.StringVar()

        # ----------------------------
        # Title
        # ----------------------------

        title = ctk.CTkLabel(
            self,
            text="Image Manager",
            font=(FONT, 28, "bold"),
            text_color=TEXT
        )

        title.pack(
            anchor="w",
            padx=20,
            pady=(20, 10)
        )

        # ----------------------------
        # Toolbar
        # ----------------------------

        toolbar = ctk.CTkFrame(
            self,
            fg_color="transparent"
        )

        toolbar.pack(
            fill="x",
            padx=20,
            pady=(0, 15)
        )

        sets = get_sets()

        if sets:
            self.selected_set.set(sets[0])

        self.set_selector = ctk.CTkOptionMenu(
            toolbar,
            values=sets,
            variable=self.selected_set,
            command=self.load_set,
            width=180
        )

        self.set_selector.pack(side="left")

        refresh = ctk.CTkButton(
            toolbar,
            text="Refresh",
            command=lambda: self.load_set(self.selected_set.get())
        )

        refresh.pack(side="right")

        # ----------------------------
        # Gallery
        # ----------------------------

        self.gallery = ImageGallery(
            self,
            on_select=self.image_selected
        )

        self.gallery.pack(
            fill="both",
            expand=True,
            padx=20,
            pady=(0, 20)
        )

        if sets:
            self.load_set(sets[0])

    # -------------------------------------

    def load_set(self, set_name):

        images = get_images(set_name)

        self.gallery.load_images(images)

    # -------------------------------------

    def image_selected(self, image_path):

        print(image_path)