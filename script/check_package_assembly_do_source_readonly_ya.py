"""SOURCE ONLY gate: PCK native Paket MOs, merged store DO and known routes.

Does not import Odoo, upgrade modules, or write database/stock/MOs.
Must pass BEFORE suggesting any install/upgrade in test database.
"""
from pathlib import Path
import ast
from xml.etree import ElementTree as ET

root = Path(__file__).resolve().parents[1]
addon = root / "addons/ya_package_store_ro"
file_tokens = {
    "models/package_assembly.py": [
        "_inherit = \"mrp.production\"",
        "ya_package_assembly_batch_id = fields.Many2one(",
        "UNIQUE(ya_package_assembly_batch_id, product_id)",
        "def action_ya_create_package_assembly_mos(self):",
        "if self.ya_package_assembly_mo_ids:",
        '("code", "=", "mrp_operation")',
        '("warehouse_id", "=", warehouse.id)',
        '"location_src_id": stock_location.id',
        '"location_dest_id": stock_location.id',
        "mo.action_confirm()",
        "if mo.state in",
        "if not mo.move_raw_ids:",
        "if \"workorder_ids\" in mo._fields and mo.workorder_ids:",
        "if self.env.cr.dbname != TEST_DB:",
    ],
    "models/package_delivery.py": [
        "_inherit = \"ya.packing.batch\"",
        "def action_ya_generate_store_do(self):",
        "if not self.ya_has_package:",
        "return super().action_ya_generate_store_do()",
        "mo.move_finished_ids.filtered(",
        'if mo.state != "done":',
        '("code", "=", "PCK")',
        'result = super().action_ya_generate_store_do()',
        '"ya_store_batch_id": self.id',
        '"ya_store_warehouse_id": store.id',
        '"ya_store_stage": "dispatch"',
        '"location_id": Packing.lot_stock_id.id',
        '"location_dest_id": Transit.id',
        "new_moves._action_confirm()",
        "return self.action_ya_open_store_deliveries()",
    ],
    "models/__init__.py": [
        "from . import package_assembly",
        "from . import package_delivery",
    ],
    "views/joint_snapshot_views.xml": [
        "action_ya_create_package_assembly_mos",
        "action_ya_open_package_assembly_mos",
        "ya_package_assembly_mo_ids",
        "ya_package_assembly_mo_count",
        "ya_package_demand_ids",
    ],
    "__manifest__.py": [
        "'version': '19.0.1.3.0'",
        "'ya_finished_packing_transfer'",
        "'ya_packing_store_delivery'",
    ],
}
errors = []
for rel, required in file_tokens.items():
    path = addon / rel
    if not path.is_file():
        errors.append("MISSING FILE: " + rel)
        continue
    src = path.read_text(encoding="utf8")
    for token in required:
        if token not in src:
            errors.append("MISSING TOKEN: " + rel + " :: " + token)
    try:
        if path.suffix == ".py":
            ast.parse(src, filename=str(path))
        if path.suffix == ".xml":
            ET.parse(path)
    except (SyntaxError, ET.ParseError) as exc:
        errors.append("PARSE ERROR: %s: %s" % (rel, exc))
    print("SOURCE:", rel)

for rel in ("script/audit_pck_package_manufacturing_route_readonly_ya.py",):
    if not (root / rel).is_file():
        errors.append("Missing read-only master route audit: " + rel)

# Check original, proven SO-independent Packing FG / DO implementations
# remain available and are not mutated as part of the new source stage.
fg = (root / "addons/ya_finished_packing_transfer/models/finished_packing.py")
delivery = (root / "addons/ya_packing_store_delivery/models/store_delivery.py")
for p, must in (
    (fg, "def action_ya_fg_move_to_packing(self):"),
    (delivery, "def action_ya_generate_store_do(self):"),
):
    if not p.exists() or must not in p.read_text(encoding="utf8"):
        errors.append("Missing existing native operation: " + str(p))
if "button_validate()" in (
        addon / "models/package_delivery.py"
).read_text(encoding="utf8"):
    errors.append("New Paket DO method must not auto-validate/ship.")

print("ERROR_COUNT:", len(errors))
for error in errors:
    print("ERROR:", error)
if errors:
    raise SystemExit(1)
print("PACKAGE_ASSEMBLY_PCK_SOURCE_OK")
print("PACKAGE_DO_MERGE_SOURCE_OK")
print("SOURCE_ONLY_NO_DB_CHANGES")
