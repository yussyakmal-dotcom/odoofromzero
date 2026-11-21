"""YA MRP test 1: create/confirm a Manufacturing Order, ALWAYS rollback.

Runs inside Odoo shell on the dedicated MRP test DB, no files required.
Uses verified BoM BOM12499 (10 Pcs, 16 lines) to test native Odoo MRP.
No Work Order steps are created. This test never reserves or consumes stock.
"""
from collections import Counter

EXPECTED_DB = "erp-yussyakmal-mrp-test"
BOM_CODE = "BOM12499"
assert env.cr.dbname == EXPECTED_DB, "Wrong database: refusing MO test"

B = env["mrp.bom"].sudo()
M = env["mrp.production"].sudo()
SV = env["stock.quant"].sudo()
bom = B.search([("code", "=", BOM_CODE)], limit=2)
assert len(bom) == 1, f"Expected one BoM {BOM_CODE}, found {len(bom)}"
assert bom.product_id and bom.product_qty == 10, "Unexpected BOM product or batch quantity"
assert len(bom.bom_line_ids) == 16, "Unexpected BOM components"
assert not bom.operation_ids, "This test expects no operation steps"
assert bom.picking_type_id and bom.picking_type_id.code == "mrp_operation"
assert M.search_count([]) >= 0

print("DATABASE:", env.cr.dbname)
print("MODE: CREATE + CONFIRM + ALWAYS ROLLBACK")
print("BOM:", bom.code, "SKU:", bom.product_id.default_code,
      "QTY:", bom.product_qty, "UOM:", bom.product_uom_id.name)
print("PICKING TYPE:", bom.picking_type_id.display_name)
print("BOm COMPONENT LINES:", len(bom.bom_line_ids))

# Snapshot totals: no move quantities should be posted by this test.
before_mo = M.search_count([])
before_done_moves = env["stock.move"].sudo().search_count([("state", "=", "done")])
before_quant_count = SV.search_count([])

try:
    values = {
        "product_id": bom.product_id.id,
        "product_qty": bom.product_qty,
        "product_uom_id": bom.product_uom_id.id,
        "bom_id": bom.id,
        "picking_type_id": bom.picking_type_id.id,
    }
    mo = M.create(values)
    print("MO CREATED:", mo.name, "STATE:", mo.state)
    print("LOCATIONS:", "source=", mo.location_src_id.display_name,
          "destination=", mo.location_dest_id.display_name)
    assert mo.bom_id == bom
    assert mo.product_id == bom.product_id
    assert mo.product_qty == bom.product_qty
    assert mo.location_src_id and mo.location_dest_id, "Manufacturing locations missing"
    assert mo.picking_type_id == bom.picking_type_id

    # Confirm creates required stock moves but must NOT post consumption/production.
    mo.action_confirm()
    env.flush_all()
    print("MO CONFIRMED:", mo.name, "STATE:", mo.state)
    raw_moves = mo.move_raw_ids
    finished_moves = mo.move_finished_ids
    print("RAW MOVES:", len(raw_moves), "FINISHED MOVES:", len(finished_moves))
    print("RAW MOVE STATES:", dict(Counter(raw_moves.mapped("state"))))
    print("FINISHED MOVE STATES:", dict(Counter(finished_moves.mapped("state"))))
    assert len(raw_moves) > 0, "MO did not generate raw material moves"
    assert len(finished_moves) > 0, "MO did not generate finished product move"
    assert all(move.state != "done" for move in raw_moves | finished_moves), (
        "Unexpected stock posting during MO confirmation"
    )
    assert M.search_count([]) == before_mo + 1, "Unexpected number of newly created MOs"
    assert env["stock.move"].sudo().search_count([("state", "=", "done")]) == before_done_moves, (
        "Confirmation unexpectedly posted stock move(s)"
    )
    assert SV.search_count([]) == before_quant_count, (
        "Confirmation changed stock quant record count"
    )
    print("MO_CONFIRM_TEST_OK: Manufacturing Order confirmed, stock not posted")
except Exception:
    print("MO_CONFIRM_TEST_FAILED: inspect traceback; rollback guaranteed")
    raise
finally:
    env.cr.rollback()
    assert M.search_count([]) == before_mo, "Rollback failed: MO count differs"
    assert env["stock.move"].sudo().search_count([("state", "=", "done")]) == before_done_moves, (
        "Rollback failed: done move count differs"
    )
    print("MO_TEST_ROLLBACK_CONFIRMED: MO count returned to original")
