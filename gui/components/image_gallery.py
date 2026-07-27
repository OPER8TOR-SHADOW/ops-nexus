import customtkinter as ctk

from gui.components.media_card import MediaCard


class ImageGallery(ctk.CTkScrollableFrame):

    def __init__(self, master, on_select=None):

        super().__init__(
            master,
            fg_color="transparent"
        )

        self.on_select = on_select
        self.cards = []

        # Four columns
        self.grid_columnconfigure((0, 1, 2, 3), weight=1)

    # --------------------------------------------------
    # Load Images
    # --------------------------------------------------

    def load_images(self, image_paths):

        # Remove existing cards
        for card in self.cards:
            card.destroy()

        self.cards.clear()

        row = 0
        column = 0

        for image_path in image_paths:

            card = MediaCard(
                self,
                image_path=image_path,
                callback=self.image_clicked
            )

            card.grid(
                row=row,
                column=column,
                padx=12,
                pady=12,
                sticky="n"
            )

            self.cards.append(card)

            column += 1

            if column >= 4:
                column = 0
                row += 1

    # --------------------------------------------------
    # Card Clicked
    # --------------------------------------------------

    def image_clicked(self, image_path):

        for card in self.cards:

            if card.image_path == image_path:
                card.select()
            else:
                card.deselect()

        if self.on_select:
            self.on_select(image_path)