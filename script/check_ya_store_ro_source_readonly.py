"""READ-ONLY static preflight for YA Store RO phase 1.

Run as Feri:
    cd ~/odoofromzero
    python3 script/check_ya_store_ro_source_readonly.py

No Odoo import, server connections or database changes.
"""
import ast
import pathlib
import xml.etree.ElementTree as ET

root = pathlib.Path(__file__).resolve().parents[1]
addon = root / "addons" / "ya_store_ro"
required = [
    "__init__.py", "__manifest__.py",
    "models/__init__.py", "models/store_ro.py", "models/allocation_rules.py", "models/date_labels.py",
    "wizard/__init__.py", "wizard/ro_template_wizard.py",
    "wizard/ro_import.py", "wizard/packing_preview.py",
    "wizard/packing_correction.py", "security/packing_groups.xml",
    "security/ir.model.access.csv",
    "views/ro_template_wizard_views.xml", "views/ro_import_wizard_views.xml",
    "views/ro_documents_views.xml", "views/packing_preview_views.xml",
    "views/packing_correction_views.xml",
]
errors = []
for relative in required:
    file = addon / relative
    if not file.is_file():
        errors.append("MISSING: " + str(file))
        continue
    print("FOUND:", relative, file.stat().st_size, "bytes")
    if file.suffix == ".py":
        try:
            ast.parse(file.read_text(encoding="utf-8"), filename=str(file))
        except SyntaxError as exc:
            errors.append("PYTHON_SYNTAX_ERROR: " + str(exc))
    if file.suffix == ".xml":
        try:
            ET.parse(file)
        except ET.ParseError as exc:
            errors.append("XML_PARSE_ERROR: " + str(exc))
manifest = addon / "__manifest__.py"
if manifest.is_file():
    data = ast.literal_eval(manifest.read_text(encoding="utf-8"))
    print("MANIFEST_VERSION:", data.get("version"))
    print("MANIFEST_DEPENDS:", data.get("depends"))
    if "ya_production_planning" not in data.get("depends", []):
        errors.append("MISSING_PLAN_DEPENDENCY")
wizard_file = addon / "wizard/ro_template_wizard.py"
if wizard_file.is_file():
    text = wizard_file.read_text(encoding="utf-8")
    for token in ("state != 'published'", "r.max_capacity > 0",
                  "Qty Pesan", "Workbook()", "YA_STORE_RO_V1"):
        if token not in text:
            errors.append("MISSING_SAFETY_RULE: " + token)
packing_file = addon / "wizard/packing_preview.py"
if packing_file.is_file():
    packing = packing_file.read_text(encoding="utf-8")
    required_tokens = (
        "('delivery_date', '=', delivery_date)",
        "('slot', '=', self.slot)",
        "('state', '=', 'confirmed')",
        "group = (plan.id, order_line.product_id.id)",
        "allocate_surplus_prorata(requests, int(batch))",
    )
    for token in required_tokens:
        if token not in packing:
            errors.append("PACKING_CONFIRMED_RO_GROUPING_MISSING: " + token)
    if "planning_id = fields.Many2one(\n        'ya.production.planning', string='Published Planning'" in packing:
        errors.append("PACKING_WRONG_ENTRYPOINT_PLANNING_PICKER")
view = addon / "views/packing_preview_views.xml"
if view.is_file():
    view_text = view.read_text(encoding="utf-8")
    if '<field name="delivery_date_yyyymmdd"' not in view_text or '<field name="slot"' not in view_text:
        errors.append("PACKING_DATE_SLOT_PICKER_MISSING")
# Date display must be YYYY-Mon-DD, e.g. 2026-Nov-22.
for relative, required_tokens in {
    "models/store_ro.py": ("delivery_date_yyyymmdd", "ro_date_yyyymmdd", "format_ymondd"),
    "wizard/packing_preview.py": ("delivery_date_yyyymmdd", "ro_date_yyyymmdd", "parse_ymondd("),
    "views/ro_documents_views.xml": ('name="delivery_date_yyyymmdd"', 'name="ro_date_yyyymmdd"'),
    "views/packing_preview_views.xml": ('name="delivery_date_yyyymmdd"', 'name="ro_date_yyyymmdd"'),
}.items():
    body = (addon / relative).read_text(encoding="utf-8")
    for token in required_tokens:
        if token not in body:
            errors.append("YYYY_MON_DD_DISPLAY_MISSING: " + relative + ": " + token)
print("ERROR_COUNT:", len(errors))
for issue in errors:
    print(issue)
if errors:
    raise SystemExit(1)
print("RO_TEMPLATE_SOURCE_PREFLIGHT_OK")
