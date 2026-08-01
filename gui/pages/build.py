import customtkinter as ctk
from datetime import datetime
from pathlib import Path
import json
import os
import webbrowser

from gui.theme import *
from gui.build_worker import BuildWorker
from config import GITHUB_OWNER, GITHUB_REPO

from gui.components.set_selector import SetSelector
from gui.components.progress_card import ProgressCard
from gui.components.console import Console
from gui.components.build_history_card import BuildHistoryCard


class BuildPage(ctk.CTkFrame):

    STAGE_NAMES = {
        "download": "Downloading Images",
        "upload": "Uploading Images",
        "csv": "Generating CSV",
        "complete": "Complete",
    }

    TASK_TO_STAGE = {
        "Downloading Pokémon Images": "download",
        "Uploading Images to GitHub": "upload",
        "Generating eBay CSV": "csv",
        "Build Complete": "complete",
    }

    def __init__(self, master):

        super().__init__(master, fg_color="transparent")

        self.history_file = Path("output") / "build_history.json"
        self.build_history = []
        self.worker = None
        self.build_running = False
        self.start_time = None
        self.end_time = None
        self.overall_progress = 0.0
        self.current_stage = "download"
        self.current_set = "--"
        self.timer_job = None

        self.metrics = {
            "set": "--",
            "cards_processed": 0,
            "images_downloaded": 0,
            "images_uploaded": 0,
            "images_skipped": 0,
            "upload_failures": 0,
            "download_failures": 0,
            "csv_generated": False,
            "csv_output": "output/Ebay_Variation_Upload.csv",
            "csv_rows_processed": 0,
            "csv_rows_total": 0,
            "failed_stage": None,
            "error_message": "",
        }

        # ======================================================
        # Layout
        # ======================================================

        self.grid_columnconfigure(0, weight=3)
        self.grid_columnconfigure(1, weight=2)
        self.grid_rowconfigure(5, weight=1)

        # ======================================================
        # Title
        # ======================================================

        title = ctk.CTkLabel(
            self,
            text="Build Listing",
            font=(FONT, 30, "bold"),
            text_color=TEXT
        )

        title.grid(
            row=0,
            column=0,
            columnspan=2,
            sticky="w",
            pady=(0, 20)
        )

        subtitle = ctk.CTkLabel(
            self,
            text="Draft workspace for validation, pricing, and listing preparation before upload to eBay.",
            font=(FONT, 14),
            text_color=MUTED,
        )

        subtitle.grid(
            row=1,
            column=0,
            columnspan=2,
            sticky="w",
            pady=(0, 18)
        )

        # ======================================================
        # Set Selector
        # ======================================================

        self.set_selector = SetSelector(self)

        self.set_selector.grid(
            row=2,
            column=0,
            sticky="ew",
            pady=(0, 20)
        )

        # ======================================================
        # Progress Card
        # ======================================================

        self.progress = ProgressCard(
            self,
            action_callbacks={
                "open_csv": self.open_csv,
                "open_output": self.open_output_folder,
                "open_images": self.open_images_folder,
                "open_repo": self.open_github_repository,
            },
        )

        self.progress.grid(
            row=3,
            column=0,
            sticky="ew",
            pady=(0, 20)
        )

        # ======================================================
        # Build Button
        # ======================================================

        self.build_button = ctk.CTkButton(
            self,
            text="🚀 BUILD LISTING",
            height=50,
            corner_radius=12,
            font=(FONT, 18, "bold"),
            fg_color=ACCENT,
            hover_color="#B00000",
            command=self.build
        )

        self.build_button.grid(
            row=4,
            column=0,
            sticky="ew",
            pady=(0, 20)
        )

        # ======================================================
        # Build History
        # ======================================================

        self.history_card = BuildHistoryCard(self)

        self.history_card.grid(
            row=2,
            column=1,
            rowspan=3,
            sticky="nsew",
            padx=(16, 0),
        )

        # ======================================================
        # Console
        # ======================================================

        self.console = Console(self)

        self.console.grid(
            row=5,
            column=0,
            columnspan=2,
            sticky="nsew"
        )

        self._load_history()
        self._render_history()
        self.progress.reset()

    # ======================================================
    # Build
    # ======================================================

    def build(self):

        self.console.clear()
        self.build_button.configure(state="disabled")
        self._reset_build_state()
        self.progress.set_overall_status("Running")
        self.log("Starting build pipeline...", "INFO")
        self.log("Pipeline: Download Images -> Upload Images -> Generate CSV -> Complete", "INFO")

        try:
            selected_set = self.set_selector.get_id()
        except KeyError:
            self.log("No valid set selected.", "ERROR")
            self.progress.set_overall_status("Failed")
            self.build_button.configure(state="normal")
            return

        self.current_set = str(selected_set).upper()
        self.metrics["set"] = self.current_set

        self.start_time = datetime.now()
        self.build_running = True
        self._start_timer()

        self.log("=" * 60, "INFO")
        self.log("OPS Nexus", "INFO")
        self.log("=" * 60, "INFO")
        self.log(f"Selected Set: {self.current_set}", "INFO")
        self.log("", "INFO")

        self.worker = BuildWorker(
            self,
            self.current_set
        )

        self.worker.start()

    # ======================================================
    # Worker Callbacks
    # ======================================================

    def log(self, message, level=None):

        self.console.write(message, level=level or "AUTO")

    def set_progress(self, value, task):

        self.overall_progress = max(0.0, min(1.0, float(value)))

        stage = self.TASK_TO_STAGE.get(str(task).strip())
        if stage:
            self.current_stage = stage
            if stage != "complete":
                self.progress.update_stage(
                    stage,
                    status="Running",
                    operation_text=f"Current: {task}...",
                )

        if self.overall_progress > 0 and self.overall_progress < 1:
            self.progress.set_overall_status("Running")

        self._refresh_live_status()

    # ======================================================
    # Worker Events
    # ======================================================

    def handle_build_event(self, event):

        event_type = str(event.get("type", "")).lower()
        stage = event.get("stage")

        if stage in self.STAGE_NAMES:
            self.current_stage = stage

        if event_type == "stage_status":
            self.progress.update_stage(
                stage,
                status=event.get("status"),
                progress_text=event.get("progress"),
                operation_text=event.get("operation"),
                progress_value=event.get("progress_value"),
            )
            return

        if event_type == "stage_detail":
            progress_text = event.get("progress")
            operation_text = event.get("operation")
            progress_value = event.get("progress_value")

            if stage == "upload":
                uploaded = event.get("uploaded", self.metrics["images_uploaded"])
                skipped = event.get("skipped", self.metrics["images_skipped"])
                failed = event.get("failed", self.metrics["upload_failures"])
                current_file = event.get("current_file", "--")
                operation_text = (
                    f"Current File:\n{current_file}\n\n"
                    f"Uploaded:\n{uploaded}\n\n"
                    f"Skipped:\n{skipped}\n\n"
                    f"Failed:\n{failed}"
                )
                if progress_text:
                    progress_text = f"Progress:\n{progress_text}"

            elif stage == "download":
                current_file = event.get("operation", "Current: --")
                if current_file.startswith("Current: "):
                    current_file = current_file.split(": ", 1)[1]
                operation_text = f"Current:\n{current_file}"
                if progress_text:
                    progress_text = f"Progress:\n{progress_text}"

            elif stage == "csv":
                current_card = event.get("current_file")
                if current_card:
                    operation_text = f"Current:\n{current_card}"
                elif operation_text and operation_text.startswith("Current: "):
                    operation_text = operation_text.replace("Current: ", "Current:\n", 1)
                if progress_text:
                    progress_text = f"Progress:\n{progress_text}"
                elif not progress_text:
                    progress_text = "Progress:\nRunning"

            self.progress.update_stage(
                stage,
                status="Running",
                progress_text=progress_text,
                operation_text=operation_text,
                progress_value=progress_value,
            )

    # ======================================================
    # Build Finished
    # ======================================================

    def build_finished(self, succeeded=True, metrics=None):

        self.build_running = False
        self.end_time = datetime.now()

        if self.timer_job:
            self.after_cancel(self.timer_job)
            self.timer_job = None

        if metrics:
            self.metrics.update(metrics)

        duration_seconds = self._duration_seconds()
        elapsed_text = self._format_clock(duration_seconds)

        if succeeded:
            self.overall_progress = 1.0
            self.progress.set_overall_status("Complete")
            self.progress.update_stage("download", status="Complete")
            self.progress.update_stage("upload", status="Complete")
            self.progress.update_stage("csv", status="Complete", operation_text="Current:\nSaving CSV...", progress_value=1.0)
            self.progress.update_stage(
                "complete",
                status="Complete",
                progress_text="Progress:\nComplete",
                operation_text="Build finished successfully.",
                progress_value=1.0,
            )
            self.current_stage = "complete"

            self.log("", "SUCCESS")
            self.log("=" * 60, "SUCCESS")
            self.log("Build Complete", "SUCCESS")
            self.log("=" * 60, "SUCCESS")
        else:
            failed_stage = self.metrics.get("failed_stage") or self.current_stage or "download"
            error_text = self.metrics.get("error_message") or "Build failed. Review console output for details."

            self.progress.set_overall_status("Failed")
            self.progress.update_stage(
                failed_stage,
                status="Failed",
                error_text=error_text,
            )
            self.progress.update_stage(
                "complete",
                status="Waiting",
                progress_text="Progress: --",
                operation_text="Current: Build did not complete.",
                progress_value=0,
            )

            self.log("", "ERROR")
            self.log("=" * 60, "ERROR")
            self.log("Build Failed", "ERROR")
            self.log(error_text, "ERROR")
            self.log("=" * 60, "ERROR")

        self._refresh_live_status(final=True)
        self._show_summary(succeeded, duration_seconds, elapsed_text)
        self._record_history(succeeded, duration_seconds)

        self.build_button.configure(state="normal")

    # ======================================================
    # Actions
    # ======================================================

    def open_csv(self):

        csv_path = Path(self.metrics.get("csv_output", "output/Ebay_Variation_Upload.csv"))
        if not csv_path.is_absolute():
            csv_path = Path.cwd() / csv_path

        if not csv_path.exists():
            self.log(f"CSV not found: {csv_path}", "WARNING")
            return

        os.startfile(csv_path)
        self.log(f"Opened CSV: {csv_path}", "INFO")

    def open_output_folder(self):

        folder = Path.cwd() / "output"
        folder.mkdir(parents=True, exist_ok=True)
        os.startfile(folder)
        self.log(f"Opened output folder: {folder}", "INFO")

    def open_images_folder(self):

        set_id = self.current_set or self.metrics.get("set", "")
        folder = Path.cwd() / "images" / str(set_id).upper()

        if not folder.exists():
            self.log(f"Images folder not found: {folder}", "WARNING")
            return

        os.startfile(folder)
        self.log(f"Opened images folder: {folder}", "INFO")

    def open_github_repository(self):

        url = f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}"
        webbrowser.open(url)
        self.log(f"Opened repository: {url}", "INFO")

    # ======================================================
    # State
    # ======================================================

    def _reset_build_state(self):

        if self.timer_job:
            self.after_cancel(self.timer_job)
            self.timer_job = None

        self.start_time = None
        self.end_time = None
        self.overall_progress = 0.0
        self.current_stage = "download"

        self.metrics = {
            "set": "--",
            "cards_processed": 0,
            "images_downloaded": 0,
            "images_uploaded": 0,
            "images_skipped": 0,
            "upload_failures": 0,
            "download_failures": 0,
            "csv_generated": False,
            "csv_output": "output/Ebay_Variation_Upload.csv",
            "csv_rows_processed": 0,
            "csv_rows_total": 0,
            "failed_stage": None,
            "error_message": "",
        }

        self.progress.reset()
        self._refresh_live_status()

    def _start_timer(self):

        self._refresh_live_status()
        self.timer_job = self.after(1000, self._on_timer)

    def _on_timer(self):

        if not self.build_running:
            return

        self._refresh_live_status()
        self.timer_job = self.after(1000, self._on_timer)

    def _refresh_live_status(self, final=False):

        elapsed_seconds = self._duration_seconds()
        elapsed_text = self._format_clock(elapsed_seconds)

        eta_text = "--:--"
        if self.overall_progress > 0 and self.overall_progress < 1 and not final:
            remaining = int(max(0, elapsed_seconds * ((1 / self.overall_progress) - 1)))
            eta_text = self._format_clock(remaining)

        stage_label = self.STAGE_NAMES.get(self.current_stage, "Waiting")
        self.progress.set_live_status(
            stage_label,
            elapsed_text,
            eta_text,
            self.overall_progress * 100,
        )

    # ======================================================
    # Summary + History
    # ======================================================

    def _show_summary(self, succeeded, duration_seconds, elapsed_text):

        completion_time = self.end_time or datetime.now()

        summary = {
            "Set": self.metrics.get("set", "--"),
            "Build duration": elapsed_text,
            "Cards processed": self.metrics.get("cards_processed", 0),
            "Images downloaded": self.metrics.get("images_downloaded", 0),
            "Images uploaded": self.metrics.get("images_uploaded", 0),
            "Images skipped": self.metrics.get("images_skipped", 0),
            "Upload failures": self.metrics.get("upload_failures", 0),
            "CSV generated": "Yes" if succeeded and self.metrics.get("csv_generated") else "No",
            "Completion time": completion_time.strftime("%Y-%m-%d %I:%M:%S %p"),
        }

        self.progress.show_summary(summary)

    def _record_history(self, succeeded, duration_seconds):

        entry = {
            "timestamp": (self.end_time or datetime.now()).isoformat(timespec="seconds"),
            "set": self.metrics.get("set", "--"),
            "duration_seconds": int(duration_seconds),
            "duration_text": self._format_compact_duration(duration_seconds),
            "cards": int(self.metrics.get("cards_processed", 0) or 0),
            "uploaded": int(self.metrics.get("images_uploaded", 0) or 0),
            "skipped": int(self.metrics.get("images_skipped", 0) or 0),
            "failed": int(self.metrics.get("upload_failures", 0) or 0),
            "csv_generated": bool(self.metrics.get("csv_generated")),
            "result": "Success" if succeeded else "Failed",
        }

        self.build_history.insert(0, entry)
        self.build_history = self.build_history[:25]
        self._save_history()
        self._render_history()

    def _load_history(self):

        if not self.history_file.exists():
            self.build_history = []
            return

        try:
            with open(self.history_file, "r", encoding="utf-8") as file:
                data = json.load(file)
            if isinstance(data, list):
                self.build_history = data[:25]
            else:
                self.build_history = []
        except Exception:
            self.build_history = []

    def _save_history(self):

        self.history_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.history_file, "w", encoding="utf-8") as file:
            json.dump(self.build_history[:25], file, indent=2)

    def _render_history(self):

        self.history_card.set_history(self.build_history)

    # ======================================================
    # Helpers
    # ======================================================

    def _duration_seconds(self):

        if not self.start_time:
            return 0

        end_time = self.end_time or datetime.now()
        return int((end_time - self.start_time).total_seconds())

    def _format_clock(self, total_seconds):

        total_seconds = max(0, int(total_seconds))
        minutes, seconds = divmod(total_seconds, 60)
        hours, minutes = divmod(minutes, 60)

        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"

    def _format_compact_duration(self, total_seconds):

        total_seconds = max(0, int(total_seconds))
        minutes, seconds = divmod(total_seconds, 60)
        hours, minutes = divmod(minutes, 60)

        if hours > 0:
            return f"{hours}h {minutes}m {seconds}s"
        if minutes > 0:
            return f"{minutes}m {seconds}s"
        return f"{seconds}s"