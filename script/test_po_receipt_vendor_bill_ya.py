"""Create vendor bill draft in ORM and ALWAYS roll it back. Test database only.

Use AFTER read-only audit confirms P00009 is purchase, has received quantities,
and does not already have invoices. No posting, payments or real transactions.
"""
from odoo.tools.float_utils import float_compare


def near(a, b, precision=0.01):
    return abs(float(a) - float(b)) <= precision


def main():
    e = globals()["env"]
    if e.cr.dbname != "erp-yussyakmal-integer-test":
        raise RuntimeError("HANYA DATABASE TEST")
    print("DATABASE:", e.cr.dbname)
    print("MODE: DRAFT VENDOR BILL ORM TEST; ALL ROLLBACK")
    try:
        order = e["purchase.order"].sudo().search([("name", "=", "P00009")], limit=1)
        assert order and order.state in ("purchase", "done"), "Expected confirmed PO"
        assert not order.invoice_ids, "PO has existing bills: audit before testing"
        eligible = order.order_line.filtered(
            lambda x: not x.display_type and x.product_id and x.qty_received > x.qty_invoiced
        )
        assert eligible, "No received, uninvoiced lines"
        assert all(line.product_id.purchase_method == "receive" for line in eligible), (
            "Purchase method must invoice on received quantities"
        )
        for line in eligible:
            assert near(line.qty_to_invoice, line.qty_received - line.qty_invoiced, 0.000001)
        print("PASS: invoiceable PO quantities follow actual receipts")
        bills = order._create_invoices()
        assert bills and all(b.move_type == "in_invoice" for b in bills), (
            "Expected vendor bill drafts"
        )
        assert all(b.state == "draft" for b in bills), "No draft bills returned"
        print("PASS: draft Vendor Bill generated without posting")
        mapped = e["account.move.line"]
        for bill in bills:
            mapped |= bill.invoice_line_ids.filtered(lambda x: x.purchase_line_id in eligible)
        assert mapped, "No bill lines linked to PO"
        for line in eligible:
            bill_lines = mapped.filtered(lambda x: x.purchase_line_id == line)
            assert bill_lines, "Missing invoice line for PO line %s" % line.id
            invoiced_qty = sum(bill_lines.mapped("quantity"))
            assert near(invoiced_qty, line.qty_to_invoice, 0.000001), (
                "Bill quantity differs from received quantity for PO line %s: %s != %s"
                % (line.id, invoiced_qty, line.qty_to_invoice)
            )
            for invoice_line in bill_lines:
                assert near(invoice_line.price_unit, line.price_unit, 0.000001), (
                    "Base unit price mismatch for PO line %s" % line.id
                )
                assert near(invoice_line.discount, line.discount, 0.000001), (
                    "Discount mismatch for PO line %s" % line.id
                )
                assert invoice_line.tax_ids == line.tax_ids, (
                    "Taxes mismatch for PO line %s" % line.id
                )
                assert invoice_line.product_uom_id == line.product_uom_id, (
                    "Base UoM mismatch for PO line %s" % line.id
                )
            print(
                "PASS: PO LINE", line.id,
                "received qty -> billed qty:", invoiced_qty,
                "| base price:", line.price_unit,
                "| discount:", line.discount,
            )
        for bill in bills:
            assert near(
                bill.amount_total, bill.amount_untaxed + bill.amount_tax, 0.02
            ), "Bill total does not equal untaxed + tax"
            print("PASS: bill tax and total:", bill.amount_untaxed,
                  bill.amount_tax, bill.amount_total)
        assert all(
            near(line.qty_invoiced, line.qty_received, 0.000001) for line in eligible
        ), "PO qty_invoiced not synchronized with draft bill"
        print("PASS: PO invoiced quantities synchronized")
        print("PO_RECEIPT_BILL_ROLLBACK_TEST_OK")
    finally:
        e.cr.rollback()
        print("ROLLBACK_COMPLETE: no vendor bill, PO or payment persisted")


main()
