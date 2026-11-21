"""YA manufacturing checkpoint A — MO confirm, UoM, WIP and stock audit.

Odoo 19 Community / erp-yussyakmal-mrp-test ONLY.
Test BOM12499 (10 Pcs, 16 component lines). Creates and confirms a
temporary MO, checks raw requirements against source stock, always rolls
back. NEVER posts consumption or production.
"""
from collections import Counter
from decimal import Decimal

assert env.cr.dbname == "erp-yussyakmal-mrp-test", (
    "Refusing to run outside dedicated MRP test DB")
B = env["mrp.bom"].sudo()
L = env["mrp.bom.line"].sudo()
M = env["mrp.production"].sudo()
Q = env["stock.quant"].sudo()
SM = env["stock.move"].sudo()
assert B.search_count([]) == 955, "BoM count mismatch"
assert L.search_count([]) == 8502, "BoM component count mismatch"
bom = B.search([("code", "=", "BOM12499")], limit=2)
assert len(bom) == 1, "BOM12499 is missing or duplicated"
assert bom.product_id.default_code == "12499"
assert len(bom.bom_line_ids) == 16
assert abs(bom.product_qty - 10.0) < 1e-9
assert bom.product_uom_id.name.strip().casefold() == "pcs"
wip = env["product.product"].sudo().search([("default_code", "=", "11055")], limit=2)
assert len(wip) == 1 and wip.uom_id.name.strip().casefold() == "gram"
assert len(bom.bom_line_ids.filtered(lambda x: x.product_id.id == wip.id)) == 1
assert abs(bom.bom_line_ids.filtered(
    lambda x: x.product_id.id == wip.id).product_qty - 500.0) < 1e-9
assert bom.bom_line_ids.filtered(
    lambda x: x.product_id.id == wip.id).product_uom_id.name.strip().casefold() == "gram"

start_mo = M.search_count([])
start_done = SM.search_count([("state", "=", "done")])
start_quants = Q.search_count([])
print("DATABASE:", env.cr.dbname)
print("MODE: MO_CONFIRM + STOCK_AVAILABILITY + ALWAYS_ROLLBACK")
print("BOM:", bom.code, "PRODUCT:", bom.product_id.default_code,
      "OUTPUT:", bom.product_qty, bom.product_uom_id.name)
print("WIP_COMPONENT_11055:", "500 Gram", "MASTER:", wip.uom_id.name)
print("NOTE: this test does not test negative stock blocking or Mark as Done")
try:
    mo = M.create({
        "product_id": bom.product_id.id,
        "product_qty": bom.product_qty,
        "product_uom_id": bom.product_uom_id.id,
        "bom_id": bom.id,
        "picking_type_id": bom.picking_type_id.id,
    })
    assert mo.state == "draft", f"Unexpected state after create: {mo.state}"
    print("MO_CREATED:", mo.name, "STATE:", mo.state)
    print("SOURCE_LOCATION:", mo.location_src_id.complete_name,
          "USAGE:", mo.location_src_id.usage)
    print("DEST_LOCATION:", mo.location_dest_id.complete_name,
          "USAGE:", mo.location_dest_id.usage)
    print("PICKING_TYPE:", mo.picking_type_id.display_name)
    assert mo.location_src_id.usage == "internal", (
        "Source is not internal stock location")
    assert mo.location_dest_id.usage == "internal", (
        "Destination is not internal stock location")
    mo.action_confirm()
    env.flush_all()
    print("MO_CONFIRMED:", mo.name, "STATE:", mo.state)
    assert mo.state in ("confirmed", "progress", "to_close"), (
        f"Unexpected state after confirm: {mo.state}")
    raws = mo.move_raw_ids
    finished = mo.move_finished_ids
    assert len(raws) == 16, f"Expected 16 moves, got {len(raws)}"
    assert len(finished) == 1, f"Expected 1 finished move, got {len(finished)}"
    assert all(move.state != "done" for move in raws | finished)
    print("RAW_MOVES:", len(raws), "FINISHED_MOVES:", len(finished))
    missing = []
    conversion_errors = []
    for move in raws.sorted(key=lambda m: (m.product_id.default_code or "", m.id)):
        unit = move.product_uom
        base = move.product_id.uom_id
        try:
            base_demand = unit._compute_quantity(
                move.product_uom_qty, base, raise_if_failure=True)
            available = Q._get_available_quantity(
                move.product_id, move.location_id, strict=False)
            reserved = sum(Q.search([
                ("product_id", "=", move.product_id.id),
                ("location_id", "child_of", move.location_id.id),
            ]).mapped("reserved_quantity"))
        except Exception as exc:
            conversion_errors.append((move.product_id.default_code, str(exc)))
            print("UOM_ERROR:", move.product_id.default_code, str(exc))
            continue
        deficit = max(0.0, base_demand - available)
        if deficit > 1e-7:
            missing.append((move.product_id.default_code, deficit, base.name))
        print(
            "COMPONENT:", move.product_id.default_code or str(move.product_id.id),
            "| NAME:", move.product_id.display_name,
            "| REQUIRED:", move.product_uom_qty, unit.name,
            "| BASE_REQUIRED:", round(base_demand, 6), base.name,
            "| AVAILABLE:", round(available, 6), base.name,
            "| RESERVED:", round(reserved, 6), base.name,
            "| SHORTAGE:", round(deficit, 6), base.name,
            "| SOURCE:", move.location_id.complete_name,
        )
    assert not conversion_errors, f"Unit conversion errors: {conversion_errors}"
    assert M.search_count([]) == start_mo + 1, "MO create mismatch"
    assert SM.search_count([("state", "=", "done")]) == start_done, (
        "MO confirmation unexpectedly posted stock")
    assert Q.search_count([]) == start_quants, (
        "MO confirmation unexpectedly changed stock quant count")
    print("SHORTAGE_COMPONENT_COUNT:", len(missing))
    for sku, shortage, unit in missing:
        print("SHORTAGE:", sku, round(shortage, 6), unit)
    print("WIP_ROUTING_CHECK_REQUIRED: validate where WIP is produced, "
          "transferred and consumed before Mark as Done")
    print("MO_REQUIREMENTS_AUDIT_OK: confirmed MO + quantities + availability checked")
finally:
    env.cr.rollback()
    env.invalidate_all()
    assert M.search_count([]) == start_mo, "MO count not restored"
    assert SM.search_count([("state", "=", "done")]) == start_done, (
        "Posted stock moves not restored")
    assert Q.search_count([]) == start_quants, "Quant count not restored"
    print("MO_REQUIREMENTS_ROLLBACK_CONFIRMED: no transactions retained")
