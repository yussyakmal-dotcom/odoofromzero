"""Inspect applied QWeb inheritance and rendered receipt HTML, read-only."""
from lxml import etree, html as html_parser
assert env.cr.dbname == "erp-yussyakmal-integer-test", "TEST DB ONLY"
view = env.ref("stock.report_picking")
custom = env.ref("ya_purchase_reports.ya_picking_print_received_units", raise_if_not_found=False)
print("DATABASE:", env.cr.dbname)
print("BASE VIEW:", view.id, view.key, view.active)
print("CUSTOM VIEW:", custom.id if custom else None, custom.active if custom else None,
      custom.inherit_id.id if custom else None)
print("CUSTOM ARCH SUMMARY:", "Ringkasan Penerimaan Fisik" in custom.arch_db if custom else None)
combined = view._get_combined_arch()
if isinstance(combined, bytes):
    combined = combined.decode()
if not isinstance(combined, str):
    combined = etree.tostring(combined, encoding="unicode")
print("COMBINED ARCH SUMMARY:", "Ringkasan Penerimaan Fisik" in combined)
po = env["purchase.order"].sudo().search([("name", "=", "P00009")], limit=1)
picking = po.picking_ids.filtered(lambda p: p.state == "done")[:1]
print("PICK:", picking.name, "TYPE:", picking.picking_type_code)
for move in picking.move_ids:
    print("MOVE:", move.id, "PHYSICAL:", move.ya_received_unit_qty, repr(move.ya_received_unit_label))
rendered = env["ir.actions.report"].sudo()._render_qweb_html("stock.report_picking", picking.ids)[0]
if isinstance(rendered, bytes):
    rendered = rendered.decode()
print("RENDER SUMMARY:", "Ringkasan Penerimaan Fisik" in rendered)
print("RENDER KW:", "Total diterima:" in rendered, "Kg" in rendered, "Gram" in rendered)
root = html_parser.fromstring(rendered)
for el in root.xpath("//*[contains(text(), 'Ringkasan') or contains(text(), 'Total diterima')]"):
    print("ELEMENT:", etree.tostring(el, encoding="unicode")[:500])
print("RECEIPT_TEMPLATE_EFFECTIVE_AUDIT_OK: read only")
