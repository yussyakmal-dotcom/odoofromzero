"""Read-only go/no-go for REAL Paket UAT dates/slots and whole-BoM capacity.

Run ONLY in test Odoo shell. No master/RO/batch/MO/stock writes.
Goal: distinguish a plausible two-kitchen BoM match from a date-slot that
CAN actually stage a new immutable Pre Produksi snapshot (unique date+slot).
One-Paket feasibility is advisory; physical stock and SOP remain separate.
"""
from collections import defaultdict
from odoo.tools import float_compare

assert env.cr.dbname == "erp-yussyakmal-mrp-test", "REFUSED: WRONG DB"
print("DATABASE:", env.cr.dbname)
print("MODE: READ_ONLY_PACKAGE_UAT_SLOT_READINESS")

Wh = env["stock.warehouse"].sudo()
pck = Wh.search([("code", "=", "PCK")])
assert len(pck) == 1 and pck.lot_stock_id, "Unique PCK/Stock required"

category = env["product.category"].sudo().search([
    ("complete_name", "=", "All / Produk Jadi / Paket"),
])
assert len(category) == 1, "Unique Paket category required"
P = env["product.product"].sudo()
Bom = env["mrp.bom"].sudo()
Planning = env["ya.production.planning"].sudo()
Batch = env["ya.packing.batch"].sudo()
Ordinary = env["ya.store.ro"].sudo()
Quants = env["stock.quant"].sudo()

slots = defaultdict(lambda: defaultdict(list))
for planning in Planning.search([("state", "=", "published")]):
    key = (str(planning.delivery_date), planning.slot)
    for line in planning.line_ids:
        if line.max_capacity > 0:
            slots[key][line.product_id.id].append(line)

package_boms = []
for package in P.search([("categ_id", "=", category.id)]):
    boms = Bom.search([
        ("active", "=", True), ("type", "=", "normal"),
        ("product_tmpl_id", "=", package.product_tmpl_id.id),
        "|", ("product_id", "=", False), ("product_id", "=", package.id),
    ])
    if len(boms) != 1:
        continue
    bom = boms[0]
    one = bom.product_uom_id._compute_quantity(
        bom.product_qty, package.uom_id, round=False)
    if abs(one - 1.0) > 1e-9:
        continue
    items = defaultdict(float)
    for part in bom.bom_line_ids:
        items[part.product_id.id] += part.product_uom_id._compute_quantity(
            part.product_qty, part.product_id.uom_id, round=False)
    if items:
        package_boms.append((package, bom, items))

print("SLOT_COUNT:", len(slots))
summary = []
free_candidates = []
busy_candidates = []
for date, slot in sorted(slots, reverse=True):
    batch = Batch.search([("delivery_date", "=", date),
                          ("slot", "=", slot)], limit=2)
    original = Ordinary.search([
        ("delivery_date", "=", date), ("slot", "=", slot),
        ("state", "=", "confirmed"),
    ])
    feasible = []
    not_feasible = 0
    for pkg, bom, items in package_boms:
        kitchen_parts = []
        kitchen_codes = set()
        other_parts = []
        all_mapped = True
        for pid, requirement in sorted(items.items()):
            product = P.browse(pid)
            category_name = product.categ_id.complete_name or ""
            if category_name.startswith("All / Produk Jadi /") and not (
                    category_name.startswith("All / Produk Jadi / Paket")):
                matched = slots[(date, slot)].get(pid, [])
                if len(matched) != 1:
                    all_mapped = False
                    break
                pl = matched[0]
                kitchen_codes.add(pl.planning_id.kitchen_code)
                kitchen_parts.append((product, requirement, pl))
            else:
                other_parts.append((product, requirement))
        if not all_mapped or len(kitchen_codes) < 2:
            continue

        max_ok = True
        plan_details = []
        for product, need, line in kitchen_parts:
            try:
                kitchen_bom = line._capacity_bom()
                bo = kitchen_bom.product_uom_id._compute_quantity(
                    kitchen_bom.product_qty, product.uom_id, round=False)
                cap = line.uom_id._compute_quantity(
                    line.max_capacity, product.uom_id, round=False)
                original_qty = sum(
                    row.uom_id._compute_quantity(
                        row.qty_requested, product.uom_id, round=False)
                    for ro in original if ro.planning_id == line.planning_id
                    for row in ro.line_ids
                    if row.product_id == product and row.qty_requested > 0
                )
                if (bo <= 0 or abs(bo - round(bo)) > 1e-9 or
                        cap < 0 or abs(cap - round(cap)) > 1e-9 or
                        abs(need - round(need)) > 1e-9):
                    max_ok = False
                    break
                gross = need + original_qty
                mo = int(((gross + bo - 1) // bo) * bo)
                max_multiple = int((cap // bo) * bo)
                # Paket first: max production need not cover all original
                # store RO demand, but MUST cover protected Paket quantity.
                if max_multiple < need:
                    max_ok = False
                plan_details.append((
                    product.default_code or str(product.id),
                    line.planning_id.kitchen_code,
                    round(need, 3), int(bo), int(cap), int(mo),
                    int(max_multiple), round(original_qty, 3)
                ))
            except Exception as exc:
                max_ok = False
                plan_details.append(("ROUTE_ERROR", type(exc).__name__, str(exc)[:100]))
                break
        if not max_ok:
            not_feasible += 1
            continue

        other_requirements = []
        for product, need in other_parts:
            stock = sum(Quants.search([
                ("product_id", "=", product.id),
                ("location_id", "=", pck.lot_stock_id.id),
                ("company_id", "=", pck.company_id.id),
            ]).mapped("quantity"))
            other_requirements.append((
                product.default_code or str(product.id),
                round(need, 3), round(stock, 3)
            ))
        candidate = {
            "date": date, "slot": slot, "pkg": pkg.default_code or str(pkg.id),
            "name": pkg.display_name, "bom": bom.id,
            "kitchens": sorted(kitchen_codes),
            "parts": plan_details, "pck": other_requirements,
            "already_batch": [x.id for x in batch],
            "existing_ordinary_ro": len(original),
        }
        feasible.append(candidate)
        if batch:
            busy_candidates.append(candidate)
        else:
            free_candidates.append(candidate)
    row = (date, slot, [x.id for x in batch], len(original),
           len(feasible), not_feasible)
    summary.append(row)

for row in summary:
    print("SLOT:", row[0], row[1], "BATCH_IDS:", row[2],
          "CONFIRMED_ORDINARY_RO:", row[3],
          "CAPACITY_FEASIBLE_PAKET:", row[4],
          "CAPACITY_LIMITED_PAKET:", row[5])
print("FREE_SLOT_CANDIDATES:", len(free_candidates))
print("ALREADY_BATCHED_SLOT_CANDIDATES:", len(busy_candidates))
for candidate in free_candidates[:10]:
    print("FREE_CANDIDATE:", candidate)
for candidate in busy_candidates[:3]:
    print("BUSY_EXAMPLE:", candidate["date"], candidate["slot"],
          candidate["pkg"], "BATCH_IDS:", candidate["already_batch"])

if not free_candidates:
    print("UAT_SLOT_ACTION: No unoccupied Published Planning slot matches "
          "a feasible two-kitchen Paket. Use a new authorized test-only "
          "date/slot and normal Published Planning/RO SOP; do NOT reuse "
          "an existing Pre Produksi batch or change production data.")
else:
    print("UAT_SLOT_ACTION: Choose a FREE_CANDIDATE for controlled rollback "
          "testing, then inspect source RO, stock and user permissions.")
print("READ_ONLY_PACKAGE_UAT_SLOT_READINESS_OK")
