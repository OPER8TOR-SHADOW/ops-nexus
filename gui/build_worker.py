import subprocess
import sys
import threading
import re


class BuildWorker:

    STAGE_DOWNLOAD = "download"
    STAGE_UPLOAD = "upload"
    STAGE_CSV = "csv"

    STAGE_LABELS = {
        "Downloading Pokémon Images": STAGE_DOWNLOAD,
        "Uploading Images to GitHub": STAGE_UPLOAD,
        "Generating eBay CSV": STAGE_CSV,
    }


    def __init__(self, gui, selected_set):

        self.gui = gui
        self.selected_set = selected_set
        self.current_stage = None

        self.metrics = {
            "set": selected_set.upper(),
            "cards_processed": 0,
            "images_downloaded": 0,
            "images_uploaded": 0,
            "images_skipped": 0,
            "upload_failures": 0,
            "csv_generated": False,
            "csv_output": "output/Ebay_Variation_Upload.csv",
            "failed_stage": None,
            "error_message": "",
        }

    def start(self):

        threading.Thread(
            target=self.run,
            daemon=True
        ).start()

    def run(self):

        process = subprocess.Popen(

            [
                sys.executable,
                "build_listing.py",
                self.selected_set
            ],

            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1

        )

        for line in process.stdout:

            line = line.rstrip()

            if line.startswith("[PROGRESS]"):

                line = line.replace("[PROGRESS]", "")

                percent, task = line.split("|", 1)

                stage_key = self.STAGE_LABELS.get(task.strip())
                if stage_key:
                    self.current_stage = stage_key
                    self._emit_event({
                        "type": "stage_status",
                        "stage": stage_key,
                        "status": "Running",
                        "operation": f"Current: {task.strip()}...",
                    })

                self.gui.after(
                    0,
                    lambda p=percent, t=task:
                    self.gui.set_progress(
                        int(p) / 100,
                        t
                    )
                )

            else:

                self._parse_line(line)

                self.gui.after(
                    0,
                    lambda l=line: self.gui.log(l)
                )

        process.wait()

        succeeded = process.returncode == 0

        self.gui.after(
            0,
            lambda: self.gui.build_finished(succeeded=succeeded, metrics=self.metrics)
        )

    # --------------------------------

    def _emit_event(self, event_payload):

        self.gui.after(
            0,
            lambda event=event_payload: self.gui.handle_build_event(event)
        )

    # --------------------------------

    def _parse_line(self, line):

        text = str(line or "").strip()

        if not text:
            return

        stage_key = self.STAGE_LABELS.get(text)
        if stage_key:
            self.current_stage = stage_key
            self._emit_event({
                "type": "stage_status",
                "stage": stage_key,
                "status": "Running",
                "operation": f"Current: {text}...",
            })
            return

        if text.endswith("complete."):
            for stage_text, key in self.STAGE_LABELS.items():
                if text.lower().startswith(stage_text.lower()):
                    self._emit_event({
                        "type": "stage_status",
                        "stage": key,
                        "status": "Complete",
                    })
                    return

        cards_match = re.search(r"Found\s+(\d+)\s+cards", text, re.IGNORECASE)
        if cards_match:
            cards = int(cards_match.group(1))
            self.metrics["cards_processed"] = max(self.metrics["cards_processed"], cards)
            if self.current_stage == self.STAGE_DOWNLOAD:
                self._emit_event({
                    "type": "stage_detail",
                    "stage": self.STAGE_DOWNLOAD,
                    "progress": f"{cards} / {cards}",
                    "operation": "Current: Preparing image downloads...",
                })
            elif self.current_stage == self.STAGE_CSV:
                self._emit_event({
                    "type": "stage_detail",
                    "stage": self.STAGE_CSV,
                    "operation": "Current: Creating Parent Listing...",
                })
            return

        if self.current_stage == self.STAGE_DOWNLOAD:
            self._parse_download_line(text)
            return

        if self.current_stage == self.STAGE_UPLOAD:
            self._parse_upload_line(text)
            return

        if self.current_stage == self.STAGE_CSV:
            self._parse_csv_line(text)
            return

        if "error:" in text.lower():
            self.metrics["error_message"] = text
            if not self.metrics["failed_stage"]:
                self.metrics["failed_stage"] = self.current_stage

    # --------------------------------

    def _parse_download_line(self, text):

        progress_match = re.search(r"\[(\d+)/(\d+)\]\s*[✓✗]\s+(.+)", text)
        if progress_match:
            current = int(progress_match.group(1))
            total = int(progress_match.group(2))
            filename = progress_match.group(3).strip()
            self._emit_event({
                "type": "stage_detail",
                "stage": self.STAGE_DOWNLOAD,
                "progress": f"{current} / {total}",
                "operation": f"Current: {filename}",
            })
            return

        download_count = re.search(r"Downloaded\s*:\s*(\d+)", text, re.IGNORECASE)
        if download_count:
            self.metrics["images_downloaded"] = int(download_count.group(1))
            return

        failed_count = re.search(r"Failed\s*:\s*(\d+)", text, re.IGNORECASE)
        if failed_count:
            self.metrics["upload_failures"] = max(
                self.metrics["upload_failures"],
                int(failed_count.group(1))
            )

    # --------------------------------

    def _parse_upload_line(self, text):

        total_match = re.search(r"Images\s*:\s*(\d+)", text, re.IGNORECASE)
        if total_match:
            total = int(total_match.group(1))
            self._emit_event({
                "type": "stage_detail",
                "stage": self.STAGE_UPLOAD,
                "progress": f"0 / {total}",
                "operation": "Current: Preparing upload queue...",
                "uploaded": 0,
                "skipped": 0,
                "failed": 0,
            })
            return

        upload_match = re.search(r"\[(\d+)/(\d+)\]\s+\[(.*?)\]\s+(.+)", text)
        if upload_match:
            current = int(upload_match.group(1))
            total = int(upload_match.group(2))
            status_token = upload_match.group(3).strip().upper()
            filename = upload_match.group(4).strip()

            if status_token == "OK":
                self.metrics["images_uploaded"] += 1
            elif status_token == "SKIP":
                self.metrics["images_skipped"] += 1
            else:
                self.metrics["upload_failures"] += 1

            self._emit_event({
                "type": "stage_detail",
                "stage": self.STAGE_UPLOAD,
                "progress": f"{current} / {total}",
                "operation": f"Current: {filename}",
                "uploaded": self.metrics["images_uploaded"],
                "skipped": self.metrics["images_skipped"],
                "failed": self.metrics["upload_failures"],
            })
            return

        uploaded_count = re.search(r"Uploaded\s*:\s*(\d+)", text, re.IGNORECASE)
        if uploaded_count:
            self.metrics["images_uploaded"] = int(uploaded_count.group(1))
            return

        skipped_count = re.search(r"Skipped\s*:\s*(\d+)", text, re.IGNORECASE)
        if skipped_count:
            self.metrics["images_skipped"] = int(skipped_count.group(1))
            return

        failed_count = re.search(r"Failed\s*:\s*(\d+)", text, re.IGNORECASE)
        if failed_count:
            self.metrics["upload_failures"] = int(failed_count.group(1))
            return

        if any(token in text.upper() for token in ("[FAIL]", "[ERROR]", "[TIMEOUT]")):
            if not self.metrics["error_message"]:
                self.metrics["error_message"] = text
            if not self.metrics["failed_stage"]:
                self.metrics["failed_stage"] = self.STAGE_UPLOAD

    # --------------------------------

    def _parse_csv_line(self, text):

        if "Building variations" in text:
            self._emit_event({
                "type": "stage_detail",
                "stage": self.STAGE_CSV,
                "operation": "Current: Writing Variations...",
            })
            return

        if text.startswith("Created "):
            self._emit_event({
                "type": "stage_detail",
                "stage": self.STAGE_CSV,
                "operation": "Current: Saving CSV...",
            })
            return

        output_match = re.search(r"Output File\s*:\s*(.+)", text, re.IGNORECASE)
        if output_match:
            self.metrics["csv_output"] = output_match.group(1).strip()
            return

        if "Export Complete" in text:
            self.metrics["csv_generated"] = True
            self._emit_event({
                "type": "stage_status",
                "stage": self.STAGE_CSV,
                "status": "Complete",
                "progress": "Progress: Complete",
            })
            return

        if "Unexpected Error" in text or "Missing file" in text:
            if not self.metrics["error_message"]:
                self.metrics["error_message"] = text
            if not self.metrics["failed_stage"]:
                self.metrics["failed_stage"] = self.STAGE_CSV