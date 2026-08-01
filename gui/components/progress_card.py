import customtkinter as ctk

from gui.theme import *
from gui.components.status_badge import StatusBadge


class ProgressCard(ctk.CTkFrame):

    STAGES = [
        ("download", "Downloading Images"),
        ("upload", "Uploading Images"),
        ("csv", "Generating CSV"),
        ("complete", "Complete"),
    ]

    def __init__(self, master, action_callbacks=None):

        super().__init__(
            master,
            fg_color=CARD,
            border_width=1,
            border_color=BORDER,
            corner_radius=15
        )

        self.action_callbacks = action_callbacks or {}
        self.stage_widgets = {}

        self.grid_columnconfigure(0, weight=1)

        # ----------------------------
        # Title
        # ----------------------------

        self.title = ctk.CTkLabel(
            self,
            text="Build Dashboard",
            font=(FONT, 18, "bold"),
            text_color=TEXT
        )

        self.title.pack(
            anchor="w",
            padx=20,
            pady=(18, 5)
        )

        # ----------------------------
        # Status Badge
        # ----------------------------

        self.status = StatusBadge(
            self,
            "Waiting"
        )

        self.status.pack(
            anchor="w",
            padx=20,
            pady=(0, 15)
        )

        # ----------------------------
        # Live Status
        # ----------------------------

        self.live_status = ctk.CTkFrame(
            self,
            fg_color=PANEL,
            border_width=1,
            border_color=BORDER,
            corner_radius=10,
        )

        self.live_status.pack(
            fill="x",
            padx=20,
            pady=(0, 14),
        )

        for column in range(4):
            self.live_status.grid_columnconfigure(column, weight=1)

        self.current_stage = ctk.CTkLabel(
            self.live_status,
            text="Current Stage: Waiting",
            text_color=TEXT,
            font=(FONT, 13, "bold"),
            anchor="w",
        )
        self.current_stage.grid(row=0, column=0, sticky="w", padx=12, pady=(10, 2))

        self.elapsed = ctk.CTkLabel(
            self.live_status,
            text="Elapsed Time: 00:00",
            text_color=SUBTEXT,
            font=(FONT, 12),
            anchor="w",
        )
        self.elapsed.grid(row=0, column=1, sticky="w", padx=12, pady=(10, 2))

        self.eta = ctk.CTkLabel(
            self.live_status,
            text="ETA: --:--",
            text_color=SUBTEXT,
            font=(FONT, 12),
            anchor="w",
        )
        self.eta.grid(row=0, column=2, sticky="w", padx=12, pady=(10, 2))

        self.overall = ctk.CTkLabel(
            self.live_status,
            text="Overall Progress: 0%",
            text_color=SUBTEXT,
            font=(FONT, 12),
            anchor="w",
        )
        self.overall.grid(row=0, column=3, sticky="w", padx=12, pady=(10, 2))

        # ----------------------------
        # Stages
        # ----------------------------

        self.stages_frame = ctk.CTkFrame(
            self,
            fg_color="transparent",
        )

        self.stages_frame.pack(
            fill="both",
            padx=20,
            pady=(0, 8),
        )

        for index, stage in enumerate(self.STAGES):
            stage_key, stage_title = stage
            self._create_stage_row(index, stage_key, stage_title)

        # ----------------------------
        # Summary
        # ----------------------------

        self.summary = ctk.CTkFrame(
            self,
            fg_color=PANEL,
            border_width=1,
            border_color=BORDER,
            corner_radius=10,
        )

        self.summary.pack(
            fill="x",
            padx=20,
            pady=(8, 20),
        )

        self.summary_title = ctk.CTkLabel(
            self.summary,
            text="Build Summary",
            font=(FONT, 16, "bold"),
            text_color=TEXT,
            anchor="w",
        )

        self.summary_title.pack(anchor="w", padx=12, pady=(10, 8))

        self.summary_grid = ctk.CTkFrame(self.summary, fg_color="transparent")
        self.summary_grid.pack(fill="x", padx=12)
        for column in range(2):
            self.summary_grid.grid_columnconfigure(column, weight=1)

        self.summary_labels = {}
        summary_fields = [
            "Set",
            "Build duration",
            "Cards processed",
            "Images downloaded",
            "Images uploaded",
            "Images skipped",
            "Upload failures",
            "CSV generated",
            "Completion time",
        ]
        for index, field in enumerate(summary_fields):
            row = index // 2
            col = index % 2
            label = ctk.CTkLabel(
                self.summary_grid,
                text=f"{field}: --",
                text_color=SUBTEXT,
                font=(FONT, 12),
                anchor="w",
                justify="left",
            )
            label.grid(row=row, column=col, sticky="w", padx=(0, 18), pady=2)
            self.summary_labels[field] = label

        self.actions = ctk.CTkFrame(self.summary, fg_color="transparent")
        self.actions.pack(fill="x", padx=12, pady=(10, 12))
        for column in range(4):
            self.actions.grid_columnconfigure(column, weight=1)

        self._add_action_button(0, "Open CSV", "open_csv")
        self._add_action_button(1, "Open Output Folder", "open_output")
        self._add_action_button(2, "Open Images Folder", "open_images")
        self._add_action_button(3, "Open GitHub Repository", "open_repo")

        self.hide_summary()

    # --------------------------------

    def _create_stage_row(self, index, stage_key, stage_title):

        row = ctk.CTkFrame(
            self.stages_frame,
            fg_color=PANEL,
            border_width=1,
            border_color=BORDER,
            corner_radius=10,
        )

        row.pack(fill="x", pady=(0, 8))

        badge = StatusBadge(row, stage_title)
        badge.pack(anchor="w", fill="x", padx=12, pady=(10, 2))
        badge.set_status("Waiting", SUCCESS)

        progress_label = ctk.CTkLabel(
            row,
            text="Progress: --",
            text_color=SUBTEXT,
            font=(FONT, 12),
            anchor="w",
        )
        progress_label.pack(anchor="w", padx=12, pady=(0, 2))

        operation_label = ctk.CTkLabel(
            row,
            text="Current: Waiting...",
            text_color=SUBTEXT,
            font=(FONT, 12),
            anchor="w",
            justify="left",
        )
        operation_label.pack(anchor="w", padx=12, pady=(0, 10))

        self.stage_widgets[stage_key] = {
            "row": row,
            "badge": badge,
            "progress": progress_label,
            "operation": operation_label,
        }

    # --------------------------------

    def _add_action_button(self, column, title, action_name):

        button = ctk.CTkButton(
            self.actions,
            text=title,
            height=36,
            corner_radius=8,
            fg_color="#2A2A2A",
            hover_color="#343434",
            command=lambda a=action_name: self._call_action(a),
        )

        button.grid(row=0, column=column, sticky="ew", padx=4)

    # --------------------------------

    def _call_action(self, action_name):

        callback = self.action_callbacks.get(action_name)
        if callback:
            callback()

    # --------------------------------

    def reset(self):

        self.status.set_status("Waiting", SUCCESS)
        self.set_live_status("Waiting", "00:00", "--:--", 0)

        for _, stage in self.stage_widgets.items():
            stage["row"].configure(border_color=BORDER)
            stage["badge"].set_status("Waiting", SUCCESS)
            stage["progress"].configure(text="Progress: --", text_color=SUBTEXT)
            stage["operation"].configure(text="Current: Waiting...", text_color=SUBTEXT)

        self.hide_summary()

    # --------------------------------

    def set_live_status(self, stage_name, elapsed_text, eta_text, overall_percent):

        self.current_stage.configure(text=f"Current Stage: {stage_name}")
        self.elapsed.configure(text=f"Elapsed Time: {elapsed_text}")
        self.eta.configure(text=f"ETA: {eta_text}")
        self.overall.configure(text=f"Overall Progress: {int(max(0, min(100, overall_percent)))}%")

    # --------------------------------

    def update_stage(self, stage_key, status=None, progress_text=None, operation_text=None, error_text=None):

        stage = self.stage_widgets.get(stage_key)

        if not stage:
            return

        if status:
            status_lower = status.lower()

            if status_lower == "failed":
                stage["badge"].set_status("Failed", ERROR)
                stage["row"].configure(border_color=ERROR)
            elif status_lower == "running":
                stage["badge"].set_status("Running", WARNING)
                stage["row"].configure(border_color=WARNING)
            elif status_lower == "complete":
                stage["badge"].set_status("Complete", SUCCESS)
                stage["row"].configure(border_color=SUCCESS)
            else:
                stage["badge"].set_status("Waiting", SUCCESS)
                stage["row"].configure(border_color=BORDER)

        if progress_text is not None:
            stage["progress"].configure(text=progress_text)

        if operation_text is not None:
            stage["operation"].configure(text=operation_text)

        if error_text:
            stage["operation"].configure(text=f"Error: {error_text}", text_color=ERROR)

    # --------------------------------

    def set_overall_status(self, status):

        if status == "Failed":
            self.status.set_status("Failed", ERROR)
        elif status == "Complete":
            self.status.set_status("Complete", SUCCESS)
        elif status == "Running":
            self.status.set_status("Running", WARNING)
        else:
            self.status.set_status("Waiting", SUCCESS)

    # --------------------------------

    def show_summary(self, summary_data):

        for key, label in self.summary_labels.items():
            value = summary_data.get(key, "--")
            label.configure(text=f"{key}: {value}")

        self.summary.pack(fill="x", padx=20, pady=(8, 20))

    # --------------------------------

    def hide_summary(self):

        self.summary.pack_forget()