import subprocess
import sys
from pathlib import Path

from progress import Progress

ROOT = Path(__file__).resolve().parent


def run_step(name, script, progress, selected_set):
    Progress.update(progress, name)

    print("\n" + "=" * 60)
    print(name)
    print("=" * 60)

    command = [
        sys.executable,
        str(ROOT / script),
        selected_set,
    ]

    print("Running:", " ".join(command))
    print()

    result = subprocess.run(
        command,
        cwd=ROOT,
    )

    if result.returncode != 0:
        print(f"\nERROR: {name} failed.")
        sys.exit(result.returncode)

    print(f"\n{name} complete.")


def run_build(selected_set):
    print("=" * 60)
    print("OPS Nexus")
    print("=" * 60)
    print(f"Selected Set: {selected_set}")

    Progress.update(0, "Starting Build")

    run_step(
        "Downloading Pokémon Images",
        "image_downloader.py",
        10,
        selected_set,
    )

    run_step(
        "Uploading Images to GitHub",
        "github_upload.py",
        45,
        selected_set,
    )

    run_step(
        "Generating eBay CSV",
        "ebay_variation_exporter.py",
        80,
        selected_set,
    )

    Progress.update(100, "Build Complete")

    print("\n" + "=" * 60)
    print("BUILD COMPLETE!")
    print("=" * 60)


def main():
    if len(sys.argv) != 2:
        print("Usage:")
        print("python build_listing.py ME5")
        sys.exit(1)

    run_build(sys.argv[1].upper())


if __name__ == "__main__":
    main()