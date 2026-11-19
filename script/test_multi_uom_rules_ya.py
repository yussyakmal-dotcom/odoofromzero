"""Uji konversi YA di DATABASE DUPLIKAT; selalu rollback setelah pengujian.

Modul ya_purchase_multi_uom harus terpasang pada database duplikat.
Tidak membuat PO/stock.move dan tidak pernah commit.
"""

from decimal import Decimal
from odoo.exceptions import ValidationError


def main():
    e = globals().get("env")
    if e is None:
        raise RuntimeError("Jalankan melalui Odoo shell")
    if e.cr.dbname == "erp-yussyakmal":
        raise RuntimeError("UJI DILARANG pada database utama erp-yussyakmal")
    if "ya.purchase.uom.rule" not in e.registry.models:
        raise RuntimeError("Install ya_purchase_multi_uom pada database duplikat dahulu")
    products = e["product.product"].sudo().search([], limit=2)
    if len(products) != 2:
        raise RuntimeError("Memerlukan 2 produk pada database duplikat")
    Rule = e["ya.purchase.uom.rule"].sudo()
    print("DATABASE:", e.cr.dbname)
    print("MODE: TEST + ROLLBACK; tanpa perubahan persisten")
    try:
        a = Rule.create({"product_id": products[0].id, "purchase_label": "Dus", "factor": 100})
        b = Rule.create({"product_id": products[1].id, "purchase_label": "Dus", "factor": 120})
        assert a.to_base_quantity(2) == 200
        assert b.to_base_quantity(2) == 240
        assert Decimal(str(a.price_per_base_unit(100000))) == Decimal("1000")
        print("PASS: Dus berbeda faktor antar SKU (100 dan 120)")
        print("PASS: 2 Dus -> 200/240 unit dasar, harga/unit dasar benar")

        try:
            with e.cr.savepoint():
                Rule.create({"product_id": products[0].id, "purchase_label": " dus ", "factor": 100})
        except ValidationError:
            print("PASS: duplikat SKU + label ditolak")
        else:
            raise RuntimeError("Duplikat SKU + label tidak ditolak")

        try:
            a.to_base_quantity(1.5)
        except ValidationError:
            print("PASS: jumlah pembelian desimal ditolak")
        else:
            raise RuntimeError("Jumlah desimal tidak ditolak")

        try:
            with e.cr.savepoint():
                Rule.create({"product_id": products[0].id, "purchase_label": "Peti", "factor": 0})
        except ValidationError:
            print("PASS: faktor 0 ditolak")
        else:
            raise RuntimeError("Faktor 0 tidak ditolak")

        print("MULTI_UOM_RULE_TEST_OK: semua tes lulus; ROLLBACK")
    finally:
        e.cr.rollback()
        print("TEST_ROLLBACK_COMPLETE: tidak ada aturan uji tersimpan")


main()
