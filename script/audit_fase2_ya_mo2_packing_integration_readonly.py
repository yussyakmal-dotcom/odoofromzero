"""Read-only integration audit for YA MO2/late SO-Packing linkage.

Run ONLY against erp-yussyakmal-mrp-test-RO_SO via Odoo shell.
No ORM creates/writes/unlinks and no SQL mutations.
Only structure, IDs, anonymous quantities and statuses are printed.
"""
from collections import Counter

CLONE = "erp-yussyakmal-mrp-test-RO_SO"
assert env.cr.dbname == CLONE, "STOP_WRONG_DATABASE"
print("DATABASE:", env.cr.dbname)
print("MODE: READ_ONLY_YA_MO2_PACKING_INTEGRATION_GATE")

Batch = env["ya.packing.batch"].sudo()
batch = Batch.search([], order="delivery_date desc,slot,id", limit=1)
print("EXISTING_PACKING_BATCHES:", Batch.search_count([]))
print("BATCH_FIELDS:", {
    name: name in Batch._fields for name in (
        "delivery_date", "slot", "state", "line_ids", "allocation_ids",
        "ya_package_component_ids", "ya_package_demand_ids",
        "ya_store_delivery_ids", "ya_fg_transfer_ids", "ya_package_assembly_mo_ids",
        "ya_has_package",
    )
})
MO = env["mrp.production"].sudo()
print("MRP_PRODUCTION_FIELDS:", {
    name: name in MO._fields for name in (
        "ya_packing_batch_line_id", "product_id", "product_qty",
        "product_uom_id", "bom_id", "picking_type_id", "location_src_id",
        "location_dest_id", "company_id", "date_start", "origin", "state",
        "move_finished_ids", "move_raw_ids",
    )
})
PlanLine = env["ya.production.planning.line"].sudo()
print("PLANNING_LINE_FIELDS:", {
    name: name in PlanLine._fields for name in (
        "product_id", "bom_id", "planning_id", "uom_id", "max_capacity",
    )
})
Ledger = env["ya.sale.capacity.reservation"].sudo()
print("SO_LEDGER_TOTAL:", Ledger.search_count([]))
print("YA_SO_CONFIRMED_TOTAL:", env["sale.order"].sudo().search_count([
    ("ya_is_capacity_so", "=", True), ("state", "in", ("sale", "done"))
]))

if not batch:
    print("NO_EXISTING_BATCH_TO_INSPECT")
else:
    print("BATCH_ID:", batch.id, "DATE:", batch.delivery_date,
          "SLOT:", batch.slot, "STATE:", batch.state,
          "HAS_PACKAGE:", getattr(batch, "ya_has_package", False))
    print("MO1_LINK_COUNT:", len(batch.line_ids.mapped("mo_id")))
    print("BATCH_LINE_COUNT:", len(batch.line_ids))
    print("ALLOC_SNAPSHOT_COUNT:", len(batch.allocation_ids))
    print("PAKET_COMPONENT_SNAPSHOT_COUNT:",
          len(batch.ya_package_component_ids))
    print("PAKET_SOURCE_KINDS:",
          dict(Counter(batch.ya_package_component_ids.mapped("source_kind"))))
    print("STORE_DO_COUNT:", len(batch.ya_store_delivery_ids))
    print("FG_TRANSFER_STATES:",
          dict(Counter(batch.ya_fg_transfer_ids.mapped("state"))))
    print("PACKAGE_ASSEMBLY_MO_COUNT:", len(batch.ya_package_assembly_mo_ids))
    print("MO1_STATES:", dict(Counter(batch.line_ids.mapped("mo_id").mapped("state"))))

    # Inspect original RO snapshot and kitchen Paket components separately:
    # don't assume that kitchen qty_requested already includes Paket.
    for line in batch.line_ids[:20]:
        original = sum(r.qty_requested for r in batch.allocation_ids
                       if r.line_id == line)
        comps = batch.ya_package_component_ids.filtered(
            lambda r: r.source_kind == "kitchen" and
            r.kitchen_line_id == line)
        pkg_qty = sum(c.uom_id._compute_quantity(
            c.qty_required, line.product_id.uom_id, round=False)
            for c in comps)
        bom = line.bom_id
        mo1 = line.mo_id
        mo1_qty = (mo1.product_uom_id._compute_quantity(
            mo1.product_qty, line.product_id.uom_id, round=False)
            if mo1 else 0)
        plan = line.planning_id.line_ids.filtered(
            lambda p: p.product_id == line.product_id)
        print("BATCH_SKU:", {
            "batch_line_id": line.id,
            "product_id": line.product_id.id,
            "planning_id": line.planning_id.id,
            "planning_line_count": len(plan),
            "packing_uom_matches_product_base": line.uom_id == line.product_id.uom_id,
            "snapshot_direct_alloc_qty": original,
            "snapshot_line_qty_requested": line.qty_requested,
            "snapshot_package_component_qty": pkg_qty,
            "snapshot_protected_package_qty": line.ya_package_component_qty,
            "snapshot_production_qty": line.qty_production,
            "mo1_id": mo1.id,
            "mo1_state": mo1.state if mo1 else None,
            "mo1_qty_base": mo1_qty,
            "bom_id": bom.id,
            "mo1_bom_id": mo1.bom_id.id if mo1 else None,
        })

print("READ_ONLY_YA_MO2_PACKING_INTEGRATION_GATE_COMPLETE")
