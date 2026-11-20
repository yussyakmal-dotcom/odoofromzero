"""Audit read-only target qty untuk modul ya_integer_quantity Odoo 19.

Jalankan via odoo-bin shell pada erp-yussyakmal. Tidak membuat transaksi.
"""


def main():
    e = globals().get("env")
    if e is None or e.cr.dbname != "erp-yussyakmal":
        raise RuntimeError("Audit hanya untuk database erp-yussyakmal")

    targets = {
        "purchase.order.line": ["product_qty", "product_uom_id"],
        "stock.move": ["product_uom_qty", "quantity", "product_uom"],
        "stock.move.line": ["quantity", "product_uom_id"],
        "stock.quant": ["inventory_quantity", "quantity", "product_uom_id"],
        "stock.scrap": ["scrap_qty", "product_uom_id"],
        "sale.order.line": ["product_uom_qty", "product_uom_id"],
        "pos.order.line": ["qty", "product_id"],
        "mrp.production": ["product_qty", "product_uom_id"],
        "mrp.bom.line": ["product_qty", "product_uom_id"],
    }
    print("DATABASE:", e.cr.dbname)
    print("MODE: AUDIT READ-ONLY INTEGER QUANTITY")
    for model_name, fields in targets.items():
        if model_name not in e.registry.models:
            print("MODEL:", model_name, "TIDAK TERPASANG")
            continue
        model = e[model_name]
        print("MODEL:", model_name, "RECORDS:", model.sudo().search_count([]))
        for name in fields:
            field = model._fields.get(name)
            if not field:
                print(" FIELD:", name, "TIDAK ADA")
                continue
            print(" FIELD: %s | type=%s | digits=%s | compute=%s | readonly=%s" %
                  (name, field.type, getattr(field, "digits", None),
                   bool(field.compute), field.readonly))

    views = e["ir.ui.view"].sudo().search([
        ("model", "in", list(targets)),
        ("type", "in", ["form", "list"]),
        ("active", "=", True),
    ])
    print("ACTIVE FORM/LIST VIEWS:", len(views))
    for view in views.sorted(key=lambda v: (v.model, v.id)):
        fields = [name for name in targets[view.model] if
                  ('name="%s"' % name) in (view.arch_db or "") or
                  ("name='%s'" % name) in (view.arch_db or "")]
        if fields:
            print(" VIEW: id=%s | model=%s | name=%s | inherit=%s | fields=%s" %
                  (view.id, view.model, view.name,
                   view.inherit_id.id or "ROOT", ",".join(fields)))
    print("INTEGER_QTY_VIEW_AUDIT_COMPLETE: database tidak diubah")


main()
