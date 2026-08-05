from pathlib import Path
import os

from inventory_service import load_inventory_rows


class DashboardService:

    IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}

    def __init__(self):

        self.project_root = Path(__file__).parent.parent

        self.inventory = self.project_root / "inventory"
        self.images = self.project_root / "images"
        self.output = self.project_root / "output"
        self.templates = self.project_root / "templates"

    # -----------------------------
    # Inventory
    # -----------------------------

    def inventory_count(self):
        rows = load_inventory_rows(self.inventory / "OPS_Inventory.xlsx")
        return len(rows)

    # -----------------------------
    # Images
    # -----------------------------

    def image_count(self):

        if not self.images.exists():
            return 0

        return sum(
            1
            for path in self.images.rglob("*")
            if path.is_file() and path.suffix.lower() in self.IMAGE_EXTENSIONS
        )

    # -----------------------------
    # CSV Files
    # -----------------------------

    def csv_count(self):

        if not self.output.exists():
            return 0

        return len(list(self.output.glob("*.csv")))

    # -----------------------------
    # Status Checks
    # -----------------------------

    def python_ok(self):

        return True

    def github_ok(self):

        return os.path.exists(".env")

    def templates_ok(self):

        return self.templates.exists()

    def output_ok(self):

        return self.output.exists()

    def images_ok(self):

        return self.images.exists()

    def inventory_ok(self):

        return self.inventory.exists()

    # -----------------------------
    # Dashboard Data
    # -----------------------------

    def get_dashboard_data(self):

        recommendations = self.recommendation_widget()

        return {
            "inventory": self.inventory_count(),
            "images": self.image_count(),
            "csv": self.csv_count(),
            "python": self.python_ok(),
            "github": self.github_ok(),
            "templates": self.templates_ok(),
            "output": self.output_ok(),
            "images_folder": self.images_ok(),
            "inventory_folder": self.inventory_ok(),
            "recommendations": recommendations,
        }

    def recommendation_widget(self):
        return {
            "ready_to_list": 0,
            "missing_images": 0,
            "pricing_issues": 0,
        }