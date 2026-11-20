"""Inspect printed PO, incoming receipt and vendor-bill QWeb reports.

READ-ONLY. Never generates PDFs or changes records. Test database only.
"""
from lxml import etree


def xml_ids(env, rec):
    return rec.get_external_id().get(rec.id, "-")


def main():
    e = globals()["env"]
    if e.cr.dbname != "erp-yussyakmal-integer-test":
        raise RuntimeError("HANYA database erp-yussyakmal-integer-test")
    print("DATABASE:", e.cr.dbname)
    print("MODE: AUDIT READ-ONLY TEMPLATE CETAK PO / RECEIPT / VENDOR BILL")
    Report = e["ir.actions.report"].sudo()
    View = e["ir.ui.view"].sudo().with_context(active_test=False)

    for model in ("purchase.order", "stock.picking", "account.move"):
        print("=" * 65)
        print("REPORT MODEL:", model)
        reports = Report.search([("model", "=", model)])
        for r in reports:
            print(" REPORT:", r.id, "| XMLID:", xml_ids(e, r),
                  "| NAME:", r.name, "| REPORT NAME:", r.report_name,
                  "| TYPE:", r.report_type, "| BINDING:", r.binding_model_id.model or "-")
            candidates = View.search([
                "|", ("key", "=", r.report_name), ("name", "=", r.report_name),
            ])
            for v in candidates:
                print("  TEMPLATE:", v.id, "| KEY:", v.key, "| XMLID:", xml_ids(e, v),
                      "| INHERIT:", v.inherit_id.id or "-", "| ACTIVE:", v.active)
        print(" REPORT COUNT:", len(reports))

    print("=" * 65)
    print("QWEB TEMPLATES WITH PURCHASE / RECEIPT / INVOICE REFERENCES")
    needles = ("purchase.report_purchaseorder_document",
               "stock.report_delivery_document",
               "stock.report_picking",
               "account.report_invoice_document")
    for key in needles:
        views = View.search(["|", ("key", "=", key), ("name", "=", key)])
        for view in views:
            print(" TEMPLATE:", view.id, "|", view.key, "| XMLID:", xml_ids(e, view))
            try:
                root = etree.fromstring(view.arch_db.encode())
                fields = sorted(set(
                    node.get("t-field") or node.get("t-esc") or node.get("t-out")
                    for node in root.iter()
                    if node.get("t-field") or node.get("t-esc") or node.get("t-out")
                ))
                for field in fields:
                    if any(token in field for token in
                           ("quantity", "product_qty", "product_uom",
                            "price_unit", "discount", "amount", "tax")):
                        print("   FIELD:", field)
            except (etree.XMLSyntaxError, AttributeError) as error:
                print("   XML PARSE WARNING:", type(error).__name__)
        if not views:
            print(" TEMPLATE NOT FOUND:", key)

    print("=" * 65)
    for model, fields in (
        ("purchase.order.line", ("ya_purchase_qty", "ya_purchase_rule_id",
                                  "ya_purchase_price", "product_qty", "discount")),
        ("stock.move", ("ya_received_unit_qty", "ya_received_unit_label",
                         "quantity", "product_uom_qty", "purchase_line_id")),
        ("account.move.line", ("purchase_line_id", "quantity", "product_uom_id",
                               "price_unit", "discount")),
    ):
        print("DATA FIELDS:", model)
        for name in fields:
            f = e[model]._fields.get(name)
            print(" ", name, f.type if f else "TIDAK ADA")
    print("PRINT_REPORT_AUDIT_OK: database tidak diubah")


main()
