"""Koreksi satuan dasar satu SKU secara aman di Odoo 19.

Default PREVIEW; koreksi hanya jika YA_UOM_SKU_APPLY=YES.
Parameter YA_SKU, YA_UOM_LAMA, YA_UOM_BARU wajib disediakan via env.
Tidak mengubah harga, biaya, stok, atau data produk lainnya.
"""

import os
import traceback
from decimal import Decimal


def main():
    env19 = globals().get("env")
    if not env19 or env19.cr.dbname != "erp-yussyakmal":
        raise RuntimeError("Database harus erp-yussyakmal")
    sku = os.environ.get("YA_SKU", "").strip()
    old_label = os.environ.get("YA_UOM_LAMA", "").strip()
    new_label = os.environ.get("YA_UOM_BARU", "").strip()
    if not all((sku, old_label, new_label)) or old_label.casefold() == new_label.casefold():
        raise RuntimeError("Set YA_SKU, YA_UOM_LAMA dan YA_UOM_BARU yang berbeda")
    applying = os.environ.get("YA_UOM_SKU_APPLY") == "YES"
    companies = env19["res.company"].sudo().search([])
    if len(companies) != 1:
        raise RuntimeError("Diharapkan satu perusahaan")
    Products = env19["product.template"].sudo().with_company(companies[0])
    product = Products.search([("default_code", "=", sku)])
    if len(product) != 1:
        raise RuntimeError("SKU tidak ditemukan/duplikat")
    old_uom = product.uom_id
    if old_uom.name.casefold() != old_label.casefold():
        raise RuntimeError("Satuan lama bukan %s; aktual=%s" % (old_label, old_uom.name))
    Uom = env19["uom.uom"].sudo()
    new_candidates = Uom.search([]).filtered(lambda u: u.name.casefold() == new_label.casefold())
    if len(new_candidates) != 1 or not new_candidates.active:
        raise RuntimeError("Satuan baru tidak ditemukan, tidak unik, atau tidak aktif")
    dest_uom = new_candidates[0]
    variants = product.product_variant_ids
    if len(variants) != 1:
        raise RuntimeError("Produk tidak memiliki tepat satu varian")
    if env19["stock.move"].sudo().search_count([("product_id", "in", variants.ids)]):
        raise RuntimeError("SKU sudah memiliki stock.move")
    if env19["stock.quant"].sudo().search_count([("product_id", "in", variants.ids), ("quantity", "!=", 0)]):
        raise RuntimeError("SKU sudah memiliki stok")
    if env19["purchase.order.line"].sudo().search_count([("product_id", "in", variants.ids)]):
        raise RuntimeError("SKU sudah memiliki baris PO")
    before = (product.name, product.default_code, product.categ_id.id,
              Decimal(str(product.standard_price)), Decimal(str(product.list_price)),
              product.sale_ok, product.purchase_ok, product.is_storable)
    print("DATABASE:", env19.cr.dbname)
    print("MODE:", "APPLY" if applying else "PREVIEW (tanpa perubahan)")
    print("SKU:", sku, "| PRODUK:", product.name)
    print("SATUAN DASAR:", old_uom.name, "->", dest_uom.name)
    print("PENGAMAN: stock.move=0, stok=0, PO=0; harga dan biaya dipertahankan")
    if not applying:
        print("KOREKSI_UOM_SKU_PREVIEW_OK: database tidak diubah")
        return
    try:
        product.write({"uom_id": dest_uom.id})
        env19.flush_all()
        now = (product.name, product.default_code, product.categ_id.id,
               Decimal(str(product.standard_price)), Decimal(str(product.list_price)),
               product.sale_ok, product.purchase_ok, product.is_storable)
        if product.uom_id.id != dest_uom.id or now != before:
            raise RuntimeError("Verifikasi satuan/atribut produk gagal")
        env19.cr.commit()
        print("KOREKSI_UOM_SKU_SUCCESS: satuan dasar satu SKU diperbarui; COMMIT selesai")
    except Exception:
        env19.cr.rollback()
        print("KOREKSI_UOM_SKU_FAILED: perubahan dibatalkan")
        traceback.print_exc()
        raise


main()
