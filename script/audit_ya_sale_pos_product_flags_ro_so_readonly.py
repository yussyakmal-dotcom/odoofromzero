"""Read-only Odoo 19 audit: YA categories for Sales and Point of Sale.

ONLY the isolated Fase 2 clone. Does not write or commit.
Run with Odoo shell --no-http < script/audit_ya_sale_pos_product_flags_ro_so_readonly.py
"""
assert env.cr.dbname == "erp-yussyakmal-mrp-test-RO_SO", (
    "REFUSED: only Fase 2 RO_SO clone")
print("DATABASE:", env.cr.dbname)
print("MODE: READ_ONLY_PRODUCT_SALES_POS_CATEGORY_AUDIT")

Template = env["product.template"].sudo()
Category = env["product.category"].sudo()

for field_name in ("sale_ok", "available_in_pos", "categ_id"):
    field = Template._fields.get(field_name)
    print("PRODUCT_TEMPLATE_FIELD:", field_name,
          field.type if field else "MISSING")
print("PRODUCT_PRODUCT_POS_FIELD:",
      "available_in_pos" in env["product.product"]._fields)
print("POS_MODULE_STATES:", [
    (m.name, m.state) for m in env["ir.module.module"].sudo().search([
        ("name", "in", ["point_of_sale", "sale", "sale_stock"])
    ])
])

def full_path(category):
    names = []
    node = category
    while node:
        names.append(node.name)
        node = node.parent_id
    return " / ".join(reversed(names))

all_cats = Category.search([])
targets = ["All / Produk Jadi", "All / Konsinyasi Masuk"]
for target in targets:
    exact = all_cats.filtered(lambda c: full_path(c) == target)
    print("TARGET:", target, "EXACT_CATEGORY_COUNT:", len(exact),
          "IDS:", exact.ids)
    if len(exact) != 1:
        print("STOP_TARGET_NOT_UNIQUE:", target)
        continue
    cat = exact[0]
    subtree = Category.search([("id", "child_of", cat.id)])
    print("TARGET_SUBTREE:", target, "CATEGORY_COUNT:", len(subtree),
          "PATH_SAMPLE:", [full_path(c) for c in subtree[:15]])
    for scope, category_ids in [
        ("EXACT_ONLY", [cat.id]),
        ("WITH_CHILDREN", subtree.ids),
    ]:
        products = Template.search([("categ_id", "in", category_ids)])
        no_sale = products.filtered(lambda p: not p.sale_ok)
        if "available_in_pos" in Template._fields:
            no_pos = products.filtered(lambda p: not p.available_in_pos)
        else:
            no_pos = Template.browse()
        print("SCOPE:", scope, "TARGET:", target,
              "TEMPLATE_COUNT:", len(products),
              "SALE_FALSE:", len(no_sale),
              "POS_FALSE:", len(no_pos),
              "EXAMPLE_IDS_NEED_SALES:", no_sale.ids[:12],
              "EXAMPLE_IDS_NEED_POS:", no_pos.ids[:12])
print("AUDIT_COMPLETE_READ_ONLY")
