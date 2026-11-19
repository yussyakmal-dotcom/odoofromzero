"""Uji read-only fungsi konversi modul YA pada database utama.

Tidak membuat record, PO, atau stock.move. `new()` membuat record virtual
di memori ORM saja. Uji constraint duplikat saat CREATE ditunda ke database uji.
"""

from decimal import Decimal
from odoo.exceptions import ValidationError


def main():
    e = globals().get("env")
    if e is None or e.cr.dbname != "erp-yussyakmal":
        raise RuntimeError("Pengujian hanya untuk erp-yussyakmal")
    if "ya.purchase.uom.rule" not in e.registry.models:
        raise RuntimeError("Modul ya_purchase_multi_uom belum terpasang")
    variants = e["product.product"].sudo().search([], limit=2)
    if len(variants) != 2:
        raise RuntimeError("Diperlukan 2 varian produk")
    Rule = e["ya.purchase.uom.rule"].sudo()

    print("DATABASE:", e.cr.dbname)
    print("MODE: READ-ONLY; record virtual ORM (new), tanpa CREATE/WRITE/COMMIT")
    before_rules = Rule.search_count([])
    before_po = e["purchase.order.line"].sudo().search_count([])
    before_moves = e["stock.move"].sudo().search_count([])

    a = Rule.new({"product_id": variants[0].id, "purchase_label": "Dus", "factor": 100})
    b = Rule.new({"product_id": variants[1].id, "purchase_label": "Dus", "factor": 120})
    assert a.to_base_quantity(2) == 200
    assert b.to_base_quantity(2) == 240
    assert Decimal(str(a.price_per_base_unit(100000))) == Decimal("1000")
    print("PASS: dua SKU memakai Dus dengan faktor berbeda (100 dan 120)")
    print("PASS: 2 Dus -> 200/240 unit dasar dan harga per unit dasar benar")

    try:
        a.to_base_quantity(1.5)
    except ValidationError:
        print("PASS: kuantitas pembelian desimal ditolak")
    else:
        raise RuntimeError("Kuantitas desimal tidak ditolak")

    invalid = Rule.new({"product_id": variants[0].id, "purchase_label": "Peti", "factor": 0})
    try:
        invalid._check_rule()
    except ValidationError:
        print("PASS: faktor 0 ditolak")
    else:
        raise RuntimeError("Faktor 0 tidak ditolak")

    if (Rule.search_count([]) != before_rules
            or e["purchase.order.line"].sudo().search_count([]) != before_po
            or e["stock.move"].sudo().search_count([]) != before_moves):
        raise RuntimeError("Jumlah record berubah tanpa diduga")
    print("CATATAN: pengujian duplikat CREATE dan integrasi PO memerlukan tahap berikut")
    print("MULTI_UOM_RULE_READONLY_OK: tidak ada data database diubah")


main()
