"""READ ONLY: verify one BoM output = exactly ONE finished Paket.

Run only with Odoo shell on erp-yussyakmal-mrp-test.
This is a targeted master-data audit, never a BoM update.
Compare BoM product_qty in BoM UoM AND converted to Paket base UoM;
do not interpret a multi-batch BoM as a one-unit package.
"""
from collections import Counter
from math import isclose

assert env.cr.dbname == "erp-yussyakmal-mrp-test", "TEST DB ONLY"
Category = env["product.category"].sudo()
Product = env["product.product"].sudo()
Bom = env["mrp.bom"].sudo()

category = Category.search([
    ("complete_name", "=", "All / Produk Jadi / Paket")
])
assert len(category) == 1, "Expected one unique All / Produk Jadi / Paket category"
packages = Product.search([("categ_id", "=", category.id)], order="default_code,id")
counts = Counter()
non_one = []
one_examples = []
no_bom = []
multiple = []
errors = []
seen = set()

print("DATABASE:", env.cr.dbname)
print("MODE: READ_ONLY_PACKAGE_BOM_OUTPUT_QTY")
print("PACKAGE_CATEGORY:", category.complete_name, "CATEGORY_ID:", category.id)
print("CURRENT_PACKAGE_SKU_COUNT:", len(packages))
print("RULE: each active normal Paket BoM must output exactly 1 Paket in product base UoM")
for product in packages:
    code = product.default_code or str(product.id)
    boms = Bom.search([
        ("active", "=", True),
        ("type", "=", "normal"),
        ("product_tmpl_id", "=", product.product_tmpl_id.id),
        "|", ("product_id", "=", False), ("product_id", "=", product.id),
    ], order="id")
    if not boms:
        counts["PACKAGE_SKUS_WITHOUT_ACTIVE_NORMAL_BOM"] += 1
        no_bom.append((code, product.display_name))
        continue
    if len(boms) > 1:
        counts["PACKAGE_SKUS_WITH_MULTIPLE_BOMS"] += 1
        multiple.append((code, [b.id for b in boms]))
    else:
        counts["PACKAGE_SKUS_WITH_ONE_BOM"] += 1
    for bom in boms:
        key = (product.id, bom.id)
        if key in seen:
            continue
        seen.add(key)
        try:
            output = bom.product_uom_id._compute_quantity(
                bom.product_qty, product.uom_id, round=False)
        except Exception as exc:
            counts["BOM_UOM_CONVERSION_ERROR"] += 1
            errors.append((code, bom.id, str(exc)[:140]))
            continue
        detail = (
            code, product.display_name, bom.id,
            bom.product_qty, bom.product_uom_id.name,
            output, product.uom_id.name
        )
        if output <= 0:
            counts["BOM_OUTPUT_ZERO_OR_NEGATIVE"] += 1
            non_one.append(detail)
        elif isclose(output, 1.0, rel_tol=1e-9, abs_tol=1e-9):
            counts["BOM_OUTPUT_EQUAL_ONE"] += 1
            if len(one_examples) < 12:
                one_examples.append(detail)
        elif output > 1.0:
            counts["BOM_OUTPUT_GREATER_THAN_ONE"] += 1
            non_one.append(detail)
        else:
            counts["BOM_OUTPUT_LESS_THAN_ONE"] += 1
            non_one.append(detail)

print("COUNTS:", sorted(counts.items()))
print("BOM_OUTPUT_ONE_EXAMPLES:", one_examples)
print("=== ALL BOM OUTPUT NOT EQUAL TO ONE ===")
print("NOT_ONE_COUNT:", len(non_one))
for detail in non_one:
    print("NON_ONE: SKU=%s NAME=%s BOM_ID=%s BOM_QTY=%s BOM_UOM=%s "
          "OUTPUT_IN_PACKAGE_UOM=%s PACKAGE_UOM=%s" % detail)
print("MISSING_BOM_COUNT:", len(no_bom))
print("MISSING_BOM_SKUS:", no_bom[:100])
print("MULTIPLE_BOM_COUNT:", len(multiple))
print("MULTIPLE_BOM_SKUS:", multiple[:100])
print("UOM_CONVERSION_ERRORS:", errors)
print("NOTE: counts relate to the current Paket category, after any master recategorization.")
print("NOTE: no BoM/product/category/stock/RO/MO/GL modifications.")
print("READ_ONLY_PACKAGE_BOM_OUTPUT_QTY_OK")
