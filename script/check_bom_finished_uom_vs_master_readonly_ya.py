"""Read-only: compare finished-product BoM UoM versus product stock UoM.
Run on erp-yussyakmal-mrp-test only. No writes, transactions, or commits.
"""
from collections import Counter
assert env.cr.dbname == "erp-yussyakmal-mrp-test", "STOP: wrong database"

Bom = env["mrp.bom"].sudo().with_context(active_test=False)
print("DATABASE:", env.cr.dbname)
print("MODE: READ_ONLY_BOM_FINISHED_UOM_VS_PRODUCT_MASTER")
print("FIELDS:", {field: (Bom._fields[field].type if field in Bom._fields else "MISSING")
                  for field in ("product_id", "product_tmpl_id", "product_qty",
                                "product_uom_id", "type", "picking_type_id")})

boms = Bom.search([])
stats = Counter()
examples = []
for bom in boms:
    product = bom.product_id or bom.product_tmpl_id.product_variant_id
    if not product:
        stats["no_unique_finished_product"] += 1
        continue
    master_uom = product.uom_id
    bom_uom = bom.product_uom_id
    if not bom_uom:
        stats["bom_uom_missing"] += 1
        continue
    if bom_uom == master_uom:
        stats["same_uom"] += 1
        continue
    stats["different_uom"] += 1
    if len(examples) < 60:
        examples.append({
            "bom_id": bom.id,
            "sku": product.default_code,
            "product": product.display_name,
            "bom_qty": bom.product_qty,
            "bom_uom": bom_uom.name,
            "master_uom": master_uom.name,
            "warehouse": (bom.picking_type_id.warehouse_id.name
                          if bom.picking_type_id and bom.picking_type_id.warehouse_id else "(none)"),
        })

print("BOM_TOTAL:", len(boms))
print("SAME_UOM:", stats["same_uom"])
print("DIFFERENT_UOM:", stats["different_uom"])
print("NO_UNIQUE_FINISHED_PRODUCT:", stats["no_unique_finished_product"])
print("BOM_UOM_MISSING:", stats["bom_uom_missing"])
for row in examples:
    print("UOM_MISMATCH_SAMPLE:", row)
print("NOTE: quantity on BoM is batch output; product master uom is unit, not batch qty.")
print("READ_ONLY_BOM_MASTER_UOM_COMPARE_OK")
