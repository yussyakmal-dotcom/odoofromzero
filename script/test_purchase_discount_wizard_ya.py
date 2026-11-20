"""ORM CREATE/WRITE wizard tests on test clone; ALWAYS rollback.

Run only after -u ya_purchase_discount on erp-yussyakmal-integer-test.
This test does not confirm RFQ or create stock/invoices.
"""

from odoo import fields


def check(ok, label):
    if not ok:
        raise AssertionError(label)
    print("PASS:", label)


def main():
    e = globals().get("env")
    if e is None or e.cr.dbname != "erp-yussyakmal-integer-test":
        raise RuntimeError("HANYA database erp-yussyakmal-integer-test")
    if "ya.purchase.discount.wizard" not in e.registry.models:
        raise RuntimeError("Upgrade ya_purchase_discount terlebih dahulu")
    print("DATABASE:", e.cr.dbname)
    print("MODE: ORM TEST ROLLBACK (bukan transaksi operasional)")
    try:
        with e.cr.savepoint():
            product = e["product.product"].sudo().search([
                ("default_code", "=", "10840")], limit=1)
            if not product:
                raise RuntimeError("SKU 10840 tidak ditemukan")
            partner = e["res.partner"].sudo().create({
                "name": "YA DISCOUNT WIZARD TEST - ROLLBACK"})
            order = e["purchase.order"].sudo().create({"partner_id": partner.id})
            Line = e["purchase.order.line"].sudo()
            lines = e["purchase.order.line"]
            for qty, price in ((10, 1000), (20, 2000)):
                lines |= Line.create({
                    "order_id": order.id,
                    "product_id": product.id,
                    "name": "YA discount test",
                    "product_qty": qty,
                    "product_uom_id": product.uom_id.id,
                    "price_unit": price,
                    "date_planned": fields.Datetime.now(),
                })

            def apply(kind, percentage=0, amount=0, line=None):
                wizard = e["ya.purchase.discount.wizard"].sudo().create({
                    "order_id": order.id,
                    "discount_type": kind,
                    "discount_percentage": percentage,
                    "discount_amount": amount,
                    "line_id": line.id if line else False,
                })
                wizard.action_apply_discount()
                e.invalidate_all()
                return order.exists()

            apply("all_lines", percentage=10)
            check(order.ya_discount_mode == "line" and all(
                abs(x.discount - 10) < 0.0001 for x in lines),
                "diskon 10% pada semua baris")

            apply("global_percent", percentage=10)
            check(order.ya_discount_mode == "global" and all(
                abs(x.discount - 10) < 0.0001 for x in lines),
                "pindah dari baris ke global 10%")

            apply("global_amount", amount=5000)
            check(order.ya_global_discount_type == "amount" and all(
                abs(x.discount - 10) < 0.0001 for x in lines),
                "diskon global Rp5.000 atas Rp50.000 => 10%")

            apply("one_line_amount", amount=1000, line=lines[0])
            check(order.ya_discount_mode == "line" and
                  abs(lines[0].discount - 10) < 0.0001 and
                  abs(lines[1].discount) < 0.0001,
                  "diskon Rp1.000 hanya pada baris pertama")

            apply("one_line_percent", percentage=5, line=lines[1])
            check(abs(lines[0].discount) < 0.0001 and
                  abs(lines[1].discount - 5) < 0.0001,
                  "diskon 5% hanya pada baris kedua")

            print("YA_DISCOUNT_WIZARD_TEST_OK: skenario ORM lulus")
    finally:
        e.cr.rollback()
        print("ROLLBACK: semua record uji dibatalkan")


main()
