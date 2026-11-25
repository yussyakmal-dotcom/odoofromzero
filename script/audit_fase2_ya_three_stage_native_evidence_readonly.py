"""READ-ONLY FASE2 native three-stage evidence: RO/MO1, SO/MO2, PCK.

STRICT clone-only. No write, no confirm, no transfer, no module upgrade.
Purpose: separate huge FROZEN Planning leftover (5,833 reported across
3 slots) from actual DONE MO outputs and real current PCK stock.
Current PCK quants are GLOBAL SHARED across dates/slots, NOT stock
earmarked for this batch; unreserved is NOT proof of SO entitlement.
All values for one SKU use product BASE UOM.

Run ONLY using odoo-bin shell -d erp-yussyakmal-mrp-test-RO_SO.
"""
from collections import defaultdict

DB = "erp-yussyakmal-mrp-test-RO_SO"
assert env.cr.dbname == DB, "STOP_WRONG_DATABASE"
env.cr.rollback()
env.cr.execute("SET TRANSACTION READ ONLY")
env.cr.execute("SHOW transaction_read_only")
assert env.cr.fetchone()[0] == "on", "STOP_NOT_READONLY"

Batch = env["ya.packing.batch"].sudo()
SO = env["sale.order"].sudo()
Reservation = env["ya.sale.capacity.reservation"].sudo()
MO2 = env["ya.sale.mo2.release.line"].sudo()
WH = env["stock.warehouse"].sudo()
Quant = env["stock.quant"].sudo()
company = env["res.company"].sudo().browse(1).exists()
assert company, "STOP_MISSING_COMPANY1"
pcks = WH.search([("code", "=", "PCK"), ("company_id", "=", company.id)])
assert len(pcks) == 1 and pcks.lot_stock_id, "STOP_PCK_NOT_UNIQUE"
pck = pcks.lot_stock_id

required = {
    "ya.packing.batch": [
        "delivery_date", "slot", "line_ids", "allocation_ids",
        "ya_package_component_ids", "ya_fg_transfer_ids",
        "ya_store_delivery_ids"
    ],
    "ya.packing.batch.line": [
        "product_id", "mo_id", "qty_production",
        "qty_surplus", "qty_requested", "ya_package_component_qty",
    ],
    "ya.sale.capacity.reservation": [
        "order_id", "product_id", "qty_required",
        "delivery_date", "slot"
    ],
    "ya.sale.mo2.release.line": [
        "mo_id", "product_id", "finalization_id", "qty_mo2"
    ],
    "mrp.production": ["state", "move_finished_ids", "product_id"],
    "stock.move": [
        "product_id", "product_uom", "quantity", "state",
        "location_dest_id"
    ],
    "stock.quant": [
        "quantity", "reserved_quantity", "location_id",
        "lot_id", "owner_id", "package_id"
    ],
}
for model, names in required.items():
    missing = [name for name in names if name not in env[model]._fields]
    assert not missing, "STOP_SCHEMA_MISMATCH %s: %s" % (model, missing)

print("DATABASE:", env.cr.dbname)
print("MODE: READ_ONLY_FASE2_THREE_STAGE_NATIVE_EVIDENCE")
print("COMPANY_ID:", company.id, "PCK_ROOT_LOCATION_ID:", pck.id)
print("PCK_POLICY: exact PCK root, company1, untracked/unowned/unpacked quants")
print("WARNING: PCK QUANTS ARE SHARED ACROSS ALL SLOTS; NEVER SUM PCK FREE"
      " REPEATED IN PER-BATCH/SKU ROWS")

batches = Batch.search([], order="delivery_date desc, slot, id")
print("ACTUAL_BATCH_COUNT:", len(batches))
print("NATIVE_SO_RESERVATION_COUNT:", Reservation.search_count([]))
print("NATIVE_MO2_RELEASE_LINE_COUNT:", MO2.search_count([]))
overall = {
    "frozen_line_surplus": 0,
    "original_direct_ro": 0,
    "frozen_direct_allocated": 0,
    "planned_mo1_output": 0,
    "mo1_done_product_output": 0.0,
    "so_confirmed_ledger_kitchen_qty": 0,
    "so_confirmed_source_order_count": 0,
    "mo2_released_output": 0,
    "mo2_done_product_output": 0.0,
}
for batch in batches:
    target_date, target_slot = batch.delivery_date, batch.slot
    so_records = SO.search([
        ("ya_is_capacity_so", "=", True),
        ("ya_delivery_date", "=", target_date),
        ("ya_slot", "=", target_slot),
        ("state", "in", ["sale", "done"]),
    ])
    ledgers = Reservation.search([
        ("delivery_date", "=", target_date),
        ("slot", "=", target_slot),
    ])
    mo2_lines = MO2.search([
        ("finalization_id.batch_id", "=", batch.id),
    ])
    ledger_by_sku = defaultdict(int)
    ledger_order_ids = set()
    for r in ledgers:
        ledger_by_sku[r.product_id.id] += r.qty_required
        ledger_order_ids.add(r.order_id.id)
        assert r.order_id.state in ("sale", "done"), (
            "STOP_LEDGER_NOT_CONFIRMED", r.id
        )
    assert set(so_records.ids) == ledger_order_ids, (
        "STOP_SO_LEDGER_MISMATCH", batch.id,
        sorted(set(so_records.ids)-ledger_order_ids),
        sorted(ledger_order_ids-set(so_records.ids))
    )
    overall["so_confirmed_ledger_kitchen_qty"] += sum(
        ledger_by_sku.values()
    )
    overall["so_confirmed_source_order_count"] += len(so_records)

    frozen_by_sku = defaultdict(lambda: {"requested":0,"allocated":0})
    for a in batch.allocation_ids:
        frozen_by_sku[a.product_id.id]["requested"] += a.qty_requested
        frozen_by_sku[a.product_id.id]["allocated"] += a.qty_allocated
        overall["original_direct_ro"] += a.qty_requested
        overall["frozen_direct_allocated"] += a.qty_allocated

    mo2_by_sku = defaultdict(list)
    for row in mo2_lines:
        mo2_by_sku[row.product_id.id].append(row)
        overall["mo2_released_output"] += row.qty_mo2

    fg_pick_counts = defaultdict(int)
    for picking in batch.ya_fg_transfer_ids:
        fg_pick_counts[picking.state] += 1
    do_counts = defaultdict(int)
    for picking in batch.ya_store_delivery_ids:
        do_counts[(
            picking.ya_store_stage
            if "ya_store_stage" in picking._fields else "UNKNOWN",
            picking.state
        )] += 1

    package_comp_qty_by_sku = defaultdict(float)
    for c in batch.ya_package_component_ids:
        if c.source_kind == "kitchen":
            product = c.product_id
            package_comp_qty_by_sku[product.id] += (
                c.uom_id._compute_quantity(
                    c.qty_required, product.uom_id, round=False
                )
            )

    result_rows = []
    for line in batch.line_ids:
        product = line.product_id
        pid = product.id
        mo = line.mo_id
        native_mo_done_qty = 0.0
        if mo:
            for move in mo.move_finished_ids:
                if (move.state == "done"
                        and move.product_id == product):
                    native_mo_done_qty += (
                        move.product_uom._compute_quantity(
                            move.quantity, product.uom_id, round=False
                        )
                    )
        mo2_native_done = 0.0
        for mo2_row in mo2_by_sku.get(pid, []):
            for move in mo2_row.mo_id.move_finished_ids:
                if (move.state == "done"
                        and move.product_id == product):
                    mo2_native_done += (
                        move.product_uom._compute_quantity(
                            move.quantity, product.uom_id, round=False
                        )
                    )
        # Native PCK root is a CURRENT stock picture shared with all
        # batches, not a quantity belonging to this particular date/slot.
        quants = Quant.search([
            ("product_id", "=", pid),
            ("location_id", "=", pck.id),
            ("company_id", "=", company.id),
            ("lot_id", "=", False),
            ("owner_id", "=", False),
            ("package_id", "=", False),
        ])
        native_pck_physical = sum(quants.mapped("quantity"))
        native_pck_reserved = sum(quants.mapped("reserved_quantity"))
        original = frozen_by_sku.get(pid, {"requested":0,"allocated":0})
        overall["frozen_line_surplus"] += line.qty_surplus
        overall["planned_mo1_output"] += line.qty_production
        overall["mo1_done_product_output"] += native_mo_done_qty
        overall["mo2_done_product_output"] += mo2_native_done
        result_rows.append({
            "sku": product.default_code or str(pid),
            "product_id": pid,
            "MO1_plan_output": line.qty_production,
            "MO1_native_id": mo.id if mo else None,
            "MO1_state": mo.state if mo else "MISSING",
            "MO1_native_DONE_finished_qty": native_mo_done_qty,
            "RO_direct_original": original["requested"],
            "RO_direct_frozen_allocated": original["allocated"],
            "RO_Paket_kitchen_component": package_comp_qty_by_sku[pid],
            "PREPROD1_frozen_unallocated_surplus": line.qty_surplus,
            "SO_confirmed_ledger_qty": ledger_by_sku[pid],
            "MO2_released_qty": sum(
                x.qty_mo2 for x in mo2_by_sku.get(pid, [])
            ),
            "MO2_native_DONE_finished_qty": mo2_native_done,
            "PCK_root_CURRENT_global_physical": native_pck_physical,
            "PCK_root_CURRENT_global_reserved": native_pck_reserved,
            "PCK_root_CURRENT_global_free_unclaimed": (
                native_pck_physical-native_pck_reserved
            ),
            "PCK_qty_IS_NOT_batch_earmarked": True,
        })

    no_mo1 = len([row for row in result_rows
                  if row["MO1_native_id"] is None])
    not_done_mo1 = len([row for row in result_rows
                        if row["MO1_state"] != "done"])
    print("BATCH_THREE_STAGE_NATIVE_COUNTS:", {
        "batch_id": batch.id,
        "date": str(target_date), "slot":target_slot,
        "line_count":len(batch.line_ids),
        "so_confirmed_order_count":len(so_records),
        "so_capacity_ledger_line_count":len(ledgers),
        "so_capacity_ledger_qty":sum(ledger_by_sku.values()),
        "mo2_native_release_line_count":len(mo2_lines),
        "mo1_missing_count":no_mo1,
        "mo1_not_DONE_count":not_done_mo1,
        "frozen_rounup_surplus":sum(r["PREPROD1_frozen_unallocated_surplus"]
                                    for r in result_rows),
        "frozen_original_ro":sum(r["RO_direct_original"]
                                 for r in result_rows),
        "frozen_allocated_to_store":sum(r["RO_direct_frozen_allocated"]
                                       for r in result_rows),
        "fg_kitchen_to_pck_picking_by_state":sorted(fg_pick_counts.items()),
        "store_do_stage_state":sorted(
            (str(stage),str(state), count)
            for (stage,state),count in do_counts.items()
        ),
        "has_package":batch.ya_has_package
    })
    for row in sorted(
        result_rows,
        key=lambda r: (-r["PREPROD1_frozen_unallocated_surplus"],
                       str(r["sku"]))
    )[:20]:
        print("SKU_THREE_STAGE_EVIDENCE:", row)
    missed_so_skus = sorted(
        set(ledger_by_sku)-set(x["product_id"] for x in result_rows)
    )
    if missed_so_skus:
        print("SO_SKUS_WITH_NO_PREPROD1_MO1_ROUTE:", missed_so_skus)
    print("BATCH_FINISHED_EVIDENCE_WARNING: Planned MO1/2 and prior"
          " frozen surplus are NOT proof of PCK free inventory")

print("OVERALL_THREE_STAGE_NATIVE_SOURCE_TOTALS:", overall)
print("IMPORTANT: PCK current quant repeats across dates/slots,"
      " do not add repeated PCK stock rows")
print("IMPORTANT: Confirmed SO must be reconciled to reserved actual free"
      " stock and FULL Paket components before any final DO")
print("IMPORTANT: Historical frozen RO and done/assigned pickings"
      " remain immutable; no automatic store extras or transfer")
print("READ_ONLY_FASE2_THREE_STAGE_NATIVE_EVIDENCE_PASS")
print("NO_MO_SO_RO_PCK_STOCK_DO_OR_PACKING_MUTATION")
env.cr.rollback()
