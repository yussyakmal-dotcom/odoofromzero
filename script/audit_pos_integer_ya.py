"""Audit POS YA + uji validator virtual, tanpa membuat transaksi.

Jalankan di erp-yussyakmal-integer-test melalui odoo-bin shell.
"""

from odoo.exceptions import ValidationError


def main():
    e = globals().get("env")
    if e is None or e.cr.dbname != "erp-yussyakmal-integer-test":
        raise RuntimeError("Gunakan hanya erp-yussyakmal-integer-test")
    if "pos.order.line" not in e.registry.models:
        raise RuntimeError("POS belum terpasang")
    Model = e["pos.order.line"].sudo()
    if not hasattr(Model, "_ya_check_integer_pos"):
        raise RuntimeError("Validator POS modul YA tidak ditemukan")

    print("DATABASE:", e.cr.dbname)
    print("MODE: POS AUDIT READ-ONLY")
    for model_name in ("pos.config", "pos.session", "pos.order", "pos.order.line",
                       "pos.payment.method", "pos.payment"):
        if model_name not in e.registry.models:
            print("MODEL:", model_name, "TIDAK ADA")
            continue
        model = e[model_name].sudo()
        print("MODEL:", model_name, "RECORDS:", model.search_count([]))
        for field_name in ("config_id", "session_id", "partner_id", "name", "qty",
                           "price_unit", "product_id", "order_id", "amount_total"):
            field = model._fields.get(field_name)
            if field:
                print(" FIELD: %s | type=%s | required=%s | compute=%s" %
                      (field_name, field.type, field.required, bool(field.compute)))

    # Virtual record has no database id: no POS order, cash session, or payments.
    for value in (1, 3, -1, -3, 0):
        record = Model.new({"qty": value})
        record._ya_check_integer_pos()
        print("PASS: POS virtual qty=%s diterima" % value)
    for value in (1.5, -2.5):
        record = Model.new({"qty": value})
        try:
            record._ya_check_integer_pos()
        except ValidationError:
            print("PASS: POS virtual qty=%s ditolak" % value)
        else:
            raise AssertionError("POS menerima pecahan %s" % value)

    print("POS_INTEGER_AUDIT_COMPLETE: tidak membuat POS order/line/payment")
    print("NEXT: uji CREATE/WRITE POS setelah konfigurasi dan skenario tersedia")


main()
