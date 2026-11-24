"""Static preflight for NEW, UNINSTALLED RO Paket joint preview addon.

Run as feri: python3 script/check_package_joint_preview_source_readonly_ya.py
No Odoo import/DB transactions, RO, MO, stock, transfers or GL changes.
"""
import ast
import csv
from pathlib import Path
from xml.etree import ElementTree as ET

root = Path(__file__).resolve().parents[1]
addon = root / "addons/ya_package_store_ro"
rules = addon / "models/joint_slot_rules.py"
orm = addon / "models/joint_slot_preview.py"
view = addon / "views/joint_slot_preview_views.xml"
manifest_path = addon / "__manifest__.py"
acl = addon / "security/ir.model.access.csv"
init = addon / "models/__init__.py"
tests = root / "script/test_package_joint_slot_pure_ya.py"
errors = []
for p in (rules, orm, view, manifest_path, acl, init, tests):
    if not p.is_file():
        errors.append("Missing: " + str(p))
        continue
    if p.suffix == ".py":
        try:
            ast.parse(p.read_text(encoding="utf-8"), filename=str(p))
        except SyntaxError as exc:
            errors.append("Python error: %s %s" % (p, exc))
    if p.suffix == ".xml":
        try:
            ET.parse(p)
        except ET.ParseError as exc:
            errors.append("XML error: %s %s" % (p, exc))
    print("SOURCE:", str(p.relative_to(root)))
manifest = ast.literal_eval(manifest_path.read_text(encoding="utf8"))
assert "ya_store_ro" in manifest["depends"]
assert "views/joint_slot_preview_views.xml" in manifest["data"]
assert manifest["version"] == "19.0.1.1.0"

model_text = orm.read_text(encoding="utf8")
for token in (
    "_name = \"ya.package.joint.slot.preview\"",
    '("state", "=", "confirmed")',
    '("state", "=", "published")',
    "bom_line.product_uom_id._compute_quantity(",
    "plan_joint_slot(",
    "plan_kitchen_capacity_with_package_priority",
    '"source_kind": kind',
    '"qty_per_package": qty_per_package',
    "if len(candidates) == 1:",
):
    if token not in model_text:
        errors.append("MISSING LOGIC TOKEN: " + token)

view_text = view.read_text(encoding="utf8")
for token in (
    "menu_ya_package_joint_slot_preview",
    "groups=\"ya_store_ro.group_ya_packing_admin\"",
    "action_preview",
    "name=\"pending_internal_transfer\"",
):
    if token not in view_text:
        errors.append("MISSING VIEW TOKEN: " + token)
if "from . import joint_slot_preview" not in init.read_text(encoding="utf8"):
    errors.append("Joint preview model not imported")

with acl.open(newline="", encoding="utf8") as f:
    csv_rows = list(csv.DictReader(f))
if not any(
    row.get("model_id:id") == "model_ya_package_joint_slot_preview"
    and row.get("group_id:id") == "ya_store_ro.group_ya_packing_admin"
    and row.get("perm_read") == "1"
    for row in csv_rows
):
    errors.append("Missing Packing Admin ACL")

regular_preview = (root / "addons/ya_store_ro/wizard/packing_preview.py").read_text(encoding="utf8")
if "def action_move_to_preproduction" not in regular_preview:
    errors.append("Missing existing ordinary RO Pre Produksi flow")
print("ERROR_COUNT:", len(errors))
for err in errors:
    print("ERROR:", err)
if errors:
    raise SystemExit(1)
print("PACKAGE_JOINT_PREVIEW_SOURCE_OK")
print("UNINSTALLED_ONLY: not a test of an Odoo joint Pre Produksi snapshot")
