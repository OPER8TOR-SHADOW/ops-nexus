import subprocess
import sys
import threading


class BuildWorker:

    def __init__(self, gui, selected_set):

        self.gui = gui
        self.selected_set = selected_set

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

                self.gui.after(
                    0,
                    lambda p=percent, t=task:
                    self.gui.set_progress(
                        int(p) / 100,
                        t
                    )
                )

            else:

                self.gui.after(
                    0,
                    lambda l=line: self.gui.log(l)
                )

        process.wait()

        succeeded = process.returncode == 0

        self.gui.after(
            0,
            lambda: self.gui.build_finished(succeeded=succeeded)
        )