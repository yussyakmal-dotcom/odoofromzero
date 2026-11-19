"""Buat All / Produk Jadi / Paket, read-only PREVIEW secara default.

Paket adalah SKU hasil perakitan BoM Produk Jadi di Packing. Pengaturan BoM,
lokasi produksi, rute dan satuan tidak dibuat oleh skrip kategori ini.
"""

import os
import traceback


def main():
    odoo_env = globals().get("env")
    if odoo_env is None or odoo_env.cr.dbname != "erp-yussyakmal":
        raise RuntimeError("Jalankan pada Odoo shell erp-yussyakmal")
    apply_mode = os.environ.get("PAKET_KATEGORI_APPLY") == "YES"
    companies = odoo_env["res.company"].sudo().search([])
    if len(companies) != 1:
        raise RuntimeError("Diharapkan tepat satu perusahaan")
    cats = odoo_env["product.category"].sudo().with_company(companies[0])
    roots = cats.search([("name", "=", "All"), ("parent_id", "=", False)])
    ya_roots = roots.filtered(lambda c: any(x.name == "Bahan Baku" for x in c.child_id)
                                      and any(x.name == "Produk Jadi" for x in c.child_id))
    if len(ya_roots) != 1:
        raise RuntimeError("Induk All YA tidak unik")
    root = ya_roots[0]
    ready_names = (("Produk Jadi", "Kue Kering"), ("Produk Jadi", "Frozen Food"), ("Bahan Baku", "Agar-agar"))
    verified = []
    for parent_name, child_name in ready_names:
        parent = root.child_id.filtered(lambda c: c.name == parent_name)
        present = len(parent) == 1 and len(parent.child_id.filtered(lambda c: c.name == child_name)) == 1
        verified.append((parent_name, child_name, present))

    parent = root.child_id.filtered(lambda c: c.name == "Produk Jadi")
    if len(parent) != 1:
        raise RuntimeError("Induk Produk Jadi tidak unik")
    parent = parent[0]
    existing = parent.child_id.filtered(lambda c: c.name == "Paket")
    if len(existing) > 1:
        raise RuntimeError("Kategori Paket sudah duplikat")

    print("DATABASE:", odoo_env.cr.dbname)
    print("MODE:", "APPLY" if apply_mode else "PREVIEW (tanpa perubahan)")
    for parent_name, child_name, present in verified:
        print("CEK: All / %s / %s | %s" % (parent_name, child_name, "ADA" if present else "BELUM ADA"))
    if not all(present for _, _, present in verified):
        raise RuntimeError("Tiga subkategori sebelumnya belum lengkap; jalankan APPLY script/tambah_3_subkategori_produk.py dahulu")
    if cats.search_count([]) not in (74, 75):
        raise RuntimeError("Jumlah kategori di luar kondisi yang diharapkan (74 atau 75)")

    values = {"name": "Paket", "parent_id": parent.id}
    copy_fields = (
        "property_cost_method", "property_valuation", "property_account_income_categ_id",
        "property_account_expense_categ_id", "property_stock_valuation_account_id",
    )
    for field in copy_fields:
        if field not in cats._fields:
            raise RuntimeError("Field kategori tidak tersedia: " + field)
        value = parent[field]
        values[field] = value.id if field.endswith("_id") else value
    if "account_stock_variation_id" in cats._fields:
        values["account_stock_variation_id"] = parent.account_stock_variation_id.id or False

    print("TARGET: All / Produk Jadi / Paket |", "SUDAH ADA" if existing else "TAMBAH")
    print("CONFIG: mengikuti Produk Jadi | costing=%s | valuation=%s" %
          (values["property_cost_method"], values["property_valuation"]))
    print("FIFO/FEFO, BoM, UoM, rute: tidak diubah")
    if not apply_mode:
        print("PAKET_KATEGORI_PREVIEW_OK: database tidak diubah.")
        return

    try:
        if not existing:
            cats.create(values)
        odoo_env.flush_all()
        if len(parent.child_id.filtered(lambda c: c.name == "Paket")) != 1 or cats.search_count([]) != 75:
            raise RuntimeError("Verifikasi jumlah/path kategori Paket gagal")
        odoo_env.cr.commit()
        print("PAKET_KATEGORI_IMPORT_SUCCESS: kategori Paket tersedia; total 75 kategori.")
    except Exception:
        odoo_env.cr.rollback()
        print("PAKET_KATEGORI_IMPORT_FAILED: perubahan dibatalkan.")
        traceback.print_exc()
        raise


main()
