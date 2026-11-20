"""Read-only audit of PO -> Receipt -> Vendor Bill on the test clone.

Never creates, posts, writes, or commits records.
"""
def main():
    e = globals()["env"]
    if e.cr.dbname != "erp-yussyakmal-integer-test":
        raise RuntimeError("AUDIT HANYA DI DATABASE TEST")
    print("DATABASE:", e.cr.dbname)
    print("MODE: AUDIT READ-ONLY PO / RECEIPT / VENDOR BILL")
    names = {
        "purchase.order": ("_create_invoices", "_get_invoiceable_lines"),
        "purchase.order.line": ("_prepare_account_move_line", "_compute_qty_invoiced"),
    }
    for model, methods in names.items():
        recordset = e[model]
        print("MODEL:", model)
        for method in methods:
            print("  METHOD:", method, "AVAILABLE:", callable(getattr(recordset, method, None)))
    fields_by_model = {
        "purchase.order": ["name", "state", "invoice_status", "invoice_ids", "amount_untaxed",
                           "amount_tax", "amount_total", "ya_discount_mode",
                           "ya_global_discount_type", "ya_global_discount_amount"],
        "purchase.order.line": ["product_id", "product_qty", "qty_received", "qty_invoiced",
                                "qty_to_invoice", "product_uom_id", "ya_purchase_rule_id",
                                "ya_purchase_qty", "ya_purchase_price", "price_unit",
                                "discount", "price_subtotal", "tax_ids"],
        "account.move": ["move_type", "state", "invoice_origin", "invoice_line_ids",
                         "amount_untaxed", "amount_tax", "amount_total", "currency_id"],
        "account.move.line": ["purchase_line_id", "quantity", "product_uom_id",
                              "price_unit", "discount", "tax_ids", "price_subtotal"],
    }
    for model, names in fields_by_model.items():
        print("FIELDS:", model)
        for name in names:
            field = e[model]._fields.get(name)
            print(" ", name, field.type if field else "TIDAK ADA")
    order = e["purchase.order"].sudo().search([("name", "=", "P00009")], limit=1)
    if not order:
        print("PO P00009 TIDAK ADA; audit struktur tetap selesai")
    else:
        print("PO:", order.name, "| state:", order.state, "| invoice_status:", order.invoice_status)
        print("AMOUNTS:", order.amount_untaxed, order.amount_tax, order.amount_total)
        print("INVOICE COUNT:", len(order.invoice_ids))
        for line in order.order_line.filtered(lambda x: not x.display_type):
            rule = line.ya_purchase_rule_id
            print(
                "PO LINE:", line.id, "| SKU:", line.product_id.default_code,
                "| ORDERED BASE:", line.product_qty,
                "| RECEIVED BASE:", line.qty_received,
                "| INVOICED BASE:", line.qty_invoiced,
                "| QTY TO INVOICE:", getattr(line, "qty_to_invoice", "N/A"),
                "| PURCHASE:", line.ya_purchase_qty, rule.purchase_label if rule else "-",
                "| FACTOR:", rule.factor if rule else "-",
                "| UNIT PRICE BASE:", line.price_unit,
                "| DISCOUNT %:", line.discount,
                "| SUBTOTAL:", line.price_subtotal,
                "| TAX IDs:", line.tax_ids.ids,
            )
        for picking in order.picking_ids:
            print("RECEIPT:", picking.name, "| STATE:", picking.state,
                  "| BACKORDERS:", len(picking.backorder_ids))
            for move in picking.move_ids:
                print(" MOVE:", move.id, "| SKU:", move.product_id.default_code,
                      "| DONE BASE:", move.quantity, "| PHYSICAL:",
                      getattr(move, "ya_received_unit_qty", "-"),
                      getattr(move, "ya_received_unit_label", "-"))
        for bill in order.invoice_ids:
            print("BILL:", bill.name, "| ID:", bill.id, "| STATE:", bill.state,
                  "| TYPE:", bill.move_type, "| TOTAL:", bill.amount_total)
            for line in bill.invoice_line_ids:
                print(" BILL LINE:", line.id, "| PO LINE:",
                      line.purchase_line_id.id if line.purchase_line_id else "-",
                      "| QTY:", line.quantity, "| UNIT PRICE:", line.price_unit,
                      "| DISCOUNT:", line.discount, "| SUBTOTAL:", line.price_subtotal)
    print("PO_RECEIPT_BILL_AUDIT_OK: database tidak diubah")


main()
