"""Source-only checks: YA Packing -> DO -> Transit -> Store Receipt."""
from pathlib import Path
import ast
import xml.etree.ElementTree as ET

root = Path(__file__).resolve().parents[1]
addon = root / "addons" / "ya_packing_store_delivery"
manifest = ast.literal_eval((addon / "__manifest__.py").read_text())
assert "ya_workflow_navigation" in manifest["depends"]
code = (addon / "models" / "store_delivery.py").read_text()
ast.parse(code)
for term in (
    "erp-yussyakmal-mrp-test",
    "ya_store_batch_id",
    "ya_store_stage",
    "SELECT id FROM ya_packing_batch WHERE id = %s FOR UPDATE",
    "action_ya_generate_store_do",
    "ya_store_delivery_ids",
    "Inter-warehouse transit",
    "stock.picking",
    "button_validate",
    "_action_done",
    '"receipt"',
    "ya_do_not_shipped_reason",
    "_ya_cancel_zero_qty_dispatch_moves",
    "move._action_cancel()",
    "description_picking",
    "Catatan: %s",
    "_onchange_ya_do_not_shipped_reason",
):
    assert term in code, term
xml = ET.parse(addon / "views" / "store_delivery_views.xml")
names = {b.attrib.get("name") for b in xml.findall(".//button")}
assert "action_ya_generate_store_do" in names
assert "action_ya_open_store_deliveries" in names
assert any(e.attrib.get("name") == "DO Toko"
           for e in xml.findall(".//menuitem"))
assert "SKU Tidak Dikirim / Catatan DO" in (addon / "views" / "store_delivery_views.xml").read_text()
assert "stock.view_picking_form" in (addon / "views" / "store_delivery_views.xml").read_text()
assert "report/store_picking_list.xml" not in manifest["data"]
assert 'stock.action_report_picking' in code
assert "action_ya_print_store_picking_list" in code
assert "Cetak Picking List" in (addon / "views" / "store_delivery_views.xml").read_text()
print("YA_PACKING_STORE_DELIVERY_SOURCE_OK")
