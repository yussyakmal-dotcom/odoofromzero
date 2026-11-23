"""Source-only check of grouped YA Production Capacity menu declarations."""
from pathlib import Path
from ast import literal_eval
import xml.etree.ElementTree as ET

root = Path(__file__).resolve().parents[1]
addon = root / "addons/ya_workflow_navigation"
m = literal_eval((addon / "__manifest__.py").read_text())
assert set(m["depends"]) == {
    "ya_production_planning", "ya_store_ro",
    "ya_material_requirement", "ya_finished_packing_transfer",
}
tree = ET.parse(addon / "views/workflow_navigation_menus.xml")
root_element = tree.getroot()
menu_names = [x.attrib.get("name") for x in root_element.findall("menuitem")]
assert all(x in menu_names for x in (
    "SEBELUM PRODUKSI", "PROSES PRODUKSI", "SESUDAH PRODUKSI",
    "MO Produksi"))
records = {e.attrib["id"]: e for e in root_element.findall("record")}
for key in ("ya_store_ro.menu_ya_packing_preview",
            "ya_store_ro.menu_ya_packing_qty_correction",
            "ya_store_ro.menu_ya_packing_preproduction",
            "ya_material_requirement.menu_ya_material_requirement",
            "ya_finished_packing_transfer.ya_fg_packing_batch_menu"):
    assert key in records, key
assert "ya_store_ro.menu_ya_packing_batch" not in records
print("YA_WORKFLOW_NAVIGATION_SOURCE_OK")
