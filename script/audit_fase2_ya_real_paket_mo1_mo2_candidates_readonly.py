"""READ ONLY: discover REAL Paket BoMs usable in MO1/MO2 mixed test.

Check cross-kitchen Paket final SKU, its active one-Paket assembly BoM,
and at least two kitchen components with Published Planning on SAME
delivery date/slot. No model writes, no master additions, no stock moves.
Do not invent Paket products or use unplanned component as fake kitchen SKU.
"""
from collections import defaultdict

DB = "erp-yussyakmal-mrp-test-RO_SO"
assert env.cr.dbname == DB, "STOP_WRONG_DATABASE"
env.cr.rollback()
env.cr.execute("SET TRANSACTION READ ONLY")
env.cr.execute("SHOW transaction_read_only")
assert env.cr.fetchone()[0] == "on", "STOP_CANNOT_ENFORCE_READ_ONLY"

CATEGORY = "All / Produk Jadi / Paket"
print("DATABASE:", env.cr.dbname)
print("MODE: READ_ONLY_REAL_PAKET_BOM_MO1_MO2_CANDIDATE_DISCOVERY")

Cat = env["product.category"].sudo().search([
    ("complete_name", "=", CATEGORY)
])
assert len(Cat) <= 1, "STOP_PAKET_CATEGORY_AMBIGUOUS"
print("PAKET_CATEGORY:", [(c.id, c.complete_name) for c in Cat])
products = (env["product.product"].sudo().search(
    [("categ_id", "in", Cat.ids)], order="id", limit=150
) if Cat else env["product.product"].browse())
all_count = (env["product.product"].sudo().search_count([
    ("categ_id", "in", Cat.ids)
]) if Cat else 0)
print("PAKET_PRODUCTS:", all_count, "CHECKED:", len(products),
      "TRUNCATED:", all_count > len(products))

Planning = env["ya.production.planning"].sudo()
lines_by_slot = defaultdict(lambda: defaultdict(list))
published = Planning.search([("state", "=", "published")])
for p in published:
    for line in p.line_ids:
        lines_by_slot[(p.delivery_date, p.slot)][line.product_id.id].append(
            line
        )
print("PUBLISHED_PLANNING:", len(published),
      "DATE_SLOTS:", len(lines_by_slot))

Bom = env["mrp.bom"].sudo()
valid_package_boms = 0
multi_kitchen_candidates = []
reasons = defaultdict(int)
for product in products:
    boms = Bom.search([
        ("active", "=", True),
        ("type", "=", "normal"),
        ("product_tmpl_id", "=", product.product_tmpl_id.id),
        "|", ("product_id", "=", False), ("product_id", "=", product.id),
    ])
    if len(boms) != 1:
        reasons["NOT_EXACTLY_ONE_ACTIVE_NORMAL_BOM"] += 1
        continue
    bom = boms[0]
    package_qty = bom.product_uom_id._compute_quantity(
        bom.product_qty, product.uom_id, round=False
    )
    if abs(package_qty - 1.0) > 1e-9:
        reasons["ASSEMBLY_OUTPUT_NOT_ONE_PAKET"] += 1
        continue
    if not bom.bom_line_ids:
        reasons["NO_COMPONENTS"] += 1
        continue
    valid_package_boms += 1
    for (date, slot), routes in sorted(lines_by_slot.items()):
        kitchen_components = []
        pck_components = []
        kitchens = set()
        ambiguous = []
        for item in bom.bom_line_ids:
            component = item.product_id
            qty = item.product_uom_id._compute_quantity(
                item.product_qty, component.uom_id, round=False
            )
            if qty <= 0 or component.categ_id.complete_name == CATEGORY:
                ambiguous.append((component.id, "invalid_nested_or_qty"))
                continue
            matches = routes.get(component.id, [])
            if len(matches) > 1:
                ambiguous.append((component.id, "duplicate_planning_route"))
                continue
            if len(matches) == 0:
                pck_components.append({
                    "sku": component.default_code,
                    "id": component.id,
                    "qty_per_package": qty,
                    "source": "UNROUTED_PCK_REVIEW_REQUIRED",
                })
                continue
            plan_line = matches[0]
            try:
                kitchen_bom = plan_line._capacity_bom()
            except Exception as exc:
                ambiguous.append((component.id, "invalid_planning_bom"))
                continue
            if not kitchen_bom or not kitchen_bom.picking_type_id:
                ambiguous.append((component.id, "no_native_kitchen_picking_type"))
                continue
            kitchen = kitchen_bom.picking_type_id.warehouse_id
            k_qty = plan_line.uom_id._compute_quantity(
                plan_line.max_capacity, component.uom_id, round=False
            )
            if (not kitchen or not kitchen.lot_stock_id
                    or k_qty < 2 or abs(qty - round(qty)) > 1e-9):
                ambiguous.append((component.id, "invalid_component_capacity_or_uom"))
                continue
            kitchens.add(kitchen.id)
            kitchen_components.append({
                "sku": component.default_code,
                "id": component.id,
                "per_package": qty,
                "kitchen": kitchen.code,
                "planning_line_id": plan_line.id,
                "published_max": k_qty,
                "bom_id": kitchen_bom.id,
                "product_tracking": component.tracking,
            })
        if len(kitchen_components) >= 2 and len(kitchens) >= 2 and not ambiguous:
            candidate = {
                "paket_sku": product.default_code,
                "paket_id": product.id,
                "assembly_bom_id": bom.id,
                "date": str(date), "slot": slot,
                "distinct_kitchens": len(kitchens),
                "kitchen_components": kitchen_components,
                "pck_components": pck_components,
                "unrouted_pck_components_require_review": bool(
                    pck_components
                ),
            }
            multi_kitchen_candidates.append(candidate)
            if len(multi_kitchen_candidates) <= 10:
                print("ELIGIBLE_CROSS_KITCHEN_PAKET_CANDIDATE:", candidate)

print("VALID_SINGLE_OUTPUT_PAKET_BOMS:", valid_package_boms)
print("MULTI_KITCHEN_PAKET_PUBLISHED_SLOT_MATCHES:",
      len(multi_kitchen_candidates))
print("REJECTION_COUNTS:", sorted(reasons.items()))
if multi_kitchen_candidates:
    print("REAL_PAKET_MO1_MO2_CANDIDATE_DISCOVERED_PASS")
else:
    print("REAL_PAKET_CANDIDATE_NOT_PROVEN: do not fabricate Paket BoM;")
    print("next test must first verify real product/BoM/Planning setup.")
print("NO_SNAPSHOT_PACKAGE_ROWS_REQUIRED_FOR_READONLY_DISCOVERY")
print("READ_ONLY_FASE2_REAL_PAKET_CANDIDATE_AUDIT_COMPLETE")
print("NO_MASTER_MO_SALES_STOCK_OR_DO_MUTATION")
env.cr.rollback()
