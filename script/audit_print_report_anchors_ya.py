"""Read-only detailed QWeb nodes for safe view inheritance in Odoo 19."""
from lxml import etree

if env.cr.dbname != "erp-yussyakmal-integer-test":
    raise RuntimeError("TEST DB ONLY")
print("DATABASE:", env.cr.dbname)
print("MODE: AUDIT READ-ONLY QWEB ANCHORS")
targets = [
    "purchase.report_purchaseorder_document",
    "purchase.report_purchasequotation_document",
    "stock.report_picking",
    "stock.report_delivery_document",
    "account.report_invoice_document",
]
for key in targets:
    view = env["ir.ui.view"].sudo().search([("key", "=", key)], limit=1)
    print("=" * 65)
    print("TEMPLATE:", key, "| ID:", view.id if view else "MISSING")
    if not view:
        continue
    root = etree.fromstring(view.arch_db.encode())
    for node in root.iter():
        expression = " ".join([
            node.get("t-field") or "", node.get("t-esc") or "", node.get("t-out") or "",
        ])
        if any(token in expression for token in (
            "line.product_qty", "line.product_uom_id", "line.price_unit",
            "line.discount", "line.quantity", "line.product_uom_id",
            "move.quantity", "move.product_uom", "format_number(line.quantity)",
        )):
            parent = node.getparent()
            grandparent = parent.getparent() if parent is not None else None
            print(" ANCHOR:", etree.tostring(node, encoding="unicode")[:500])
            print(" PARENT:", etree.tostring(parent, encoding="unicode")[:1300]
                  if parent is not None else "-")
            print(" GRANDPARENT TAG:", grandparent.tag if grandparent is not None else "-")
print("PRINT_REPORT_ANCHORS_AUDIT_OK: database tidak diubah")
