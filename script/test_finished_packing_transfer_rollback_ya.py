"""ROLLBACK E2E test for one-click kitchen -> Packing stock move.

Run with Odoo shell ONLY on erp-yussyakmal-mrp-test, after GUI backup.
Simulates real native Odoo Validate but ALWAYS rolls the transaction back.
No commit. Does not run against live database.
"""
from collections import defaultdict
from odoo.tools import float_compare

assert env.cr.dbname == "erp-yussyakmal-mrp-test", "REFUSED: WRONG DATABASE"
print("DATABASE:", env.cr.dbname)
print("MODE: E2E_FINISHED_TO_PACKING_ROLLBACK_ONLY")

def stock_at(product_id, location_id):
    return sum(env["stock.quant"].sudo().search([
        ("product_id", "=", product_id),
        ("location_id", "=", location_id),
    ]).mapped("quantity"))

class ExpectedRollback(Exception):
    pass

success = False
try:
    # Savepoint plus explicit exception means even successful stock moves and
    # native Odoo validations never survive this trial run.
    with env.cr.savepoint():
        Batch = env["ya.packing.batch"].sudo()
        batches = Batch.search([
            ("delivery_date", "=", "2026-11-25"),
            ("slot", "=", "S3"),
            ("state", "=", "production_ok"),
        ])
        assert len(batches) == 1, "Expected exactly one test batch"
        batch = batches[0]
        assert "action_ya_fg_move_to_packing" in batch._fields or hasattr(
            batch, "action_ya_fg_move_to_packing"
        ), "New finished-Packing addon not installed"
        assert not batch.ya_fg_transfer_ids, (
            "This batch already has a finished-goods transfer; choose a fresh test batch."
        )
        Warehouse = env["stock.warehouse"].sudo()
        packing = Warehouse.search([("code", "=", "PCK")])
        assert len(packing) == 1, "Expected one Packing warehouse"
        before = {}
        expected = defaultdict(float)
        for mo in batch.line_ids.mapped("mo_id"):
            if mo.state != "done" or mo.product_id.default_code == "11076":
                continue
            warehouse = mo.picking_type_id.warehouse_id
            for move in mo.move_finished_ids.filtered(
                lambda m: m.state == "done" and m.product_id == mo.product_id
                and m.location_dest_id == warehouse.lot_stock_id
            ):
                key = (warehouse.lot_stock_id.id, mo.product_id.id)
                expected[key] += move.product_uom._compute_quantity(
                    move.quantity, mo.product_id.uom_id, round=False
                )
        assert expected, "No finished output available"
        for (src_id, product_id), qty in expected.items():
            before[(src_id, product_id)] = (
                stock_at(product_id, src_id),
                stock_at(product_id, packing.lot_stock_id.id),
            )
        print("EXPECTED_KITCHEN_SKU:", len(expected))
        print("EXPECTED_PICKINGS:", len(set(src for src, _ in expected)))
        print("EXPECTED_WIP_EXCLUDED: 11076")

        # Run actual button action (creates native pickings, then validates).
        action = batch.action_ya_fg_move_to_packing()
        pickings = batch.ya_fg_transfer_ids
        assert len(pickings) == len(set(src for src, _ in expected)), (
            "Wrong picking count"
        )
        assert all(p.state == "done" for p in pickings), (
            "Picking validation did not finish"
        )
        actual = defaultdict(float)
        for picking in pickings:
            assert picking.location_dest_id == packing.lot_stock_id, (
                "Wrong Packing destination"
            )
            for move in picking.move_ids:
                assert move.state == "done", "Not all stock moves done"
                assert move.product_id.default_code != "11076", (
                    "Intermediate WIP was transferred"
                )
                key = (picking.location_id.id, move.product_id.id)
                actual[key] += move.product_uom._compute_quantity(
                    move.quantity, move.product_id.uom_id, round=False
                )
        assert set(actual) == set(expected), (
            "Different kitchen+SKU set than completed MOs"
        )
        for key, qty in expected.items():
            src_id, product_id = key
            product = env["product.product"].browse(product_id)
            rounding = product.uom_id.rounding
            assert float_compare(actual[key], qty, precision_rounding=rounding) == 0, (
                "Wrong transferred Qty for %s" % product.display_name
            )
            before_source, before_pck = before[key]
            after_source = stock_at(product_id, src_id)
            after_pck = stock_at(product_id, packing.lot_stock_id.id)
            assert float_compare(
                before_source - after_source, qty,
                precision_rounding=rounding
            ) == 0, "Source stock delta mismatch: %s" % product.display_name
            assert float_compare(
                after_pck - before_pck, qty,
                precision_rounding=rounding
            ) == 0, "Packing stock delta mismatch: %s" % product.display_name

        # Repeated button must open existing pickings, not issue stock again.
        count = len(pickings)
        batch.action_ya_fg_move_to_packing()
        assert len(batch.ya_fg_transfer_ids) == count, (
            "Duplicate picking created on second click"
        )
        print("NATIVE_TRANSFER_VALIDATION_PASS")
        print("STOCK_DELTAS_PASS")
        print("DOUBLE_CLICK_GUARD_PASS")
        success = True
        raise ExpectedRollback()
except ExpectedRollback:
    print("ROLLBACK_EXPECTED_OK")
finally:
    env.cr.rollback()

if not success:
    raise AssertionError("Test failed; transaction rolled back")
env.invalidate_all()
check = env["ya.packing.batch"].sudo().search([
    ("delivery_date", "=", "2026-11-25"),
    ("slot", "=", "S3"),
])
assert len(check) == 1 and not check.ya_fg_transfer_ids, (
    "Unexpected persisted transfer after rollback"
)
print("ROLLBACK_VERIFIED_NO_PICKING_PERSISTED")
print("FINISHED_PACKING_E2E_ROLLBACK_PASS")
