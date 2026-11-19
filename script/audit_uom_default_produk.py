"""Audit read-only relasi dan nilai default UoM produk Odoo 19.

Memastikan apakah 2.543 produk bisa dibuat tanpa mengisi uom_id manual.
"""


def main():
    odoo_env = globals().get("env")
    if odoo_env is None or odoo_env.cr.dbname != "erp-yussyakmal":
        raise RuntimeError("Database harus erp-yussyakmal")
    products = odoo_env["product.template"].sudo()
    field = products._fields["uom_id"]
    print("DATABASE:", odoo_env.cr.dbname)
    print("MODE: AUDIT READ-ONLY")
    print("FIELD uom_id: required=%s relation=%s" % (field.required, field.comodel_name))
    print("REGISTRY UOM MODELS:", sorted(x for x in odoo_env.registry.models if "uom" in x.lower()))
    defaults = products.default_get(["uom_id", "type", "is_storable", "tracking", "sale_ok", "purchase_ok", "categ_id"])
    print("PRODUCT DEFAULTS:", defaults)
    relation = field.comodel_name
    if relation not in odoo_env.registry.models:
        print("WARNING: relation uom_id tidak ditemukan dalam registry:", relation)
    else:
        units = odoo_env[relation].sudo()
        print("UOM TOTAL:", units.search_count([]))
        default_id = defaults.get("uom_id")
        if default_id:
            unit = units.browse(default_id).exists()
            print("DEFAULT UOM:", unit.id, unit.name if unit else "tidak ditemukan")
        else:
            print("WARNING: tidak ada default uom_id; wajib memilih sebelum impor")
    print("AUDIT_UOM_DEFAULT_COMPLETE: database tidak diubah.")


main()
