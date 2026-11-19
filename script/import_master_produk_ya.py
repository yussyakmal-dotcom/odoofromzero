"""Import 2.543 produk YA dalam satu transaksi Odoo 19.

PREVIEW default; PRODUK_APPLY=YES untuk simpan. File sumber PRIVAT:
PRODUCT_STAGING_PRIVATE.csv pada root repository server (jangan unggah ke GitHub publik).

Semua produk menggunakan UoM Units sementara. Penjualan/pembelian dinonaktifkan
dan tidak ada stok awal atau transaksi stok yang dibuat oleh skrip ini.
"""

import csv
import os
import traceback
from decimal import Decimal, InvalidOperation
from pathlib import Path


def main():
    odoo_env = globals().get("env")
    if odoo_env is None or odoo_env.cr.dbname != "erp-yussyakmal":
        raise RuntimeError("Jalankan dengan Odoo shell pada database erp-yussyakmal")
    apply_mode = os.environ.get("PRODUK_APPLY") == "YES"
    companies = odoo_env["res.company"].sudo().search([])
    if len(companies) != 1:
        raise RuntimeError("Diharapkan tepat satu perusahaan")
    company = companies[0]
    templates = odoo_env["product.template"].sudo().with_company(company)
    variants = odoo_env["product.product"].sudo().with_company(company)
    cats = odoo_env["product.category"].sudo().with_company(company)

    # Jangan membuat duplikasi/produk parsial secara diam-diam.
    if templates.search_count([]) or variants.search_count([]):
        raise RuntimeError("Produk sudah ada di database; hentikan impor otomatis dan audit dahulu")
    if cats.search_count([]) != 76:
        raise RuntimeError("Kategori produk bukan 76; jalankan audit ulang")
    if odoo_env["stock.move"].sudo().search_count([]):
        raise RuntimeError("Sudah ada pergerakan stok; impor otomatis dibatalkan")

    fields = ("name", "default_code", "categ_id", "type", "is_storable", "tracking",
              "uom_id", "list_price", "standard_price", "sale_ok", "purchase_ok")
    missing = [f for f in fields if f not in templates._fields]
    if missing:
        raise RuntimeError("Field product.template tidak tersedia: %s" % missing)
    for field_name, expected in (("type", "consu"), ("tracking", "none")):
        selection = dict(templates._fields[field_name]._description_selection(odoo_env))
        if expected not in selection:
            raise RuntimeError("Pilihan %s=%s tidak tersedia: %s" % (field_name, expected, selection))

    unit_field = templates._fields["uom_id"]
    relation = unit_field.comodel_name
    if relation not in odoo_env.registry.models:
        raise RuntimeError("Model UoM untuk uom_id belum tersedia: " + str(relation))
    Uom = odoo_env[relation].sudo()
    default_uom_id = templates.default_get(["uom_id"]).get("uom_id")
    default_uom = Uom.browse(default_uom_id).exists() if default_uom_id else Uom.browse([])
    if default_uom and default_uom.name != "Units":
        default_uom = Uom.browse([])
    if not default_uom:
        candidates = Uom.search([("name", "=", "Units")])
        if len(candidates) != 1:
            raise RuntimeError("UoM Units tidak unik/tersedia; tidak boleh menebak ID: %s" % len(candidates))
        default_uom = candidates[0]
    unit_id = default_uom.id

    # Beberapa database Odoo memiliki induk 'All' bawaan dan 'All' YA.
    all_roots = cats.search([("name", "=", "All"), ("parent_id", "=", False)])
    ya_roots = all_roots.filtered(lambda c: any(x.name == "Bahan Baku" for x in c.child_id)
                                         and any(x.name == "Produk Jadi" for x in c.child_id))
    if len(ya_roots) != 1:
        raise RuntimeError("Induk kategori All YA tidak unik")
    root = ya_roots[0]
    category_paths = {}

    def walk(category, path):
        if path in category_paths:
            raise RuntimeError("Path kategori duplikat: " + path)
        category_paths[path] = category
        for child in category.child_id:
            walk(child, path + " / " + child.name)

    walk(root, "All")

    input_path = Path(os.environ.get("PRODUK_YA_FILE", "PRODUCT_STAGING_PRIVATE.csv"))
    with input_path.open(encoding="utf-8-sig", newline="") as file_obj:
        rows = list(csv.DictReader(file_obj))
    if len(rows) != 2543:
        raise RuntimeError("File staging harus berisi 2.543 SKU; ditemukan %s" % len(rows))

    sku_seen = set()
    prepared = []
    category_counts = {}
    for line_no, row in enumerate(rows, 2):
        sku = row["Internal Reference"].strip()
        name = row["Name"].strip()
        path = row["Product Category"].strip()
        if not sku or sku in sku_seen or not name:
            raise RuntimeError("SKU kosong/duplikat atau nama kosong di baris %s: %s" % (line_no, sku))
        sku_seen.add(sku)
        if path not in category_paths:
            raise RuntimeError("Kategori tidak ditemukan baris %s: %s" % (line_no, path))
        if (row["Product Type"], row["Track Inventory"], row["UoM Decision"], row["Import Decision"]) != (
                "Goods", "YES", "PENDING_CUSTOM_UOM", "STAGING_ONLY"):
            raise RuntimeError("File staging berubah/tidak sesuai keputusan baris %s" % line_no)
        try:
            price = Decimal(row["Sales Price"])
            cost = Decimal(row["Cost"])
        except InvalidOperation:
            raise RuntimeError("Harga/biaya tidak valid pada SKU " + sku)
        if not price.is_finite() or not cost.is_finite() or price < 0 or cost < 0:
            raise RuntimeError("Harga/biaya tidak wajar pada SKU " + sku)
        values = {
            "default_code": sku,
            "name": name,
            "categ_id": category_paths[path].id,
            "type": "consu",
            "is_storable": True,
            "tracking": "none",
            "uom_id": unit_id,
            "list_price": float(price),
            "standard_price": float(cost),
            # Kunci operasional sementara sampai master satuan dan flag per produk siap.
            "sale_ok": False,
            "purchase_ok": False,
        }
        prepared.append(values)
        category_counts[path] = category_counts.get(path, 0) + 1

    print("DATABASE:", odoo_env.cr.dbname)
    print("MODE:", "APPLY" if apply_mode else "PREVIEW (tanpa perubahan)")
    print("INPUT:", input_path)
    print("PRODUK:", len(prepared), "SKU unik; kategori unik:", len(category_counts))
    print("UOM SEMENTARA:", default_uom.name, "| model:", relation, "| id:", unit_id)
    print("TYPE: Goods | Track Inventory: Ya | Tracking: By Quantity")
    print("SALE_OK=False | PURCHASE_OK=False | STOK AWAL: tidak diisi")
    print("PENTING: jangan lakukan transaksi sebelum satuan dasar asli dan aturan pembelian selesai")
    if not apply_mode:
        print("PRODUK_PREVIEW_OK: tidak ada perubahan database.")
        return

    try:
        for offset in range(0, len(prepared), 100):
            templates.create(prepared[offset:offset + 100])
        odoo_env.flush_all()
        final = templates.search([])
        final_variants = variants.search([])
        if len(final) != 2543 or len(final_variants) != 2543:
            raise RuntimeError("Jumlah produk/varian tidak sesuai: %s/%s" % (len(final), len(final_variants)))
        by_sku = {r.default_code: r for r in final}
        if len(by_sku) != 2543 or set(by_sku) != sku_seen:
            raise RuntimeError("Hasil SKU duplikat atau tidak cocok dengan master")
        for product in final:
            if (product.uom_id.id != unit_id or product.type != "consu" or
                    not product.is_storable or product.tracking != "none" or
                    product.sale_ok or product.purchase_ok):
                raise RuntimeError("Verifikasi pengaturan produk gagal: " + str(product.default_code))
        odoo_env.cr.commit()
        print("PRODUK_IMPORT_SUCCESS: 2.543 produk dan varian tersimpan; UoM sementara Units.")
        print("Semua produk belum dapat dijual/dibeli; tidak ada stok awal diimpor.")
    except Exception:
        odoo_env.cr.rollback()
        print("PRODUK_IMPORT_FAILED: seluruh perubahan dibatalkan.")
        traceback.print_exc()
        raise


main()
