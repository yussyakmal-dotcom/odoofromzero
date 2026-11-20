"""Audit read-only untuk desain diskon PO YA (line XOR global).

Jalankan melalui Odoo shell pada erp-yussyakmal-integer-test.
Tidak ada CREATE/WRITE/COMMIT; tidak mengubah transaksi.
"""


def main():
    e = globals().get("env")
    if e is None or e.cr.dbname != "erp-yussyakmal-integer-test":
        raise RuntimeError("HANYA database erp-yussyakmal-integer-test")
    print("DATABASE:", e.cr.dbname)
    print("MODE: AUDIT READ-ONLY DISKON PO")
    for model_name, names in [
        ("purchase.order", [
            "order_line", "amount_untaxed", "amount_tax", "amount_total",
            "currency_id", "company_id", "state", "discount", "discount_type",
            "global_discount", "global_discount_rate", "discount_amount",
        ]),
        ("purchase.order.line", [
            "order_id", "product_id", "product_qty", "product_uom_id",
            "price_unit", "discount", "price_subtotal", "price_tax",
            "price_total", "taxes_id", "ya_purchase_price", "ya_purchase_rule_id",
        ]),
        ("account.move.line", [
            "purchase_line_id", "discount", "price_unit", "quantity",
            "tax_ids", "price_subtotal",
        ]),
    ]:
        Model = e[model_name]
        print("MODEL:", model_name, "| RECORDS:", Model.search_count([]))
        for name in names:
            field = Model._fields.get(name)
            print("  FIELD:", name, "|",
                  ("type=%s compute=%s store=%s" %
                   (field.type, bool(field.compute), field.store)) if field
                  else "TIDAK ADA")
        for name in ("_compute_amount", "_amount_all", "_compute_tax_totals"):
            print("  METHOD:", name, "|", callable(getattr(Model, name, None)))
    modules = e["ir.module.module"].sudo().search([
        ("name", "ilike", "discount"),
        ("state", "=", "installed"),
    ])
    print("MODUL DISKON TERPASANG:", [m.name for m in modules])
    print("DISCOUNT_PO_AUDIT_COMPLETE: database tidak diubah")


main()
