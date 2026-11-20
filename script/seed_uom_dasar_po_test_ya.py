"""Seed pilihan satuan dasar (factor=1) bagi semua SKU pada DB duplikat.

PREVIEW default, APPLY dengan YA_BASE_UOM_APPLY=YES. Tidak mengubah aturan
pembelian besar, PO, harga, stok, atau produk. Idempotent dan satu COMMIT.
"""

import os


def main():
    e = globals().get("env")
    if e is None or e.cr.dbname != "erp-yussyakmal-integer-test":
        raise RuntimeError("HANYA database erp-yussyakmal-integer-test")
    apply = os.environ.get("YA_BASE_UOM_APPLY") == "YES"
    Products = e["product.product"].sudo()
    Rules = e["ya.purchase.uom.rule"].sudo().with_context(active_test=False)
    products = Products.search([])
    if len(products) != 2543:
        raise RuntimeError("Jumlah SKU berubah dari 2543; audit ulang sebelum seed")
    existing = {}
    for rule in Rules.search([]):
        existing.setdefault(rule.product_id.id, []).append(rule)
    additions = []
    matched = 0
    conflicts = []
    for product in products:
        label = product.uom_id.name
        matching = [rule for rule in existing.get(product.id, [])
                    if (rule.purchase_label or "").strip().casefold() == label.casefold()]
        if not matching:
            additions.append({"product_id": product.id, "purchase_label": label,
                              "factor": 1,
                              "company_id": product.company_id.id or e.company.id})
        elif len(matching) == 1 and matching[0].factor == 1 and matching[0].active:
            matched += 1
        else:
            conflicts.append(product.default_code)
    print("DATABASE:", e.cr.dbname)
    print("MODE:", "APPLY" if apply else "PREVIEW")
    print("PRODUK:", len(products))
    print("PILIHAN SATUAN DASAR: tambah=%s | sudah ada=%s | konflik=%s" %
          (len(additions), matched, len(conflicts)))
    for sku in conflicts[:20]:
        print("KONFLIK SKU:", sku)
    if conflicts:
        raise RuntimeError("Aturan nama satuan dasar konflik; tidak ada COMMIT")
    if not apply:
        print("BASE_UOM_PREVIEW_OK: tidak ada perubahan")
        return
    try:
        if additions:
            Rules.create(additions)
        e.cr.commit()
    except Exception:
        e.cr.rollback()
        print("BASE_UOM_FAILED: seluruh penambahan ROLLBACK")
        raise
    print("BASE_UOM_SUCCESS: %s pilihan satuan dasar ditambahkan; COMMIT selesai" % len(additions))


main()
