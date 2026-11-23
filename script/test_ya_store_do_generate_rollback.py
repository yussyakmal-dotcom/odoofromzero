"""ROLLBACK E2E: Generate native DO per store from immutable RO allocations.

Does NOT validate stock transfer: source-to-transit movement belongs to
Packing dispatch, and store receipt belongs to store acceptance.
Run in Odoo shell ONLY on erp-yussyakmal-mrp-test after backup.
"""
from collections import defaultdict

assert env.cr.dbname == "erp-yussyakmal-mrp-test", "REFUSED: wrong DB"
print("DATABASE:", env.cr.dbname)
print("MODE: TEST_GENERATE_STORE_DO_ROLLBACK")

class ExpectedRollback(Exception):
    pass

success = False
try:
    with env.cr.savepoint():
        Batch = env["ya.packing.batch"].sudo()
        batches = Batch.search([
            ("delivery_date", "=", "2026-11-27"),
            ("slot", "=", "S1"),
            ("state", "=", "production_ok"),
        ])
        assert len(batches) == 1, "One batch expected"
        batch = batches[0]
        assert "ya_store_delivery_ids" in batch._fields, "DO addon not installed"
        assert not batch.ya_store_delivery_ids, (
            "DO already exists: use a fresh test batch"
        )
        assert batch.ya_fg_transfer_ids and all(
            p.state == "done" for p in batch.ya_fg_transfer_ids
        ), "Finished products must already be in Packing"

        Warehouse = env["stock.warehouse"].sudo()
        PCK = Warehouse.search([("code", "=", "PCK")])
        assert len(PCK) == 1
        Quant = env["stock.quant"].sudo()
        def total(loc):
            return sum(Quant.search([
                ("location_id", "=", loc.id),
            ]).mapped("quantity"))

        transit = env["stock.location"].sudo().search([
            ("usage", "=", "transit"),
            ("name", "=", "Inter-warehouse transit"),
        ])
        assert len(transit) == 1
        stores = batch.allocation_ids.mapped("store_warehouse_id")
        before = {
            location.id: total(location)
            for location in (PCK.lot_stock_id | transit |
                             stores.mapped("lot_stock_id"))
        }
        required = defaultdict(float)
        for a in batch.allocation_ids:
            if a.qty_allocated > 0:
                required[(a.store_warehouse_id.id, a.product_id.id)] += a.qty_allocated
        assert required

        batch.action_ya_generate_store_do()
        deliveries = batch.ya_store_delivery_ids
        assert len(deliveries) == len(stores), "Wrong number of store DOs"
        assert all(p.ya_store_stage == "dispatch" for p in deliveries)
        assert all(p.state != "done" for p in deliveries)
        seen = defaultdict(float)
        for picking in deliveries:
            assert picking.location_id == PCK.lot_stock_id
            assert picking.location_dest_id == transit
            assert picking.ya_store_warehouse_id in stores
            for move in picking.move_ids:
                key = (picking.ya_store_warehouse_id.id, move.product_id.id)
                seen[key] += move.product_uom._compute_quantity(
                    move.product_uom_qty, move.product_id.uom_id, round=False
                )
                if move.product_id.default_code in ("10031", "11076"):
                    assert move.quantity == 0, (
                        "Unavailable SKU must not be marked as shipped"
                    )
        assert dict(seen) == dict(required), "DO Demand differs from RO allocation"
        for loc_id, before_qty in before.items():
            assert total(env["stock.location"].browse(loc_id)) == before_qty, (
                "Generating DO unexpectedly moved physical stock"
            )
        print("STORE_DO_DEMAND_MATCH_RO_PASS")
        print("STORE_DO_NO_STOCK_CHANGE_PASS")
        count = len(deliveries)
        batch.action_ya_generate_store_do()
        assert len(batch.ya_store_delivery_ids) == count
        print("STORE_DO_DOUBLE_CLICK_PASS")
        success = True
        raise ExpectedRollback()
except ExpectedRollback:
    print("ROLLBACK_EXPECTED_OK")
finally:
    env.cr.rollback()

if not success:
    raise AssertionError("Test failed and was rolled back")
batch = env["ya.packing.batch"].sudo().search([
    ("delivery_date", "=", "2026-11-27"),
    ("slot", "=", "S1"),
])
assert len(batch) == 1 and not batch.ya_store_delivery_ids
print("ROLLBACK_VERIFIED_NO_STORE_DO_PERSISTED")
print("YA_STORE_DO_GENERATE_ROLLBACK_PASS")
