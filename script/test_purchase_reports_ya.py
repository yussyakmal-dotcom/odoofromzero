"""Smoke-test QWeb HTML reports on test DB; draft bill is ALWAYS rolled back.

No PDFs, no posting, no payment, no persistent data.
"""
def render(report_name, ids):
    Report = env["ir.actions.report"].sudo()
    result = Report._render_qweb_html(report_name, ids)
    html = result[0]
    if isinstance(html, bytes):
        html = html.decode("utf-8")
    assert html and "<" in html, "Empty HTML: " + report_name
    return html


if env.cr.dbname != "erp-yussyakmal-integer-test":
    raise RuntimeError("TEST DB ONLY")
print("DATABASE:", env.cr.dbname)
print("MODE: RENDER QWEB HTML + DRAFT BILL; ALL ROLLBACK")
try:
    po = env["purchase.order"].sudo().search([("name", "=", "P00009")], limit=1)
    assert po, "PO P00009 missing"
    html = render("purchase.report_purchaseorder", po.ids)
    assert "Kg" in html and "Gram" in html, "PO print physical units missing"
    print("PASS: PO QWeb HTML renders physical purchase units")
    pick = po.picking_ids.filtered(lambda p: p.state == "done")[:1]
    assert pick, "No completed receipt linked to PO"
    html = render("stock.report_picking", pick.ids)
    assert "Ringkasan Penerimaan Fisik" in html, "Receipt physical summary missing"
    assert "Kg" in html and "Gram" in html, "Receipt print physical units missing"
    assert "24975" not in html, "Technical split line leaked into simple receipt print"
    print("PASS: Picking Operations QWeb HTML renders physical units")
    assert not po.invoice_ids, "Existing vendor bills: audit first"
    po.action_create_invoice()
    env.invalidate_all()
    bill = po.invoice_ids.filtered(lambda b: b.move_type == "in_invoice")[:1]
    assert bill and bill.state == "draft", "Draft bill not created"
    html = render("account.report_invoice", bill.ids)
    assert "Kg" in html and "Gram" in html, "Vendor Bill print physical units missing"
    print("PASS: Vendor Bill QWeb HTML renders physical purchase units")
    print("YA_PURCHASE_REPORTS_RENDER_OK")
finally:
    env.cr.rollback()
    print("ROLLBACK_COMPLETE: no bill or stock changes persisted")
