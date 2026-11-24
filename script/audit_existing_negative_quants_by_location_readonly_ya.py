"""Read-only TEST inventory discrepancy inventory, before considering OCA guard.

NO writes, confirms, postings or adjustments. Enumerates ALL negative
storable internal/transit stock quants and a small recent native move sample
per SKU/location. Move history is diagnostic, NOT proof of physical counts.
"""
from collections import Counter, defaultdict

assert env.cr.dbname == "erp-yussyakmal-mrp-test", "REFUSED: WRONG DB"
print("DATABASE:", env.cr.dbname)
print("MODE: READ_ONLY_ALL_NEGATIVE_QUANTS_BY_LOCATION")
Quant = env["stock.quant"].sudo()
Warehouse = env["stock.warehouse"].sudo()
MoveLine = env["stock.move.line"].sudo()
negative = Quant.search([
    ("quantity", "<", -0.000001),
    ("location_id.usage", "in", ("internal", "transit")),
    ("product_id.is_storable", "=", True),
], order="location_id,product_id,id")
print("NEGATIVE_QUANT_COUNT:", len(negative))
location_totals = Counter()
location_count = Counter()
products = set()
all_quants = []
for q in negative:
    location = q.location_id
    product = q.product_id
    products.add(product.id)
    location_count[location.complete_name] += 1
    # Sum is diagnostic only: do not combine different units of measure
    # into one physical quantity, especially gram + pcs.
    location_totals[location.complete_name] += 1
    all_quants.append(q)
print("NEGATIVE_BY_LOCATION_COUNT:", sorted(location_count.items()))
print("NEGATIVE_DISTINCT_PRODUCT_COUNT:", len(products))

sul = Warehouse.search([("code", "=", "SUL")], limit=2)
assert len(sul) <= 1, "Ambiguous SUL warehouse code"
print("SUL_WAREHOUSE:", sul.name if sul else "NO_SUL_WAREHOUSE",
      "STOCK_LOCATION:", sul.lot_stock_id.complete_name if sul else "UNKNOWN")
for q in all_quants:
    prod = q.product_id
    loc = q.location_id
    print("NEGATIVE_QUANT:",
          "quant_id:", q.id,
          "sku:", prod.default_code or "<NO_SKU>",
          "product:", prod.display_name,
          "category:", prod.categ_id.complete_name,
          "uom:", prod.uom_id.name,
          "qty:", q.quantity,
          "reserved:", q.reserved_quantity,
          "location:", loc.complete_name,
          "warehouse_root:", (
              sul.code if sul and
              loc.id == sul.lot_stock_id.id else "OTHER"),
          "lot:", q.lot_id.name if q.lot_id else "-")
    # Recent stock moves touching this exact quant location, not all
    # subsidiaries/warehouse child bins. No query for CREATE or UPDATE.
    recent = MoveLine.search([
        ("product_id", "=", prod.id),
        ("state", "=", "done"),
        "|",
        ("location_id", "=", loc.id),
        ("location_dest_id", "=", loc.id),
    ], order="date desc, id desc", limit=3)
    if not recent:
        print("  RECENT_DONE_MOVE: NONE_FOUND")
    for line in recent:
        print("  RECENT_DONE_MOVE:",
              "date:", str(line.date),
              "qty:", line.quantity,
              "uom:", line.product_uom_id.name,
              "source:", line.location_id.complete_name,
              "dest:", line.location_dest_id.complete_name,
              "reference:", line.move_id.reference or
              line.move_id.picking_id.name or line.move_id.name)

print("NOTE: NEGATIVE quantity is ERP balance, not physical stock proof.")
print("NOTE: A location with a negative quant does not establish what caused it.")
print("NOTE: Correct using authorized physical counting/reconciliation; "
      "do NOT auto-seed/zero or post stock adjustments in this audit.")
print("READ_ONLY_NEGATIVE_QUANTS_LOCATIONS_DETAIL_OK")
