"""Odoo 19 virtual ORM smoke test; run AFTER installing addon on test clone.

Uses `new` (not CREATE), no write, and always rolls the shell transaction back.
Test the UI and vendor bill separately before production deployment.
"""

from odoo import Command
from odoo.tools.float_utils import float_compare


def require(condition, label):
    if not condition:
        raise AssertionError(label)
    print("PASS:", label)


def main():
    e = globals().get("env")
    if e is None or e.cr.dbname != "erp-yussyakmal-integer-test":
        raise RuntimeError("TEST ONLY: erp-yussyakmal-integer-test")
    if "ya_discount_mode" not in e["purchase.order"]._fields:
        raise RuntimeError("Install ya_purchase_discount pada database TEST dahulu")
    product = e["product.product"].search([("default_code", "=", "10840")], limit=1)
    partner = e["res.partner"].search([], limit=1)
    require(bool(product and partner), "data produk dan partner uji tersedia")
    rule = e["ya.purchase.uom.rule"].search([
        ("product_id", "=", product.id), ("factor", "=", 1),
    ], limit=1)
    require(bool(rule), "satuan dasar Cabe Jengki ditemukan")

    def make_order(mode, dtype, value, line_type="percent", line_value=0):
        return e["purchase.order"].new({
            "partner_id": partner.id,
            "ya_discount_mode": mode,
            "ya_global_discount_type": dtype,
            "ya_global_discount_value": value,
            "order_line": [Command.create({
                "product_id": product.id,
                "product_uom_id": product.uom_id.id,
                "product_qty": 1000,
                "price_unit": 60,
                "ya_purchase_rule_id": rule.id,
                "ya_purchase_qty": 1000,
                "ya_purchase_price": 60,
                "ya_line_discount_type": line_type,
                "ya_line_discount_value": line_value,
            })],
        })

    try:
        print("DATABASE:", e.cr.dbname)
        print("MODE: VIRTUAL ORM READ-ONLY; NO CREATE/WRITE/COMMIT")
        cases = [
            ("none", "percent", 0, "percent", 0, 0),
            ("line", "percent", 0, "percent", 10, 10),
            ("line", "percent", 0, "amount", 6000, 10),
            ("global", "percent", 10, "percent", 0, 10),
            ("global", "amount", 6000, "percent", 0, 10),
        ]
        for mode, dtype, value, lt, lv, expected in cases:
            po = make_order(mode, dtype, value, lt, lv)
            line = po.order_line[0]
            line._ya_apply_discount_percent()
            require(not float_compare(line.discount, expected, precision_rounding=0.000001),
                    "%s/%s/%s => discount %s%%" % (mode, dtype, lt, expected))
            po._ya_validate_discount()
            line._ya_validate_line_discount()
        print("YA_DISCOUNT_VIRTUAL_TEST_OK: tidak ada data diubah")
    finally:
        e.cr.rollback()


main()
