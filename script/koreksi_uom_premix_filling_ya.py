"""PREVIEW/APPLY satuan dasar Gram untuk produk Filling di All / Premix.

Tidak memakai file master privat. Set PREMIX_FILLING_APPLY=YES untuk APPLY.
Hanya SKU tanpa PO, pergerakan stok, atau stok aktif yang bisa dikoreksi.
"""

import os
import traceback


EXPECTED_PRODUCTS = 15  # Kontrol terhadap data master yang sudah direview.


def main():
    env19 = globals().get("env")
    if not env19 or env19.cr.dbname != "erp-yussyakmal":
        raise RuntimeError("Hanya boleh dijalankan di database erp-yussyakmal")
    applying = os.environ.get("PREMIX_FILLING_APPLY") == "YES"
    company = env19["res.company"].sudo().search([])
    if len(company) != 1:
        raise RuntimeError("Database harus memiliki tepat satu perusahaan")

    categories = env19["product.category"].sudo().search([("name", "=", "Premix")])
    premix = categories.filtered(
        lambda category: category.parent_id and category.parent_id.name == "All"
    )
    if len(premix) != 1:
        raise RuntimeError("Kategori All / Premix tidak ditemukan secara unik")

    Products = env19["product.template"].sudo().with_company(company[0])
    products = Products.search([("categ_id", "=", premix.id)])
    matching = products.filtered(lambda product: "filling" in product.name.casefold())
    if len(matching) != EXPECTED_PRODUCTS:
        raise RuntimeError(
            "Jumlah produk Filling berubah: aktual=%s, diharapkan=%s; audit dahulu"
            % (len(matching), EXPECTED_PRODUCTS)
        )

    Uoms = env19["uom.uom"].sudo().with_context(active_test=False)
    grams = Uoms.search([("name", "=", "Gram")])
    if len(grams) != 1 or not grams.active:
        raise RuntimeError("UoM Gram tidak ada, duplikat, atau diarsipkan")
    gram = grams[0]
    moves = env19["stock.move"].sudo()
    quants = env19["stock.quant"].sudo()
    po_lines = env19["purchase.order.line"].sudo()

    changes = []
    print("DATABASE:", env19.cr.dbname)
    print("MODE:", "APPLY" if applying else "PREVIEW (tanpa perubahan)")
    print("FILTER: All / Premix + nama mengandung filling (tanpa membedakan huruf)")
    for product in matching.sorted(key=lambda product: product.default_code or ""):
        sku = (product.default_code or "").strip()
        if not sku or len(Products.search([("default_code", "=", sku)])) != 1:
            raise RuntimeError("SKU kosong/duplikat pada produk %s" % product.id)
        variants = product.product_variant_ids
        if len(variants) != 1:
            raise RuntimeError("SKU %s bukan produk satu varian" % sku)
        previous = product.uom_id.name
        if previous not in ("Resep", "Gram"):
            raise RuntimeError("SKU %s memiliki UoM di luar ekspektasi: %s" % (sku, previous))
        action = "SUDAH BENAR" if product.uom_id.id == gram.id else "UBAH KE GRAM"
        if action == "UBAH KE GRAM":
            if moves.search_count([("product_id", "in", variants.ids)]):
                raise RuntimeError("SKU %s sudah punya pergerakan stok" % sku)
            if quants.search_count([("product_id", "in", variants.ids), ("quantity", "!=", 0)]):
                raise RuntimeError("SKU %s memiliki stok" % sku)
            if po_lines.search_count([("product_id", "in", variants.ids)]):
                raise RuntimeError("SKU %s sudah dipakai pada PO" % sku)
            changes.append(product)
        print("SKU %s | %s | %s -> Gram | %s" % (sku, product.name, previous, action))

    print("TOTAL: %s produk | KOREKSI: %s | TETAP: %s" % (
        len(matching), len(changes), len(matching) - len(changes)
    ))
    if not applying:
        print("PREMIX_FILLING_PREVIEW_OK: tidak ada perubahan database")
        return
    try:
        for product in changes:
            product.write({"uom_id": gram.id})
        env19.flush_all()
        for product in matching:
            if product.uom_id.id != gram.id:
                raise RuntimeError("Verifikasi gagal untuk SKU %s" % product.default_code)
        env19.cr.commit()
        print("PREMIX_FILLING_IMPORT_SUCCESS: %s produk dikoreksi; COMMIT selesai" % len(changes))
    except Exception:
        env19.cr.rollback()
        print("PREMIX_FILLING_IMPORT_FAILED: seluruh perubahan dibatalkan")
        traceback.print_exc()
        raise


main()
