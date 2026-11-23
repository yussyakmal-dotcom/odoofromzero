"""READ ONLY: summarize all Paket BoMs by component category and flag review cases.

Odoo shell on erp-yussyakmal-mrp-test. This script makes no writes.
"""
from collections import Counter

assert env.cr.dbname == "erp-yussyakmal-mrp-test", "WRONG DATABASE"
Categ = env["product.category"].sudo()
Product = env["product.product"].sudo()
Bom = env["mrp.bom"].sudo()
pack_categories = Categ.search([("complete_name", "=", "All / Produk Jadi / Paket")])
print("DATABASE:", env.cr.dbname)
print("MODE: READ_ONLY_PACKAGE_BOM_CATEGORY_SUMMARY")
print("CATEGORY_MATCH_COUNT:", len(pack_categories))
if len(pack_categories) != 1:
    print("BLOCKER: Package category path not unique")
else:
    cat = pack_categories[0]
    products = Product.search([("categ_id", "=", cat.id)])
    summary = Counter()
    bom_count_hist = Counter()
    sku_classes = Counter()
    review = []
    print("PACKAGE_SKU_COUNT_EXACT_CATEGORY:", len(products))
    for product in products:
        boms = Bom.search([
            ("active", "=", True),
            ("product_tmpl_id", "=", product.product_tmpl_id.id),
            "|", ("product_id", "=", False), ("product_id", "=", product.id),
        ])
        bom_count_hist[len(boms)] += 1
        if len(boms) != 1:
            review.append((product.default_code or str(product.id), "BOM_COUNT", len(boms)))
            continue
        bom = boms[0]
        kinds = set()
        for line in bom.bom_line_ids:
            component_category = line.product_id.categ_id.complete_name or ""
            if component_category.startswith("All / Produk Jadi / Paket"):
                kind = "NESTED_PACKAGE"
            elif component_category.startswith("All / Produk Jadi /"):
                kind = "FINISHED_KITCHEN"
            elif component_category.startswith("All / Konsinyasi Masuk"):
                kind = "CONSIGNMENT"
            elif component_category.startswith("All / Packaging"):
                kind = "PACKAGING"
            else:
                kind = "OTHER_REVIEW"
            summary[kind] += 1
            kinds.add(kind)
            if kind in ("NESTED_PACKAGE", "OTHER_REVIEW"):
                review.append((product.default_code or str(product.id),
                               kind, line.product_id.default_code or line.product_id.id))
        if not kinds:
            review.append((product.default_code or str(product.id), "EMPTY_BOM", bom.id))
        sku_classes[";".join(sorted(kinds)) or "EMPTY_BOM"] += 1
    print("BOM_MATCH_COUNT_DISTRIBUTION:", sorted(bom_count_hist.items()))
    print("COMPONENT_LINE_COUNTS_BY_CATEGORY:", sorted(summary.items()))
    print("PACKAGE_SKU_CATEGORY_MIX:", sorted(sku_classes.items()))
    print("REVIEW_CASE_COUNT:", len(review))
    for entry in review[:80]:
        print("REVIEW:", entry)
    if len(review) > 80:
        print("REVIEW_MORE_NOT_SHOWN:", len(review) - 80)
print("READ_ONLY_PACKAGE_BOM_SUMMARY_OK")
