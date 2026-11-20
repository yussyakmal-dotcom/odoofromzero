"""Tambah aturan pembelian SKU 10840: 1 Kg = 1000 Gram pada DB UJI.

PREVIEW default, APPLY dengan CABE_JENGKI_APPLY=YES. Idempotent.
"""

import os


def main():
    e = globals().get("env")
    if e is None or e.cr.dbname != "erp-yussyakmal-integer-test":
        raise RuntimeError("Hanya erp-yussyakmal-integer-test")
    apply = os.environ.get("CABE_JENGKI_APPLY") == "YES"
    product = e["product.product"].sudo().search([
        ("default_code", "=", "10840")
    ])
    if len(product) != 1 or product.uom_id.name.casefold() != "gram":
        raise RuntimeError("SKU 10840 tidak unik atau satuan dasar bukan Gram")

    Rule = e["ya.purchase.uom.rule"].sudo().with_context(active_test=False)
    existing = Rule.search([("product_id", "=", product.id)])
    same_label = existing.filtered(lambda r: (r.purchase_label or "").strip().casefold() == "kg")
    if len(same_label) > 1:
        raise RuntimeError("Duplikat aturan Kg pada SKU 10840")
    if same_label and (same_label.factor != 1000 or not same_label.active):
        raise RuntimeError("Konflik aturan Kg; tidak akan ditimpa otomatis")
    print("DATABASE:", e.cr.dbname)
    print("MODE:", "APPLY" if apply else "PREVIEW")
    print("PRODUK:", product.display_name)
    print("KONVERSI: 1 Kg = 1000 Gram")
    print("STATUS:", "SUDAH ADA" if same_label else "TAMBAH")
    if not apply:
        print("CABE_JENGKI_PREVIEW_OK: tidak ada perubahan")
        return
    try:
        if not same_label:
            Rule.create({
                "product_id": product.id,
                "purchase_label": "Kg",
                "factor": 1000,
                "company_id": e.company.id,
            })
        e.cr.commit()
    except Exception:
        e.cr.rollback()
        print("CABE_JENGKI_FAILED: ROLLBACK")
        raise
    print("CABE_JENGKI_SUCCESS: aturan tersedia; COMMIT selesai")


main()
