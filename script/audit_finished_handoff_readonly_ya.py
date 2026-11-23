"""READ ONLY: finished-goods handoff from completed MOs to Packing.

Run with Odoo shell ONLY on erp-yussyakmal-mrp-test.
No writes, confirms, reservations, changes to quants, or stock transfers.
"""
from collections import defaultdict

assert env.cr.dbname == "erp-yussyakmal-mrp-test", "REFUSED: WRONG DATABASE"
print("DATABASE:", env.cr.dbname)
print("MODE: READ_ONLY_FINISHED_HANDOFF")

Warehouse = env["stock.warehouse"].sudo()
packing = Warehouse.search([("code", "=", "PCK")])
assert len(packing) == 1 and packing.lot_stock_id, "Expected exactly one PCK warehouse"
print("PACKING:", packing.name, "| DESTINATION:", packing.lot_stock_id.complete_name)

Batch = env["ya.packing.batch"].sudo()
Move = env["stock.move"].sudo()
Picking = env["stock.picking"].sudo()
Quant = env["stock.quant"].sudo()

for day, slot in [("2026-11-25", "S3"), ("2026-11-27", "S1")]:
    batches = Batch.search([("delivery_date", "=", day), ("slot", "=", slot)])
    print("\n=== BATCH:", day, slot, "| COUNT:", len(batches), "===")
    if len(batches) != 1:
        print("SKIP: ambiguous batch")
        continue
    batch = batches[0]
    mos = batch.line_ids.mapped("mo_id")
    grouped = defaultdict(lambda: {"finished": 0.0, "mo": [], "uom": None})
    skipped = []
    for mo in mos:
        if mo.state != "done":
            skipped.append((mo.name, mo.state, mo.product_id.display_name))
            continue
        wh = mo.picking_type_id.warehouse_id
        if not wh or not wh.lot_stock_id:
            skipped.append((mo.name, "NO_WAREHOUSE", mo.product_id.display_name))
            continue
        if mo.location_dest_id != wh.lot_stock_id:
            skipped.append((mo.name, "NONDEFAULT_DEST", mo.location_dest_id.complete_name))
            continue
        outgoing = mo.move_finished_ids.filtered(
            lambda m: m.state == "done" and m.product_id == mo.product_id
            and m.location_dest_id == wh.lot_stock_id
        )
        if not outgoing:
            skipped.append((mo.name, "NO_DONE_FINISHED_MOVE", mo.product_id.display_name))
            continue
        qty = sum(
            move.product_uom._compute_quantity(
                move.quantity, move.product_id.uom_id, round=False)
            for move in outgoing
        )
        key = (wh.id, mo.product_id.id)
        grouped[key]["finished"] += qty
        grouped[key]["uom"] = mo.product_id.uom_id.name
        grouped[key]["mo"].append(mo.name)
    print("MO_TOTAL:", len(mos), "| GROUPED_KITCHEN_SKU:", len(grouped))
    print("SKIPPED:", skipped)

    for (wh_id, product_id), data in sorted(grouped.items()):
        wh = Warehouse.browse(wh_id)
        product = env["product.product"].sudo().browse(product_id)
        stock = Quant.search([
            ("location_id", "child_of", wh.lot_stock_id.id),
            ("location_id.usage", "=", "internal"),
            ("product_id", "=", product_id),
        ])
        onhand = sum(q.quantity for q in stock)
        reserved = sum(q.reserved_quantity for q in stock)
        outstanding = Move.search([
            ("product_id", "=", product_id),
            ("location_id", "child_of", wh.lot_stock_id.id),
            ("location_dest_id", "child_of", packing.lot_stock_id.id),
            ("state", "not in", ["done", "cancel"]),
        ])
        issued = sum(
            m.product_uom._compute_quantity(m.product_uom_qty,
                                              product.uom_id, round=False)
            for m in outstanding
        )
        done = Move.search([
            ("product_id", "=", product_id),
            ("location_id", "child_of", wh.lot_stock_id.id),
            ("location_dest_id", "child_of", packing.lot_stock_id.id),
            ("state", "=", "done"),
        ])
        print("SKU:", product.default_code,
              "| PRODUCT:", product.display_name,
              "| KITCHEN:", wh.code,
              "| DONE_MO_OUTPUT:", data["finished"],
              "| UOM:", data["uom"],
              "| KITCHEN_ONHAND_NOW:", onhand,
              "| KITCHEN_RESERVED_NOW:", reserved,
              "| OPEN_KITCHEN_TO_PCK_DEMAND:", issued,
              "| DONE_KITCHEN_TO_PCK_MOVE_COUNT:", len(done),
              "| MO_NAMES:", ",".join(data["mo"]))
        for move in outstanding[:3]:
            print("  OPEN_TRANSFER:", move.picking_id.name or "-",
                  "| MOVE:", move.id,
                  "| DEMAND:", move.product_uom_qty,
                  "| STATE:", move.state)
    print("BATCH_READ_ONLY_OK")

print("\nNOTE: DONE_MO_OUTPUT is actual done stock.move quantity; all stock")
print("and outstanding quantities are snapshots across all batches, not")
print("permission to issue a new transfer or proof stock is dedicated.")
print("WIP/intermediate SKUs require SOP classification before handoff.")
print("READ_ONLY_FINISHED_HANDOFF_AUDIT_OK")
