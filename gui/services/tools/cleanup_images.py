from pathlib import Path

IMAGE_ROOT = Path("images")

deleted = 0

for folder in IMAGE_ROOT.iterdir():

    if not folder.is_dir():
        continue

    for normal in folder.glob("*-N.png"):

        duplicate = folder / normal.name.replace("-N.png", ".png")

        if duplicate.exists():

            print(f"Deleting {duplicate.name}")

            duplicate.unlink()

            deleted += 1

print()
print(f"Finished! Deleted {deleted} duplicate images.")