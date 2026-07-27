import sys


class Progress:

    @staticmethod
    def update(percent, task):
        print(f"[PROGRESS]{percent}|{task}")
        sys.stdout.flush()

    @staticmethod
    def log(message):
        print(message)
        sys.stdout.flush()