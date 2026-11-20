"""Uji read-only policy integer pada Odoo shell. Tidak membuat record."""

from odoo.exceptions import ValidationError


def main():
    e = globals().get("env")
    if e is None or e.cr.dbname != "erp-yussyakmal":
        raise RuntimeError("Gunakan database erp-yussyakmal")
    if "ya_integer_quantity" not in e["ir.module.module"].sudo().search([
        ("name", "=", "ya_integer_quantity"), ("state", "=", "installed")
    ]).mapped("name"):
        raise RuntimeError("Modul ya_integer_quantity belum terpasang")

    from odoo.addons.ya_integer_quantity.models.integer_quantity import check_whole_quantity

    print("DATABASE:", e.cr.dbname)
    print("MODE: TEST READ-ONLY, TANPA CREATE/WRITE/COMMIT")
    for quantity in (0, 1, 2, 100, -1, -3):
        check_whole_quantity(quantity, "TEST")
    print("PASS: 0, positif integer, refund negatif integer")
    for quantity in (0.1, 1.5, -2.5, float("nan"), float("inf")):
        try:
            check_whole_quantity(quantity, "TEST")
        except ValidationError:
            continue
        raise AssertionError("Pecahan/non-finite diterima: %r" % quantity)
    print("PASS: pecahan, NaN, infinity ditolak")

    for model, name in (
        ("purchase.order.line", "_ya_check_integer_qty"),
        ("stock.move", "_ya_check_integer_demand"),
        ("stock.move.line", "_ya_check_integer_done"),
        ("stock.quant", "_ya_check_integer_count"),
        ("stock.scrap", "_ya_check_integer_scrap"),
        ("sale.order.line", "_ya_check_integer_sale"),
        ("pos.order.line", "_ya_check_integer_pos"),
        ("mrp.production", "_ya_check_integer_mo"),
        ("mrp.bom.line", "_ya_check_integer_bom"),
    ):
        if not hasattr(e[model], name):
            raise AssertionError("Validator tidak ditemukan: %s.%s" % (model, name))
        print("PASS:", model, "validator terpasang")
    print("YA_INTEGER_QUANTITY_TEST_OK: database tidak diubah")


main()
