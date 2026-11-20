"""Uji ORM Sales, BoM, MO di clone YA. Semua CREATE dibatalkan (ROLLBACK).

Menggunakan model Odoo 19 aktual, bukan simulasi helper. POS diuji terpisah.
"""

from odoo.exceptions import ValidationError


class EndRollback(Exception):
    pass


def check_create_and_write(e, model, vals, field, initial, fractional, label):
    values = dict(vals, **{field: initial})
    record = model.create(values)
    if abs(record[field] - initial) > 1e-9:
        raise AssertionError("%s integer berubah setelah CREATE" % label)
    print("PASS: %s CREATE integer=%s" % (label, initial))
    try:
        with e.cr.savepoint():
            fractional_values = dict(values, **{field: fractional})
            if model._name == "mrp.production":
                # Odoo may reuse the same MO sequence within rollback test.
                fractional_values["name"] = "YA-INT-MO-FRACTIONAL-TEST"
            model.create(fractional_values)
    except ValidationError:
        print("PASS: %s CREATE desimal=%s ditolak" % (label, fractional))
    else:
        raise AssertionError("%s CREATE desimal tidak ditolak" % label)
    try:
        with e.cr.savepoint():
            record.write({field: fractional})
    except ValidationError:
        print("PASS: %s WRITE desimal=%s ditolak" % (label, fractional))
    else:
        raise AssertionError("%s WRITE desimal tidak ditolak" % label)


def main():
    e = globals().get("env")
    if e is None or e.cr.dbname != "erp-yussyakmal-integer-test":
        raise RuntimeError("HANYA untuk erp-yussyakmal-integer-test")
    module = e["ir.module.module"].sudo()
    if module.search_count([("name", "=", "ya_integer_quantity"),
                            ("state", "=", "installed")]) != 1:
        raise RuntimeError("Addon integer belum terpasang")
    products = e["product.product"].sudo().search([("is_storable", "=", True)], limit=2)
    if len(products) < 2:
        raise RuntimeError("Diperlukan dua produk storable")
    finished, component = products[0], products[1]

    print("DATABASE:", e.cr.dbname)
    print("MODE: SALES/MRP ORM TEST, SELURUH RECORD ROLLBACK")
    try:
        with e.cr.savepoint():
            customer = e["res.partner"].sudo().create({
                "name": "YA INTEGER TEST CUSTOMER - ROLLBACK"
            })
            sale = e["sale.order"].sudo().create({"partner_id": customer.id})
            check_create_and_write(
                e, e["sale.order.line"].sudo(), {
                    "order_id": sale.id,
                    "product_id": finished.id,
                    "name": "YA integer sale test",
                    "price_unit": 1,
                }, "product_uom_qty", 3, 3.5, "Sales Order Line"
            )

            bom = e["mrp.bom"].sudo().create({
                "product_tmpl_id": finished.product_tmpl_id.id,
                "product_qty": 1,
                "product_uom_id": finished.uom_id.id,
            })
            check_create_and_write(
                e, e["mrp.bom.line"].sudo(), {
                    "bom_id": bom.id,
                    "product_id": component.id,
                    "product_uom_id": component.uom_id.id,
                }, "product_qty", 50, 50.5, "BoM Component"
            )

            check_create_and_write(
                e, e["mrp.production"].sudo(), {
                    "name": "YA-INT-MO-INTEGER-TEST",
                    "product_id": finished.id,
                    "product_uom_id": finished.uom_id.id,
                    "bom_id": bom.id,
                }, "product_qty", 2, 2.5, "Manufacturing Order"
            )
            raise EndRollback()
    except EndRollback:
        pass
    finally:
        e.cr.rollback()
    print("INTEGER_QTY_SALES_MRP_TEST_OK: semua record telah ROLLBACK")


main()
