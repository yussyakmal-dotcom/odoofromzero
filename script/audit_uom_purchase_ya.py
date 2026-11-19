"""Audit read-only UoM, Purchase, dan penerimaan stok pada Odoo 19 YA.

Tidak mengubah database. Gunakan hasilnya untuk merancang UoM bertingkat per SKU.
"""


def main():
    odoo_env = globals().get("env")
    if odoo_env is None or odoo_env.cr.dbname != "erp-yussyakmal":
        raise RuntimeError("Jalankan di database erp-yussyakmal")
    print("DATABASE:", odoo_env.cr.dbname)
    print("MODE: AUDIT READ-ONLY")

    Module = odoo_env["ir.module.module"].sudo()
    for name in ("purchase", "purchase_stock", "stock", "uom", "mrp", "account"):
        modules = Module.search([("name", "=", name)])
        print("MODULE:", name, "|", modules.state if len(modules) == 1 else "TIDAK DITEMUKAN")
    extensions = Module.search([("state", "=", "installed"),
                                "|", ("name", "ilike", "uom"), ("name", "ilike", "purchase")])
    print("MODUL PURCHASE/UOM TERPASANG:", sorted(extensions.mapped("name")))

    candidates = {
        "product.template": ("type", "is_storable", "uom_id", "uom_po_id", "purchase_ok",
                             "sale_ok", "standard_price", "categ_id"),
        "product.product": ("uom_id", "uom_po_id", "product_tmpl_id"),
        "purchase.order": ("order_line", "picking_ids", "state", "company_id"),
        "purchase.order.line": ("product_id", "product_qty", "product_uom",
                                "product_uom_id", "product_packaging_id", "price_unit",
                                "qty_received", "qty_received_method"),
        "stock.move": ("product_id", "product_uom", "product_uom_qty", "quantity",
                       "product_qty", "picking_id", "location_id", "location_dest_id"),
        "stock.move.line": ("product_id", "product_uom_id", "quantity", "qty_done",
                            "move_id", "lot_id"),
        "stock.picking": ("picking_type_id", "move_ids", "move_ids_without_package", "state"),
        "product.packaging": ("product_id", "qty", "name", "package_type_id"),
        "uom.uom": ("name", "factor", "factor_inv", "rounding", "category_id", "uom_type", "relative_factor"),
        "uom.category": ("name",),
    }

    for model_name, field_names in candidates.items():
        if model_name not in odoo_env.registry.models:
            print("MODEL:", model_name, "| TIDAK TERSEDIA")
            continue
        Model = odoo_env[model_name].sudo()
        print("MODEL:", model_name, "| RECORDS:", Model.search_count([]))
        for field_name in field_names:
            field = Model._fields.get(field_name)
            if not field:
                print("  FIELD:", field_name, "| TIDAK ADA")
                continue
            extra = ""
            if field.type in ("many2one", "one2many", "many2many"):
                extra = " | relation=" + str(field.comodel_name)
            elif field.type == "selection":
                try:
                    extra = " | choices=" + repr(field._description_selection(odoo_env))
                except Exception:
                    extra = " | pilihan tidak dapat dibaca"
            print("  FIELD:", field_name, "| type=" + field.type + extra)

    Product = odoo_env["product.template"].sudo()
    products = Product.search([])
    if "uom_id" in Product._fields:
        from collections import Counter
        usage = Counter((p.uom_id.id, p.uom_id.name) for p in products)
        print("UOM PADA MASTER PRODUK:", sorted((uom_id, label, count)
                                             for (uom_id, label), count in usage.items()))
    print("AUDIT_UOM_PURCHASE_COMPLETE: database tidak diubah")


main()
