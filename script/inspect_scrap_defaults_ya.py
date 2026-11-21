"""Read-only follow-up: inspect Odoo19 Scrap defaults and virtual locations.

No assumptions about stock.location.scrap_location existing.
No records created, no changes to DB.
"""
assert env.cr.dbname == "erp-yussyakmal-mrp-test", "Wrong database"
S = env["stock.scrap"].sudo()
Loc = env["stock.location"].sudo().with_context(active_test=False)
print("DATABASE:", env.cr.dbname, "MODE: READ_ONLY")
print("STOCK_SCRAP_FIELDS:")
for key in sorted(S._fields):
    if any(part in key for part in ("location", "reason", "note", "origin", "production", "company", "move", "state")):
        f = S._fields[key]
        print("  FIELD:", key, "TYPE:", f.type, "RELATED:", getattr(f, "related", None))
print("SCRAP_DEFAULT_GET:")
try:
    defaults = S.default_get([
        name for name in ("location_id", "scrap_location_id",
                         "company_id", "product_uom_id", "state")
        if name in S._fields
    ])
    print("  DEFAULTS:", defaults)
    if defaults.get("scrap_location_id"):
        dest = Loc.browse(defaults["scrap_location_id"])
        print("  SCRAP_DEFAULT_DEST:", dest.id, dest.complete_name,
              "| USAGE:", dest.usage, "| ACTIVE:", dest.active)
except Exception as exc:
    print("  DEFAULT_GET_ERROR:", type(exc).__name__, str(exc))
print("SCRAP_DEST_FIELD:")
if "scrap_location_id" in S._fields:
    f = S._fields["scrap_location_id"]
    print("  DOMAIN:", repr(getattr(f, "domain", None)))
    print("  DEFAULT:", repr(getattr(f, "default", None)))
print("VIRTUAL_LOCATIONS:")
for loc in Loc.search([("usage", "in", ["inventory", "production", "transit"])], order="usage,complete_name"):
    print("  LOCATION:", loc.id, "|", loc.complete_name,
          "| USAGE:", loc.usage, "| ACTIVE:", loc.active,
          "| COMPANY:", loc.company_id.name or "Shared")
print("SCRAP_LOCATION_XMLIDS:")
imodel = env["ir.model.data"].sudo()
for xid in imodel.search([
    ("model", "=", "stock.location"),
    ("name", "ilike", "scrap")
]):
    print("  XMLID:", f"{xid.module}.{xid.name}", "| RES_ID:", xid.res_id,
          "| EXISTS:", bool(Loc.browse(xid.res_id).exists()))
print("SCRAP_MODEL_METHODS:")
for name in ("action_validate", "action_get_stock_move_lines", "_prepare_move_values",
             "_prepare_move_vals", "_get_scrap_location_id"):
    print("  METHOD:", name, "EXISTS:", callable(getattr(S, name, None)))
print("INVENTORY_ADJUSTMENT_MODEL_METHODS:")
Q = env["stock.quant"].sudo()
for name in ("action_apply_inventory", "_apply_inventory", "_get_inventory_move_values"):
    print("  METHOD:", name, "EXISTS:", callable(getattr(Q, name, None)))
print("FINISHED_MO_METHODS:")
M = env["mrp.production"].sudo()
for name in ("button_mark_done", "_post_inventory", "_get_move_finished_values"):
    print("  METHOD:", name, "EXISTS:", callable(getattr(M, name, None)))
print("SCRAP_LOCATION_FOLLOWUP_OK: no database changes")
