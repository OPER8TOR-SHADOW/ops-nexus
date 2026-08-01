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
        self.upload_progress = None
        self.csv_progress = None

        self.metrics = {
            "set": selected_set.upper(),
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

                parse_result = self._parse_line(line)

                console_line = parse_result.get("console_line")
                if console_line:
                    console_level = parse_result.get("console_level", "INFO")
                    self.gui.after(
                        0,
                        lambda l=console_line, level=console_level: self.gui.log(l, level)
                    )

                if not parse_result.get("suppress_console"):
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

        structured_result = self._parse_structured_progress(text)
        if structured_result is not None:
            return structured_result

        if not text:
            return {"suppress_console": False}

        stage_key = self.STAGE_LABELS.get(text)
        if stage_key:
            self.current_stage = stage_key
            self._emit_event({
                "type": "stage_status",
                "stage": stage_key,
                "status": "Running",
                "operation": f"Current: {text}...",
            })
            return {"suppress_console": False}

        if text.endswith("complete."):
            for stage_text, key in self.STAGE_LABELS.items():
                if text.lower().startswith(stage_text.lower()):
                    self._emit_event({
                        "type": "stage_status",
                        "stage": key,
                        "status": "Complete",
                    })
                    return {"suppress_console": False}

        cards_match = re.search(r"Found\s+(\d+)\s+cards", text, re.IGNORECASE)
        if cards_match:
            cards = int(cards_match.group(1))
            self.metrics["cards_processed"] = max(self.metrics["cards_processed"], cards)
            if self.current_stage == self.STAGE_DOWNLOAD:
                self._emit_event({
                    "type": "stage_detail",
                    "stage": self.STAGE_DOWNLOAD,
                    "progress": f"{cards} / {cards}",
                    "progress_value": 1.0,
                    "operation": "Current: Preparing image downloads...",
                })
            elif self.current_stage == self.STAGE_CSV:
                self._emit_event({
                    "type": "stage_detail",
                    "stage": self.STAGE_CSV,
                    "operation": "Current: Creating Parent Listing...",
                })
            return {"suppress_console": False}

        if self.current_stage == self.STAGE_DOWNLOAD:
            self._parse_download_line(text)
            return {"suppress_console": False}

        if self.current_stage == self.STAGE_UPLOAD:
            self._parse_upload_line(text)
            return {"suppress_console": False}

        if self.current_stage == self.STAGE_CSV:
            self._parse_csv_line(text)
            return {"suppress_console": False}

        if "error:" in text.lower():
            self.metrics["error_message"] = text
            if not self.metrics["failed_stage"]:
                self.metrics["failed_stage"] = self.current_stage

        return {"suppress_console": False}

    # --------------------------------

    def _parse_structured_progress(self, text):

        upload_header = re.match(r"\[UPLOAD\]\s+(\d+)/(\d+)", text)
        if upload_header:
            current = int(upload_header.group(1))
            total = int(upload_header.group(2))
            self.upload_progress = {
                "current": current,
                "total": total,
            }
            return {"suppress_console": True}

        if self.upload_progress and text.startswith("FILE="):
            self.upload_progress["file"] = text.split("=", 1)[1].strip()
            return {"suppress_console": True}

        if self.upload_progress and text.startswith("UPLOADED="):
            self.upload_progress["uploaded"] = int(text.split("=", 1)[1].strip() or 0)
            return {"suppress_console": True}

        if self.upload_progress and text.startswith("SKIPPED="):
            self.upload_progress["skipped"] = int(text.split("=", 1)[1].strip() or 0)
            return {"suppress_console": True}

        if self.upload_progress and text.startswith("FAILED="):
            self.upload_progress["failed"] = int(text.split("=", 1)[1].strip() or 0)

            current = int(self.upload_progress.get("current", 0))
            total = max(1, int(self.upload_progress.get("total", 0) or 1))
            file_name = self.upload_progress.get("file", "--")
            uploaded = int(self.upload_progress.get("uploaded", 0))
            skipped = int(self.upload_progress.get("skipped", 0))
            failed = int(self.upload_progress.get("failed", 0))

            self.metrics["images_uploaded"] = uploaded
            self.metrics["images_skipped"] = skipped
            self.metrics["upload_failures"] = failed

            self._emit_event({
                "type": "stage_detail",
                "stage": self.STAGE_UPLOAD,
                "progress": f"{current} / {total}",
                "progress_value": current / total,
                "current_file": file_name,
                "uploaded": uploaded,
                "skipped": skipped,
                "failed": failed,
            })

            console_line = f"[UPLOAD] {current}/{total} {file_name}"
            self.upload_progress = None
            return {
                "suppress_console": True,
                "console_line": console_line,
                "console_level": "INFO",
            }

        csv_header = re.match(r"\[CSV\]\s+(\d+)/(\d+)", text)
        if csv_header:
            processed = int(csv_header.group(1))
            total = int(csv_header.group(2))
            self.csv_progress = {
                "processed": processed,
                "total": total,
            }
            return {"suppress_console": True}

        if self.csv_progress and text.startswith("CURRENT="):
            current_card = text.split("=", 1)[1].strip()
            processed = int(self.csv_progress.get("processed", 0))
            total = max(1, int(self.csv_progress.get("total", 0) or 1))

            self.metrics["csv_rows_processed"] = processed
            self.metrics["csv_rows_total"] = total
            self.metrics["cards_processed"] = max(self.metrics["cards_processed"], total)

            self._emit_event({
                "type": "stage_detail",
                "stage": self.STAGE_CSV,
                "progress": f"{processed} / {total}",
                "progress_value": processed / total,
                "current_file": current_card,
            })

            console_line = f"[CSV] {processed}/{total} {current_card}"
            self.csv_progress = None
            return {
                "suppress_console": True,
                "console_line": console_line,
                "console_level": "INFO",
            }

        return None

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
                "progress_value": current / max(1, total),
                "operation": f"Current: {filename}",
            })
            return

        download_count = re.search(r"Downloaded\s*:\s*(\d+)", text, re.IGNORECASE)
        if download_count:
            self.metrics["images_downloaded"] = int(download_count.group(1))
            return

        failed_count = re.search(r"Failed\s*:\s*(\d+)", text, re.IGNORECASE)
        if failed_count:
            self.metrics["download_failures"] = int(failed_count.group(1))

    # --------------------------------

    def _parse_upload_line(self, text):

        total_match = re.search(r"Images\s*:\s*(\d+)", text, re.IGNORECASE)
        if total_match:
            total = int(total_match.group(1))
            self._emit_event({
                "type": "stage_detail",
                "stage": self.STAGE_UPLOAD,
                "progress": f"0 / {total}",
                "progress_value": 0,
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
                "progress_value": current / max(1, total),
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
                "progress_value": 0,
                "operation": "Current: Writing Variations...",
            })
            return

        if text.startswith("Created "):
            self._emit_event({
                "type": "stage_detail",
                "stage": self.STAGE_CSV,
                "operation": "Current: Saving CSV...",
                "progress_value": 1.0,
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
                "progress": "Complete",
                "progress_value": 1.0,
            })
            return

        if "Unexpected Error" in text or "Missing file" in text:
            if not self.metrics["error_message"]:
                self.metrics["error_message"] = text
            if not self.metrics["failed_stage"]:
                self.metrics["failed_stage"] = self.STAGE_CSV