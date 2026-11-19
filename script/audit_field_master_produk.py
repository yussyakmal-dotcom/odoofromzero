"""Audit read-only model produk Odoo 19 sebelum impor 2.543 SKU YA.

Tidak membuat produk, tidak mengatur UoM, tidak mengubah database.
"""


def main():
    odoo_env = globals().get("env")
    if odoo_env is None or odoo_env.cr.dbname != "erp-yussyakmal":
        raise RuntimeError("Jalankan melalui Odoo shell pada erp-yussyakmal")

    tpl = odoo_env["product.template"].sudo()
    var = odoo_env["product.product"].sudo()
    cats = odoo_env["product.category"].sudo()
    uoms = odoo_env["uom.uom"].sudo() if "uom.uom" in odoo_env.registry.models else None

    print("DATABASE:", odoo_env.cr.dbname)
    print("MODE: AUDIT READ-ONLY")
    print("PRODUCT TEMPLATES:", tpl.search_count([]))
    print("PRODUCT VARIANTS:", var.search_count([]))
    print("PRODUCT CATEGORIES:", cats.search_count([]))
    fields = (
        "name", "default_code", "categ_id", "type", "detailed_type", "is_storable",
        "tracking", "uom_id", "uom_po_id", "list_price", "standard_price",
        "sale_ok", "purchase_ok", "active", "company_id", "taxes_id",
        "supplier_taxes_id", "route_ids", "bom_count",
    )
    for name in fields:
        f = tpl._fields.get(name)
        if not f:
            print("FIELD %s: TIDAK ADA" % name)
            continue
        print("FIELD %s: ada | tipe=%s | required=%s | readonly=%s" %
              (name, f.type, f.required, f.readonly))
        if f.type == "selection":
            print("  PILIHAN:", f._description_selection(odoo_env))

    if uoms:
        print("UOM RECORDS:", uoms.search_count([]))
        for uom in uoms.search([], order="id", limit=25):
            print("  UOM: id=%s name=%s" % (uom.id, uom.name))
    else:
        print("UOM MODEL uom.uom: tidak tersedia")

    print("AUDIT_PRODUCT_FIELDS_COMPLETE: tidak ada perubahan database.")


main()
