"""Odoo19 Fase2 CLONE ONLY: READ-ONLY audit for excessive frozen RO store entitlement.

Purpose: assess already-stored, immutable MO1/RO Pre Production snapshots
and native Picking headers/moves BEFORE integrating new Fase2 surplus guard.
No write, no create, no stock reservation, no DO, no addon upgrade.

Critical: legacy RO/Paket planner can automatically prorate recipe surplus
onto stores beyond original confirmed RO demand. At Fase2 this should
never be silently carried into a final delivery/entitlement ledger.
This diagnostic does NOT modify Fase1 allocations or infer physical DO.
"""
from collections import defaultdict

DB = "erp-yussyakmal-mrp-test-RO_SO"
assert env.cr.dbname == DB, "STOP_WRONG_DB"
env.cr.rollback()
env.cr.execute("SET TRANSACTION READ ONLY")
env.cr.execute("SHOW transaction_read_only")
assert env.cr.fetchone()[0] == "on", "STOP_READ_ONLY_NOT_ENFORCED"

modules = env["ir.module.module"].sudo().search([
    ("name", "in", [
        "ya_store_ro", "ya_package_store_ro",
        "ya_sale_production_capacity",
    ])
])
print("DATABASE:", env.cr.dbname)
print("MODE: READ_ONLY_FASE2_FROZEN_RO_PAKET_SURPLUS_AND_DO")
print("MODULE_STATES:", sorted(
    (m.name, m.state, m.installed_version) for m in modules
))

Batch = env["ya.packing.batch"].sudo()
Allocation = env["ya.packing.batch.allocation"].sudo()
Picking = env["stock.picking"].sudo()

required = {
    "ya.packing.batch": [
        "delivery_date", "slot", "state", "line_ids", "allocation_ids",
        "ya_store_delivery_ids", "ya_has_package"
    ],
    "ya.packing.batch.allocation": [
        "batch_id", "line_id", "ro_id", "product_id",
        "store_warehouse_id", "qty_requested", "qty_allocated",
        "qty_shortage", "qty_surplus"
    ],
    "stock.picking": [
        "state", "ya_store_batch_id", "move_ids", "picking_type_id"
    ],
    "stock.move": [
        "product_id", "product_uom_qty", "product_uom",
        "quantity", "state", "location_id", "location_dest_id"
    ],
}
for model, keys in required.items():
    missing = [key for key in keys
               if key not in env[model]._fields]
    assert not missing, "STOP_SCHEMA_MISMATCH: %s: %s" % (
        model, missing
    )

print("BATCH_TOTAL:", Batch.search_count([]))
print("FROZEN_ALLOCATIONS_TOTAL:", Allocation.search_count([]))
print("DISPATCH_PICKING_TOTAL:", Picking.search_count([
    ("ya_store_batch_id", "!=", False),
]))

totals = {
    "frozen_requested": 0,
    "frozen_allocated": 0,
    "frozen_over_entitled": 0,
    "surplus_field_total": 0,
    "frozen_shortage_total": 0,
    "batch_line_residual_surplus": 0,
    "native_store_done_move_base_qty": 0.0,
    "native_store_open_demand_base_qty": 0.0,
    "native_store_done_pickings": 0,
    "native_store_not_done_pickings": 0,
}
for batch in Batch.search([], order="delivery_date desc, slot, id", limit=50):
    over_rows = []
    requested = allocated = overs = surplus = shortage = 0
    per_sku = defaultdict(lambda: {
        "requested": 0, "allocated": 0,
        "over_entitlement": 0, "surplus_recorded": 0,
    })
    for a in batch.allocation_ids:
        assert a.batch_id == batch
        assert a.line_id.batch_id == batch
        assert all(isinstance(v, int) and v >= 0 for v in (
            a.qty_requested, a.qty_allocated,
            a.qty_surplus, a.qty_shortage
        )), "STOP_INVALID_INTEGER_FROZEN_ALLOCATION_%s" % a.id
        assert a.qty_allocated == (
            a.qty_requested - a.qty_shortage + a.qty_surplus
        ), "STOP_FROZEN_ACCOUNTING_IDENTITY_%s" % a.id
        excess = max(0, a.qty_allocated - a.qty_requested)
        requested += a.qty_requested
        allocated += a.qty_allocated
        overs += excess
        surplus += a.qty_surplus
        shortage += a.qty_shortage
        p = per_sku[a.product_id.id]
        p["requested"] += a.qty_requested
        p["allocated"] += a.qty_allocated
        p["over_entitlement"] += excess
        p["surplus_recorded"] += a.qty_surplus
        if excess:
            over_rows.append({
                "allocation_id": a.id,
                "store": a.store_warehouse_id.code,
                "sku": a.product_id.default_code,
                "ro_id": a.ro_id.id,
                "requested": a.qty_requested,
                "allocated": a.qty_allocated,
                "above_confirmed_ro": excess,
                "surplus_field": a.qty_surplus,
            })
    totals["frozen_requested"] += requested
    totals["frozen_allocated"] += allocated
    totals["frozen_over_entitled"] += overs
    totals["surplus_field_total"] += surplus
    totals["frozen_shortage_total"] += shortage
    # This is a frozen pre-production PRODUCTION planning measure, not
    # completed PCK physical free stock and not proof of real stock transfer.
    remaining = sum(max(0, x.qty_surplus) for x in batch.line_ids)
    totals["batch_line_residual_surplus"] += remaining

    docs = batch.ya_store_delivery_ids
    by_stage = defaultdict(int)
    native_done = 0.0
    open_demand = 0.0
    for picking in docs:
        stage = (picking.ya_store_stage
                 if "ya_store_stage" in picking._fields else "UNKNOWN")
        by_stage[(stage, picking.state)] += 1
        if (stage != "dispatch"
                and "ya_store_stage" in picking._fields):
            continue
        if picking.state == "done":
            totals["native_store_done_pickings"] += 1
        else:
            totals["native_store_not_done_pickings"] += 1
        for move in picking.move_ids:
            base_uom = move.product_id.uom_id
            if move.state == "done":
                qty = move.product_uom._compute_quantity(
                    move.quantity, base_uom, round=False
                )
                native_done += qty
                totals["native_store_done_move_base_qty"] += qty
            elif move.state != "cancel":
                qty = move.product_uom._compute_quantity(
                    move.product_uom_qty, base_uom, round=False
                )
                open_demand += qty
                totals["native_store_open_demand_base_qty"] += qty
    print("BATCH_FROZEN_SURPLUS_RISK:", {
        "batch_id": batch.id,
        "date": str(batch.delivery_date),
        "slot": batch.slot, "state": batch.state,
        "has_package": batch.ya_has_package,
        "frozen_allocation_count": len(batch.allocation_ids),
        "frozen_requested_total": requested,
        "frozen_allocated_total": allocated,
        "over_entitled_vs_confirmed_ro": overs,
        "surplus_field_total": surplus,
        "shortage_field_total": shortage,
        "frozen_batch_line_unallocated_surplus": remaining,
        "per_sku_risk_rows": [
            {
                "sku": env["product.product"].sudo().browse(pid).default_code,
                **d,
            }
            for pid, d in sorted(per_sku.items())
            if d["over_entitlement"] or d["surplus_recorded"]
        ][:20],
        "over_entitled_store_rows": over_rows[:20],
        "store_picking_stage_state_counts": sorted(
            (str(stage), str(state), count)
            for (stage, state), count in by_stage.items()
        ),
        "done_dispatch_move_base_units": native_done,
        "not_done_dispatch_move_demand_base_units": open_demand,
    })

print("OVERALL_EXISTING_FROZEN_SURPLUS_AND_DO_TOTALS:", totals)
if totals["frozen_over_entitled"]:
    print("EXISTING_FROZEN_OVERALLOCATION_RISK_PRESENT_REVIEW_REQUIRED")
else:
    print("NO_EXISTING_FROZEN_OVERALLOCATION_FOUND_IN_SCANNED_BATCHES")
print("IMPORTANT: Frozen allocations are planning documents, NOT native"
      " proof of completed customer/store DO")
print("IMPORTANT: Need independent authorized final entitlement from"
      " Confirmed SO/Paket/RO; do NOT overwrite frozen MO1 snapshot")
print("IMPORTANT: Any recipe surplus must remain unallocated at PCK"
      " unless separately approved; no automatic DO or transfer")
print("READ_ONLY_FASE2_FROZEN_SURPLUS_RISK_AUDIT_PASS")
print("NO_FROZEN_RO_PACKING_MO_PCK_STOCK_OR_DO_MUTATION")
env.cr.rollback()
