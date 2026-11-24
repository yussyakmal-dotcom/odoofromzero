"""READ-ONLY stock readiness for REAL Hampers 12114 upstream MOs.

Inspects manufacturing BoMs of component SKUs 11999 (PST, 7 output),
12014 (ROTI, 7 output), 12019 (PST, 5 output) in Published Planning
2026-11-24 S1. Reads raw material quantities and available quants in
each actual kitchen source location; does NOT create/confirm/finish MOs,
invent stock, reserve, or make any transfers. Not a replacement for
native Odoo reserve/stock validation; review lot/phantom/multilevel BoMs.
"""
from collections import defaultdict
from odoo.tools import float_compare

assert env.cr.dbname == "erp-yussyakmal-mrp-test", "REFUSED: WRONG DB"
print("DATABASE:", env.cr.dbname)
print("MODE: READ_ONLY_PAKET_12114_MO_MATERIAL_READINESS")

DATE, SLOT = "2026-11-24", "S1"
sku_outputs = {"11999": 7, "12014": 7, "12019": 5}
Products = env["product.product"].sudo()
Planning = env["ya.production.planning"].sudo()
Quant = env["stock.quant"].sudo()
plans = Planning.search([
    ("delivery_date", "=", DATE), ("slot", "=", SLOT),
    ("state", "=", "published")])
assert plans, "Actual Published Planning no longer exists"
planning_lines = plans.mapped("line_ids")
print("DATE_SLOT:", DATE, SLOT)
print("SKUS:", sku_outputs)

short_count = 0
zero_count = 0
tracking_rows = 0
summary = []
for code, mo_qty in sorted(sku_outputs.items()):
    products = Products.search([("default_code", "=", code)], limit=2)
    assert len(products) == 1, "Expected unique real SKU %s" % code
    product = products[0]
    candidates = planning_lines.filtered(
        lambda x: x.product_id == product and x.max_capacity > 0)
    assert len(candidates) == 1, (
        "Missing or ambiguous Published Planning SKU %s" % code)
    row = candidates[0]
    bom = row._capacity_bom()
    pt = bom.picking_type_id
    assert pt and pt.warehouse_id and pt.default_location_src_id
    assert pt.warehouse_id.company_id == env.company, "Kitchen company mismatch"
    kitchen = pt.warehouse_id
    raw_location = pt.default_location_src_id
    finished_location = pt.default_location_dest_id
    output = bom.product_uom_id._compute_quantity(
        bom.product_qty, product.uom_id, round=False)
    max_base = row.uom_id._compute_quantity(
        row.max_capacity, product.uom_id, round=False)
    assert float_compare(output, 0, precision_rounding=product.uom_id.rounding) > 0
    assert mo_qty <= max_base and abs(mo_qty / output - round(mo_qty / output)) < 1e-9
    factor = mo_qty / output
    print("MO:", code, "KITCHEN:", kitchen.code,
          "BOM_ID:", bom.id, "BOM_BATCH_OUTPUT:", output,
          "MO_TARGET:", mo_qty, "FACTOR:", factor,
          "RAW_LOCATION:", raw_location.complete_name,
          "FG_LOCATION:", finished_location.complete_name,
          "RAW_BOM_LINES:", len(bom.bom_line_ids))
    grouped = defaultdict(float)
    for raw in bom.bom_line_ids:
        raw_product = raw.product_id
        required = raw.product_uom_id._compute_quantity(
            raw.product_qty * factor, raw_product.uom_id, round=False)
        grouped[raw_product.id] += required
    if not grouped:
        print("WARNING: BOM", bom.id, "has no direct raw components")
    shortages = 0
    for raw_id, required in sorted(grouped.items()):
        material = Products.browse(raw_id)
        quants = Quant.search([
            ("product_id", "=", material.id),
            ("location_id", "=", raw_location.id),
            ("company_id", "=", kitchen.company_id.id),
        ])
        physical = sum(quants.mapped("quantity"))
        reserved = sum(quants.mapped("reserved_quantity"))
        usable = physical - reserved
        rounding = material.uom_id.rounding
        status = "ENOUGH" if float_compare(
            usable, required, precision_rounding=rounding) >= 0 else "INSUFFICIENT"
        if status == "INSUFFICIENT":
            shortages += 1
            short_count += 1
        if float_compare(usable, 0, precision_rounding=rounding) <= 0:
            zero_count += 1
        if material.tracking != "none":
            tracking_rows += 1
        print("  MATERIAL:", material.default_code or str(material.id),
              "NAME:", material.display_name,
              "NEED:", round(required, 4), material.uom_id.name,
              "PHYSICAL:", round(physical, 4),
              "RESERVED:", round(reserved, 4),
              "FREE:", round(usable, 4),
              "TRACKING:", material.tracking, "CHECK:", status)
    summary.append((code, kitchen.code, mo_qty, len(grouped), shortages))

print("MO_RAW_MATERIAL_SUMMARY:", summary)
print("SHORT_MATERIAL_COMBINATIONS:", short_count)
print("ZERO_OR_NEGATIVE_FREE_STOCK_ROWS:", zero_count)
print("LOT_TRACKED_MATERIAL_ROWS:", tracking_rows)
if short_count:
    print("PHYSICAL_MO_DONE_UAT: NOT READY with current kitchen raw quants.")
    print("NEXT: inspect existing CDC/kitchen replenishment SOP; do not")
    print("      fabricate quants or override the no-negative-stock rule.")
else:
    print("PHYSICAL_MO_DONE_UAT: raw BoM quantities appear sufficient,")
    print("      but native reservation/lot tracking and operator SOP remain")
    print("      prerequisites before any rollback stock validation.")
print("READ_ONLY_PAKET_12114_MATERIALS_OK")
