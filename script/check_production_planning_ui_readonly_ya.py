"""Read-only diagnostic of active YA Production Planning UI and deployed addon.
Run via Odoo shell on erp-yussyakmal-mrp-test, --no-http.
Never writes, upgrades, commits, or mutates records.
"""
from pathlib import Path
import hashlib

EXPECTED = "erp-yussyakmal-mrp-test"
assert env.cr.dbname == EXPECTED, "STOP: unexpected database"
print("DATABASE:", env.cr.dbname)
print("MODE: READ_ONLY_PLANNING_UI_DIAGNOSTIC")
addon = Path("/opt/odoo19/custom-addons/ya_production_planning")
for relative in ("models/planning.py", "views/planning_views.xml",
                 "security/ir.model.access.csv"):
    path = addon / relative
    print("DEPLOYED_FILE:", relative, "EXISTS:", path.is_file())
    if path.is_file():
        raw = path.read_bytes()
        print("SHA256:", hashlib.sha256(raw).hexdigest())
        if relative.endswith(".xml"):
            print("DEPLOYED_XML_EDITABLE:", b'editable="bottom"' in raw)
            print("DEPLOYED_XML_LINE_ROW:", b'name="line_row"' in raw)
            print("DEPLOYED_XML_SOURCE_ROW_COLUMN:", b'<field name="source_row"' in raw)
        if relative.endswith("planning.py"):
            print("DEPLOYED_PY_REC_NAME:", b"_rec_name = 'name'" in raw)
            print("DEPLOYED_PY_LINE_ROW:", b'def _compute_line_row' in raw)

module = env["ir.module.module"].sudo().search([("name", "=", "ya_production_planning")], limit=1)
print("MODULE_STATE:", module.state if module else "NOT FOUND")
for model_name in ("ya.production.planning", "ya.production.planning.line"):
    model = env[model_name]
    print("MODEL:", model_name, "REC_NAME:", model._rec_name)
    print("FIELD_name:", "name" in model._fields)
    print("FIELD_line_row:", "line_row" in model._fields)

for xmlid in ("ya_production_planning.view_ya_production_planning_form",
              "ya_production_planning.action_ya_production_planning"):
    record = env.ref(xmlid, raise_if_not_found=False)
    print("XML_ID:", xmlid, "FOUND:", bool(record))
    if not record:
        continue
    if record._name == "ir.ui.view":
        arch = record.arch_db or ""
        print("DB_VIEW_ID:", record.id)
        print("DB_VIEW_EDITABLE:", 'editable="bottom"' in arch)
        print("DB_VIEW_LINE_ROW:", 'name="line_row"' in arch)
        print("DB_VIEW_SOURCE_ROW_COLUMN:", '<field name="source_row"' in arch)
        print("DB_VIEW_PARENT:", record.inherit_id.id)
    elif record._name == "ir.actions.act_window":
        print("ACTION_NAME:", record.name, "RES_MODEL:", record.res_model,
              "VIEW_MODE:", record.view_mode)

plans = env["ya.production.planning"].sudo().search([], limit=5, order="id desc")
for plan in plans:
    print("PLAN_SAMPLE:", plan.id, plan.display_name, plan.state,
          plan.delivery_date, plan.slot, plan.kitchen_code, len(plan.line_ids))
print("READ_ONLY_PLANNING_UI_DIAGNOSTIC_OK")
