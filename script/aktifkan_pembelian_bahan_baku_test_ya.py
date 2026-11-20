"""Aktifkan purchase_ok pada seluruh turunan All / Bahan Baku di DB UJI saja.

PREVIEW default; APPLY dengan YA_BAHAN_BAKU_PURCHASE_APPLY=YES.
Tidak membuat supplier, PO, stok atau mengubah harga.
"""

import os


def path_of(cat):
    parts = []
    while cat:
        parts.append(cat.name)
        cat = cat.parent_id
    return " / ".join(reversed(parts))


def main():
    e = globals().get("env")
    if e is None or e.cr.dbname != "erp-yussyakmal-integer-test":
        raise RuntimeError("HANYA untuk database erp-yussyakmal-integer-test")
    apply = os.environ.get("YA_BAHAN_BAKU_PURCHASE_APPLY") == "YES"
    Cats = e["product.category"].sudo()
    Product = e["product.template"].sudo()
    roots = Cats.search([("name", "=", "Bahan Baku")])
    valid_roots = roots.filtered(lambda c: path_of(c) == "All / Bahan Baku")
    if len(valid_roots) != 1:
        raise RuntimeError("Kategori All / Bahan Baku tidak unik atau tidak ada")
    root = valid_roots[0]
    cat_ids = Cats.search([("id", "child_of", root.id)]).ids
    products = Product.search([("categ_id", "in", cat_ids)])
    if not products:
        raise RuntimeError("Tidak ada produk dalam kelompok Bahan Baku")
    targets = products.filtered(lambda p: not p.purchase_ok)
    already = products - targets
    print("DATABASE:", e.cr.dbname)
    print("MODE:", "APPLY" if apply else "PREVIEW (tanpa perubahan)")
    print("KATEGORI: All / Bahan Baku beserta seluruh subkategori")
    print("JUMLAH KATEGORI:", len(cat_ids))
    print("TOTAL PRODUK:", len(products))
    print("PERLU DIAKTIFKAN:", len(targets))
    print("SUDAH AKTIF:", len(already))
    print("TETAP: kategori lain, sale_ok, harga, UoM, stock, PO tidak diubah")
    if not apply:
        print("BAHAN_BAKU_PURCHASE_PREVIEW_OK: database tidak diubah")
        return
    try:
        if targets:
            targets.write({"purchase_ok": True})
            if any(not p.purchase_ok for p in targets):
                raise RuntimeError("Sebagian purchase_ok tetap False setelah WRITE")
        e.cr.commit()
    except Exception:
        e.cr.rollback()
        print("BAHAN_BAKU_PURCHASE_FAILED: seluruh perubahan ROLLBACK")
        raise
    print("BAHAN_BAKU_PURCHASE_SUCCESS: %s produk diaktifkan; COMMIT selesai" % len(targets))


main()
