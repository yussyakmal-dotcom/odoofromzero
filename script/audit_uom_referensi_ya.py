"""Lihat UoM aktif dan arsip beserta hubungan konversi, read-only Odoo 19."""


def main():
    e = globals().get("env")
    if e is None or e.cr.dbname != "erp-yussyakmal":
        raise RuntimeError("Database harus erp-yussyakmal")
    Uom = e["uom.uom"].sudo().with_context(active_test=False)
    print("DATABASE:", e.cr.dbname)
    print("MODE: AUDIT READ-ONLY UOM REFERENSI")
    units = Uom.search([], order="name, id")
    print("TOTAL UOM termasuk arsip:", len(units))
    for u in units:
        parent = u.relative_uom_id if "relative_uom_id" in Uom._fields else False
        print("UOM: id=%s | %s | active=%s | parent=%s | relative_factor=%s | factor=%s | rounding=%s" %
              (u.id, u.name, u.active,
               ("%s:%s" % (parent.id, parent.name)) if parent else "ROOT",
               u.relative_factor if "relative_factor" in Uom._fields else "N/A",
               u.factor if "factor" in Uom._fields else "N/A", u.rounding))
    print("UOM_REFERENCE_AUDIT_COMPLETE: database tidak diubah")


main()
