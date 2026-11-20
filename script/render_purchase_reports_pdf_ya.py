"""Render physical-unit purchase PDFs on test DB; temporary bill is rolled back.

Output PDFs stay on the server for human visual checks. No permanent Odoo
records, stock changes, bill posting, or payments.
"""
import os
import tempfile
from pathlib import Path

if env.cr.dbname != "erp-yussyakmal-integer-test":
    raise RuntimeError("TEST DATABASE ONLY")
print("DATABASE:", env.cr.dbname)
print("MODE: PDF RENDER / DRAFT VENDOR BILL / ALL DATABASE CHANGES ROLLBACK")

output_dir = None
try:
    po = env["purchase.order"].sudo().search([("name", "=", "P00009")], limit=1)
    assert po, "PO P00009 tidak ditemukan"
    picking = po.picking_ids.filtered(lambda p: p.state == "done")[:1]
    assert picking, "Receipt selesai untuk P00009 tidak ditemukan"
    assert not po.invoice_ids, "Sudah ada Vendor Bill; audit sebelum membuat draft uji"

    output_dir = Path(tempfile.mkdtemp(prefix="ya_purchase_pdf_", dir="/tmp"))
    output_dir.chmod(0o700)
    report = env["ir.actions.report"].sudo()

    def make_pdf(report_name, record, filename):
        data, fmt = report._render_qweb_pdf(report_name, record.ids)
        assert isinstance(data, bytes) and data.startswith(b"%PDF-"), (
            "Output bukan PDF: " + report_name
        )
        target = output_dir / filename
        target.write_bytes(data)
        target.chmod(0o600)
        print("PASS:", filename, "| bytes:", len(data))
        return target

    make_pdf("purchase.report_purchaseorder", po, "01_PO_P00009.pdf")
    make_pdf("stock.report_picking", picking, "02_RECEIPT_CDC_IN_00001.pdf")

    po.action_create_invoice()
    env.invalidate_all()
    bill = po.invoice_ids.filtered(lambda b: b.move_type == "in_invoice")[:1]
    assert bill and bill.state == "draft", "Draft vendor bill tidak berhasil dibuat"
    make_pdf("account.report_invoice", bill, "03_VENDOR_BILL_DRAFT_ROLLBACK.pdf")
    print("YA_PURCHASE_PDF_RENDER_OK")
finally:
    env.cr.rollback()
    print("ROLLBACK_COMPLETE: no vendor bill, stock or accounting changes persisted")
    if output_dir is not None:
        print("PDF_OUTPUT_DIR:", output_dir)
        print("AKSES: berkas privat milik odoo19, salin dengan sudo untuk review")
