"""READ ONLY: MO without WO and finished-product handoff to Packing.

Run only in erp-yussyakmal-mrp-test via odoo-bin shell.
No changes to MO, BoM, Operations, Inventory, quants or pickings.
The output identifies whether finished goods first land in kitchen Stock
or already flow to Packing. Do not create another transfer before review.
"""
from collections import Counter

DB = "erp-yussyakmal-mrp-test"
assert env.cr.dbname == DB, "REFUSED: wrong database"
print("DATABASE:", env.cr.dbname)
print("MODE: READ_ONLY_MO_FINISHED_PACKING_NO_WO")

Module = env["ir.module.module"].sudo()
for name in ("mrp", "mrp_workorder", "ya_store_ro"):
    r = Module.search([("name", "=", name)], limit=1)
    print("MODULE:", name, r.state if r else "NOT_FOUND",
          r.installed_version if r else "")

Warehouse = env["stock.warehouse"].sudo()
PickType = env["stock.picking.type"].sudo()
warehouses = Warehouse.search([])
print("WAREHOUSES:", len(warehouses))
for wh in warehouses:
    print("WAREHOUSE:", wh.code, "|", wh.name,
          "| STOCK:", wh.lot_stock_id.complete_name,
          "| INTERNAL:", wh.int_type_id.display_name if wh.int_type_id else "-")

print("POSSIBLE_PACKING_LOCATIONS:")
locs = env["stock.location"].sudo().search([
    ("usage", "=", "internal"),
    "|", ("name", "ilike", "packing"), ("complete_name", "ilike", "packing"),
], limit=30)
for loc in locs:
    print("LOCATION:", loc.id, loc.complete_name,
          "| USAGE:", loc.usage)

print("PACKING_OPERATION_TYPES:")
for typ in PickType.search([("name", "ilike", "packing")], limit=20):
    print("TYPE:", typ.id, typ.display_name, "| CODE:", typ.code,
          "| SOURCE:", typ.default_location_src_id.complete_name,
          "| DEST:", typ.default_location_dest_id.complete_name)

Batch = env["ya.packing.batch"].sudo()
for date, slot in (("2026-11-25", "S3"), ("2026-11-27", "S1")):
    batches = Batch.search([
        ("delivery_date", "=", date), ("slot", "=", slot),
        ("state", "=", "production_ok"),
    ])
    print("\nBATCH_QUERY:", date, slot, "| FOUND:", len(batches))
    for batch in batches:
        mos = batch.line_ids.mapped("mo_id")
        print("BATCH:", batch.name, "| MO:", len(mos),
              "| KITCHENS:", len(set(
                  mo.picking_type_id.warehouse_id.id for mo in mos)))
        stats = Counter()
        for mo in mos.sorted(lambda r: r.name):
            bom_ops = len(mo.bom_id.operation_ids) if mo.bom_id and "operation_ids" in mo.bom_id._fields else "N/A"
            wo_count = len(mo.workorder_ids) if "workorder_ids" in mo._fields else "FIELD_ABSENT"
            finished = mo.move_finished_ids.filtered(
                lambda m: m.state != "cancel"
            ) if "move_finished_ids" in mo._fields else env["stock.move"]
            stats["mos"] += 1
            stats["mos_with_workorders"] += bool(isinstance(wo_count, int) and wo_count)
            stats["mos_with_bom_operations"] += bool(isinstance(bom_ops, int) and bom_ops)
            stats["mos_dest_packing_named"] += "packing" in (mo.location_dest_id.complete_name or "").lower()
            print("MO:", mo.name,
                  "| STATE:", mo.state,
                  "| PRODUCT:", mo.product_id.default_code or mo.product_id.id,
                  "| UOM:", mo.product_uom_id.name,
                  "| QTY:", mo.product_qty,
                  "| KITCHEN:", mo.picking_type_id.warehouse_id.name,
                  "| SRC:", mo.location_src_id.complete_name,
                  "| DEST:", mo.location_dest_id.complete_name,
                  "| BOM_OPS:", bom_ops,
                  "| WO:", wo_count,
                  "| FINISHED_MOVES:", len(finished))
            for move in finished[:2]:
                print("  FINISHED_MOVE:", move.id, "|", move.product_id.display_name,
                      "| DEMAND:", move.product_uom_qty,
                      "| STATE:", move.state,
                      "| SRC:", move.location_id.complete_name,
                      "| DEST:", move.location_dest_id.complete_name)
        print("SUMMARY:", dict(stats))

print("\nRULES:")
print("MO completion and movement of finished stock must be reviewed before")
print("creating Dapur -> Packing transfers. WO is optional only where no")
print("operation requirement is active; this audit makes no config changes.")
print("READ_ONLY_FINISHED_PACKING_AUDIT_OK")
