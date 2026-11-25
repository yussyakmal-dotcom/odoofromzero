"""READ ONLY: identify native Odoo 19 sale discount functions and YA PO parity.

ONLY isolated Fase 2 clone. No create/write/commit. Use Odoo shell --no-http.
"""
assert env.cr.dbname == "erp-yussyakmal-mrp-test-RO_SO", "WRONG DATABASE"
print("DATABASE:", env.cr.dbname)
print("MODE: READ_ONLY_SALE_DISCOUNT_CAPABILITIES")

for model_name, names in [
    ("sale.order", ["order_line", "currency_id", "state", "amount_untaxed",
                    "amount_tax", "amount_total", "discount",
                    "discount_type", "global_discount", "global_discount_rate"]),
    ("sale.order.line", ["order_id", "product_id", "product_uom_qty",
                         "price_unit", "discount", "price_subtotal",
                         "price_tax", "price_total", "tax_id", "display_type",
                         "is_downpayment"]),
    ("sale.order.discount", ["sale_order_id", "discount_type",
                              "discount_percentage", "discount_amount",
                              "currency_id"]),
]:
    if model_name not in env.registry:
        print("MODEL_ABSENT:", model_name)
        continue
    model = env[model_name]
    print("MODEL:", model_name)
    for name in names:
        field = model._fields.get(name)
        print("FIELD:", name, field.type if field else "MISSING")
    for method in [
        "action_open_discount_wizard", "action_apply_discount",
        "_compute_amount", "_compute_tax_totals",
    ]:
        print("METHOD:", method, bool(callable(getattr(model, method, None))))

for module in env["ir.module.module"].sudo().search([
    ("name", "in", ["sale", "sale_management", "sale_stock",
                   "sale_discount", "ya_purchase_discount",
                   "ya_sale_production_capacity"])
]):
    print("MODULE:", module.name, module.state, module.latest_version)

View = env["ir.ui.view"].sudo()
for view in View.search([("model", "in", ["sale.order", "sale.order.discount"])]):
    arch = view.arch_db or ""
    if any(token in arch for token in [
        "discount", "Discount", "action_open_discount",
        "sale_order_discount",
    ]):
        print("DISCOUNT_VIEW:", view.id, view.name,
              "xml_id:", view.get_external_id().get(view.id),
              "active:", view.active,
              "inherit_id:", view.inherit_id.id)

print("READ_ONLY_SALES_DISCOUNT_AUDIT_COMPLETE")
