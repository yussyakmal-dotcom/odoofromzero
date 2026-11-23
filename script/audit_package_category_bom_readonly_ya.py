"""Read-only audit: Paket SKU identification from All / Produk Jadi / Paket.

Test database only. Reports exact category and per-package BoM composition.
No writes, no MOs, no stock moves.
"""
assert env.cr.dbname == "erp-yussyakmal-mrp-test", "WRONG DATABASE"
print("DATABASE:", env.cr.dbname)
print("MODE: READ_ONLY_PACKAGE_CATEGORY_BOM")
Category = env["product.category"].sudo()
Product = env["product.product"].sudo()
Bom = env["mrp.bom"].sudo()
target = Category.search([("complete_name", "=", "All / Produk Jadi / Paket")])
print("CATEGORY_MATCH_COUNT:", len(target))
for c in target:
    print("PACKAGE_CATEGORY:", c.id, c.complete_name, "PARENT:", c.parent_id.complete_name)
if len(target) != 1:
    print("BLOCKER: expected one exact category path; do not classify automatically")
else:
    child_categories = Category.search([("id", "child_of", target.id)])
    print("CATEGORY_DESCENDANT_COUNT_INCLUDING_SELF:", len(child_categories))
    if len(child_categories) > 1:
        print("REVIEW: descendants exist; owner must decide if included")
        for cat in child_categories:
            print("CATEGORY_PATH:", cat.id, cat.complete_name)
    package_products = Product.search([("categ_id", "=", target.id)])
    print("PACKAGE_SKU_COUNT_EXACT_CATEGORY:", len(package_products))
    for product in package_products.sorted(
            lambda p: (p.default_code or "", p.id)):
        boms = Bom.search([
            ("active", "=", True),
            ("product_tmpl_id", "=", product.product_tmpl_id.id),
            "|", ("product_id", "=", False), ("product_id", "=", product.id),
        ])
        print("PACKAGE_SKU:", product.default_code or "-", product.display_name,
              "| SKU_ID:", product.id, "| BOM_MATCHES:", len(boms))
        if len(boms) != 1:
            print("  REVIEW_BOM_COUNT:", len(boms))
        for bom in boms:
            print("  BOM:", bom.id, "| TYPE:", bom.type,
                  "| OUTPUT_QTY:", bom.product_qty, "| UOM:",
                  bom.product_uom_id.name,
                  "| COMPONENT_COUNT:", len(bom.bom_line_ids))
            for line in bom.bom_line_ids:
                comp = line.product_id
                print("    COMPONENT:", comp.default_code or "-",
                      "| QTY:", line.product_qty,
                      "| UOM:", line.product_uom_id.name,
                      "| CATEGORY:", comp.categ_id.complete_name)
                if not comp.categ_id.complete_name.startswith("All / Produk Jadi"):
                    print("    REVIEW_COMPONENT_NOT_UNDER_FINISHED_CATEGORY")
print("READ_ONLY_PACKAGE_CATEGORY_BOM_OK")
