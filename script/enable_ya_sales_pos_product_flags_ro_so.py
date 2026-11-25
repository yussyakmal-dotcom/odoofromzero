"""YA master product Sales+POS enablement — guarded two-step dry run/apply.

ONLY erp-yussyakmal-mrp-test-RO_SO.
Default: read-only. To write explicitly set YA_APPLY_PRODUCT_SALES_POS=YES
on the Odoo shell process; see checkpoint. Idempotent ORM updates.
"""
import os

DB = "erp-yussyakmal-mrp-test-RO_SO"
assert env.cr.dbname == DB, "REFUSED: wrong DB: %s" % env.cr.dbname

APPLY = os.environ.get("YA_APPLY_PRODUCT_SALES_POS") == "YES"
EXPECTED = {
    "All / Produk Jadi": (9, 757),
    "All / Konsinyasi Masuk": (11, 314),
}
Category = env["product.category"].sudo()
Template = env["product.template"].sudo()
assert "sale_ok" in Template._fields, "sale_ok not found"
assert "available_in_pos" in Template._fields, "available_in_pos not found"

def category_path(cat):
    parts = []
    while cat:
        parts.append(cat.name)
        cat = cat.parent_id
    return " / ".join(reversed(parts))

print("DATABASE:", env.cr.dbname)
print("MODE:", "APPLY_GUARDED_YA_SALES_POS" if APPLY else "DRY_RUN_READ_ONLY")

batches = []
for full_name, (category_id, expected_size) in EXPECTED.items():
    cat = Category.browse(category_id).exists()
    assert cat and category_path(cat) == full_name, (
        "STOP_CATEGORY_CHANGED: %s ID=%s" % (full_name, category_id)
    )
    subtree = Category.search([("id", "child_of", cat.id)])
    products = Template.search([("categ_id", "in", subtree.ids)])
    assert len(products) == expected_size, (
        "STOP_COUNT_CHANGED: %s expected=%s actual=%s" %
        (full_name, expected_size, len(products))
    )
    sale_off = products.filtered(lambda p: not p.sale_ok)
    pos_off = products.filtered(lambda p: not p.available_in_pos)
    print("TARGET:", full_name, "CAT_ID:", cat.id,
          "SUBCATEGORY_COUNT:", len(subtree),
          "TEMPLATES:", len(products),
          "SALE_FALSE:", len(sale_off),
          "POS_FALSE:", len(pos_off))
    batches.append((full_name, products, sale_off | pos_off))

assert len(set().union(*(set(products.ids) for _, products, _ in batches))) == 1071, (
    "STOP: expected exactly 1071 unique templates in target categories"
)

if APPLY:
    print("APPLY_ACKNOWLEDGED: YES")
    total_changed = 0
    for full_name, products, candidates in batches:
        if candidates:
            candidates.write({"sale_ok": True, "available_in_pos": True})
        # Read back from ORM in same transaction: no partial-success commit.
        remaining = products.filtered(lambda p: not p.sale_ok or not p.available_in_pos)
        assert not remaining, "STOP_POSTCHECK_FAILED: %s" % full_name
        total_changed += len(candidates)
        print("UPDATED:", full_name, "TEMPLATES_CHANGED:", len(candidates))
    print("UPDATED_TOTAL:", total_changed)
    # Odoo shell rolls back on exit unless the transaction is committed.
    # Commit only after both target categories have passed every post-check.
    env.cr.commit()
    print("APPLY_COMMITTED_TO_DB")
    print("VERIFY_WITH_FRESH_READ_ONLY_AUDIT")
else:
    print("NO_WRITES_PERFORMED")
    print("DRY_RUN_PASS")
