import base64
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

from config import (
    GITHUB_OWNER,
    GITHUB_REPO,
    GITHUB_BRANCH,
)

# ==========================================================
# Environment
# ==========================================================

load_dotenv()

TOKEN = os.getenv("GITHUB_TOKEN")

if not TOKEN:
    print("ERROR: GITHUB_TOKEN not found.")
    sys.exit(1)

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/vnd.github+json",
}


def emit_upload_progress(index, total, file_name, uploaded, skipped, failed):
    print(f"[UPLOAD] {index}/{total}", flush=True)
    print(f"FILE={file_name}", flush=True)
    print(f"UPLOADED={uploaded}", flush=True)
    print(f"SKIPPED={skipped}", flush=True)
    print(f"FAILED={failed}", flush=True)


# ==========================================================
# Upload One File
# ==========================================================

def upload_file(file_path: Path, remote_folder: str):

    remote_path = f"{remote_folder}/{file_path.name}"

    url = (
        f"https://api.github.com/repos/"
        f"{GITHUB_OWNER}/{GITHUB_REPO}/contents/{remote_path}"
    )

    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=20,
        )

        if response.status_code == 200:
            print(f"[SKIP] {file_path.name}")
            return "skipped"

        if response.status_code not in (200, 404):
            print(f"[ERROR] GET {response.status_code}")
            print(response.text)
            return "failed"

        with open(file_path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode("utf-8")

        payload = {
            "message": f"Upload {file_path.name}",
            "content": encoded,
            "branch": GITHUB_BRANCH,
        }

        response = requests.put(
            url,
            headers=HEADERS,
            json=payload,
            timeout=60,
        )

        if response.status_code in (200, 201):
            print(f"[ OK ] {file_path.name}")
            return "uploaded"

        print(f"[FAIL] {file_path.name}")
        print(response.status_code)
        print(response.text)
        return "failed"

    except requests.Timeout:
        print(f"[TIMEOUT] {file_path.name}")
        return "failed"

    except Exception as e:
        print(f"[ERROR] {file_path.name}")
        print(e)
        return "failed"


# ==========================================================
# Upload Folder
# ==========================================================

def upload_folder(set_id):

    local_folder = Path("images") / set_id.upper()

    if not local_folder.exists():
        print(f"Folder not found: {local_folder}")
        return

    remote_folder = f"cards/{set_id.upper()}"

    images = sorted(
        f
        for f in local_folder.iterdir()
        if f.suffix.lower() in (
            ".png",
            ".jpg",
            ".jpeg",
            ".webp",
        )
    )

    print()
    print("=" * 60)
    print("OPS GitHub Image Upload")
    print("=" * 60)
    print(f"Repository : {GITHUB_OWNER}/{GITHUB_REPO}")
    print(f"Local      : {local_folder}")
    print(f"Remote     : {remote_folder}")
    print(f"Images     : {len(images)}")
    print()

    uploaded = 0
    skipped = 0
    failed = 0

    total = len(images)

    for index, image in enumerate(images, start=1):

        result = upload_file(image, remote_folder)

        if result == "uploaded":
            uploaded += 1
        elif result == "skipped":
            skipped += 1
        else:
            failed += 1

        emit_upload_progress(
            index,
            total,
            image.name,
            uploaded,
            skipped,
            failed,
        )

    print()
    print("=" * 60)
    print("Upload Complete")
    print("=" * 60)
    print(f"Uploaded : {uploaded}")
    print(f"Skipped  : {skipped}")
    print(f"Failed   : {failed}")


# ==========================================================
# Main
# ==========================================================

def main():

    if len(sys.argv) < 2:
        print("Usage:")
        print("python github_upload.py ME5")
        sys.exit(1)

    upload_folder(sys.argv[1])


if __name__ == "__main__":
    main()