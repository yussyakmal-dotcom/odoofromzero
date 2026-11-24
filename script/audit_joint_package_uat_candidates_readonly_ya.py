"""READ ONLY: identify REAL multi-kitchen Paket UAT candidate in published slots.

Odoo shell on erp-yussyakmal-mrp-test only. No warehouse/BoM/master/RO/MO
mutation. A matching candidate is for later rollback E2E test; this audit
does NOT reserve materials or certify inventory availability.
"""
from collections import defaultdict

assert env.cr.dbname == "erp-yussyakmal-mrp-test", "WRONG DATABASE"
print("DATABASE:", env.cr.dbname)
print("MODE: READ_ONLY_MULTI_KITCHEN_PACKAGE_UAT_CANDIDATES")

C = env["product.category"].sudo().search([
    ("complete_name", "=", "All / Produk Jadi / Paket")])
assert len(C) == 1, "Need exact unique Paket category"
packages = env["product.product"].sudo().search([("categ_id", "=", C.id)])
published = env["ya.production.planning"].sudo().search([
    ("state", "=", "published")], order="delivery_date desc, slot")
by_slot = defaultdict(lambda: defaultdict(list))
for planning in published:
    slot_key = (str(planning.delivery_date), planning.slot)
    for row in planning.line_ids:
        if row.max_capacity > 0:
            by_slot[slot_key][row.product_id.id].append(row)
print("PUBLISHED_SLOT_COUNT:", len(by_slot))
print("SLOT_SAMPLES:", sorted(by_slot, reverse=True)[:12])

Bom = env["mrp.bom"].sudo()
valid_boms = {}
for package in packages:
    boms = Bom.search([
        ("active", "=", True), ("type", "=", "normal"),
        ("product_tmpl_id", "=", package.product_tmpl_id.id),
        "|", ("product_id", "=", False),
        ("product_id", "=", package.id),
    ])
    if len(boms) != 1:
        continue
    bom = boms[0]
    qty = bom.product_uom_id._compute_quantity(
        bom.product_qty, package.uom_id, round=False)
    if abs(qty - 1.0) > 1e-9:
        continue
    kitchen_finished = set()
    for bom_line in bom.bom_line_ids:
        comp = bom_line.product_id
        category = comp.categ_id.complete_name or ""
        if (category.startswith("All / Produk Jadi /") and
                not category.startswith("All / Produk Jadi / Paket")):
            kitchen_finished.add(comp.id)
    if kitchen_finished:
        valid_boms[package.id] = (package, bom, kitchen_finished)

candidates = []
ambiguous = 0
missing_kitchen = 0
for (date, slot), routes in sorted(by_slot.items(), reverse=True):
    for package, bom, finished in valid_boms.values():
        if not all(len(routes.get(component, [])) == 1 for component in finished):
            if any(len(routes.get(component, [])) > 1 for component in finished):
                ambiguous += 1
            else:
                missing_kitchen += 1
            continue
        codes = {routes[component][0].planning_id.kitchen_code
                 for component in finished}
        if len(codes) < 2:
            continue
        maxes = []
        for component in finished:
            row = routes[component][0]
            maxes.append((row.product_id.default_code or str(component),
                          row.planning_id.kitchen_code,
                          row.max_capacity,
                          row.bom_id.id if row.bom_id else None))
        candidates.append((date, slot, package.default_code or package.id,
                           package.display_name, bom.id, sorted(codes),
                           sorted(maxes)))
print("VALID_PACKAGE_WITH_FINISHED_COMPONENTS:", len(valid_boms))
print("CANDIDATE_MULTI_KITCHEN_SLOT_COMBINATIONS:", len(candidates))
print("MISSING_ELIGIBLE_KITCHEN_ROUTE_COMBINATIONS:", missing_kitchen)
print("AMBIGUOUS_KITCHEN_ROUTE_COMBINATIONS:", ambiguous)
for sample in candidates[:12]:
    date, slot, sku, name, bom, codes, maxes = sample
    print("CANDIDATE:", date, slot, sku, name,
          "ASSEMBLY_BOM:", bom, "KITCHENS:", codes,
          "KITCHEN_PLANNING:", maxes)
print("NOTE: Use only an actual candidate's delivery date/slot after")
print("      checking RO source, group permissions and test inventory.")
print("      No extra Planning/BoM routes or false kitchen origins created.")
print("READ_ONLY_MULTI_KITCHEN_PAKET_CANDIDATES_OK")
