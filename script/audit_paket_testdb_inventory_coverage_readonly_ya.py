"""READ-ONLY: do missing kitchen materials exist elsewhere in TEST inventory?

Do not treat empty quant records in test DB as proof physical warehouse stock
is missing. Show aggregate internal stock and exact locations of the actual
22 kitchen raw component rows for 12114 Hampers EID SET D.

Run ONLY in Odoo shell, db erp-yussyakmal-mrp-test.
No writes, no quants created, no master data or reservations changed.
"""
from collections import defaultdict

assert env.cr.dbname == "erp-yussyakmal-mrp-test", "REFUSED: WRONG DB"
print("DATABASE:", env.cr.dbname)
print("MODE: READ_ONLY_PAKET_TESTDB_INVENTORY_COVERAGE")
Quant = env["stock.quant"].sudo()
Products = env["product.product"].sudo()
Plans = env["ya.production.planning"].sudo()
Warehouse = env["stock.warehouse"].sudo()
Store = env["stock.location"].sudo()

target_codes = ("11999", "12014", "12019")
date, slot = "2026-11-24", "S1"
plannings = Plans.search([
    ("delivery_date", "=", date),
    ("slot", "=", slot),
    ("state", "=", "published"),
])
assert plannings, "Missing Published Planning for actual Paket trial"
raw_products = {}
raw_by_kitchen = defaultdict(set)
for code in target_codes:
    matched = Products.search([("default_code", "=", code)], limit=2)
    assert len(matched) == 1, "Missing/ambiguous kitchen SKU %s" % code
    product = matched[0]
    rows = plannings.mapped("line_ids").filtered(
        lambda row: row.product_id == product and row.max_capacity > 0)
    assert len(rows) == 1, "No unique kitchen Planning SKU %s" % code
    row = rows[0]
    bom = row._capacity_bom()
    source = bom.picking_type_id.default_location_src_id
    assert source and source.usage == "internal", (
        "Unexpected manufacturing raw material source location %s" % code)
    for item in bom.bom_line_ids:
        raw_products[item.product_id.id] = item.product_id
        raw_by_kitchen[source.id].add(item.product_id.id)

print("BO_M_RAW_SKU_UNIQUE_COUNT:", len(raw_products))
print("BO_M_RAW_KITCHEN_LOCATION_COUNT:", len(raw_by_kitchen))
for location_id, product_ids in sorted(raw_by_kitchen.items()):
    loc = Store.browse(location_id)
    print("KITCHEN_RAW_SOURCE:", location_id, loc.complete_name,
          "MATERIAL_SKU_COUNT:", len(product_ids))

# These are counts in the TEST DB, not a claim about real warehouse stock.
print("TEST_DB_ALL_QUANTS:", Quant.search_count([]))
print("TEST_DB_POSITIVE_INTERNAL_QUANTS:", Quant.search_count([
    ("location_id.usage", "=", "internal"),
    ("quantity", ">", 0),
]))
print("TEST_DB_NEGATIVE_INTERNAL_QUANTS:", Quant.search_count([
    ("location_id.usage", "=", "internal"),
    ("quantity", "<", 0),
]))

quants = Quant.search([
    ("product_id", "in", list(raw_products)),
    ("location_id.usage", "=", "internal"),
])
by_product_location = defaultdict(lambda: [0.0, 0.0])
for quant in quants:
    key = (quant.product_id.id, quant.location_id.id)
    by_product_location[key][0] += quant.quantity
    by_product_location[key][1] += quant.reserved_quantity

at_kitchen = 0
available_elsewhere = []
for pid, prod in sorted(raw_products.items(),
                        key=lambda item: item[1].default_code or ""):
    candidates = []
    for (p, location_id), (physical, reserved) in by_product_location.items():
        if p != pid or physical <= 0:
            continue
        loc = Store.browse(location_id)
        free = physical - reserved
        if any(
            pid in product_ids and source_id == location_id
            for source_id, product_ids in raw_by_kitchen.items()
        ):
            at_kitchen += 1
        else:
            candidates.append((loc.complete_name, round(physical, 3),
                               round(free, 3)))
    if candidates:
        available_elsewhere.append((prod.default_code or str(pid),
                                    prod.display_name,
                                    sorted(candidates)))
print("RAW_PRODUCT_LOCATIONS_WITH_POSITIVE_KITCHEN_STOCK:", at_kitchen)
print("RAW_PRODUCTS_WITH_POSITIVE_STOCK_AT_OTHER_LOCATIONS:",
      len(available_elsewhere))
for code, name, places in available_elsewhere[:35]:
    print("ELSEWHERE:", code, name, places[:10])

print("RELEVANT_WAREHOUSE_MASTERS:")
for warehouse in Warehouse.search([]).sorted("code"):
    text_name = ("%s %s" % (warehouse.code or "", warehouse.name or "")).lower()
    if (warehouse.code in ("PCK", "PST", "ROTI") or
            any(fragment in text_name for fragment in (
                "cdc", "central", "pusat", "premi"))):
        print("  WAREHOUSE:", warehouse.code, warehouse.name,
              "STOCK:", warehouse.lot_stock_id.complete_name)

if Quant.search_count([
    ("location_id.usage", "=", "internal"), ("quantity", ">", 0),
]) == 0:
    print("INVENTORY_DIAGNOSIS: No positive internal quants anywhere in test DB; "
          "likely inventory opening balance has not been imported.")
elif available_elsewhere:
    print("INVENTORY_DIAGNOSIS: Some real raw materials are recorded in other "
          "locations. Use established CDC->kitchen SOP; this audit does not "
          "authorize or create transfers.")
else:
    print("INVENTORY_DIAGNOSIS: No positive internal quants found for the "
          "required raw SKUs, although other items may have inventory.")
print("READ_ONLY_PAKET_INVENTORY_COVERAGE_OK")
