"""Audit read-only External ID dan tag Quantity pada view Odoo 19.

Hasil digunakan untuk membuat inherit XML view secara tepat, bukan menebak ID.
"""

import re


def main():
    e = globals().get("env")
    if e is None or e.cr.dbname != "erp-yussyakmal-integer-test":
        raise RuntimeError("Hanya database erp-yussyakmal-integer-test")
    targets = {
        "purchase.order.line": {"product_qty"},
        "stock.move": {"product_uom_qty", "quantity"},
        "stock.move.line": {"quantity"},
        "stock.quant": {"inventory_quantity"},
        "stock.scrap": {"scrap_qty"},
        "sale.order.line": {"product_uom_qty"},
        "mrp.production": {"product_qty"},
        "mrp.bom.line": {"product_qty"},
    }
    Views = e["ir.ui.view"].sudo()
    IMD = e["ir.model.data"].sudo()
    views = Views.search([
        ("model", "in", list(targets)),
        ("type", "in", ["form", "list"]),
        ("active", "=", True),
    ])
    external = {}
    for item in IMD.search([("model", "=", "ir.ui.view"),
                            ("res_id", "in", views.ids)]):
        external.setdefault(item.res_id, []).append(item.module + "." + item.name)
    print("DATABASE:", e.cr.dbname)
    print("MODE: READ-ONLY VIEW XML AUDIT")
    for view in views.sorted(key=lambda v: (v.model, v.id)):
        tags = []
        for match in re.finditer(r"<field\b[^>]*\bname\s*=\s*(['\"])(.*?)\1[^>]*>",
                                 view.arch_db or "", flags=re.DOTALL):
            if match.group(2) in targets[view.model]:
                tags.append(" ".join(match.group(0).split())[:450])
        if not tags:
            continue
        print("VIEW: %s | model=%s | xmlid=%s | inherit_id=%s | type=%s" % (
            view.id, view.model, external.get(view.id, []),
            view.inherit_id.id or "ROOT", view.type))
        for tag in tags[:12]:
            print(" TAG:", tag)
    print("INTEGER_QTY_VIEW_XML_AUDIT_COMPLETE: database tidak diubah")


main()
