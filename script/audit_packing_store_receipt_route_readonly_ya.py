"""READ ONLY — verify two-stage Packing dispatch -> store receipt routing.

ERP project: ODOO FROM ZERO. Database whitelist only.
Does NOT create/modify stock, routes, warehouses, locations, or pickings.
Purpose: avoid recognizing store inventory before receiving confirmation.
"""
from collections import Counter

assert env.cr.dbname == "erp-yussyakmal-mrp-test", "REFUSED: wrong database"
print("DATABASE:", env.cr.dbname)
print("MODE: READ_ONLY_PACKING_TO_STORE_RECEIPT_ROUTE")

Warehouse = env["stock.warehouse"].sudo()
Location = env["stock.location"].sudo()
PickingType = env["stock.picking.type"].sudo()
Route = env["stock.route"].sudo()
Rule = env["stock.rule"].sudo()
pck = Warehouse.search([("code", "=", "PCK")])
assert len(pck) == 1 and pck.lot_stock_id
print("PACKING_WAREHOUSE:", pck.code, pck.lot_stock_id.complete_name,
      "| DELIVERY_STEPS:", pck.delivery_steps,
      "| RECEPTION_STEPS:", pck.reception_steps)

print("\nTRANSIT_LOCATIONS:")
transits = Location.search([("usage", "=", "transit")])
print("TRANSIT_COUNT:", len(transits))
for loc in transits:
    print("TRANSIT:", loc.id, loc.complete_name,
          "| COMPANY:", loc.company_id.name if loc.company_id else "(shared)",
          "| ACTIVE:", loc.active)

print("\nSTORE_WAREHOUSES:")
Store = Warehouse.search([("code", "in", ["T_MET", "T_KD", "T_SD"])])
for wh in Store.sorted("code"):
    print("STORE:", wh.code, wh.name,
          "| STOCK:", wh.lot_stock_id.complete_name,
          "| RECEPTION_STEPS:", wh.reception_steps,
          "| DELIVERY_STEPS:", wh.delivery_steps,
          "| INTERNAL_TYPE:", wh.int_type_id.id if wh.int_type_id else None,
          "| INCOMING_TYPE:", wh.in_type_id.id if wh.in_type_id else None,
          "| COMPANY:", wh.company_id.name)

print("\nRELEVANT_PICKING_TYPES:")
types = PickingType.search([
    ("warehouse_id", "in", (pck | Store).ids),
])
for t in types.sorted(lambda x: (x.warehouse_id.code or "", x.code or "", x.id)):
    print("PICKING_TYPE:", t.id, t.name,
          "| CODE:", t.code,
          "| WAREHOUSE:", t.warehouse_id.code,
          "| SRC:", t.default_location_src_id.complete_name or "-",
          "| DEST:", t.default_location_dest_id.complete_name or "-",
          "| BACKORDER:", t.create_backorder,
          "| COMPANY:", t.company_id.name if t.company_id else "-")

print("\nINTERWAREHOUSE_ROUTE_RULES:")
warehouses = (pck | Store)
locations = warehouses.mapped("lot_stock_id") | transits
rules = Rule.search([])
matched = 0
for r in rules:
    src = r.location_src_id
    dest = r.location_dest_id
    if (src in locations or dest in locations or
        r.warehouse_id in warehouses or
        r.picking_type_id.warehouse_id in warehouses):
        matched += 1
        print("RULE:", r.id, r.route_id.name,
              "| ACTION:", r.action,
              "| SRC:", src.complete_name or "-",
              "| DEST:", dest.complete_name or "-",
              "| PICKING_TYPE:", r.picking_type_id.name,
              "| AUTO:", r.auto if "auto" in r._fields else "(absent)")
print("MATCHED_RULE_COUNT:", matched)

print("\nINTERPRETATION:")
print("ONE_STEP receipt warehouse settings do not prove store-accepted")
print("receipt; direct internal stock move to store location would book")
print("stock there immediately. DO and receipt must be two distinct")
print("accounting/stock validation moments if acceptance occurs later.")
print("READ_ONLY_PACKING_STORE_RECEIPT_ROUTE_OK")
