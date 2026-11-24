"""Static SOURCE-ONLY gate for new joint RO+Paket Pre Produksi and MO release.

Must remain UNINSTALLED until Paket Packing assembly + store DO path is ready
and tested. This script does NOT load Odoo or touch any DB, RO, MO or stock.
"""
from pathlib import Path
import ast
import csv
from xml.etree import ElementTree as ET

root = Path(__file__).resolve().parents[1]
addon = root / "addons/ya_package_store_ro"
files = {
    "models/joint_slot_snapshot.py": [
        "_inherit = \"ya.packing.batch\"",
        "_inherit = \"ya.packing.batch.line\"",
        '_name = "ya.packing.package.demand"',
        '_name = "ya.packing.package.component"',
        "ya_package_ro_ids = fields.Many2many(",
        "ya_package_component_qty = fields.Integer(",
        "ya_kitchen_bom_output = fields.Integer(",
        'def write(self, vals):',
        "ya_package_create_joint_snapshot",
    ],
    "models/joint_slot_preview.py": [
        "def _build_joint_plan(self):",
        "def _plan_digest(self, result, ordinary, packages):",
        "def action_move_to_preproduction(self):",
        "lock_ro_slot(self.env.cr, self.delivery_date, self.slot)",
        "self._plan_digest(result, ordinary, packages) != self.source_digest",
        '"ya_has_package": True',
        '"ya_package_ro_ids": [(6, 0, packages.ids)]',
        '"line_ids": lines',
        '"ya_package_component_qty": item["package_component_qty"]',
        '"ya_kitchen_bom_output": item["bom_output"]',
        'self.env["ya.packing.batch.allocation"]',
        'self.env["ya.packing.package.demand"]',
        'self.env["ya.packing.package.component"]',
        '"packing_batch_id": batch.id',
    ],
    "models/joint_release.py": [
        "_inherit = \"ya.packing.batch.line\"",
        "def action_generate_selected_mo(self, *args, **kwargs):",
        "return super().action_generate_selected_mo(*args, **kwargs)",
        "def _ya_check_joint_sources(self, batch):",
        "def _ya_generate_joint_mos(self, selected, batch, selected_ids):",
        "lock_ro_slot(self.env.cr, batch.delivery_date, batch.slot)",
        '"ya_package_component_qty"',
        "line.ya_kitchen_bom_output",
        '"ya_packing_batch_line_id": line.id',
        "mo.action_confirm()",
        '"state": "production_ok"',
    ],
    "models/packing_preview_route.py": [
        '_inherit = "ya.packing.preview"',
        "if not has_package:",
        "return super().action_move_to_preproduction()",
        "action_ya_package_joint_slot_preview",
    ],
    "views/joint_snapshot_views.xml": [
        "ya_package_demand_ids", "ya_package_component_ids",
        "ya_package_component_qty",
        "ya_store_ro.view_ya_packing_batch_form",
        "ya_store_ro.view_ya_packing_preproduction_line_list",
    ],
    "views/joint_slot_preview_views.xml": [
        "action_move_to_preproduction",
        "source_digest", "accept_shortage",
    ],
    "models/__init__.py": [
        "from . import joint_slot_snapshot",
        "from . import joint_release",
        "from . import packing_preview_route",
        "from . import joint_slot_preview",
    ],
    "__manifest__.py": [
        "'version': '19.0.1.3.0'",
        "'views/joint_snapshot_views.xml'",
    ],
}
errors = []
for rel, must_contain in files.items():
    f = addon / rel
    if not f.is_file():
        errors.append("MISSING: %s" % rel)
        continue
    data = f.read_text(encoding="utf8")
    for token in must_contain:
        if token not in data:
            errors.append("MISSING TOKEN: %s: %s" % (rel, token))
    try:
        if f.suffix == ".py":
            ast.parse(data, filename=str(f))
        elif f.suffix == ".xml":
            ET.parse(f)
    except (SyntaxError, ET.ParseError) as exc:
        errors.append("INVALID SOURCE: %s: %s" % (rel, exc))
    print("SOURCE_CHECK:", rel)

manifest = ast.literal_eval((addon / "__manifest__.py").read_text(encoding="utf8"))
assert "ya_store_ro" in manifest["depends"]
assert "views/joint_snapshot_views.xml" in manifest["data"]
assert "views/joint_slot_preview_views.xml" in manifest["data"]

with (addon / "security/ir.model.access.csv").open(newline="", encoding="utf8") as handle:
    rows = list(csv.DictReader(handle))
for model in ("model_ya_packing_package_demand",
              "model_ya_packing_package_component"):
    matches = [r for r in rows if r.get("model_id:id") == model and
               r.get("group_id:id") == "ya_store_ro.group_ya_packing_admin"]
    if len(matches) != 1:
        errors.append("ACL: missing unique Packing Admin grant for %s" % model)

# No extra production order is invented for a Paket final SKU at this stage.
# Only real kitchen components have a normal kitchen MO; native Paket assembly
# at Packing follows later, after their finished-goods transfer.
release = (addon / "models/joint_release.py").read_text(encoding="utf8")
if 'ya.packing.package.demand"].create' in release:
    errors.append("Release must not fabricate package demand.")
if '"ya_has_package": True' in (
        root / "addons/ya_store_ro/wizard/packing_preview.py"
).read_text(encoding="utf8"):
    errors.append("Existing ordinary RO Preview was changed to joint mode.")

print("ERROR_COUNT:", len(errors))
for issue in errors:
    print("ERROR:", issue)
if errors:
    raise SystemExit(1)
print("PACKAGE_JOINT_PREPRODUCTION_SOURCE_OK")
print("PACKAGE_JOINT_MO_RELEASE_SOURCE_OK")
print("SOURCE_ONLY_NO_DB_CHANGES")
