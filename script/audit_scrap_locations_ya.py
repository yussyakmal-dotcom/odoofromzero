"""READ-ONLY: Inspect actual Scrap destination locations and warehouses.

Database: erp-yussyakmal-mrp-test only. No create/write/commit.
Report all locations marked scrap_location, all inventory-loss locations,
warehouses and scrap destination defaults.
"""
assert env.cr.dbname == "erp-yussyakmal-mrp-test", "Wrong database"
Loc = env["stock.location"].sudo().with_context(active_test=False)
Wh = env["stock.warehouse"].sudo().with_context(active_test=False)
Scrap = env["stock.scrap"].sudo().with_context(active_test=False)
loc_fields = Loc._fields
print("DATABASE:", env.cr.dbname)
print("MODE: READ_ONLY")
print("LOCATION_HAS_SCRAP_FLAG:", "scrap_location" in loc_fields)
scrap_locations = Loc.search([("scrap_location", "=", True)]) if "scrap_location" in loc_fields else Loc.browse()
loss_locations = Loc.search([("usage", "=", "inventory")])
print("SCRAP_FLAGGED_LOCATION_COUNT:", len(scrap_locations))
for loc in scrap_locations.sorted(key=lambda rec: rec.complete_name or rec.name):
    print("SCRAP_LOCATION:", loc.id, "|", loc.complete_name,
          "| USAGE:", loc.usage, "| ACTIVE:", loc.active,
          "| COMPANY:", loc.company_id.name or "Shared",
          "| PARENT:", loc.location_id.complete_name or "(root)")
print("INVENTORY_LOSS_LOCATION_COUNT:", len(loss_locations))
for loc in loss_locations.sorted(key=lambda rec: rec.complete_name or rec.name):
    flag = loc.scrap_location if "scrap_location" in loc_fields else "NOT_SUPPORTED"
    print("LOSS_LOCATION:", loc.id, "|", loc.complete_name,
          "| SCRAP_FLAG:", flag, "| ACTIVE:", loc.active)
warehouses = Wh.search([])
print("WAREHOUSE_COUNT:", len(warehouses))
for wh in warehouses.sorted(key=lambda rec: rec.code or rec.name):
    print("WAREHOUSE:", wh.code, "|", wh.name,
          "| MAIN_STOCK:", wh.lot_stock_id.complete_name,
          "| COMPANY:", wh.company_id.name)
print("SCRAP_RECORD_COUNT:", Scrap.search_count([]))
print("SCRAP_MODEL_DEST_FIELD:", "scrap_location_id" in Scrap._fields)
if "scrap_location_id" in Scrap._fields:
    field = Scrap._fields["scrap_location_id"]
    print("SCRAP_DEST_FIELD_DEFAULT:", repr(field.default))
    print("SCRAP_DEST_FIELD_DOMAIN:", repr(field.domain))
print("SCRAP_DESTINATION_AUDIT_OK: no changes")
