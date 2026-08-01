import customtkinter as ctk
from datetime import datetime

from gui.theme import *


class Console(ctk.CTkFrame):

    def __init__(self, master):

        super().__init__(
            master,
            fg_color=CARD,
            border_width=1,
            border_color=BORDER,
            corner_radius=15
        )

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # -------------------------
        # Header
        # -------------------------

        self.title = ctk.CTkLabel(
            self,
            text="Live Console",
            font=(FONT, 18, "bold"),
            text_color=TEXT
        )

        self.title.grid(
            row=0,
            column=0,
            sticky="w",
            padx=20,
            pady=(18, 10)
        )

        # -------------------------
        # Console
        # -------------------------

        self.console = ctk.CTkTextbox(
            self,
            fg_color="#111111",
            border_width=0,
            corner_radius=8,
            font=("Consolas", 11),
            wrap="none"
        )

        self.console.grid(
            row=1,
            column=0,
            sticky="nsew",
            padx=20,
            pady=(0, 20)
        )

        self.console.configure(state="disabled")

        textbox = self.console._textbox
        textbox.tag_configure("INFO", foreground="#C7CED8")
        textbox.tag_configure("SUCCESS", foreground=SUCCESS)
        textbox.tag_configure("WARNING", foreground=WARNING)
        textbox.tag_configure("ERROR", foreground=ERROR)

    # -----------------------------------

    def clear(self):

        self.console.configure(state="normal")

        self.console.delete("1.0", "end")

        self.console.configure(state="disabled")

    # -----------------------------------

    def write(self, text, level="INFO"):

        level_name = str(level or "INFO").upper()
        if level_name not in ("INFO", "SUCCESS", "WARNING", "ERROR"):
            level_name = self._infer_level(text)

        timestamp = datetime.now().strftime("%H:%M:%S")
        line = f"[{timestamp}] [{level_name}] {text}"

        self.console.configure(state="normal")

        self.console.insert("end", line + "\n", level_name)

        self.console.see("end")

        self.console.configure(state="disabled")

    # -----------------------------------

    def _infer_level(self, text):

        message = str(text or "").lower()

        if any(token in message for token in ("error", "failed", "fail", "timeout", "exception")):
            return "ERROR"

        if any(token in message for token in ("warning", "warn", "skip")):
            return "WARNING"

        if any(token in message for token in ("complete", "success", "created", "uploaded", "downloaded")):
            return "SUCCESS"

        return "INFO"