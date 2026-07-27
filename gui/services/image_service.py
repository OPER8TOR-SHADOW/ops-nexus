from pathlib import Path
import os

# Root images directory
IMAGE_ROOT = Path("images")


def get_sets():
    """
    Returns a sorted list of image set folders.
    Example:
        ["ME3", "ME5"]
    """

    if not IMAGE_ROOT.exists():
        return []

    return sorted(
        folder.name
        for folder in IMAGE_ROOT.iterdir()
        if folder.is_dir()
    )


def get_images(set_name):

    folder = IMAGE_ROOT / set_name

    if not folder.exists():
        return []

    return sorted(
        file
        for file in folder.iterdir()
        if file.suffix.lower() in (
            ".png",
            ".jpg",
            ".jpeg",
            ".webp"
        )
    )


def get_image_count(set_name):

    return len(get_images(set_name))


def get_total_image_count():

    total = 0

    for image_set in get_sets():
        total += get_image_count(image_set)

    return total