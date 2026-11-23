"""READ ONLY: readiness for Packing -> store DO based on locked RO allocations.

Odoo shell, ONLY erp-yussyakmal-mrp-test. Does not create, reserve,
validate, or change any document/stock. No package assembly yet.
"""
from collections import defaultdict
from odoo.tools import float_compare

assert env.cr.dbname == "erp-yussyakmal-mrp-test", "REFUSED: wrong DB"
print("DATABASE:", env.cr.dbname)
print("MODE: PACKING_TO_STORE_DO_READ_ONLY")
Warehouse = env["stock.warehouse"].sudo()
Quant = env["stock.quant"].sudo()
Picking = env["stock.picking"].sudo()
Batch = env["ya.packing.batch"].sudo()
packing = Warehouse.search([("code", "=", "PCK")])
assert len(packing) == 1 and packing.lot_stock_id, "Missing unique PCK warehouse"
print("PCK:", packing.lot_stock_id.complete_name)
print("PCK_DELIVERY_TYPE:",
      packing.out_type_id.display_name if packing.out_type_id else "-",
      "| PCK_INTERNAL_TYPE:",
      packing.int_type_id.display_name if packing.int_type_id else "-")
print("PCK_ROUTE:", "reception_steps=", packing.reception_steps,
      "delivery_steps=", packing.delivery_steps)

for day, slot in [("2026-11-25", "S3"), ("2026-11-27", "S1")]:
    batches = Batch.search([
        ("delivery_date", "=", day), ("slot", "=", slot),
        ("state", "=", "production_ok"),
    ])
    print("\n=== BATCH:", day, slot, "FOUND:", len(batches), "===")
    if len(batches) != 1:
        continue
    batch = batches[0]
    print("BATCH:", batch.name, "RO:", len(batch.ro_ids),
          "ALLOCATIONS:", len(batch.allocation_ids))
    if "ya_fg_transfer_ids" in batch._fields:
        print("FG_TO_PCK_PICKINGS:",
              [(p.name, p.state) for p in batch.ya_fg_transfer_ids])
    else:
        print("FG_TO_PCK_ADDON_NOT_INSTALLED")

    source_totals = defaultdict(float)
    destination_totals = defaultdict(float)
    for row in batch.allocation_ids.sorted(
            lambda r: (r.store_warehouse_id.code or "",
                       r.reference or "", r.id)):
        source_totals[row.product_id.id] += row.qty_allocated
        destination_totals[(row.store_warehouse_id.id,
                            row.product_id.id)] += row.qty_allocated
        if row.qty_allocated < 0 or row.qty_shortage < 0:
            print("BAD_ALLOCATION:", row.id)
    for (store_id, product_id), qty in sorted(destination_totals.items()):
        store = Warehouse.browse(store_id)
        product = env["product.product"].sudo().browse(product_id)
        if not store.lot_stock_id:
            print("STORE_MISSING_LOCATION:", store.code)
            continue
        print("STORE_ALLOC:", store.code,
              "| SKU:", product.default_code,
              "| ALLOCATED:", qty,
              "| STORE_LOCATION:", store.lot_stock_id.complete_name,
              "| STORE_RECEIPT_STEPS:", store.reception_steps,
              "| STORE_INTERNAL_TYPE:", store.int_type_id.display_name
                                        if store.int_type_id else "-",
              "| STORE_INCOMING_TYPE:", store.in_type_id.display_name
                                        if store.in_type_id else "-")

    for product_id, needed in sorted(source_totals.items()):
        product = env["product.product"].sudo().browse(product_id)
        quants = Quant.search([
            ("location_id", "child_of", packing.lot_stock_id.id),
            ("location_id.usage", "=", "internal"),
            ("product_id", "=", product_id),
        ])
        physical = sum(quants.mapped("quantity"))
        reserved = sum(quants.mapped("reserved_quantity"))
        print("PCK_SKU:", product.default_code,
              "| ALLOCATION_ALL_STORES:", needed,
              "| PCK_PHYSICAL:", physical,
              "| PCK_RESERVED:", reserved,
              "| PCK_FREE:", physical - reserved,
              "| PCK_SUFFICIENT:",
              float_compare(needed, physical - reserved,
                            precision_rounding=product.uom_id.rounding) <= 0)
    existing = Picking.search([
        ("location_id", "child_of", packing.lot_stock_id.id),
        ("origin", "ilike", batch.name),
    ])
    print("PCK_ORIGIN_MATCH_PICKINGS:",
          [(p.name, p.state, p.origin) for p in existing[:20]])
    print("BATCH_AUDIT_OK")
print("NOTE: no transfers were created; package assembly intentionally deferred.")
print("PACKING_TO_STORE_DO_AUDIT_OK")
