"""Local source-only preflight for YA finished product -> Packing addon."""
from pathlib import Path
import ast
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
addon = ROOT / "addons" / "ya_finished_packing_transfer"
model = addon / "models" / "finished_packing.py"
manifest = addon / "__manifest__.py"
view = addon / "views" / "finished_packing_views.xml"
for name in [addon / "__init__.py", addon / "models" / "__init__.py",
             model, manifest, view]:
    assert name.is_file(), f"Missing: {name}"

code = model.read_text(encoding="utf-8")
ast.parse(code)
data = ast.literal_eval(manifest.read_text(encoding="utf-8"))
assert data["depends"] == ["ya_store_ro", "mrp", "stock"]
assert "erp-yussyakmal-mrp-test" in code
assert "SELECT id FROM ya_packing_batch WHERE id = %s FOR UPDATE" in code
assert 'ya_fg_batch_id' in code and 'ya_fg_kitchen_id' in code
assert '"done"' in code and '"cancel"' in code
assert "m.quantity" in code and "mo.product_id.uom_id" in code
assert "button_validate()" in code
assert 'get_param(' in code and '"11076"' in code
tree = ET.parse(view)
buttons = tree.findall(".//button")
assert {b.attrib.get("name") for b in buttons} == {
    "action_ya_fg_move_to_packing", "action_ya_fg_open_transfers"
}
print("FINISHED_PACKING_SOURCE_CHECK_OK")
