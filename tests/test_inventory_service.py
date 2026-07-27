import tempfile
from pathlib import Path

from openpyxl import Workbook

from inventory_service import load_inventory_rows


def test_load_inventory_rows_reads_expected_rows():
    with tempfile.TemporaryDirectory() as tmp_dir:
        workbook_path = Path(tmp_dir) / "OPS_Inventory.xlsx"

        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Inventory"
        sheet.append([
            "SKU",
            "Card Name",
            "Set",
            "Number",
            "Finish",
            "Rarity",
            "Quantity",
            "Price",
            "Image",
        ])
        sheet.append([
            "ME5-001-N",
            "Bulbasaur",
            "Pitch Black",
            "001",
            "Normal",
            "Common",
            1,
            1.5,
            "me5-001-n.png",
        ])
        workbook.save(workbook_path)

        rows = load_inventory_rows(workbook_path)

        assert len(rows) == 1
        assert rows[0]["sku"] == "ME5-001-N"
        assert rows[0]["card_name"] == "Bulbasaur"
        assert rows[0]["finish"] == "Normal"
        assert rows[0]["price"] == 1.5
