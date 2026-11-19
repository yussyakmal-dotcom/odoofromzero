"""Audit read-only dukungan aturan Multi-UoM per SKU di Odoo 19.

Tidak mengubah database dan tidak membaca data privat konversi.
"""


def main():
    e = globals().get("env")
    if e is None or e.cr.dbname != "erp-yussyakmal":
        raise RuntimeError("Database harus erp-yussyakmal")

    print("DATABASE:", e.cr.dbname)
    print("MODE: AUDIT READ-ONLY MULTI-UOM PURCHASE")
    names = (
        "product.uom", "product.template", "product.product",
        "uom.uom", "product.supplierinfo", "purchase.order.line",
        "stock.move", "stock.move.line",
    )
    for name in names:
        if name not in e.registry.models:
            print("MODEL: %s | TIDAK TERSEDIA" % name)
            continue
        Model = e[name].sudo()
        print("=" * 72)
        print("MODEL: %s | RECORDS: %s | TABLE: %s" % (
            name, Model.search_count([]), Model._table
        ))
        print("FIELDS:")
        for field_name in sorted(Model._fields):
            field = Model._fields[field_name]
            if name != "product.uom" and not any(word in field_name.lower() for word in (
                "uom", "factor", "ratio", "quantity", "product_id", "purchase", "packaging",
            )):
                continue
            if name == "product.uom" and field_name in (
                "message_ids", "message_follower_ids", "activity_ids",
            ):
                continue
            print("  %s | type=%s | relation=%s | required=%s | readonly=%s | compute=%s" % (
                field_name, field.type, getattr(field, "comodel_name", None),
                field.required, field.readonly, getattr(field, "compute", None)
            ))
        if name == "product.uom":
            for record in Model.search([], limit=10):
                print("SAMPLE: id=%s | product=%s | uom=%s" % (
                    record.id,
                    record.product_id.default_code if "product_id" in Model._fields else "n/a",
                    record.uom_id.name if "uom_id" in Model._fields else "n/a",
                ))
            for method in ("create", "write", "_compute_quantity", "_get_conversion_factor"):
                print("METHOD %s: %s" % (method, hasattr(Model, method)))

    print("=" * 72)
    modules = e["ir.module.module"].sudo().search([
        ("name", "in", ["purchase", "purchase_stock", "stock", "uom", "ya_purchase_multi_uom"])
    ])
    print("MODULES:", [(m.name, m.state) for m in modules])
    print("AUDIT_MULTI_UOM_PURCHASE_COMPLETE: database tidak diubah")


main()
