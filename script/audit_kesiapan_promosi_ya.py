"""Audit READ-ONLY sebelum mereplikasi konfigurasi test ke produksi.

Jalankan sekali untuk erp-yussyakmal-integer-test dan sekali untuk
erp-yussyakmal. Tidak ada CREATE/WRITE/COMMIT ataupun akses file privat.
"""


def main():
    e = globals().get("env")
    if e is None or e.cr.dbname not in (
        "erp-yussyakmal", "erp-yussyakmal-integer-test"
    ):
        raise RuntimeError("Database tidak termasuk dua target audit YA")

    print("DATABASE:", e.cr.dbname)
    print("MODE: AUDIT READ-ONLY PROMOSI MASTER/MODUL YA")
    modules = (
        "purchase", "purchase_stock", "sale", "point_of_sale", "mrp",
        "ya_purchase_multi_uom", "ya_integer_quantity", "ya_purchase_discount",
    )
    for name in modules:
        module = e["ir.module.module"].sudo().search([("name", "=", name)], limit=1)
        print("MODULE: %s | state=%s | latest_version=%s" % (
            name, module.state if module else "MISSING",
            module.latest_version if module else "-"))

    Products = e["product.product"].sudo().with_context(active_test=False)
    master_domain = [
        ("default_code", "!=", False),
        ("default_code", "not in", ["TIPS", "DISC"]),
    ]
    print("PRODUCT MASTER SKU:", Products.search_count(master_domain))
    print("PRODUCT TOTAL INCLUDING TECHNICAL:", Products.search_count([]))
    print("PRODUCTS PURCHASE_OK:", Products.search_count([("purchase_ok", "=", True)]))
    print("CATEGORIES:", e["product.category"].sudo().search_count([]))
    print("WAREHOUSES:", e["stock.warehouse"].sudo().search_count([]))
    print("UOMS (INCLUDING INACTIVE):", e["uom.uom"].sudo().with_context(
        active_test=False).search_count([]))
    print("ACCOUNT ACCOUNTS:", e["account.account"].sudo().search_count([]))

    if "ya.purchase.uom.rule" in e.registry.models:
        Rules = e["ya.purchase.uom.rule"].sudo().with_context(active_test=False)
        print("PURCHASE UOM RULES:", Rules.search_count([]))
        print("PURCHASE UOM RULES FACTOR=1:", Rules.search_count([("factor", "=", 1)]))
        product = Products.search([("default_code", "=", "10840")], limit=1)
        if product:
            rules = Rules.search([("product_id", "=", product.id)])
            print("SKU 10840 UOM BASE:", product.uom_id.name)
            for rule in rules:
                print("SKU 10840 RULE: %s | factor=%s | active=%s" % (
                    rule.purchase_label, rule.factor, rule.active))
    else:
        print("PURCHASE UOM RULES: MODEL TIDAK TERPASANG")

    print("PURCHASE ORDERS:", e["purchase.order"].sudo().search_count([]))
    print("STOCK MOVES:", e["stock.move"].sudo().search_count([]))
    Quant = e["stock.quant"].sudo()
    print("NONZERO QUANTS:", Quant.search_count([("quantity", "!=", 0)]))
    if "ya.purchase.discount.wizard" in e.registry.models:
        acl = e["ir.model.access"].sudo().search([
            ("model_id.model", "=", "ya.purchase.discount.wizard"),
            ("active", "=", True),
        ])
        print("DISCOUNT WIZARD ACL COUNT:", len(acl))
    else:
        print("DISCOUNT WIZARD: MODEL TIDAK TERPASANG")
    print("AUDIT_PROMOSI_YA_COMPLETE: tidak ada perubahan database")


main()
