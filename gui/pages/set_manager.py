import customtkinter as ctk
from tkinter import messagebox
import shutil
import threading
from datetime import datetime
from pathlib import Path

from database.service import DatabaseService
from gui.services.github_upload import upload_folder
from gui.services.image_downloader import download_set_images
from gui.services.importer import Importer
from pokemon_api import get_all_sets
from gui.theme import *


class SetManagerPage(ctk.CTkFrame):
    IMPORT_STAGE_IMPORT_WEIGHT = 0.15
    IMPORT_STAGE_DOWNLOAD_WEIGHT = 0.55
    IMPORT_STAGE_UPLOAD_WEIGHT = 0.30
    PROJECT_ROOT = Path(__file__).resolve().parents[2]

    def __init__(self, master, page_manager=None):

        super().__init__(
            master,
            fg_color=BACKGROUND
        )

        self.page_manager = page_manager
        self.search_results = []
        self.import_in_progress = False
        self.delete_in_progress = False
        self._is_destroyed = False

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        title = ctk.CTkLabel(
            self,
            text="Import Sets",
            font=(FONT, 30, "bold"),
            text_color=TEXT
        )

        title.grid(
            row=0,
            column=0,
            sticky="w",
            padx=30,
            pady=(25, 8)
        )

        subtitle = ctk.CTkLabel(
            self,
            text="Search Pokemon TCG API and import sets directly into your database.",
            font=(FONT, 13),
            text_color=SUBTEXT,
        )

        subtitle.grid(
            row=1,
            column=0,
            sticky="w",
            padx=30,
            pady=(0, 12)
        )

        content = ctk.CTkFrame(self, fg_color="transparent")
        content.grid(row=2, column=0, sticky="nsew", padx=30, pady=(0, 24))
        content.grid_columnconfigure(0, weight=1)
        content.grid_columnconfigure(1, weight=1)
        content.grid_rowconfigure(1, weight=1)

        search_card = ctk.CTkFrame(content, fg_color=CARD, corner_radius=12, border_width=1, border_color=BORDER)
        search_card.grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=(0, 12))
        search_card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            search_card,
            text="Search Pokemon TCG API",
            font=(FONT, 18, "bold"),
            text_color=TEXT,
        ).grid(row=0, column=0, sticky="w", padx=16, pady=(14, 10))

        self.search_input = ctk.CTkEntry(
            search_card,
            placeholder_text="Type set name, API id, or code (example: white flare, rsv10pt5, sv11b)",
            height=40,
        )
        self.search_input.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 10))
        self.search_input.bind("<Return>", lambda _event: self.search_sets())

        self.search_button = ctk.CTkButton(
            search_card,
            text="Search",
            width=120,
            command=self.search_sets,
        )
        self.search_button.grid(row=2, column=0, sticky="e", padx=16, pady=(0, 10))

        self.search_status = ctk.CTkLabel(
            search_card,
            text="Type a set name/id and click Search.",
            font=(FONT, 12),
            text_color=SUBTEXT,
        )
        self.search_status.grid(row=3, column=0, sticky="w", padx=16, pady=(0, 10))

        self.search_list = ctk.CTkScrollableFrame(search_card, fg_color="transparent", height=320)
        self.search_list.grid(row=4, column=0, sticky="nsew", padx=12, pady=(0, 12))
        self.search_list.grid_columnconfigure(0, weight=1)

        imported_card = ctk.CTkFrame(content, fg_color=CARD, corner_radius=12, border_width=1, border_color=BORDER)
        imported_card.grid(row=0, column=1, sticky="nsew", padx=(8, 0), pady=(0, 12))
        imported_card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            imported_card,
            text="Imported Sets",
            font=(FONT, 18, "bold"),
            text_color=TEXT,
        ).grid(row=0, column=0, sticky="w", padx=16, pady=(14, 10))

        self.import_status = ctk.CTkLabel(
            imported_card,
            text="",
            font=(FONT, 12),
            text_color=SUBTEXT,
        )
        self.import_status.grid(row=1, column=0, sticky="w", padx=16, pady=(0, 10))

        self.import_progress = ctk.CTkProgressBar(imported_card, mode="determinate")
        self.import_progress.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 10))
        self.import_progress.set(0)
        self.import_progress.grid_remove()

        self.imported_list = ctk.CTkScrollableFrame(imported_card, fg_color="transparent", height=320)
        self.imported_list.grid(row=3, column=0, sticky="nsew", padx=12, pady=(0, 12))
        self.imported_list.grid_columnconfigure(0, weight=1)

        self.refresh()
        self._set_search_results([], None)

    def refresh(self):
        imported_sets = self._load_imported_sets()
        self._render_imported_sets(imported_sets)

    def _load_imported_sets(self):
        db = DatabaseService()
        try:
            return [dict(row) for row in db.get_sets_with_counts()]
        finally:
            db.close()

    def search_sets(self):
        if self._is_destroyed:
            return

        query = str(self.search_input.get() or "").strip().lower()
        if not query:
            self._set_search_results([], None)
            self.search_status.configure(text="Type a set name/id and click Search.", text_color=SUBTEXT)
            return

        self.search_status.configure(text="Searching API...", text_color=SUBTEXT)
        imported_sets = self._load_imported_sets()
        imported_ids = {
            str(row.get("id") or "").strip().lower()
            for row in imported_sets
            if str(row.get("id") or "").strip()
        }
        imported_api_ids = {
            str(row.get("api_set") or row.get("id") or "").strip().lower()
            for row in imported_sets
            if str(row.get("api_set") or row.get("id") or "").strip()
        }

        def worker():
            try:
                all_sets = list(get_all_sets() or [])
                if query:
                    compact_query = "".join(ch for ch in query if ch.isalnum())
                    filtered = []
                    for row in all_sets:
                        api_id = str(row.get("id") or "").strip().lower()
                        name = str(row.get("name") or "").strip().lower()
                        series = str(row.get("series") or "").strip().lower()
                        code = str(row.get("ptcgoCode") or "").strip().lower()
                        haystack = " ".join([api_id, name, series, code])
                        api_compact = "".join(ch for ch in api_id if ch.isalnum())
                        code_compact = "".join(ch for ch in code if ch.isalnum())

                        if api_id in imported_ids or code in imported_api_ids:
                            continue

                        if query in haystack or (compact_query and compact_query in {api_compact, code_compact}):
                            filtered.append(row)
                    all_sets = filtered
                else:
                    all_sets = [
                        row
                        for row in all_sets
                        if str(row.get("id") or "").strip().lower() not in imported_api_ids
                    ]

                all_sets.sort(key=lambda row: str(row.get("releaseDate") or ""), reverse=True)
                results = all_sets[:80]
                self._safe_after(lambda: self._set_search_results(results, None))
            except Exception as exc:
                self._safe_after(lambda: self._set_search_results([], str(exc)))

        threading.Thread(target=worker, daemon=True).start()

    def _set_search_results(self, results, error_text):
        if self._is_destroyed:
            return

        try:
            if not self.winfo_exists():
                return
        except Exception:
            return

        self.search_results = list(results or [])
        if error_text:
            self.search_status.configure(text=f"Search failed: {error_text}", text_color=ERROR)
        else:
            self.search_status.configure(text=f"{len(self.search_results)} sets found", text_color=SUBTEXT)
        self._render_search_results()

    def _render_search_results(self):
        for child in self.search_list.winfo_children():
            child.destroy()

        if not self.search_results:
            ctk.CTkLabel(
                self.search_list,
                text="No results yet. Enter a set and click Search.",
                text_color=SUBTEXT,
                font=(FONT, 12),
            ).pack(anchor="w", padx=8, pady=8)
            return

        for set_row in self.search_results:
            api_id = str(set_row.get("id") or "").strip().lower()
            name = str(set_row.get("name") or "Untitled Set").strip()
            release_date = self._format_date(set_row.get("releaseDate"))
            card_count = int(set_row.get("printedTotal") or set_row.get("total") or 0)

            row = ctk.CTkFrame(self.search_list, fg_color="#1A1A1A", corner_radius=10, border_width=1, border_color=BORDER)
            row.pack(fill="x", padx=4, pady=(0, 8))

            ctk.CTkLabel(
                row,
                text=name,
                font=(FONT, 16, "bold"),
                text_color=TEXT,
            ).pack(anchor="w", padx=12, pady=(10, 4))

            ctk.CTkLabel(
                row,
                text=(
                    f"API ID: {api_id}\n"
                    f"Release: {release_date}\n"
                    f"Cards: {card_count}"
                ),
                font=(FONT, 12),
                text_color=SUBTEXT,
                justify="left",
            ).pack(anchor="w", padx=12, pady=(0, 10))

            import_button = ctk.CTkButton(
                row,
                text="Import Set",
                width=120,
                command=lambda set_id=api_id: self.import_set(set_id),
            )
            import_button.pack(anchor="e", padx=12, pady=(0, 10))

    def _render_imported_sets(self, sets):
        for child in self.imported_list.winfo_children():
            child.destroy()

        if not sets:
            ctk.CTkLabel(
                self.imported_list,
                text="No imported sets yet.",
                text_color=SUBTEXT,
                font=(FONT, 12),
            ).pack(anchor="w", padx=8, pady=8)
            return

        for set_row in sets:
            set_id = str(set_row.get("id") or "").strip().lower()
            set_name = str(set_row.get("name") or "").strip()
            series = str(set_row.get("series") or "Unknown Series")
            release_date = self._format_date(set_row.get("release_date"))
            card_count = int(set_row.get("card_count") or 0)

            card = ctk.CTkFrame(self.imported_list, fg_color="#1A1A1A", corner_radius=10, border_width=1, border_color=BORDER)
            card.pack(fill="x", padx=4, pady=(0, 8))

            ctk.CTkLabel(
                card,
                text=f"{set_name} ({set_id.upper()})",
                font=(FONT, 14, "bold"),
                text_color=TEXT,
            ).pack(anchor="w", padx=10, pady=(10, 2))

            ctk.CTkLabel(
                card,
                text=f"{series} • {release_date} • {card_count} cards",
                font=(FONT, 12),
                text_color=SUBTEXT,
            ).pack(anchor="w", padx=10, pady=(0, 10))

            button_row = ctk.CTkFrame(card, fg_color="transparent")
            button_row.pack(anchor="e", padx=10, pady=(0, 10))

            open_button = ctk.CTkButton(
                button_row,
                text="View Cards",
                width=100,
                command=lambda selected_id=set_id: self.open_set(selected_id),
            )
            open_button.pack(side="left", padx=(0, 8))

            delete_button = ctk.CTkButton(
                button_row,
                text="Delete Set",
                width=100,
                fg_color=ERROR,
                hover_color="#cc3333",
                command=lambda selected_id=set_id, selected_name=set_name: self.delete_set(selected_id, selected_name),
            )
            delete_button.pack(side="left")

    def import_set(self, set_id):
        if self._is_destroyed:
            return

        if self.import_in_progress or self.delete_in_progress:
            return

        self.import_in_progress = True
        self.import_status.configure(text=f"Importing {str(set_id).upper()}...", text_color=SUBTEXT)
        self.search_input.configure(state="disabled")
        self.search_button.configure(state="disabled")
        self.import_progress.set(0)
        self.import_progress.grid()

        def worker():
            try:
                importer = Importer()
                importer.import_set(set_id)
                self._safe_after(
                    lambda: self._set_import_progress(
                        self.IMPORT_STAGE_IMPORT_WEIGHT,
                        f"Imported {str(set_id).upper()} (15%)",
                    )
                )

                self._download_images_with_progress(set_id)
                upload_summary = self._upload_images_with_progress(set_id)

                warning_text = None
                failed_count = int(upload_summary.get("failed") or 0)
                if failed_count > 0:
                    warning_text = f"GitHub upload finished with {failed_count} failed file(s)."

                self._safe_after(lambda: self._on_import_complete(set_id, None, warning_text))
            except Exception as exc:
                self._safe_after(lambda: self._on_import_complete(set_id, str(exc), None))

        threading.Thread(target=worker, daemon=True).start()

    def _on_import_complete(self, set_id, error_text, warning_text=None):
        if self._is_destroyed:
            return

        try:
            if not self.winfo_exists():
                return
        except Exception:
            return

        self.import_in_progress = False
        self.import_progress.set(0)
        self.import_progress.grid_remove()
        self.search_input.configure(state="normal")
        self.search_button.configure(state="normal")

        if error_text:
            self.import_status.configure(text=f"Import failed: {error_text}", text_color=ERROR)
            return

        image_folder = Path("images") / str(set_id).upper()
        if warning_text:
            self.import_status.configure(
                text=(
                    f"Import complete: {str(set_id).upper()} • "
                    f"Image folder ready: {image_folder} • "
                    f"{warning_text}"
                ),
                text_color=WARNING,
            )
        else:
            self.import_status.configure(
                text=(
                    f"Import complete: {str(set_id).upper()} • "
                    f"Image folder ready: {image_folder} • "
                    "Images downloaded and uploaded to GitHub."
                ),
                text_color=SUCCESS,
            )
        self.refresh()
        if self.page_manager is not None:
            self.page_manager.notify_sets_updated()

    def delete_set(self, set_id, set_name):
        if self._is_destroyed:
            return

        if self.import_in_progress or self.delete_in_progress:
            return

        display_id = str(set_id or "").upper()
        confirmation = messagebox.askyesno(
            "Delete Imported Set",
            (
                f"Delete {set_name} ({display_id})?\n\n"
                "This removes the imported database rows and local images so you can import it again."
            ),
        )
        if not confirmation:
            return

        self.delete_in_progress = True
        self.import_status.configure(text=f"Deleting {display_id}...", text_color=SUBTEXT)
        self.search_input.configure(state="disabled")
        self.search_button.configure(state="disabled")

        def worker():
            error_text = None
            try:
                db = DatabaseService()
                try:
                    db.delete_set(set_id)
                finally:
                    db.close()

                image_folder = self.PROJECT_ROOT / "images" / display_id
                if image_folder.exists():
                    shutil.rmtree(image_folder)

                self._safe_after(lambda: self._on_delete_complete(set_id, None))
            except Exception as exc:
                error_text = str(exc)
                self._safe_after(lambda: self._on_delete_complete(set_id, error_text))

        threading.Thread(target=worker, daemon=True).start()

    def _set_import_progress(self, progress_value, status_text=None):
        if self._is_destroyed:
            return

        clamped = max(0.0, min(1.0, float(progress_value)))

        try:
            if not self.winfo_exists():
                return
        except Exception:
            return

        self.import_progress.set(clamped)
        if status_text:
            self.import_status.configure(text=status_text, text_color=SUBTEXT)

    def _on_delete_complete(self, set_id, error_text):
        if self._is_destroyed:
            return

        try:
            if not self.winfo_exists():
                return
        except Exception:
            return

        self.delete_in_progress = False
        self.search_input.configure(state="normal")
        self.search_button.configure(state="normal")

        if error_text:
            self.import_status.configure(text=f"Delete failed: {error_text}", text_color=ERROR)
            return

        self.import_status.configure(text=f"Deleted {str(set_id).upper()}. You can import it again now.", text_color=SUCCESS)
        self.refresh()
        if self.search_input.get().strip():
            self.search_sets()
        elif self.page_manager is not None:
            self.page_manager.notify_sets_updated()

    def _download_images_with_progress(self, set_id):
        def on_progress(current, total, _card, _status):
            stage_ratio = min(1.0, max(0.0, current / max(1, total)))
            overall = self.IMPORT_STAGE_IMPORT_WEIGHT + (stage_ratio * self.IMPORT_STAGE_DOWNLOAD_WEIGHT)
            percent = int(overall * 100)

            self._safe_after(
                lambda v=overall, c=current, t=total, p=percent: self._set_import_progress(
                    v,
                    f"Downloading images... {c}/{t} ({p}%)",
                )
            )

        summary = download_set_images(set_id, progress_callback=on_progress)
        if int(summary.get("failed") or 0) > 0 and int(summary.get("downloaded") or 0) == 0:
            raise RuntimeError("Image download failed.")

        self._safe_after(
            lambda: self._set_import_progress(
                self.IMPORT_STAGE_IMPORT_WEIGHT + self.IMPORT_STAGE_DOWNLOAD_WEIGHT,
                "Image download complete (70%)",
            )
        )

    def _upload_images_with_progress(self, set_id):
        def on_progress(current, total, _file_name, _uploaded, _skipped, _failed):
            stage_ratio = min(1.0, max(0.0, current / max(1, total)))
            overall = (
                self.IMPORT_STAGE_IMPORT_WEIGHT
                + self.IMPORT_STAGE_DOWNLOAD_WEIGHT
                + (stage_ratio * self.IMPORT_STAGE_UPLOAD_WEIGHT)
            )
            percent = int(overall * 100)

            self._safe_after(
                lambda v=overall, c=current, t=total, p=percent: self._set_import_progress(
                    v,
                    f"Uploading images to GitHub... {c}/{t} ({p}%)",
                )
            )

        summary = upload_folder(set_id, progress_callback=on_progress)

        self._safe_after(lambda: self._set_import_progress(1.0, "Upload complete (100%)"))
        return summary

    def _format_date(self, date_value):
        text = str(date_value or "").strip()
        if not text:
            return "Unknown"

        try:
            parsed = datetime.strptime(text, "%Y/%m/%d")
            return parsed.strftime("%d %b %Y")
        except Exception:
            return text

    def open_set(self, set_id):
        if self.page_manager is not None:
            self.page_manager.show_card_manager(selected_set=set_id)

    def _safe_after(self, callback):
        if self._is_destroyed:
            return

        try:
            if not self.winfo_exists():
                return
        except Exception:
            return

        try:
            self.after(0, callback)
        except Exception:
            return

    def destroy(self):
        self._is_destroyed = True

        super().destroy()
