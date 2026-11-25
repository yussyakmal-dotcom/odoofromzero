"""Read-only YA Fase2 finished-goods bridge gate: real DONE MO output.

Only against RO_SO clone. Checks that native MO finished moves, UoMs, old
Fase1 FG pickings and physical kitchen stock are distinguishable. Does not
alter MOs, quants, PCK, Stock Moves, pickings, source RO or SO.
This is NOT a simulation of MO2 Done or proof of the Fase2 FG transfer.
"""
from collections import Counter
from pathlib import Path

DB = "erp-yussyakmal-mrp-test-RO_SO"
assert env.cr.dbname == DB, "STOP_WRONG_DATABASE"
print("DATABASE:", env.cr.dbname)
print("MODE: READ_ONLY_MO2_FG_DONE_OUTPUT_ROUTE_GATE")

source = Path(
    "addons/ya_finished_packing_transfer/models/finished_packing.py"
)
assert source.is_file(), "STOP_FASE1_FG_SOURCE_MISSING"
s = source.read_text(encoding="utf-8")
required = (
    'TEST_DB = "erp-yussyakmal-mrp-test"',
    'self.line_ids.mapped("mo_id")',
    "UNIQUE(ya_fg_batch_id, ya_fg_kitchen_id)",
    "mo.move_finished_ids.filtered(",
    'm.state == "done"',
    'm.location_dest_id == kitchen.lot_stock_id',
    "skip_immediate=True",
    "button_validate()",
)
assert all(x in s for x in required), "STOP_FASE1_FG_SOURCE_CHANGED"

Batch = env["ya.packing.batch"].sudo()
Mo = env["mrp.production"].sudo()
Picking = env["stock.picking"].sudo()
Quant = env["stock.quant"].sudo()
Release = env["ya.sale.mo2.release.line"].sudo()
Pck = env["stock.warehouse"].sudo().search([
    ("code", "=", "PCK"), ("company_id", "=", env.company.id),
])
assert len(Pck) == 1 and Pck.lot_stock_id.usage == "internal", (
    "STOP_PCK_WAREHOUSE_AMBIGUOUS"
)

print("SCHEMA:", {
    "mo_done_finished_move_ids": "move_finished_ids" in Mo._fields,
    "mo1_batch_line_link": "ya_packing_batch_line_id" in Mo._fields,
    "mo2_native_link": "mo_id" in Release._fields,
    "mo2_planning_link": "planning_line_id" in Release._fields,
    "mo2_material_pickings": "ya_mo2_material_picking_ids" in Release._fields,
    "stock_fg_batch": "ya_fg_batch_id" in Picking._fields,
    "stock_fg_kitchen": "ya_fg_kitchen_id" in Picking._fields,
})
print("MO2_NATIVE_RELEASE_LINES_PERSISTED:", Release.search_count([]))
print("LEGACY_FG_PICKINGS_COUNT:", Picking.search_count([
    ("ya_fg_batch_id", "!=", False),
]))
print("MO1_STATUS_COUNTS:", dict(Counter(
    Batch.search([]).mapped("line_ids.mo_id.state")
)))
batch = Batch.search([("state", "=", "production_ok")],
                     order="delivery_date desc,id desc", limit=1)
if not batch:
    print("STOP_NO_COMPLETED_BATCH_SAMPLE")
else:
    print("SAMPLE_BATCH:", batch.id, "DATE:", batch.delivery_date,
          "SLOT:", batch.slot,
          "FG_PICKINGS:", len(batch.ya_fg_transfer_ids),
          "STORE_DO:", len(batch.ya_store_delivery_ids))
    statuses = Counter(batch.line_ids.mapped("mo_id").mapped("state"))
    print("SAMPLE_MO_STATES:", dict(statuses))
    samples = []
    for row in batch.line_ids:
        mo = row.mo_id
        if not mo or mo.state != "done":
            continue
        wh = mo.picking_type_id.warehouse_id
        done = mo.move_finished_ids.filtered(
            lambda m: m.state == "done"
            and m.product_id == mo.product_id
            and wh and m.location_dest_id == wh.lot_stock_id
        )
        output = sum(
            m.product_uom._compute_quantity(
                m.quantity, mo.product_id.uom_id, round=False
            )
            for m in done
        )
        exact = (
            sum(Quant.search([
                ("product_id", "=", mo.product_id.id),
                ("location_id", "=", wh.lot_stock_id.id),
                ("company_id", "=", mo.company_id.id),
            ]).mapped("quantity")) if wh and wh.lot_stock_id else None
        )
        samples.append({
            "mo_id": mo.id,
            "product_id": mo.product_id.id,
            "kitchen": wh.code if wh else None,
            "done_finished_move_count": len(done),
            "done_finished_qty_base": output,
            "exact_kitchen_stock_now": exact,
            "tracking": mo.product_id.tracking,
            "legacy_fg_pickings_in_kitchen": len(
                batch.ya_fg_transfer_ids.filtered(
                    lambda x: x.ya_fg_kitchen_id == wh
                )
            ),
        })
        if len(samples) == 6:
            break
    for item in samples:
        print("REAL_DONE_MO_SAMPLE:", item)
    assert samples, "STOP_NO_REAL_MO_DONE_TO_INSPECT"
    assert all(x["done_finished_move_count"] > 0
               and x["done_finished_qty_base"] > 0 for x in samples), (
                   "STOP_INCOMPLETE_MO_DONE_FINISHED_MOVE"
               )
    print("NOTE: exact stock NOW may be below DONE MO output because")
    print("      historical Finished Goods picking already moved it to PCK.")
    print("      Never reissue transferred MO1 as if fresh MO2 stock.")
print("BRIDGE_RULE: MO2 FG transfer must consume ONLY Done native MO2 move_finished_ids.")
print("BRIDGE_RULE: new unique MO2 picking link; do not reuse Fase1 batch/kitchen unique key.")
print("BRIDGE_RULE: PCK one-step native internal, exact kitchen stock guard, no negative.")
print("BRIDGE_RULE: cancelled/in-progress MO2 has ZERO transferable output.")
print("BRIDGE_RULE: WIP exclusion and tracked products must be handled explicitly.")
print("READ_ONLY_MO2_FG_DONE_OUTPUT_ROUTE_GATE_PASS")
print("NO_STOCK_OR_MO_MUTATION")
