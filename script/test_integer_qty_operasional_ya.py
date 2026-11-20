"""Uji operasional ORM pada duplikat; semua record uji di-ROLLBACK.

Menguji CREATE/WRITE nyata untuk PO line dan stock.move dengan qty utuh/pecahan.
Tidak memvalidasi UI, POS, Sales, atau MRP. Database utama ditolak keras.
"""

from odoo import fields
from odoo.exceptions import ValidationError


class EndRollback(Exception):
    """Sentinel to force rollback of the complete outer savepoint."""


def expect_fraction_rejected(e, model, values):
    """Nested savepoint permits expected ValidationError without poisoning TX."""
    try:
        with e.cr.savepoint():
            model.create(values)
    except ValidationError:
        return
    raise AssertionError("Kuantitas desimal tidak ditolak: %s" % model._name)


def main():
    e = globals().get("env")
    if e is None or e.cr.dbname != "erp-yussyakmal-integer-test":
        raise RuntimeError("HANYA untuk database erp-yussyakmal-integer-test")
    if e["ir.module.module"].sudo().search_count([
        ("name", "=", "ya_integer_quantity"), ("state", "=", "installed")
    ]) != 1:
        raise RuntimeError("Addon ya_integer_quantity belum installed")

    print("DATABASE:", e.cr.dbname)
    print("MODE: ORM CREATE/WRITE TEST; seluruh transaksi di-ROLLBACK")
    product = e["product.product"].sudo().search([("is_storable", "=", True)], limit=1)
    if not product:
        raise RuntimeError("Tidak ada product storable untuk uji")
    internal = e["stock.location"].sudo().search([("usage", "=", "internal")], limit=1)
    supplier = e["stock.location"].sudo().search([("usage", "=", "supplier")], limit=1)
    if not internal or not supplier:
        raise RuntimeError("Lokasi internal/supplier belum tersedia")

    try:
        with e.cr.savepoint():
            Partner = e["res.partner"].sudo()
            partner = Partner.create({"name": "YA INTEGER TEST - ROLLBACK"})
            order = e["purchase.order"].sudo().create({"partner_id": partner.id})
            POL = e["purchase.order.line"].sudo()
            po_values = {
                "order_id": order.id,
                "product_id": product.id,
                "name": "YA integer quantity test",
                "product_qty": 2,
                "product_uom_id": product.uom_id.id,
                "price_unit": 1,
                "date_planned": fields.Datetime.now(),
            }
            line = POL.create(dict(po_values))
            if line.product_qty != 2:
                raise AssertionError("PO integer berubah setelah CREATE")
            print("PASS: PO line CREATE integer=2")
            expect_fraction_rejected(e, POL, dict(po_values, product_qty=2.5))
            print("PASS: PO line CREATE pecahan=2.5 ditolak")
            try:
                with e.cr.savepoint():
                    line.write({"product_qty": 3.5})
            except ValidationError:
                print("PASS: PO line WRITE pecahan=3.5 ditolak")
            else:
                raise AssertionError("PO WRITE desimal tidak ditolak")

            Move = e["stock.move"].sudo()
            move_values = {
                "name": "YA integer stock test",
                "product_id": product.id,
                "product_uom_qty": 10,
                "location_id": supplier.id,
                "location_dest_id": internal.id,
            }
            move = Move.create(dict(move_values))
            if move.product_uom_qty != 10:
                raise AssertionError("Stock demand integer berubah setelah CREATE")
            print("PASS: stock.move CREATE demand=10")
            expect_fraction_rejected(e, Move, dict(move_values, product_uom_qty=10.5))
            print("PASS: stock.move CREATE pecahan=10.5 ditolak")
            try:
                with e.cr.savepoint():
                    move.write({"product_uom_qty": 11.5})
            except ValidationError:
                print("PASS: stock.move WRITE pecahan=11.5 ditolak")
            else:
                raise AssertionError("Stock WRITE desimal tidak ditolak")

            raise EndRollback()
    except EndRollback:
        pass
    finally:
        e.cr.rollback()
    print("INTEGER_QTY_OPERATIONAL_TEST_OK: semua record uji telah ROLLBACK")


main()
