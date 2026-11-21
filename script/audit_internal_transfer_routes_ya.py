"""Read-only audit: Odoo 19 Routes / Push / Pull / Operation Types.

Target exclusively erp-yussyakmal-mrp-test. This script does not create,
write, unlink or validate anything. It lists actual records and configuration,
not assumptions about which flow is active or operationally ready.
"""
from collections import Counter

EXPECTED_DB = "erp-yussyakmal-mrp-test"
assert env.cr.dbname == EXPECTED_DB, (
    "REFUSED: wrong database " + str(env.cr.dbname)
)
print("DATABASE:", env.cr.dbname)
print("MODE: READ_ONLY_ROUTES_AND_TRANSFER_FLOW")
print("COMPANY:", env.company.name)


def field_info(model, names):
    for n in names:
        f = model._fields.get(n)
        if f:
            print("  FIELD:", n, "| TYPE:", f.type,
                  "| RELATED_MODEL:", getattr(f, "comodel_name", None),
                  "| SELECTION:", (
                      str(f.selection)[:220]
                      if f.type == "selection" else "-"
                  ))
        else:
            print("  FIELD_ABSENT:", n)


def fmt(rec):
    return rec.display_name if rec else "-"


def m2m_names(rec, name, max_items=8):
    if name not in rec._fields:
        return "(field absent)"
    rows = rec[name]
    names = rows[:max_items].mapped("display_name")
    suffix = (" ... +" + str(len(rows)-max_items)) if len(rows) > max_items else ""
    return ", ".join(names) + suffix if rows else "-"


def field_value(rec, name):
    if name not in rec._fields:
        return "(field absent)"
    v = rec[name]
    f = rec._fields[name]
    if f.type == "many2one":
        return fmt(v)
    if f.type in ("many2many", "one2many"):
        return m2m_names(rec, name)
    return str(v)


IMD = env["ir.module.module"].sudo()
for mod_name in ("stock", "stock_account", "mrp", "purchase_stock"):
    m = IMD.search([("name", "=", mod_name)], limit=1)
    print("MODULE:", mod_name, "=", m.state if m else "missing")

Config = env["ir.config_parameter"].sudo()
for key in ("stock.group_stock_multi_locations", "stock.group_adv_location"):
    # Security groups are more reliable than sysparams; see group availability below.
    print("CONFIG_NOTE:", key, "is group configuration, not a route assignment")
for xmlid in ("stock.group_stock_multi_locations", "stock.group_adv_location"):
    obj = env.ref(xmlid, raise_if_not_found=False)
    print("SECURITY_GROUP:", xmlid, "| EXISTS:", bool(obj),
          "| NAME:", fmt(obj))

Route = env["stock.route"] if "stock.route" in env.registry.models else None
Rule = env["stock.rule"] if "stock.rule" in env.registry.models else None
PickType = env["stock.picking.type"] if "stock.picking.type" in env.registry.models else None
Warehouse = env["stock.warehouse"] if "stock.warehouse" in env.registry.models else None
Location = env["stock.location"] if "stock.location" in env.registry.models else None
assert Route is not None and Rule is not None and PickType is not None
Route = Route.sudo().with_context(active_test=False)
Rule = Rule.sudo().with_context(active_test=False)
PickType = PickType.sudo().with_context(active_test=False)
if Warehouse is not None:
    Warehouse = Warehouse.sudo().with_context(active_test=False)
if Location is not None:
    Location = Location.sudo().with_context(active_test=False)

print("\n=== ROUTE FIELD SCHEMA ===")
field_info(Route, (
    "name", "active", "sequence", "company_id", "warehouse_ids",
    "product_selectable", "product_categ_selectable",
    "warehouse_selectable", "packaging_selectable",
    "rule_ids", "supplied_wh_id"
))
print("\n=== STOCK RULE FIELD SCHEMA ===")
field_info(Rule, (
    "name", "active", "route_id", "action", "location_src_id",
    "location_dest_id", "picking_type_id", "warehouse_id",
    "procure_method", "auto", "group_propagation_option",
    "propagate_cancel", "sequence"
))
print("\n=== OPERATION TYPE FIELD SCHEMA ===")
field_info(PickType, (
    "name", "code", "active", "warehouse_id", "default_location_src_id",
    "default_location_dest_id", "sequence_code", "create_backorder",
    "show_operations", "show_reserved", "barcode"
))

routes = Route.search([], order="id")
rules = Rule.search([], order="id")
types = PickType.search([], order="id")
print("\nROUTE_TOTAL:", len(routes))
print("ROUTE_ACTIVE:", len(routes.filtered(lambda r: r.active)) if "active" in Route._fields else "unknown")
for r in routes:
    print("ROUTE:", r.id, "|", r.name,
          "| ACTIVE:", field_value(r, "active"),
          "| COMPANY:", field_value(r, "company_id"),
          "| WAREHOUSES:", m2m_names(r, "warehouse_ids"),
          "| PRODUCT_SELECTABLE:", field_value(r, "product_selectable"),
          "| CATEGORY_SELECTABLE:", field_value(r, "product_categ_selectable"),
          "| WAREHOUSE_SELECTABLE:", field_value(r, "warehouse_selectable"),
          "| RULES:", len(r.rule_ids) if "rule_ids" in r._fields else "(absent)")

print("\nSTOCK_RULE_TOTAL:", len(rules))
if "action" in Rule._fields:
    print("STOCK_RULE_ACTION_COUNTS:", dict(Counter(rules.mapped("action"))))
for rule in rules:
    print("RULE:", rule.id, "|", rule.name,
          "| ACTIVE:", field_value(rule, "active"),
          "| ACTION:", field_value(rule, "action"),
          "| ROUTE:", field_value(rule, "route_id"),
          "| SOURCE:", field_value(rule, "location_src_id"),
          "| DESTINATION:", field_value(rule, "location_dest_id"),
          "| PICKING_TYPE:", field_value(rule, "picking_type_id"),
          "| WAREHOUSE:", field_value(rule, "warehouse_id"),
          "| PROCUREMENT:", field_value(rule, "procure_method"),
          "| AUTO:", field_value(rule, "auto"))

print("\nOPERATION_TYPE_TOTAL:", len(types))
if "code" in PickType._fields:
    print("OPERATION_TYPE_CODE_COUNTS:", dict(Counter(types.mapped("code"))))
for typ in types:
    print("PICKING_TYPE:", typ.id, "|", typ.name,
          "| CODE:", field_value(typ, "code"),
          "| ACTIVE:", field_value(typ, "active"),
          "| WAREHOUSE:", field_value(typ, "warehouse_id"),
          "| SOURCE_DEFAULT:", field_value(typ, "default_location_src_id"),
          "| DEST_DEFAULT:", field_value(typ, "default_location_dest_id"),
          "| BACKORDER:", field_value(typ, "create_backorder"))

if Warehouse is not None:
    print("\nWAREHOUSE_TOTAL:", Warehouse.search_count([]))
    print("WAREHOUSE_FIELDS_PRESENT:",
          ",".join(n for n in (
              "lot_stock_id", "int_type_id", "reception_steps",
              "delivery_steps", "resupply_wh_ids"
          ) if n in Warehouse._fields))
    for wh in Warehouse.search([], order="id"):
        print("WAREHOUSE:", wh.id, wh.name,
              "| STOCK:", field_value(wh, "lot_stock_id"),
              "| INTERNAL_TYPE:", field_value(wh, "int_type_id"),
              "| RECEPTION_STEPS:", field_value(wh, "reception_steps"),
              "| DELIVERY_STEPS:", field_value(wh, "delivery_steps"),
              "| RESUPPLY_WH:", m2m_names(wh, "resupply_wh_ids"))

if Location is not None:
    print("\nTRANSIT_LOCATIONS:")
    for loc in Location.search([("usage", "=", "transit")], order="id"):
        print("TRANSIT:", loc.id, "|", loc.complete_name,
              "| ACTIVE:", field_value(loc, "active"),
              "| COMPANY:", field_value(loc, "company_id"))

print("\nINTERPRETATION:")
print("Existing stock.rule records indicate configured route rules; this audit")
print("does NOT prove automatic triggering, two-step receipt, or stock movement.")
print("OPERATION TYPE is a document type; it is not by itself proof of")
print("a push/pull rule or an approved business policy.")
print("ROUTES_TRANSFER_READ_ONLY_AUDIT_OK")
